"""
Thin client for Cisco ISE's certificate-install API.

Talks to mock_devices/ise_mock.py, which mimics the shape of ISE's ERS API
(`/ers/config/trustedcertificate`, basic/token auth, JSON body). Swapping to
a real ISE PSN/PAN means changing ISE_API_BASE_URL / ISE_API_TOKEN in .env —
see app/devices/f5_client.py for the equivalent F5 note.
"""
import httpx

from app.config import settings
from app.devices.base import DeviceApiError

INSTALL_PATH = "/ers/config/trustedcertificate"


def install_certificate(device_name: str, domain: str, cert_pem: str, key_pem: str) -> dict:
    url = f"{settings.ise_api_base_url}{INSTALL_PATH}"
    headers = {"Authorization": f"Bearer {settings.ise_api_token}"}
    payload = {"deviceName": device_name, "domain": domain, "certPem": cert_pem, "keyPem": key_pem}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
    except httpx.HTTPError as exc:
        raise DeviceApiError(f"無法連線至 ISE 管理 API（{url}）：{exc}") from exc

    if resp.status_code != 200:
        raise DeviceApiError(f"ISE 憑證安裝失敗（HTTP {resp.status_code}）：{resp.text}")

    data = resp.json()
    if data.get("result") != "SUCCESS":
        raise DeviceApiError(f"ISE 回應非成功狀態：{data}")
    return data
