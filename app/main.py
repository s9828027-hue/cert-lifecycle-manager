import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import api as api_router
from app.routers import dashboard as dashboard_router
from app.scheduler import setup_scheduler
from app.watcher import start_watcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.scheduler = setup_scheduler()
    app.state.watcher_observer = start_watcher()
    yield
    app.state.scheduler.shutdown(wait=False)
    app.state.watcher_observer.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
app.include_router(api_router.router)
app.include_router(dashboard_router.router)
