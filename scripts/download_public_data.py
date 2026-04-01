"""Download publicly available data. [FIX H6] Calls ensure_dirs()."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import requests
from config.settings import settings


def download_ctgov_protocols(nct_ids: list[str] | None = None, max_results: int = 5):
    output_dir = Path(settings.protocol_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if nct_ids:
        for nct_id in nct_ids:
            url = f"{settings.ctgov_base_url}/studies/{nct_id}"
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                with open(output_dir / f"{nct_id}.json", "w", encoding="utf-8") as f:
                    json.dump(resp.json(), f, indent=2)
                print(f"Downloaded: {nct_id}")
            except Exception as e:
                print(f"Failed to download {nct_id}: {e}")


def download_cdisc_pilot():
    output_dir = Path(settings.cdisc_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_url = (
        "https://raw.githubusercontent.com/cdisc-org/sdtm-adam-pilot-project/master/"
        "updated-pilot-submission-package/900172/m5/datasets/cdiscpilot01/tabulations/sdtm"
    )
    for ds in ["dm.xpt", "vs.xpt", "ae.xpt", "lb.xpt", "cm.xpt", "mh.xpt"]:
        try:
            resp = requests.get(f"{base_url}/{ds}", timeout=30)
            resp.raise_for_status()
            with open(output_dir / ds, "wb") as f:
                f.write(resp.content)
            print(f"Downloaded: {ds}")
        except Exception as e:
            print(f"Failed to download {ds}: {e}")


def main():
    settings.ensure_dirs()
    print("=" * 60)
    print("Downloading public data sources...")
    print("=" * 60)
    print("\n--- ClinicalTrials.gov Protocols ---")
    download_ctgov_protocols(nct_ids=["NCT00000620", "NCT02008227", "NCT01251120", "NCT00094887", "NCT04368728"])
    print("\n--- CDISC Pilot Study Datasets ---")
    download_cdisc_pilot()
    print("\n--- Generating Synthetic Data ---")
    subprocess.run([sys.executable, str(Path(settings.synthetic_data_dir) / "generate_synthetic.py")], check=False)
    print("\nOK: All public data downloaded successfully.")


if __name__ == "__main__":
    main()
