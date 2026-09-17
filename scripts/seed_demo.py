#!/usr/bin/env python3
"""
Seed the database with a realistic-looking set of F5 / ISE wildcard
certificates for demo purposes, including a couple that are already inside
the 7-day warning window so the dashboard has something interesting to show
immediately after `docker-compose up`.

Usage:
    python scripts/seed_demo.py [--reset]
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import Certificate  # noqa: E402
from app.scheduler import scan_for_expiring_certificates  # noqa: E402

DEMO_CERTS = [
    dict(device_type="F5", device_name="f5-demo-01", domain="*.example.com", days_left=45),
    dict(device_type="F5", device_name="f5-demo-02", domain="*.web.example.com", days_left=5),
    dict(device_type="F5", device_name="f5-demo-03", domain="*.api.example.com", days_left=20),
    dict(device_type="ISE", device_name="ise-demo-01", domain="*.auth.example.com", days_left=3),
    dict(device_type="ISE", device_name="ise-demo-02", domain="*.guest.example.com", days_left=90),
    dict(device_type="ISE", device_name="ise-demo-03", domain="*.legacy.example.com", days_left=-2),
    # domain deliberately contains "fail-demo": mock_devices/common.py rejects any install
    # for such a domain, so this row is handy for demoing the failure / rollback path live.
    dict(device_type="F5", device_name="f5-demo-04", domain="*.fail-demo.example.com", days_left=6),
]


def main(reset: bool):
    if reset:
        Base.metadata.drop_all(bind=engine)
    init_db()

    db = SessionLocal()
    try:
        if db.query(Certificate).count() > 0 and not reset:
            print("資料庫已有資料，若要重新產生 demo 資料請加上 --reset")
            return

        now = dt.datetime.utcnow()
        for item in DEMO_CERTS:
            cert = Certificate(
                device_type=item["device_type"],
                device_name=item["device_name"],
                domain=item["domain"],
                cert_type="wildcard",
                serial_number=f"{abs(hash(item['device_name'])):x}"[:16],
                issued_at=now - dt.timedelta(days=365 - item["days_left"]),
                expires_at=now + dt.timedelta(days=item["days_left"]),
                status="active",
            )
            db.add(cert)
        db.commit()
        print(f"已建立 {len(DEMO_CERTS)} 筆示範憑證")

        result = scan_for_expiring_certificates(db)
        print(f"已執行到期掃描：檢查 {result['checked']} 筆，發送 {result['warned']} 則預警通知")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="清空現有資料後重建")
    args = parser.parse_args()
    main(reset=args.reset)
