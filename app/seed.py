"""
Shared demo-data seeding logic.

Used by three callers that all need the exact same behaviour:
  - scripts/seed_demo.py       (manual CLI seeding for local/docker-compose use)
  - app/main.py's lifespan     (auto-seed on startup for the public hosted demo,
                                 so a visitor never lands on an empty dashboard —
                                 useful since free hosting tiers wipe on restart)
  - app/routers/api.py's       POST /api/reset-demo (a visible "reset demo data"
    reset endpoint              button, since a public demo is a shared, mutable
                                 sandbox anyone can click buttons in)
"""
import datetime as dt

from sqlalchemy.orm import Session

from app.models import Certificate, RenewalEvent
from app.scheduler import scan_for_expiring_certificates

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


def seed_demo_data(db: Session, reset: bool = False) -> dict:
    """Populate (or, if reset=True, wipe and repopulate) the demo certificate set.

    Returns a small summary dict; never raises for the "already seeded" case,
    it just reports that nothing changed.
    """
    if reset:
        # bulk delete() bypasses ORM cascades, so clear the child table explicitly
        # too — otherwise a reset leaves orphaned events pointing at deleted certs.
        db.query(RenewalEvent).delete()
        db.query(Certificate).delete()
        db.commit()

    if db.query(Certificate).count() > 0 and not reset:
        return {"seeded": False, "reason": "already has data"}

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

    scan_result = scan_for_expiring_certificates(db)
    return {"seeded": True, "count": len(DEMO_CERTS), **scan_result}
