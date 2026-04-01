"""
Synthetic SDTM dataset generator. [FIX M4] Consistent consent dates across DM and VS.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
NUM_SUBJECTS = 100
NUM_VISITS = 10
STUDY_ID = "SYNTH-001"
STUDY_START = datetime(2024, 1, 15)

VS_TESTS = {
    "SYSBP": {"name": "Systolic Blood Pressure", "unit": "mmHg", "mean": 120, "std": 12},
    "DIABP": {"name": "Diastolic Blood Pressure", "unit": "mmHg", "mean": 75, "std": 8},
    "PULSE": {"name": "Pulse Rate", "unit": "beats/min", "mean": 72, "std": 10},
    "TEMP": {"name": "Temperature", "unit": "C", "mean": 36.6, "std": 0.3},
    "RESP": {"name": "Respiratory Rate", "unit": "breaths/min", "mean": 16, "std": 3},
    "WEIGHT": {"name": "Weight", "unit": "kg", "mean": 75, "std": 15},
}
VISITS = [f"Visit {i}" for i in range(1, NUM_VISITS + 1)]


def _generate_consent_dates(rng: np.random.Generator) -> dict[str, datetime]:
    """Generate consent dates ONCE for all subjects. [FIX M4]"""
    return {
        f"{STUDY_ID}-{i:04d}": STUDY_START + timedelta(days=int(rng.integers(0, 30)))
        for i in range(1, NUM_SUBJECTS + 1)
    }


def generate_clean_vs_data(rng: np.random.Generator, consent_dates: dict[str, datetime]) -> pd.DataFrame:
    records = []
    seq = 1
    for subj_idx in range(1, NUM_SUBJECTS + 1):
        subject_id = f"{STUDY_ID}-{subj_idx:04d}"
        consent_date = consent_dates[subject_id]
        for visit_idx, visit_name in enumerate(VISITS):
            visit_date = consent_date + timedelta(days=visit_idx * 14 + int(rng.integers(-2, 3)))
            for test_code, test_info in VS_TESTS.items():
                value = round(max(rng.normal(test_info["mean"], test_info["std"]), 1), 1)
                records.append({
                    "STUDYID": STUDY_ID, "DOMAIN": "VS", "USUBJID": subject_id,
                    "VSSEQ": seq, "VSTESTCD": test_code, "VSTEST": test_info["name"],
                    "VSORRES": str(value), "VSORRESU": test_info["unit"],
                    "VSSTRESC": str(value), "VSSTRESN": value, "VSSTRESU": test_info["unit"],
                    "VISITNUM": visit_idx + 1, "VISIT": visit_name,
                    "VSDTC": visit_date.strftime("%Y-%m-%d"),
                    "RFSTDTC": consent_date.strftime("%Y-%m-%d"),
                })
                seq += 1
    return pd.DataFrame(records)


def inject_anomalies(df: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, list[dict]]:
    df = df.copy()
    ground_truth = []

    sysbp_mask = df["VSTESTCD"] == "SYSBP"
    sysbp_indices = df[sysbp_mask].sample(n=5, random_state=SEED).index
    for idx in sysbp_indices:
        bad_value = round(rng.uniform(210, 260), 1)
        df.loc[idx, "VSSTRESN"] = bad_value
        df.loc[idx, "VSORRES"] = str(bad_value)
        df.loc[idx, "VSSTRESC"] = str(bad_value)
        ground_truth.append({"index": int(idx), "type": "out_of_range",
                             "subject": df.loc[idx, "USUBJID"], "visit": df.loc[idx, "VISIT"],
                             "field": "SYSBP", "injected_value": bad_value})

    non_anomaly = df[~df.index.isin(sysbp_indices)]
    temporal_indices = non_anomaly.sample(n=5, random_state=SEED + 1).index
    for idx in temporal_indices:
        consent = pd.to_datetime(df.loc[idx, "RFSTDTC"])
        bad_date = consent - timedelta(days=int(rng.integers(10, 60)))
        df.loc[idx, "VSDTC"] = bad_date.strftime("%Y-%m-%d")
        ground_truth.append({"index": int(idx), "type": "temporal",
                             "subject": df.loc[idx, "USUBJID"], "visit": df.loc[idx, "VISIT"],
                             "field": "VSDTC", "injected_value": bad_date.strftime("%Y-%m-%d")})

    remaining = df[~df.index.isin(sysbp_indices.union(temporal_indices))]
    missing_indices = remaining.sample(n=5, random_state=SEED + 2).index
    for idx in missing_indices:
        df.loc[idx, "VSSTRESN"] = np.nan
        df.loc[idx, "VSORRES"] = ""
        df.loc[idx, "VSSTRESC"] = ""
        ground_truth.append({"index": int(idx), "type": "missing",
                             "subject": df.loc[idx, "USUBJID"], "visit": df.loc[idx, "VISIT"],
                             "field": "VSSTRESN", "injected_value": None})

    all_used = sysbp_indices.union(temporal_indices).union(missing_indices)
    available = df[~df.index.isin(all_used)]
    bp_pairs = available[available["VSTESTCD"].isin(["SYSBP", "DIABP"])]
    grouped = bp_pairs.groupby(["USUBJID", "VISIT"]).filter(lambda x: len(x) == 2)
    if len(grouped) >= 10:
        pair_keys = list(grouped.groupby(["USUBJID", "VISIT"]).first().index[:5])
        for subj, visit in pair_keys:
            sys_idx = df[(df["USUBJID"] == subj) & (df["VISIT"] == visit) & (df["VSTESTCD"] == "SYSBP")].index
            dia_idx = df[(df["USUBJID"] == subj) & (df["VISIT"] == visit) & (df["VSTESTCD"] == "DIABP")].index
            if len(sys_idx) > 0 and len(dia_idx) > 0:
                sys_val = df.loc[sys_idx[0], "VSSTRESN"]
                df.loc[dia_idx[0], "VSSTRESN"] = sys_val + 10
                df.loc[dia_idx[0], "VSORRES"] = str(sys_val + 10)
                df.loc[dia_idx[0], "VSSTRESC"] = str(sys_val + 10)
                ground_truth.append({"index": int(dia_idx[0]), "type": "cross_field",
                                     "subject": subj, "visit": visit,
                                     "field": "DIABP", "injected_value": sys_val + 10})
    return df, ground_truth


def generate_dm_data(rng: np.random.Generator, consent_dates: dict[str, datetime]) -> pd.DataFrame:
    """[FIX M4] Uses same consent_dates as VS data."""
    records = []
    for subj_idx in range(1, NUM_SUBJECTS + 1):
        subject_id = f"{STUDY_ID}-{subj_idx:04d}"
        consent_date = consent_dates[subject_id]
        age = int(rng.integers(18, 80))
        arm = rng.choice(["TREATMENT", "PLACEBO"])  # BUG2 FIX: single choice for both
        records.append({
            "STUDYID": STUDY_ID, "DOMAIN": "DM", "USUBJID": subject_id,
            "SUBJID": f"{subj_idx:04d}",
            "RFSTDTC": consent_date.strftime("%Y-%m-%d"),
            "RFENDTC": (consent_date + timedelta(days=NUM_VISITS * 14)).strftime("%Y-%m-%d"),
            "SITEID": f"SITE-{(subj_idx % 10) + 1:02d}",
            "BRTHDTC": (consent_date - timedelta(days=age * 365)).strftime("%Y-%m-%d"),
            "AGE": age, "AGEU": "YEARS",
            "SEX": rng.choice(["M", "F"]),
            "RACE": rng.choice(["WHITE", "BLACK OR AFRICAN AMERICAN", "ASIAN", "MULTIPLE"]),
            "ETHNIC": rng.choice(["HISPANIC OR LATINO", "NOT HISPANIC OR LATINO"]),
            "ARMCD": "TRT" if arm == "TREATMENT" else "PBO",
            "ARM": arm,
            "COUNTRY": "USA",
        })
    return pd.DataFrame(records)


def main():
    rng = np.random.default_rng(SEED)
    output_dir = Path(__file__).parent
    consent_dates = _generate_consent_dates(rng)  # FIX M4: shared dates
    vs_clean = generate_clean_vs_data(rng, consent_dates)
    vs_anomalous, ground_truth = inject_anomalies(vs_clean, rng)
    dm = generate_dm_data(rng, consent_dates)
    vs_clean.to_csv(output_dir / "vs_clean.csv", index=False)
    vs_anomalous.to_csv(output_dir / "vs_anomalous.csv", index=False)
    dm.to_csv(output_dir / "dm.csv", index=False)
    with open(output_dir / "ground_truth_anomalies.json", "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, default=str)
    print(f"Generated {len(vs_clean)} clean VS records")
    print(f"Generated {len(vs_anomalous)} VS records with {len(ground_truth)} injected anomalies")
    print(f"Generated {len(dm)} DM records")
    for atype in ["out_of_range", "temporal", "missing", "cross_field"]:
        print(f"  - {atype}: {sum(1 for a in ground_truth if a['type'] == atype)}")


if __name__ == "__main__":
    main()
