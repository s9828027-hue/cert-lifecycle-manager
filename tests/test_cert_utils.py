import datetime as dt

from app.cert_utils import generate_self_signed_wildcard, parse_certificate


def test_generate_and_parse_round_trip():
    cert_pem, key_pem = generate_self_signed_wildcard("*.example.com", valid_days=30)

    assert b"BEGIN CERTIFICATE" in cert_pem
    assert b"BEGIN RSA PRIVATE KEY" in key_pem

    parsed = parse_certificate(cert_pem)
    assert parsed.domain == "*.example.com"
    assert parsed.serial_number  # non-empty hex string

    days_left = (parsed.expires_at.date() - dt.datetime.utcnow().date()).days
    assert 28 <= days_left <= 30  # allow for slight clock skew during the test run
