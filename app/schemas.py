import datetime as dt
from pydantic import BaseModel, ConfigDict


class RenewalEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    message: str
    created_at: dt.datetime


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_type: str
    device_name: str
    domain: str
    cert_type: str
    serial_number: str
    issued_at: dt.datetime
    expires_at: dt.datetime
    status: str
    days_left: int


class CertificateDetailOut(CertificateOut):
    events: list[RenewalEventOut] = []
