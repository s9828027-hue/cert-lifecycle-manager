"""
Thin client for F5's certificate-install API.

Today it talks to mock_devices/f5_mock.py, which mimics the shape of a real
F5 BIG-IP iControl REST call (`/mgmt/tm/sys/crypto/cert-key-install`,
token auth header, JSON body/response). Swapping this to a real F5 means
changing F5_API_BASE_URL / F5_API_TOKEN in .env and, if the real endpoint
path differs, editing INSTALL_PATH below — the rest of the application
(scheduler, watcher, dashboard) does not need to change.
"""
import httpx

from app.config import settings
from app.devices.base import DeviceApiError

INSTALL_PATH = "/mgmt/tm/sys/crypto/cert-key-install"


def install_certificate(device_name: str, domain: str, cert_pem: str, key_pem: str) -> dict:
    url = f"{settings.f5_api_base_url}{INSTALL_PATH}"
    headers = {"X-F5-Auth-Token": settings.f5_api_token}
    payload = {"deviceName": device_name, "domain": domain, "certPem": cert_pem, "keyPem": key_pem}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
    except httpx.HTTPError as exc:
        raise DeviceApiError(f"無法連線至 F5 管理 API（{url}）：{exc}") from exc

    if resp.status_code != 200:
        raise DeviceApiError(f"F5 憑證安裝失敗（HTTP {resp.status_code}）：{resp.text}")

    data = resp.json()
    if data.get("result") != "SUCCESS":
        raise DeviceApiError(f"F5 回應非成功狀態：{data}")
    return data
