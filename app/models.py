import datetime as dt

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Certificate(Base):
    """One managed certificate on one device (F5 or ISE)."""

    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    device_type = Column(String, nullable=False)       # "F5" | "ISE"
    device_name = Column(String, nullable=False)        # e.g. "f5-demo-01"
    domain = Column(String, nullable=False)              # e.g. "*.example.com"
    cert_type = Column(String, default="wildcard")
    serial_number = Column(String, default="")
    issued_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    status = Column(String, default="active")             # active | expiring_soon | expired | renewing
    last_warned_at = Column(DateTime, nullable=True)     # last time a D-7 warning was sent (throttle to 1/day)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    events = relationship("RenewalEvent", back_populates="certificate", order_by="desc(RenewalEvent.created_at)")

    @property
    def days_left(self) -> int:
        return (self.expires_at.date() - dt.datetime.utcnow().date()).days


class RenewalEvent(Base):
    """Audit trail: every warning / upload / renewal attempt is recorded here."""

    __tablename__ = "renewal_events"

    id = Column(Integer, primary_key=True, index=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"), nullable=False)
    event_type = Column(String, nullable=False)  # expiry_warning | renewal_started | renewal_success | renewal_failed
    message = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)

    certificate = relationship("Certificate", back_populates="events")
