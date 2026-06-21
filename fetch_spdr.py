"""
Fetch OHLC data for Select Sector SPDR ETFs + SPY benchmark
from the local Schwab broker API and save as CSV files for RRG-Lite.

Usage:
    python fetch_spdr.py [--api-key KEY] [--host HOST] [--out DIR] [--years N]

Defaults:
    host    http://localhost:8080
    out     ./data
    years   2
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

SPDR_ETFS = {
    "SPY":  "S&P 500 (benchmark)",
    "XLB":  "Materials",
    "XLC":  "Communication Services",
    "XLE":  "Energy",
    "XLF":  "Financial",
    "XLI":  "Industrials",
    "XLK":  "Technology",
    "XLP":  "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
    "XLV":  "Health Care",
    "XLY":  "Consumer Discretionary",
}


def fetch_history(host: str, api_key: str, symbol: str, start: str, end: str) -> list[dict]:
    url = f"{host}/api/v1/market/history/{symbol}"
    params = {
        "period_type": "year",
        "frequency_type": "weekly",
        "frequency": "1",
        "start_date": start,
        "end_date": end,
    }
    headers = {"X-API-Key": api_key}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    return data.get("candles", [])


def candles_to_csv(candles: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        for c in candles:
            date = c["timestamp"][:10]
            writer.writerow([date, c["open"], c["high"], c["low"], c["close"], c["volume"]])

    return len(candles)


def fetch_all(
    host: str,
    api_key: str,
    out_dir: Path,
    years: int = 2,
    progress_cb=None,
) -> tuple[list, list]:
    """Fetch all SPDR ETFs and SPY. Returns (success_list, failed_list)."""
    end = datetime.today()
    start = end - timedelta(days=365 * years)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    out_dir = Path(out_dir)

    success, failed = [], []

    for symbol, label in SPDR_ETFS.items():
        if progress_cb:
            progress_cb(f"Fetching {symbol} — {label}...")
        try:
            candles = fetch_history(host, api_key, symbol, start_str, end_str)
            if not candles:
                failed.append(symbol)
                continue
            candles_to_csv(candles, out_dir / f"{symbol.lower()}.csv")
            success.append(symbol)
        except Exception as exc:
            if progress_cb:
                progress_cb(f"Error fetching {symbol}: {exc}")
            failed.append(symbol)

    return success, failed


def main():
    parser = argparse.ArgumentParser(description="Fetch SPDR ETF OHLC data for RRG-Lite")
    parser.add_argument("--api-key", default="dev-api-key", help="Broker API key")
    parser.add_argument("--host", default="http://localhost:8080", help="Broker API base URL")
    parser.add_argument("--out", default="data", help="Output directory for CSV files")
    parser.add_argument("--years", type=int, default=2, help="Years of history to fetch")
    args = parser.parse_args()

    out_dir = Path(args.out)
    print(f"Fetching into {out_dir}/\n")

    def progress(msg):
        print(f"  {msg}", flush=True)

    success, failed = fetch_all(
        host=args.host,
        api_key=args.api_key,
        out_dir=out_dir,
        years=args.years,
        progress_cb=progress,
    )

    print(f"\nDone: {len(success)} fetched, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)

    user_json = Path(__file__).parent / "src" / "user.json"
    if not user_json.exists():
        abs_data = out_dir.resolve()
        user_json.write_text(
            f'{{\n  "DATA_PATH": "{abs_data}/",\n  "DEFAULT_TF": "weekly"\n}}\n'
        )
        print(f"\nCreated src/user.json pointing to {abs_data}/")


if __name__ == "__main__":
    main()
