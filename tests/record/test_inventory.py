"""Experiment inventory (REC-28): complete, unreadable entries kept, no titles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ailsa.record.inventory import build_inventory

CANARY = "CANARY-COMPOUND-NAME-9431"


def _acqus(pulprog: str, nuc: str, *, sfo1: float, extra: str = "") -> str:
    return (
        f"##TITLE= Parameter file {CANARY}\n"
        f"##$PULPROG= <{pulprog}>\n##$NUC1= <{nuc}>\n##$NS= 16\n"
        f"##$SFO1= {sfo1}\n##$TE= 298.0\n##$SW_h= 12000.0\n##$SOLVENT= <CDCl3>\n{extra}"
    )


def _make(root: Path) -> Path:
    one = root / "1"
    (one / "pdata" / "1").mkdir(parents=True)
    # TopSpin writes NusAMOUNT for every experiment; FnTYPE 0 means fully sampled.
    (one / "acqus").write_text(
        _acqus("zgpg30", "13C", sfo1=100.6, extra="##$FnTYPE= 0\n##$NusAMOUNT= 25\n")
    )
    (one / "fid").write_bytes(b"1234")
    (one / "pdata" / "1" / "1r").write_bytes(b"5678")
    (one / "pdata" / "1" / "procs").write_text("##$SI= 32768\n")
    (one / "pdata" / "1" / "title").write_text(CANARY)

    two = root / "2"
    (two / "pdata" / "1").mkdir(parents=True)
    (two / "acqus").write_text(
        _acqus("hsqcedetgpsisp2.3", "1H", sfo1=400.1, extra="##$FnTYPE= 2\n##$NusAMOUNT= 25\n")
    )
    (two / "acqu2s").write_text("##$NUC1= <13C>\n##$SFO1= 100.6\n")
    (two / "ser").write_bytes(b"abcd")
    (two / "nuslist").write_text("0\n1\n")
    (two / "pdata" / "1" / "title").write_text(CANARY)

    three = root / "3"
    three.mkdir()
    (three / "acqus").write_text(_acqus("weird_pp", "1H", sfo1=400.1))
    (three / "acqu2s").write_text("##$NUC1= <1H>\n##$SFO1= 400.1\n")
    (three / "ser").write_bytes(b"x")

    (root / "4").mkdir()
    (root / "4" / "readme.txt").write_text("nothing")

    foo = root / "foo"
    foo.mkdir()
    (foo / "acqus").write_text(_acqus("zg30", "1H", sfo1=400.1))
    (foo / "fid").write_bytes(b"f")

    (root / "spec.jdx").write_text(
        f"##TITLE= {CANARY}\n##OWNER= {CANARY}\n##JCAMP-DX= 5.01\n##.OBSERVE FREQUENCY= 400.1\n"
        "##XYDATA= (X++(Y..Y))\n1 2 3\n##END=\n"
    )
    return root


def test_inventory_entries(tmp_path: Path) -> None:
    ds = _make(tmp_path / "ds")
    inv = build_inventory(ds, blind=True, fingerprint="sha256:abc")
    assert inv["schema"] == "ailsa.experiment-inventory"
    assert inv["schema_version"] == "1"
    assert inv["dataset_fingerprint"] == "sha256:abc"
    assert inv["blind"] is True
    by_id = {e["id"]: e for e in inv["experiments"]}
    assert set(by_id) == {"exp:1", "exp:2", "exp:3", "exp:4", "exp:x1"}
    assert by_id["exp:1"]["readable"] and by_id["exp:2"]["readable"] and by_id["exp:x1"]["readable"]
    assert by_id["exp:x1"]["folder_alias"] == "x1"
    for key in ("exp:3", "exp:4"):
        assert by_id[key]["readable"] is False
        assert by_id[key]["reason"]
    assert by_id["exp:4"]["reason"] == "no acqus"
    assert by_id["exp:3"]["reason"].startswith("unknown experiment type")
    assert inv["unreadable"] == 2


def test_entry_two_fields(tmp_path: Path) -> None:
    ds = _make(tmp_path / "ds")
    inv = build_inventory(ds, blind=False, fingerprint="sha256:abc")
    e = {x["id"]: x for x in inv["experiments"]}["exp:2"]
    assert e["kind"] == "HSQC"
    assert e["edited"] is True
    assert e["processed"] is False
    assert e["raw"] is True
    assert e["nus"] == {"fraction": 0.25, "schedule_present": True}
    assert e["sfo1_mhz"] == 400.1
    assert e["sfo1_f1_mhz"] == 100.6
    assert e["temperature_k"] == 298.0
    names = {f["path"] for f in e["source_files"]}
    assert {"2/acqus", "2/acqu2s", "2/ser"} <= names
    assert all(len(f["sha256"]) == 64 for f in e["source_files"])
    one = {x["id"]: x for x in inv["experiments"]}["exp:1"]
    assert one["nus"] is None  # NusAMOUNT alone (FnTYPE 0) is not NUS


PSP = Path(__file__).resolve().parents[2] / "data" / "PSP"


@pytest.mark.skipif(not PSP.is_dir(), reason="repo test data data/PSP absent")
@pytest.mark.parametrize("exp", ["1", "6", "7"])
def test_fully_sampled_topspin_data_is_not_nus(exp: str) -> None:
    """CR-03: zg30, HSQC and HMBC there carry NusAMOUNT= 25 with FnTYPE= 0 (fully sampled)."""
    from ailsa.case.scan import read_experiment

    info = read_experiment(PSP / exp)
    assert info is not None
    assert "NusAMOUNT" in (PSP / exp / "acqus").read_text()
    assert info.nus_fraction is None and not info.nus_schedule
    data = info.to_dict()
    assert "nus_fraction" in data and "nus_schedule" in data  # case scan JSON keys stay


def test_nus_flag_and_schedule(tmp_path: Path) -> None:
    from ailsa.case.scan import read_experiment

    exp = tmp_path / "3"
    exp.mkdir()
    (exp / "acqus").write_text(
        _acqus("hsqcetgpsisp2.2", "1H", sfo1=400.1, extra="##$FnTYPE= 2\n##$NusAMOUNT= 25\n")
    )
    (exp / "acqu2s").write_text("##$NUC1= <13C>\n##$SFO1= 100.6\n##$NusTD= 128\n")
    (exp / "ser").write_bytes(b"abcd")
    info = read_experiment(exp)
    assert info is not None and info.nus_fraction == 0.25 and info.nus_schedule is False
    (exp / "nuslist").write_text("0\n3\n")
    info = read_experiment(exp)
    assert info is not None and info.nus_fraction == 0.25 and info.nus_schedule is True


def test_titles_never_leak(tmp_path: Path) -> None:
    ds = _make(tmp_path / "ds")
    inv = build_inventory(ds, blind=True, fingerprint="sha256:abc")
    assert CANARY not in json.dumps(inv)
    assert "foo" not in json.dumps(inv)


def test_jcamp_headers(tmp_path: Path) -> None:
    ds = _make(tmp_path / "ds")
    inv = build_inventory(ds, blind=True, fingerprint="sha256:abc")
    (jc,) = inv["jcamp_files"]
    assert jc["path"] == "j1.jdx"  # WR-14: blind runs alias JCAMP file names
    assert len(jc["sha256"]) == 64
    keys = {k.upper() for k in jc["headers"]}
    assert "TITLE" not in keys and "OWNER" not in keys
    assert "JCAMP-DX" in keys
    assert "XYDATA" not in keys
    (open_jc,) = build_inventory(ds, blind=False, fingerprint="sha256:abc")["jcamp_files"]
    assert open_jc["path"] == "spec.jdx"


def test_jcamp_name_headers_never_recorded(tmp_path: Path) -> None:
    """WR-14: only measurement headers are kept (allow-list), whatever names the sample."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / f"{CANARY}.dx").write_text(
        f"##TITLE= x\n##JCAMP-DX= 5.01\n##NAMES= {CANARY}\n##CAS NAME= {CANARY}\n"
        f"##CAS REGISTRY NO= {CANARY}\n##$NAME= {CANARY}\n##SAMPLE DESCRIPTION= {CANARY}\n"
        f"##BLOCK_ID= {CANARY}\n##ORIGIN= {CANARY}\n##.OBSERVE NUCLEUS= ^13C\n"
        "##.SOLVENT NAME= CDCl3\n##XYDATA= (X++(Y..Y))\n1 2 3\n##END=\n"
    )
    inv = build_inventory(ds, blind=True, fingerprint="sha256:abc")
    assert CANARY not in json.dumps(inv)
    (jc,) = inv["jcamp_files"]
    assert set(jc["headers"]) == {"JCAMP-DX", ".OBSERVE NUCLEUS", ".SOLVENT NAME"}


def test_validates_against_model(tmp_path: Path) -> None:
    from ailsa.record.models import ExperimentInventory

    ds = _make(tmp_path / "ds")
    inv = build_inventory(ds, blind=True, fingerprint="sha256:abc")
    ExperimentInventory.model_validate(inv)
