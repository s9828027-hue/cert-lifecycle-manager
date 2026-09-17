import datetime as dt
from types import SimpleNamespace

import pytest

from app import watcher
from app.cert_utils import generate_self_signed_wildcard
from app.devices.base import DeviceApiError
from app.models import Certificate, RenewalEvent


def _seed_certificate(db_session, domain="*.example.com"):
    cert = Certificate(
        device_type="F5",
        device_name="test-lb01",
        domain=domain,
        cert_type="wildcard",
        serial_number="old",
        issued_at=dt.datetime.utcnow() - dt.timedelta(days=360),
        expires_at=dt.datetime.utcnow() + dt.timedelta(days=5),
        status="expiring_soon",
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)
    return cert


def _write_pair(tmp_path, stem, domain, valid_days=200):
    cert_pem, key_pem = generate_self_signed_wildcard(domain, valid_days=valid_days)
    (tmp_path / f"{stem}.pem").write_bytes(cert_pem)
    (tmp_path / f"{stem}.key").write_bytes(key_pem)
    return tmp_path / f"{stem}.pem"


@pytest.fixture(autouse=True)
def _redirect_move_dirs(tmp_path, monkeypatch):
    """Keep test artifacts out of the real data/certs_incoming/ directory."""
    monkeypatch.setattr(watcher, "PROCESSED_DIR", tmp_path / "_processed")
    monkeypatch.setattr(watcher, "FAILED_DIR", tmp_path / "_failed")
    monkeypatch.setattr(watcher, "REJECTED_DIR", tmp_path / "_rejected")


def test_successful_renewal_updates_record_and_logs_event(db_session, tmp_path, monkeypatch):
    cert = _seed_certificate(db_session)
    pem_path = _write_pair(tmp_path, "F5_test-lb01", cert.domain, valid_days=200)

    fake_client = SimpleNamespace(install_certificate=lambda *a, **k: {"result": "SUCCESS"})
    monkeypatch.setattr(watcher, "get_client", lambda device_type: fake_client)

    result = watcher.process_certificate_file(pem_path, db_session)

    assert result["ok"] is True
    db_session.refresh(cert)
    assert cert.status == "active"
    assert (cert.expires_at - dt.datetime.utcnow()).days >= 198

    events = db_session.query(RenewalEvent).filter_by(certificate_id=cert.id).all()
    event_types = {e.event_type for e in events}
    assert {"renewal_started", "renewal_success"} <= event_types
    assert (tmp_path / "_processed" / "F5_test-lb01.pem").exists()


def test_failed_device_install_keeps_old_expiry_and_logs_failure(db_session, tmp_path, monkeypatch):
    cert = _seed_certificate(db_session)
    original_expiry = cert.expires_at
    pem_path = _write_pair(tmp_path, "F5_test-lb01", cert.domain, valid_days=200)

    def _raise(*args, **kwargs):
        raise DeviceApiError("設備拒絕：憑證鏈驗證失敗")

    fake_client = SimpleNamespace(install_certificate=_raise)
    monkeypatch.setattr(watcher, "get_client", lambda device_type: fake_client)

    result = watcher.process_certificate_file(pem_path, db_session)

    assert result["ok"] is False
    db_session.refresh(cert)
    assert cert.expires_at == original_expiry  # unchanged — failed renewal must not silently update expiry
    events = db_session.query(RenewalEvent).filter_by(certificate_id=cert.id).all()
    assert any(e.event_type == "renewal_failed" for e in events)
    assert (tmp_path / "_failed" / "F5_test-lb01.pem").exists()


def test_domain_mismatch_is_rejected_without_calling_device(db_session, tmp_path, monkeypatch):
    cert = _seed_certificate(db_session, domain="*.example.com")
    pem_path = _write_pair(tmp_path, "F5_test-lb01", "*.wrong-domain.com", valid_days=200)

    called = []
    monkeypatch.setattr(watcher, "get_client", lambda device_type: called.append(1))

    result = watcher.process_certificate_file(pem_path, db_session)

    assert result["ok"] is False
    assert called == []  # device API must never be called for a mismatched domain
    assert (tmp_path / "_rejected" / "F5_test-lb01.pem").exists()
