"""
Folder watcher: this is the "管理者將新憑證放置固定資料夾" half of the pipeline.

Naming convention for a dropped-in certificate (kept deliberately simple for
the demo): `<DeviceType>_<DeviceName>.pem` with a matching `.key` file of the
same stem, e.g.

    F5_f5-dc1-prod-lb01.pem
    F5_f5-dc1-prod-lb01.key

process_certificate_file() is the single entry point used both by the
filesystem watcher (watchdog, for the "drop a file with scp/sftp" workflow)
and by the dashboard's manual upload endpoint (for the "click upload in the
browser" workflow) — one code path, two triggers, so behaviour never drifts
between them.

Demo trick: name a file so device_name/domain contains "fail-demo" to see
the mock device reject the install and watch the failure path (event log +
chat alert) instead of the happy path.
"""
import logging
import shutil
import time
from pathlib import Path

from sqlalchemy.orm import Session
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.cert_utils import parse_certificate
from app.config import settings
from app.database import SessionLocal
from app.devices import get_client
from app.devices.base import DeviceApiError
from app.models import Certificate, RenewalEvent
from app.notifier import format_renewal_result, send_chat_message

logger = logging.getLogger("watcher")

PROCESSED_DIR = settings.incoming_dir / "_processed"
FAILED_DIR = settings.incoming_dir / "_failed"
REJECTED_DIR = settings.incoming_dir / "_rejected"


def _wait_for_sibling_key(pem_path: Path, attempts: int = 10, delay: float = 0.5) -> Path | None:
    key_path = pem_path.with_suffix(".key")
    for _ in range(attempts):
        if key_path.exists():
            return key_path
        time.sleep(delay)
    return None


def _move(path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(path), str(dest_dir / path.name))
    except OSError as exc:
        logger.warning("無法搬移檔案 %s -> %s: %s", path, dest_dir, exc)


def process_certificate_file(pem_path: Path, db: Session | None = None) -> dict:
    """Validate + install a dropped certificate. Returns a result dict; never raises."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        stem = pem_path.stem
        if "_" not in stem:
            reason = f"檔名格式錯誤，應為 <DeviceType>_<DeviceName>.pem，收到：{pem_path.name}"
            logger.warning(reason)
            _move(pem_path, REJECTED_DIR)
            return {"ok": False, "reason": reason}

        device_type, device_name = stem.split("_", 1)

        key_path = _wait_for_sibling_key(pem_path)
        if key_path is None:
            reason = f"找不到對應的私鑰檔 {pem_path.with_suffix('.key').name}"
            logger.warning(reason)
            _move(pem_path, REJECTED_DIR)
            return {"ok": False, "reason": reason}

        cert_pem = pem_path.read_bytes()
        key_pem = key_path.read_bytes()

        try:
            parsed = parse_certificate(cert_pem)
        except ValueError as exc:
            reason = f"憑證檔案格式錯誤，無法解析：{exc}"
            logger.warning(reason)
            _move(pem_path, REJECTED_DIR)
            _move(key_path, REJECTED_DIR)
            return {"ok": False, "reason": reason}

        record = (
            db.query(Certificate)
            .filter(Certificate.device_type == device_type.upper(), Certificate.device_name == device_name)
            .first()
        )
        if record is None:
            reason = f"找不到對應的受管理憑證紀錄（{device_type}/{device_name}），請確認檔名"
            logger.warning(reason)
            _move(pem_path, REJECTED_DIR)
            _move(key_path, REJECTED_DIR)
            return {"ok": False, "reason": reason}

        if parsed.domain != record.domain:
            reason = f"網域不符：新憑證為 {parsed.domain}，管理中憑證為 {record.domain}"
            logger.warning(reason)
            _move(pem_path, REJECTED_DIR)
            _move(key_path, REJECTED_DIR)
            db.add(RenewalEvent(certificate_id=record.id, event_type="renewal_failed", message=reason))
            db.commit()
            return {"ok": False, "reason": reason}

        record.status = "renewing"
        db.add(RenewalEvent(certificate_id=record.id, event_type="renewal_started",
                             message=f"偵測到新憑證 {pem_path.name}，開始自動更換"))
        db.commit()

        client = get_client(device_type)
        try:
            client.install_certificate(device_name, parsed.domain, cert_pem.decode(), key_pem.decode())
        except DeviceApiError as exc:
            record.status = "active" if record.days_left > 0 else "expired"
            db.add(RenewalEvent(certificate_id=record.id, event_type="renewal_failed", message=str(exc)))
            db.commit()
            send_chat_message(format_renewal_result(record, success=False, detail=str(exc)))
            _move(pem_path, FAILED_DIR)
            _move(key_path, FAILED_DIR)
            return {"ok": False, "reason": str(exc)}

        record.issued_at = parsed.issued_at
        record.expires_at = parsed.expires_at
        record.serial_number = parsed.serial_number
        record.status = "active"
        record.last_warned_at = None
        db.add(RenewalEvent(certificate_id=record.id, event_type="renewal_success",
                             message=f"已成功更換為新憑證，新到期日 {parsed.expires_at:%Y-%m-%d}"))
        db.commit()
        send_chat_message(format_renewal_result(record, success=True,
                                                  detail=f"新到期日 {parsed.expires_at:%Y-%m-%d}"))
        _move(pem_path, PROCESSED_DIR)
        _move(key_path, PROCESSED_DIR)
        return {"ok": True, "certificate_id": record.id}
    finally:
        if owns_session:
            db.close()


class _IncomingCertHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pem":
            return
        # give the OS a moment to finish flushing the file
        time.sleep(0.3)
        logger.info("偵測到新憑證檔案：%s", path.name)
        process_certificate_file(path)


def start_watcher() -> Observer:
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(_IncomingCertHandler(), str(settings.incoming_dir), recursive=False)
    observer.start()
    logger.info("資料夾監控已啟動：%s", settings.incoming_dir)
    return observer
