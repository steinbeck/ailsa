"""Append-only, hash-chained event log with a tolerant reader (standard library only).

Each event is one JSON line. ``prev`` is the sha256 of the raw bytes of the previous line
without its newline; the first event chains to ``sha256(run_id)``. Writers serialise through
``fcntl.flock`` on ``events.lock`` and write each line with a single ``os.write`` on an
``O_APPEND`` descriptor. POSIX only.

Honest scope: the chain makes accidental edits, truncation and out-of-band writes visible.
It is tamper-evident, not tamper-proof: a writer who recomputes every hash is not detected
(there is no secret key). Damaged tails are never truncated; the bytes stay as evidence.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ailsa.record.events import (
    COUNTERS,
    EVENTS,
    EVENTS_LOCK,
    FINISHED,
    HEARTBEAT,
    HOOK_TYPES,
    MARKER,
    SCHEMA_VERSION,
)
from ailsa.record.fsutil import atomic_write_json, sha256_bytes
from ailsa.record.workspace import host_alias

_TAIL_WINDOW = 64 * 1024
_ACTOR_KEYS = ("kind", "name", "role", "agent_id", "model")


class RecordWriteRefused(Exception):
    """The writer refuses an event (the run is finished)."""


class LogLockTimeout(TimeoutError):
    """events.lock stayed busy beyond the timeout."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _run_id(run_dir: Path) -> str:
    try:
        data = json.loads((run_dir / MARKER).read_text(encoding="utf-8"))
        return str(data["run_id"])
    except (OSError, ValueError, KeyError, TypeError):
        return run_dir.name


def _seq_of(raw: bytes) -> int | None:
    """The ``seq`` of a complete line that parses as an event (the reader's rule), else None."""
    try:
        obj = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    seq = obj.get("seq")
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else None


def _tail_state(fd: int, run_id: str) -> tuple[int, str, bytes]:
    """Return (highest seq in the tail, hash of the last complete line, partial tail bytes).

    The next event continues after the highest sequence number, so a duplicated or
    out-of-order line never makes the writer reuse a number. It chains to the raw bytes of the
    last complete line, parseable or not, which is what the reader expects after it. The
    window grows until it holds an event; the genesis hash is used only while the file has no
    complete line at all (a partial tail is then chained by ``log.recovered``).
    """
    size = os.fstat(fd).st_size
    genesis = sha256_bytes(run_id.encode("utf-8"))
    if size == 0:
        return 0, genesis, b""
    window = _TAIL_WINDOW
    while True:
        start = max(0, size - window)
        data = os.pread(fd, size - start, start)
        parts = data.split(b"\n")
        partial = parts[-1]
        # A line with a leading cut-off is only safe when something precedes it in the window.
        complete = parts[:-1] if start == 0 else parts[1:-1]
        seqs = [s for s in (_seq_of(raw) for raw in complete) if s is not None]
        if start == 0 or seqs:
            break
        window *= 2
    prev = sha256_bytes(complete[-1]) if complete else genesis
    return (max(seqs) if seqs else 0), prev, partial


