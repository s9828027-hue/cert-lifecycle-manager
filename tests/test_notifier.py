import datetime as dt
from types import SimpleNamespace

from app import notifier


def _fake_cert(**overrides):
    base = dict(
        device_type="F5",
        device_name="f5-dc1-prod-lb01",
        domain="*.example.com",
        cert_type="wildcard",
        expires_at=dt.datetime.utcnow() + dt.timedelta(days=5),
        days_left=5,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_format_expiry_warning_contains_key_fields():
    cert = _fake_cert()
    text = notifier.format_expiry_warning(cert)
    assert "F5" in text
    assert "*.example.com" in text
    assert "剩餘 5 天" in text


def test_format_renewal_result_success_and_failure():
    cert = _fake_cert()
    success_text = notifier.format_renewal_result(cert, success=True, detail="ok")
    failure_text = notifier.format_renewal_result(cert, success=False, detail="設備拒絕連線")

    assert "更換完成" in success_text
    assert "更換失敗" in failure_text
    assert "設備拒絕連線" in failure_text


def test_send_chat_message_falls_back_to_console_without_webhook(monkeypatch):
    monkeypatch.setattr(notifier.settings, "chat_provider", "console")
    assert notifier.send_chat_message("hello") is True
