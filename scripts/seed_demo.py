#!/usr/bin/env python3
"""
Seed the database with a realistic-looking set of F5 / ISE wildcard
certificates for demo purposes, including a couple that are already inside
the 7-day warning window so the dashboard has something interesting to show
immediately after `docker-compose up`.

The actual dataset and logic live in app/seed.py, shared with the
auto-seed-on-startup path and the dashboard's "reset demo data" button.

Usage:
    python scripts/seed_demo.py [--reset]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.seed import seed_demo_data  # noqa: E402


def main(reset: bool):
    init_db()
    db = SessionLocal()
    try:
        result = seed_demo_data(db, reset=reset)
        if not result["seeded"]:
            print("資料庫已有資料，若要重新產生 demo 資料請加上 --reset")
            return
        print(f"已建立 {result['count']} 筆示範憑證")
        print(f"已執行到期掃描：檢查 {result['checked']} 筆，發送 {result['warned']} 則預警通知")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="清空現有資料後重建")
    args = parser.parse_args()
    main(reset=args.reset)
