"""
Background job: the "監控 -> D-7 通知" half of the pipeline.

Runs on a fixed interval (settings.scan_interval_seconds — short in the demo
so you don't have to wait a day to see it fire, hourly/daily in a real
deployment). Each run:
  1. recomputes each certificate's status from its expiry date,
  2. sends exactly one Chat warning per certificate per day once it is
     within the warning window, using `last_warned_at` as a throttle so a
     15-minute demo interval doesn't spam the channel.
"""
import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Certificate, RenewalEvent
from app.notifier import format_expiry_warning, send_chat_message

logger = logging.getLogger("scheduler")


def scan_for_expiring_certificates(db: Session | None = None) -> dict:
    owns_session = db is None
    db = db or SessionLocal()
    warned = 0
    try:
        certs = db.query(Certificate).all()
        today = dt.datetime.utcnow().date()
        for cert in certs:
            days_left = (cert.expires_at.date() - today).days

            if days_left < 0:
                cert.status = "expired"
            elif days_left <= settings.expiry_warning_days:
                cert.status = "expiring_soon"
            elif cert.status not in ("renewing",):
                cert.status = "active"

            should_warn = (
                0 <= days_left <= settings.expiry_warning_days
                and (cert.last_warned_at is None or cert.last_warned_at.date() < today)
            )
            if should_warn:
                send_chat_message(format_expiry_warning(cert))
                cert.last_warned_at = dt.datetime.utcnow()
                db.add(RenewalEvent(
                    certificate_id=cert.id,
                    event_type="expiry_warning",
                    message=f"到期前預警通知已發送（剩餘 {days_left} 天）",
                ))
                warned += 1
        db.commit()
        logger.info("到期掃描完成：共檢查 %d 筆，發送 %d 則預警", len(certs), warned)
        return {"checked": len(certs), "warned": warned}
    finally:
        if owns_session:
            db.close()


def setup_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(
        scan_for_expiring_certificates,
        "interval",
        seconds=settings.scan_interval_seconds,
        id="expiry_scan",
        next_run_time=dt.datetime.now(),  # also run once immediately on startup
    )
    scheduler.start()
    logger.info("到期掃描排程已啟動：每 %d 秒一次", settings.scan_interval_seconds)
    return scheduler
