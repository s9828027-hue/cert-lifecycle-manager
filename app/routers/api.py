import datetime as dt

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Certificate, RenewalEvent
from app.scheduler import scan_for_expiring_certificates
from app.schemas import CertificateDetailOut, CertificateOut, RenewalEventOut
from app.watcher import process_certificate_file

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/certificates", response_model=list[CertificateOut])
def list_certificates(db: Session = Depends(get_db)):
    return db.query(Certificate).order_by(Certificate.expires_at.asc()).all()


@router.get("/certificates/{cert_id}", response_model=CertificateDetailOut)
def get_certificate(cert_id: int, db: Session = Depends(get_db)):
    cert = db.get(Certificate, cert_id)
    if cert is None:
        raise HTTPException(404, "找不到憑證")
    return cert


@router.get("/events", response_model=list[RenewalEventOut])
def list_recent_events(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(RenewalEvent).order_by(RenewalEvent.created_at.desc()).limit(limit).all()


@router.post("/scan-now")
def trigger_scan_now(db: Session = Depends(get_db)):
    """Manual trigger for the D-7 expiry scan — lets a live demo skip waiting for the interval."""
    return scan_for_expiring_certificates(db)


@router.post("/certificates/{cert_id}/simulate-expiry")
def simulate_expiry(cert_id: int, days: int = 5, db: Session = Depends(get_db)):
    """Demo helper: fast-forward a certificate's expiry so the D-7 warning fires immediately."""
    cert = db.get(Certificate, cert_id)
    if cert is None:
        raise HTTPException(404, "找不到憑證")
    cert.expires_at = dt.datetime.utcnow() + dt.timedelta(days=days)
    cert.last_warned_at = None
    db.commit()
    scan_for_expiring_certificates(db)
    db.refresh(cert)
    return cert


@router.post("/certificates/{cert_id}/upload")
async def upload_new_certificate(
    cert_id: int,
    cert_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    The web-UI equivalent of 管理者將新憑證放置固定資料夾: saves the uploaded
    cert/key into data/certs_incoming/ under the naming convention the
    watcher expects, then runs the same processing path it would use.
    """
    record = db.get(Certificate, cert_id)
    if record is None:
        raise HTTPException(404, "找不到憑證")

    stem = f"{record.device_type}_{record.device_name}"
    cert_path = settings.incoming_dir / f"{stem}.pem"
    key_path = settings.incoming_dir / f"{stem}.key"
    cert_path.write_bytes(await cert_file.read())
    key_path.write_bytes(await key_file.read())

    result = process_certificate_file(cert_path, db)
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    db.refresh(record)
    return record
