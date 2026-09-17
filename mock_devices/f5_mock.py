"""
Mock F5 BIG-IP management API — stands in for the real iControl REST
endpoint at /mgmt/tm/sys/crypto/cert-key-install. Run standalone with:

    uvicorn mock_devices.f5_mock:app --port 9001
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from mock_devices.common import check_should_simulate_failure, installed_certs, record_install

app = FastAPI(title="Mock F5 BIG-IP Management API")


class InstallRequest(BaseModel):
    deviceName: str
    domain: str
    certPem: str
    keyPem: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-f5"}


@app.get("/installed")
def list_installed():
    return installed_certs


@app.post("/mgmt/tm/sys/crypto/cert-key-install")
def install_cert(req: InstallRequest, x_f5_auth_token: str | None = Header(default=None)):
    if not x_f5_auth_token:
        raise HTTPException(status_code=401, detail="缺少 X-F5-Auth-Token")

    failure_reason = check_should_simulate_failure(req.domain)
    if failure_reason:
        raise HTTPException(status_code=500, detail=failure_reason)

    record = record_install(req.deviceName, req.domain)
    return {
        "result": "SUCCESS",
        "profile": f"{req.deviceName}-clientssl-profile",
        "installedAt": record["installedAt"],
    }
