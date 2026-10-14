#!/usr/bin/env python3
"""Upload compounds database to Zenodo."""

import os
import sys
from pathlib import Path

import requests

# Configuration
ZENODO_API = "https://zenodo.org/api"
FILE_PATH = Path("data/reference/compounds.db.gz")

METADATA = {
    "metadata": {
        "title": "AILSA reference database: 13C NMR shifts and HOSE statistics for natural-product dereplication and shift prediction (COCONUT + NMRShiftDB)",
        "upload_type": "dataset",
        "description": """Pre-built SQLite reference database for AILSA (AI + LSD + Agents), an AI-agent system for computer-assisted structure elucidation (CASE) of organic natural products from NMR spectra. AILSA is built on the LSD structure generator by Jean-Marc Nuzillard (Université de Reims Champagne-Ardenne).

**Contents:**
- **928,443 compounds** total
- **COCONUT**: 895,099 natural products with predicted 13C shifts (ACD/Labs C+H NMR Predictors and DB 2020.1.0)
- **NMRShiftDB**: 33,344 compounds with experimental 13C shifts
- **111,493 unique molecular formulas**
- **7.9 million HOSE-code statistics**

One file serves both dereplication and 13C prediction.

**Data source:** COCONUT 13C shifts: ACD/Labs predictions from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0.

**Usage:**
```bash
# Install AILSA
# https://github.com/steinbeck/ailsa
ailsa database download
ailsa database info
```

**Related software:** https://github.com/steinbeck/ailsa
""",
        "creators": [
            {"name": "Steinbeck, Christoph", "affiliation": "Friedrich Schiller University Jena"}
        ],
        "keywords": [
            "NMR spectroscopy",
            "natural products",
            "chemical shifts",
            "13C NMR",
            "dereplication",
            "COCONUT",
            "NMRShiftDB",
            "structure elucidation"
        ],
        "license": "cc-by-4.0",
        "related_identifiers": [
            {
                "identifier": "https://github.com/steinbeck/ailsa",
                "relation": "isSupplementTo",
                "resource_type": "software"
            },
            {"identifier": "10.5281/zenodo.6561449", "relation": "isDerivedFrom", "resource_type": "dataset"}
        ],
    }
}


def main():
    token = os.environ.get("ZENODO_TOKEN")

    # Also accept token as command-line argument
    if len(sys.argv) > 1:
        token = sys.argv[1]

    if not token:
        print("Usage: python zenodo_upload.py <ZENODO_TOKEN>")
        print("   or: export ZENODO_TOKEN='...' && python zenodo_upload.py")
        sys.exit(1)

    if not FILE_PATH.exists():
        print(f"Error: File not found: {FILE_PATH}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    print("=" * 60)
    print("Zenodo Upload: AILSA reference database")
    print("=" * 60)

    # Step 1: Create deposition
    print("\n[1/4] Creating deposition...")
    r = requests.post(
        f"{ZENODO_API}/deposit/depositions",
        json={},
        headers=headers
    )
    if r.status_code != 201:
        print(f"Error creating deposition: {r.status_code}")
        print(r.json())
        sys.exit(1)

    deposition = r.json()
    deposition_id = deposition["id"]
    bucket_url = deposition["links"]["bucket"]
    print(f"  Created deposition ID: {deposition_id}")

    # Step 2: Upload file
    print(f"\n[2/4] Uploading {FILE_PATH.name} ({FILE_PATH.stat().st_size / 1e6:.1f} MB)...")
    print("  This may take a few minutes...")

    with open(FILE_PATH, "rb") as f:
        r = requests.put(
            f"{bucket_url}/{FILE_PATH.name}",
            data=f,
            headers=headers
        )

    if r.status_code not in (200, 201):
        print(f"Error uploading file: {r.status_code}")
        print(r.json())
        sys.exit(1)
    print(f"  Uploaded successfully!")

    # Step 3: Add metadata
    print("\n[3/4] Adding metadata...")
    r = requests.put(
        f"{ZENODO_API}/deposit/depositions/{deposition_id}",
        json=METADATA,
        headers={**headers, "Content-Type": "application/json"}
    )
    if r.status_code != 200:
        print(f"Error adding metadata: {r.status_code}")
        print(r.json())
        sys.exit(1)
    print("  Metadata added!")

    # Step 4: Publish
    print("\n[4/4] Publishing...")
    r = requests.post(
        f"{ZENODO_API}/deposit/depositions/{deposition_id}/actions/publish",
        headers=headers
    )
    if r.status_code != 202:
        print(f"Error publishing: {r.status_code}")
        print(r.json())
        sys.exit(1)

    result = r.json()
    doi = result.get("doi", "N/A")
    doi_url = result.get("doi_url", f"https://doi.org/{doi}")
    record_url = result["links"]["record_html"]

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"\n  DOI: {doi}")
    print(f"  URL: {doi_url}")
    print(f"  Record: {record_url}")
    print(f"\nDownload link for AILSA:")
    print(f"  {result['files'][0]['links']['download']}")


if __name__ == "__main__":
    main()
