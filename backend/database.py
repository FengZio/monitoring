"""SQLite database models"""
import datetime
import json

from sqlalchemy import Column, text, Integer, String, Float, Boolean, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import DB_PATH

Base = declarative_base()


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_name = Column(String(32), nullable=False)
    confidence = Column(Float)
    bbox = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    video_source = Column(String(256))
    snapshot_path = Column(String(512))
    clip_path = Column(String(512), nullable=True)
    handled = Column(Boolean, default=False)
    status = Column(String(16), default="pending")     # pending/processing/dismissed/resolved
    handler = Column(String(64), nullable=True)
    opinion = Column(Text, nullable=True)
    handled_at = Column(DateTime, nullable=True)
    vllm_analysis = Column(Text, nullable=True)
    vllm_risk_level = Column(String(16), nullable=True)
    vllm_is_destructive = Column(Boolean, nullable=True)


class Fence(Base):
    __tablename__ = "fence"
    id = Column(Integer, primary_key=True)
    source_id = Column(String(32), default="default")   # per-source fence support
    points = Column(Text, nullable=False)
    world_points = Column(Text, default="[]")
    mode = Column(String(16), default="restricted")
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    email_enabled = Column(Boolean, default=False)
    email_smtp_server = Column(String(128))
    email_smtp_port = Column(Integer, default=465)
    email_user = Column(String(128))
    email_password = Column(String(128))
    email_to = Column(String(256))
    dingtalk_enabled = Column(Boolean, default=False)
    dingtalk_webhook = Column(String(512))
    alert_classes = Column(Text, default='["person","bicycle","car","motorcycle","bus","truck"]')
    picgo_key = Column(String(256), default="")
    vllm_enabled = Column(Boolean, default=False)
    vllm_base_url = Column(String(512), default="")
    vllm_model = Column(String(128), default="GLM-4V-Flash")
    vllm_api_key = Column(String(512), default="")
    vllm_timeout_seconds = Column(Integer, default=30)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)
    # Add alert_classes column if missing (migration for existing DB)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE config ADD COLUMN alert_classes TEXT DEFAULT '[\"person\",\"bicycle\",\"car\",\"motorcycle\",\"bus\",\"truck\"]'"))
        except Exception:
            pass  # column already exists
        try:
            conn.execute(text("ALTER TABLE config ADD COLUMN picgo_key VARCHAR(256) DEFAULT ''"))
        except Exception:
            pass
        for column, definition in [
            ("vllm_analysis", "TEXT"), ("vllm_risk_level", "VARCHAR(16)"),
            ("vllm_is_destructive", "BOOLEAN"), ("vllm_enabled", "BOOLEAN DEFAULT 0"),
            ("vllm_base_url", "VARCHAR(512) DEFAULT ''"), ("vllm_model", "VARCHAR(128) DEFAULT 'GLM-4V-Flash'"),
            ("vllm_api_key", "VARCHAR(512) DEFAULT ''"), ("vllm_timeout_seconds", "INTEGER DEFAULT 30"),
        ]:
            try:
                table = "alerts" if column.startswith("vllm_") and column not in {
                    "vllm_enabled", "vllm_base_url", "vllm_model", "vllm_api_key", "vllm_timeout_seconds"
                } else "config"
                conn.execute(text("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, definition)))
            except Exception:
                pass
        conn.commit()
    with SessionLocal() as session:
        if not session.query(Fence).filter(Fence.source_id == "default").first():
            session.add(Fence(id=1, source_id="default", points=json.dumps([]), world_points=json.dumps([])))
        if not session.query(Config).first():
            session.add(Config(id=1))
        session.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
