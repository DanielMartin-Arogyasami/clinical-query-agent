"""
Data loading and manipulation tools.
[FIX L5] Better error messages for unsupported formats.
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


def load_sdtm_dataset(path: str | Path, domain: str | None = None) -> pd.DataFrame:
    """Load an SDTM dataset from CSV/XPT/Parquet."""
    path = Path(path)
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    elif path.suffix == ".xpt":
        try:
            df = pd.read_sas(path, format="xport")
        except Exception as e:
            raise ImportError(
                f"Failed to read {path}. For .xpt files, ensure pyreadstat is installed: "
                f"pip install pyreadstat. Original error: {e}"
            ) from e
    elif path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Supported: .csv, .xpt, .parquet")

    if domain and "DOMAIN" in df.columns:
        df = df[df["DOMAIN"] == domain]

    logger.info("data.loaded", path=str(path), rows=len(df), cols=len(df.columns))
    return df


def export_sdtm_dataset(df: pd.DataFrame, path: str | Path, domain: str = "") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if "DOMAIN" not in df.columns and domain:
        df = df.copy()
        df.insert(1, "DOMAIN", domain)
    df.to_csv(path, index=False)
    logger.info("data.exported", path=str(path), rows=len(df))
    return path


def compute_dataset_summary(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_pct": {col: round(df[col].isna().mean() * 100, 2) for col in df.columns},
        "unique_subjects": df["USUBJID"].nunique() if "USUBJID" in df.columns else None,
        "unique_visits": df["VISIT"].nunique() if "VISIT" in df.columns else None,
    }