class LockedLog:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_id = _run_id(run_dir)

    def finished(self) -> bool:
        return (self.run_dir / FINISHED).exists()

    def next_counter(self, name: str) -> int:
        path = self.run_dir / COUNTERS
        try:
            counters = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(counters, dict):
                counters = {}
        except (OSError, ValueError):
            counters = {}
        value = int(counters.get(name, 0)) + 1
        counters[name] = value
        atomic_write_json(path, counters)
        return value

    def append(
        self,
        type: str,
        payload: dict[str, Any],
        *,
        actor: dict[str, Any],
        refs: list[str] | None = None,
        span: dict[str, Any] | None = None,
        artefacts: list[dict[str, Any]] | None = None,
        allow_after_finish: bool = False,
        fsync: bool = False,
        utc: str | None = None,
        host: str | None = None,
    ) -> dict[str, Any]:
        # ``allow_after_finish`` only permits a hook event once the run has finished; the
        # envelope's ``after_finish`` says whether it really was written after run.finished.
        finished = self.finished()
        if finished and not (type in HOOK_TYPES and allow_after_finish):
            raise RecordWriteRefused(
                "run finished: post-run material goes to the verification store, not the run folder"
            )
        fd = os.open(self.run_dir / EVENTS, os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o600)
        try:
            seq, prev, partial = _tail_state(fd, self.run_id)
            if partial:
                recovered = self._envelope(
                    "log.recovered",
                    {
                        "discarded_bytes": len(partial),
                        "partial_sha256": sha256_bytes(partial),
                    },
                    seq=seq + 1,
                    prev=sha256_bytes(partial),
                    actor={"kind": "tool", "name": "ailsa.record.log"},
                    utc=utc,
                    host=host,
                )
                line = self._dump(recovered)
                os.write(fd, b"\n" + line + b"\n")
                seq = recovered["seq"]
                prev = sha256_bytes(line)
            ev = self._envelope(
                type,
                payload,
                seq=seq + 1,
                prev=prev,
                actor=actor,
                refs=refs,
                span=span,
                artefacts=artefacts,
                after_finish=finished,
                utc=utc,
                host=host,
            )
            line = self._dump(ev)
            os.write(fd, line + b"\n")
            if fsync or type == "run.finished":
                os.fsync(fd)
        finally:
            os.close(fd)
        if type == "run.finished":
            atomic_write_json(
                self.run_dir / FINISHED,
                {"seq": ev["seq"], "utc": ev["utc"], "head": sha256_bytes(line)},
                fsync=True,
            )
        return ev

    @staticmethod
    def _dump(ev: dict[str, Any]) -> bytes:
        return json.dumps(ev, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _envelope(
        self,
        type: str,
        payload: dict[str, Any],
        *,
        seq: int,
        prev: str,
        actor: dict[str, Any],
        refs: list[str] | None = None,
        span: dict[str, Any] | None = None,
        artefacts: list[dict[str, Any]] | None = None,
        after_finish: bool = False,
        utc: str | None = None,
        host: str | None = None,
    ) -> dict[str, Any]:
        return {
            "v": SCHEMA_VERSION,
            "seq": seq,
            "utc": utc or _now_utc(),
            "host": host or host_alias(),
            "run_id": self.run_id,
            "type": type,
            "actor": {key: actor.get(key) for key in _ACTOR_KEYS},
            "span": span,
            "refs": list(refs or []),
            "payload": payload,
            "artefacts": list(artefacts or []),
            "post_run": False,
            "after_finish": bool(after_finish),
            "prev": prev,
        }


@contextmanager
def log_session(run_dir: str | os.PathLike[str], timeout: float = 10.0) -> Iterator[LockedLog]:
    path = Path(run_dir)
    lock_fd = os.open(path / EVENTS_LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise LogLockTimeout("events.lock busy") from None
                time.sleep(0.02)
        try:
            yield LockedLog(path)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def append_event(
    run_dir: str | os.PathLike[str],
    type: str,
    payload: dict[str, Any],
    *,
    actor: dict[str, Any],
    refs: list[str] | None = None,
    span: dict[str, Any] | None = None,
    artefacts: list[dict[str, Any]] | None = None,
    allow_after_finish: bool = False,
    fsync: bool = False,
    utc: str | None = None,
    host: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    with log_session(run_dir, timeout=timeout) as session:
        return session.append(
            type,
            payload,
            actor=actor,
            refs=refs,
            span=span,
            artefacts=artefacts,
            allow_after_finish=allow_after_finish,
            fsync=fsync,
            utc=utc,
            host=host,
        )


def read_events(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Read every parseable event; mark events from the first break on as suspect."""
    path = Path(run_dir)
    run_id = _run_id(path)
    integrity: dict[str, Any] = {
        "clean": True,
        "first_bad_seq": None,
        "first_bad_line": None,
        "reason": None,
        "events": 0,
        "head": None,
        "bad_lines": [],
    }
    try:
        data = (path / EVENTS).read_bytes()
    except OSError:
        return {"events": [], "integrity": integrity}

    events: list[dict[str, Any]] = []
    hashes: dict[int, str] = {}
    # Suspects are marked by position in the file, not by seq: after a duplicated or
    # out-of-order line the seq numbers no longer say where the record changed (D-09).
    first_bad_pos: int | None = None

    def flag(seq: int, reason: str, pos: int, line: int | None) -> None:
        nonlocal first_bad_pos
        if integrity["first_bad_seq"] is None:
            integrity["first_bad_seq"] = seq
            integrity["first_bad_line"] = line
            integrity["reason"] = reason
            integrity["clean"] = False
            first_bad_pos = pos

    parts = data.split(b"\n")
    tail = parts[-1]
    lines = parts[:-1]
    expected_prev = sha256_bytes(run_id.encode("utf-8"))
    expected_seq = 1
    # (hash, expected seq, event position, line number) of an unparseable line not yet settled
    pending: tuple[str, int, int, int] | None = None
    last_event_hash: str | None = None
    last_seq = 0
    last_line = 0

    def settle_pending() -> None:
        nonlocal pending
        if pending is not None:
            flag(pending[1], "unparseable", pending[2], pending[3])
            pending = None

    for number, raw in enumerate(lines, start=1):
        digest = sha256_bytes(raw)
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict) or not isinstance(obj.get("seq"), int):
                raise ValueError("not an event")
        except ValueError:
            settle_pending()
            integrity["bad_lines"].append({"line": number, "bytes": len(raw)})
            pending = (digest, expected_seq, len(events), number)
            expected_prev = digest
            continue
        seq = obj["seq"]
        if (
            pending is not None
            and obj.get("type") == "log.recovered"
            and obj.get("prev") == pending[0]
            and seq == expected_seq
        ):
            flag(seq, "truncated_recovered", len(events), pending[3])
            pending = None
        else:
            settle_pending()
            if seq != expected_seq:
                flag(expected_seq, "seq_gap", len(events), number)
            elif obj.get("prev") != expected_prev:
                # The previous event's bytes changed (its hash no longer matches): it is the
                # first suspect one.
                if events:
                    flag(max(last_seq, 1), "chain_break", len(events) - 1, last_line)
                else:
                    flag(seq, "chain_break", 0, number)
        events.append(obj)
        hashes[seq] = digest
        last_event_hash = digest
        last_seq = seq
        last_line = number
        expected_prev = digest
        expected_seq = seq + 1
    settle_pending()
    if tail:
        integrity["bad_lines"].append({"line": len(lines) + 1, "bytes": len(tail)})
        flag(expected_seq, "truncated", len(events), len(lines) + 1)

    finished = path / FINISHED
    if finished.exists():
        try:
            fin = json.loads(finished.read_text(encoding="utf-8"))
            fseq = int(fin["seq"])
            pos = next((i for i, e in enumerate(events) if e["seq"] >= fseq), len(events))
            if fseq in hashes and hashes[fseq] != fin.get("head"):
                flag(fseq, "chain_break", pos, None)
            elif fseq not in hashes:
                flag(fseq, "seq_gap", pos, None)
        except (OSError, ValueError, KeyError, TypeError):
            pass

    if first_bad_pos is not None:
        for obj in events[first_bad_pos:]:
            obj["_suspect"] = True
    integrity["events"] = len(events)
    integrity["head"] = last_event_hash
    return {"events": events, "integrity": integrity}


def verify_chain(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    result: dict[str, Any] = read_events(run_dir)["integrity"]
    return result


def chain_head(run_dir: str | os.PathLike[str]) -> str:
    head = verify_chain(run_dir)["head"]
    return str(head) if head else sha256_bytes(_run_id(Path(run_dir)).encode("utf-8"))


def first_event(run_dir: str | os.PathLike[str]) -> dict[str, Any] | None:
    try:
        with open(Path(run_dir) / EVENTS, "rb") as fh:
            line = fh.readline()
    except OSError:
        return None
    if not line.endswith(b"\n"):
        return None
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def write_heartbeat(run_dir: str | os.PathLike[str], source: str) -> None:
    atomic_write_json(Path(run_dir) / HEARTBEAT, {"utc": _now_utc(), "source": source})
