from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.app_name, "warning_days": settings.expiry_warning_days},
    )
