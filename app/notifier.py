"""
Chat notification layer.

Supports Slack and Discord incoming webhooks. If neither is configured the
message is still produced and logged to the console — this is what keeps the
demo runnable out of the box before anyone has pasted in a webhook URL, and
is also useful as a local-dev fallback.

This module intentionally knows nothing about certificates; it just sends
text. app/scheduler.py and app/watcher.py build the messages.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("notifier")


def _send_slack(text: str) -> None:
    httpx.post(settings.slack_webhook_url, json={"text": text}, timeout=10)


def _send_discord(text: str) -> None:
    httpx.post(settings.discord_webhook_url, json={"content": text}, timeout=10)


def send_chat_message(text: str) -> bool:
    """Send `text` to whichever chat provider is configured. Returns True on success."""
    provider = settings.chat_provider.lower()
    try:
        if provider == "slack" and settings.slack_webhook_url:
            _send_slack(text)
        elif provider == "discord" and settings.discord_webhook_url:
            _send_discord(text)
        else:
            logger.info("[CHAT:console] %s", text)
            return True
        logger.info("[CHAT:%s] sent", provider)
        return True
    except httpx.HTTPError as exc:
        logger.error("Chat notification failed (%s): %s", provider, exc)
        logger.info("[CHAT:fallback-console] %s", text)
        return False


def format_expiry_warning(cert) -> str:
    return (
        f"⚠️ *憑證到期預警*\n"
        f"設備：{cert.device_type} / {cert.device_name}\n"
        f"網域：{cert.domain}（{cert.cert_type}）\n"
        f"到期日：{cert.expires_at:%Y-%m-%d}（剩餘 {cert.days_left} 天）\n"
        f"請於到期前將新憑證放置於指定資料夾，系統將自動偵測並完成更換。"
    )


def format_renewal_result(cert, success: bool, detail: str) -> str:
    icon = "✅" if success else "❌"
    title = "憑證更換完成" if success else "憑證更換失敗"
    return (
        f"{icon} *{title}*\n"
        f"設備：{cert.device_type} / {cert.device_name}\n"
        f"網域：{cert.domain}（{cert.cert_type}）\n"
        f"新到期日：{cert.expires_at:%Y-%m-%d}\n"
        f"詳情：{detail}"
    )
