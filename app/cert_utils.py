"""
Certificate helpers built on `cryptography`.

generate_self_signed_wildcard() creates realistic-looking wildcard certs for
the demo (self-signed, but structurally identical to a real one: CN + SAN,
notBefore/notAfter, serial number). parse_certificate() reads one back — this
is what app/watcher.py calls on every file dropped into data/certs_incoming/,
so a malformed or mismatched file is rejected before any device API is ever
called (see the 憑證誤置或格式錯誤 risk item in the project's risk register).
"""
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@dataclass
class ParsedCertificate:
    domain: str
    serial_number: str
    issued_at: dt.datetime
    expires_at: dt.datetime


def generate_self_signed_wildcard(domain: str, valid_days: int = 365) -> tuple[bytes, bytes]:
    """Return (cert_pem, key_pem) for a self-signed wildcard cert, e.g. domain='*.example.com'."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TW"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Demo Corp"),
        x509.NameAttribute(NameOID.COMMON_NAME, domain),
    ])

    now = dt.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=valid_days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(domain), x509.DNSName(domain.lstrip("*."))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def parse_certificate(cert_bytes: bytes) -> ParsedCertificate:
    cert = x509.load_pem_x509_certificate(cert_bytes)
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    domain = cn[0].value if cn else "unknown"
    return ParsedCertificate(
        domain=domain,
        serial_number=format(cert.serial_number, "x"),
        issued_at=cert.not_valid_before_utc.replace(tzinfo=None),
        expires_at=cert.not_valid_after_utc.replace(tzinfo=None),
    )


def write_pem_pair(directory: Path, filename_stem: str, cert_pem: bytes, key_pem: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    cert_path = directory / f"{filename_stem}.pem"
    key_path = directory / f"{filename_stem}.key"
    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)
    return cert_path
