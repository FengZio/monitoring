"""异步通知服务 --- 邮件 + 钉钉 Webhook"""
import asyncio
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from typing import Optional

from database import SessionLocal, Config

logger = logging.getLogger(__name__)


async def send_alert_notification(alert_info: dict) -> None:
    """Send email and/or DingTalk notification for an alert event."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_email, alert_info)
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")

    try:
        await _send_dingtalk(alert_info)
    except Exception as e:
        logger.warning(f"DingTalk notification failed: {e}")


def _send_email(alert_info: dict) -> None:
    """Send email notification (sync, runs in executor)."""
    db = SessionLocal()
    try:
        cfg = db.query(Config).filter(Config.id == 1).first()
        if not cfg or not cfg.email_enabled:
            return

        subject = f"[监控告警] {alert_info['class_name']} 闯入电子围栏"
        body = (
            f"<h3>电子围栏告警</h3>"
            f"<p>目标类型: {alert_info['class_name']}</p>"
            f"<p>置信度: {alert_info.get('confidence', 0):.1%}</p>"
            f"<p>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        )

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = cfg.email_user
        msg["To"] = cfg.email_to
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP_SSL(cfg.email_smtp_server, cfg.email_smtp_port) as server:
            server.login(cfg.email_user, cfg.email_password)
            server.sendmail(cfg.email_user, cfg.email_to.split(","), msg.as_string())
        logger.info(f"Email sent to {cfg.email_to}")
    finally:
        db.close()


async def _upload_dingtalk_media(client: httpx.AsyncClient, webhook_url: str, file_path: str) -> str | None:
    """Upload an image to DingTalk robot media API, return media_id or None."""
    try:
        parsed = urlparse(webhook_url)
        params = parse_qs(parsed.query)
        access_token = params.get("access_token", [None])[0]
        if not access_token:
            logger.error("DingTalk: cannot extract access_token from webhook URL")
            return None

        upload_url = "https://oapi.dingtalk.com/robot/messageFile/upload?access_token={}".format(access_token)
        file_name = Path(file_path).name

        with open(file_path, "rb") as f:
            files = {"file": (file_name, f, "image/jpeg")}
            resp = await client.post(upload_url, files=files)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("errcode") == 0:
                media_id = data.get("media_id", "")
                logger.info("DingTalk media uploaded: {}".format(media_id))
                return media_id
            else:
                logger.error("DingTalk upload error: {}".format(data))
                return None
        else:
            logger.error("DingTalk upload HTTP {}: {}".format(resp.status_code, resp.text))
            return None
    except Exception as e:
        logger.error("DingTalk upload failed: {}".format(e))
        return None




async def _upload_dingtalk_media(client: httpx.AsyncClient, webhook_url: str, file_path: str) -> Optional[str]:
    """Upload an image to DingTalk robot media API, return media_id or None."""
    try:
        parsed = urlparse(webhook_url)
        params = parse_qs(parsed.query)
        access_token = params.get("access_token", [None])[0]
        if not access_token:
            logger.error("DingTalk: cannot extract access_token from webhook URL")
            return None

        upload_url = "https://oapi.dingtalk.com/robot/messageFile/upload?access_token={}".format(access_token)
        file_name = Path(file_path).name

        with open(file_path, "rb") as f:
            files = {"file": (file_name, f, "image/jpeg")}
            resp = await client.post(upload_url, files=files)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("errcode") == 0:
                media_id = data.get("media_id", "")
                logger.info("DingTalk media uploaded: {}".format(media_id))
                return media_id
            else:
                logger.error("DingTalk upload error: {}".format(data))
                return None
        else:
            logger.error("DingTalk upload HTTP {}: {}".format(resp.status_code, resp.text))
            return None
    except Exception as e:
        logger.error("DingTalk upload failed: {}".format(e))
        return None

async def _send_dingtalk(alert_info: dict) -> None:
    """Send DingTalk bot message with rich tracking info and snapshot image."""
    db = SessionLocal()
    try:
        cfg = db.query(Config).filter(Config.id == 1).first()
        if not cfg or not cfg.dingtalk_enabled or not cfg.dingtalk_webhook:
            return

        class_name = alert_info.get("class_name", "unknown")
        confidence = alert_info.get("confidence", 0)
        track_id = alert_info.get("track_id", "?")
        alert_count = alert_info.get("alert_count", 1)
        is_repeat = alert_info.get("is_repeat", False)
        repeat_interval = alert_info.get("repeat_interval", 0)
        snapshot_path = alert_info.get("snapshot_path", "")

        if alert_count >= 5:
            pattern = "[高频] 闯入警告 (第{}次)".format(alert_count)
        elif is_repeat and repeat_interval < 60:
            pattern = "[短时多次] 进入 (第{}次, {:.0f}s内)".format(alert_count, repeat_interval)
        elif is_repeat:
            pattern = "[重复] 进入 (第{}次)".format(alert_count)
        else:
            pattern = "[首次] 进入"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            "## 电子围栏告警\n"
            "- 目标类型: **{}**  (ID: #{})\n"
            "- 置信度: {:.1%}\n"
            "- 模式: {}\n"
            "- 时间: {}\n"
        ).format(class_name, track_id, confidence, pattern, now_str)

        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            # Upload snapshot image to DingTalk if available
            if snapshot_path and os.path.isfile(snapshot_path):
                media_id = await _upload_dingtalk_media(client, cfg.dingtalk_webhook, snapshot_path)
                if media_id:
                    text += "\n![snapshot]({})\n".format(media_id)

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "电子围栏告警",
                    "text": text,
                },
            }
            resp = await client.post(cfg.dingtalk_webhook, json=payload)
            if resp.status_code == 200:
                logger.info("DingTalk sent OK")
            else:
                logger.error("DingTalk HTTP {}: {}".format(resp.status_code, resp.text))
    except Exception as e:
        logger.error("DingTalk failed: {}".format(e), exc_info=True)
    finally:
        db.close()
