"""
Centralised configuration, loaded from environment variables / .env.

Keeping every tunable in one place (instead of scattered os.environ calls)
is a small thing, but it is what lets the same codebase run three ways
without touching source: docker-compose demo, local `uvicorn` dev server,
and (with different env values) a real deployment pointed at real
F5 / ISE management APIs instead of the mocks.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- storage ---
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'certs.db'}"
    incoming_dir: Path = BASE_DIR / "data" / "certs_incoming"

    # --- certificate policy ---
    expiry_warning_days: int = 7          # 到期前幾天發出預警通知
    scan_interval_seconds: int = 3600     # 到期掃描排程間隔（demo 可調短，如 60）

    # --- chat notifications ---
    chat_provider: str = "console"        # slack | discord | console
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # --- mock device endpoints (swap for real F5/ISE mgmt URLs in production) ---
    f5_api_base_url: str = "http://localhost:9001"
    ise_api_base_url: str = "http://localhost:9002"
    f5_api_token: str = "demo-f5-token"
    ise_api_token: str = "demo-ise-token"

    # --- app ---
    app_name: str = "憑證自動化監控與更換管理平台"
    timezone: str = "Asia/Taipei"


settings = Settings()
settings.incoming_dir.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
