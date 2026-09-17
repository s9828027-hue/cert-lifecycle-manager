"""
Mock Cisco ISE management API — stands in for the real ERS endpoint at
/ers/config/trustedcertificate. Run standalone with:

    uvicorn mock_devices.ise_mock:app --port 9002
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from mock_devices.common import check_should_simulate_failure, installed_certs, record_install

app = FastAPI(title="Mock Cisco ISE ERS API")


class InstallRequest(BaseModel):
    deviceName: str
    domain: str
    certPem: str
    keyPem: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-ise"}


@app.get("/installed")
def list_installed():
    return installed_certs


@app.post("/ers/config/trustedcertificate")
def install_cert(req: InstallRequest, authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization Bearer token")

    failure_reason = check_should_simulate_failure(req.domain)
    if failure_reason:
        raise HTTPException(status_code=500, detail=failure_reason)

    record = record_install(req.deviceName, req.domain)
    return {
        "result": "SUCCESS",
        "trustId": f"{req.deviceName}-trust-{len(installed_certs)}",
        "installedAt": record["installedAt"],
    }
