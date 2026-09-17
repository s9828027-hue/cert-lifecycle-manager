"""
Shared plumbing for the two mock device services.

These services exist purely so the demo can run end-to-end without a real
F5 or ISE appliance. They deliberately mimic realistic quirks of the real
management APIs (token auth header, non-200 on failure, a JSON error body)
so that app/devices/*_client.py is exercising the same error-handling paths
it would against production hardware.

Trick for demos: install a certificate whose domain contains "fail-demo"
(e.g. "*.fail-demo.example.com") to make the mock return a failure, which is
useful for showing the rollback / failure-notification path live.
"""
import datetime as dt
from typing import Optional

from fastapi import Header, HTTPException

# in-memory "what's currently installed on this device" — resets on restart,
# which is fine for a demo; a real device obviously persists this itself.
installed_certs: list[dict] = []


def record_install(device_name: str, domain: str) -> dict:
    record = {
        "deviceName": device_name,
        "domain": domain,
        "installedAt": dt.datetime.utcnow().isoformat() + "Z",
    }
    installed_certs.append(record)
    return record


def check_should_simulate_failure(domain: str) -> Optional[str]:
    if "fail-demo" in domain:
        return f"模擬失敗情境：網域 {domain} 觸發設備端拒絕（憑證鏈驗證失敗）"
    return None


def require_bearer_or_token(authorization: str | None = Header(default=None),
                             x_f5_auth_token: str | None = Header(default=None)):
    if not authorization and not x_f5_auth_token:
        raise HTTPException(status_code=401, detail="缺少認證憑據 (Authorization / X-F5-Auth-Token)")
    return True
