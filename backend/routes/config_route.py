"""通知配置路由"""
import json
from fastapi import APIRouter
from pydantic import BaseModel

from database import SessionLocal, Config

router = APIRouter(prefix="/api/config", tags=["config"])

DEFAULT_CLASSES = ["person", "bicycle", "car", "motorcycle", "bus", "truck"]


class ConfigPayload(BaseModel):
    email_enabled: bool = False
    email_smtp_server: str = ""
    email_smtp_port: int = 465
    email_user: str = ""
    email_password: str = ""
    email_to: str = ""
    dingtalk_enabled: bool = False
    dingtalk_webhook: str = ""
    alert_classes: list[str] = []


@router.get("")
def get_config():
    db = SessionLocal()
    try:
        cfg = db.query(Config).filter(Config.id == 1).first()
        classes = DEFAULT_CLASSES
        if cfg and cfg.alert_classes:
            try:
                classes = json.loads(cfg.alert_classes)
            except (json.JSONDecodeError, TypeError):
                pass
        if not cfg:
            return {**ConfigPayload().model_dump(), "alert_classes": classes}
        return {
            "email_enabled": cfg.email_enabled,
            "email_smtp_server": cfg.email_smtp_server or "",
            "email_smtp_port": cfg.email_smtp_port or 465,
            "email_user": cfg.email_user or "",
            "email_password": cfg.email_password or "",
            "email_to": cfg.email_to or "",
            "dingtalk_enabled": cfg.dingtalk_enabled,
            "dingtalk_webhook": cfg.dingtalk_webhook or "",
            "alert_classes": classes,
        }
    finally:
        db.close()


@router.post("")
def save_config(payload: ConfigPayload):
    db = SessionLocal()
    try:
        cfg = db.query(Config).filter(Config.id == 1).first()
        if not cfg:
            cfg = Config(id=1)
            db.add(cfg)
        cfg.email_enabled = payload.email_enabled
        cfg.email_smtp_server = payload.email_smtp_server
        cfg.email_smtp_port = payload.email_smtp_port
        cfg.email_user = payload.email_user
        cfg.email_password = payload.email_password
        cfg.email_to = payload.email_to
        cfg.dingtalk_enabled = payload.dingtalk_enabled
        cfg.dingtalk_webhook = payload.dingtalk_webhook
        if payload.alert_classes:
            cfg.alert_classes = json.dumps(payload.alert_classes, ensure_ascii=False)
        db.commit()
        return {"status": "saved"}
    finally:
        db.close()