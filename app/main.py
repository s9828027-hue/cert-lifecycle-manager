import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, init_db
from app.routers import api as api_router
from app.routers import dashboard as dashboard_router
from app.scheduler import setup_scheduler
from app.seed import seed_demo_data
from app.watcher import start_watcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    if settings.auto_seed_demo_data:
        db = SessionLocal()
        try:
            result = seed_demo_data(db)
            if result["seeded"]:
                logger.info("已自動建立示範資料（%d 筆）", result["count"])
        finally:
            db.close()

    app.state.scheduler = setup_scheduler()
    app.state.watcher_observer = start_watcher()
    yield
    app.state.scheduler.shutdown(wait=False)
    app.state.watcher_observer.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
app.include_router(api_router.router)
app.include_router(dashboard_router.router)

if settings.single_service_mode:
    # Co-host the two mock device APIs in this same process/port so a single
    # free-tier web service (Render, Railway, ...) is enough to run the whole
    # demo — see app/config.py's single_service_mode for the base-URL wiring.
    from mock_devices.f5_mock import app as f5_mock_app
    from mock_devices.ise_mock import app as ise_mock_app

    app.mount("/mock-f5", f5_mock_app)
    app.mount("/mock-ise", ise_mock_app)
    logger.info("單服務模式：已將 F5/ISE mock API 掛載於 /mock-f5、/mock-ise")
