#!/usr/bin/env python3
"""
Create small sample datasets for local testing and CI.

Downloads a minimal subset from Zenodo and saves to tests/fixtures/sample_data/.
Use before running tests that need local fixtures, or in CI before dataset tests.

Usage:
    python scripts/create_sample_data.py
    SAMPLE_MAX_ROWS=50 python scripts/create_sample_data.py  # override max rows
    python scripts/create_sample_data.py --fdata-only
    python scripts/create_sample_data.py --pm100-only

Output:
    tests/fixtures/sample_data/sample_fdata.parquet
    tests/fixtures/sample_data/sample_pm100.parquet
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _max_rows() -> int:
    return int(os.environ.get("SAMPLE_MAX_ROWS", os.environ.get("CI_MAX_SAMPLES", "100")))


def _output_dir() -> Path:
    d = PROJECT_ROOT / "tests" / "fixtures" / "sample_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_fdata_sample(max_rows: int, out_dir: Path) -> None:
    """Create sample_fdata.parquet from Zenodo."""
    import pandas as pd

    url = "https://zenodo.org/records/11467483/files/21_04.parquet"
    # F-DATA schema: jid, nnuma, duration, avgpcon, adt, flops, mbwidth, etc.
    cols = ["nnuma", "duration", "avgpcon", "adt"]
    print(f"Fetching F-DATA from Zenodo (21_04.parquet), max {max_rows} rows...")

    df = pd.read_parquet(url, columns=cols)
    sample = df.head(max_rows)
    out_path = out_dir / "sample_fdata.parquet"
    sample.to_parquet(out_path, index=False)
    print(f"  Saved {len(sample)} rows to {out_path}")


def create_pm100_sample(max_rows: int, out_dir: Path) -> None:
    """Create sample_pm100.parquet from Zenodo."""
    import pandas as pd

    url = "https://zenodo.org/records/10127767/files/job_table.parquet"
    print(f"Fetching PM100 from Zenodo, max {max_rows} rows...")

    df = pd.read_parquet(url)
    # Prefer known columns for tests; fallback to numeric cols
    preferred = ["num_nodes_req", "num_nodes_alloc", "elapsed_time", "n_tasks"]
    available = [c for c in preferred if c in df.columns]
    if len(available) >= 2:
        cols = available[:3]
    else:
        cols = df.select_dtypes(include=["number"]).columns[:3].tolist()
    sample = df[cols].head(max_rows)
    out_path = out_dir / "sample_pm100.parquet"
    sample.to_parquet(out_path, index=False)
    print(f"  Saved {len(sample)} rows to {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Create small sample datasets for tests (from Zenodo)."
    )
    parser.add_argument(
        "--fdata-only",
        action="store_true",
        help="Only create F-DATA sample.",
    )
    parser.add_argument(
        "--pm100-only",
        action="store_true",
        help="Only create PM100 sample.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help=f"Max rows per sample (default: SAMPLE_MAX_ROWS or CI_MAX_SAMPLES or 100).",
    )
    args = parser.parse_args()

    max_rows = args.max_rows or _max_rows()
    out_dir = _output_dir()

    do_fdata = not args.pm100_only
    do_pm100 = not args.fdata_only

    try:
        if do_fdata:
            create_fdata_sample(max_rows, out_dir)
        if do_pm100:
            create_pm100_sample(max_rows, out_dir)
        print("Done.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
