from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


job_status_enum = (
    "pending",
    "running",
    "success",
    "failed",
    "canceled",
)

job_step_status_enum = (
    "pending",
    "running",
    "success",
    "failed",
    "skipped",
)

account_status_enum = (
    "active",
    "disabled",
    "online",
    "offline",
    "error",
)

log_level_enum = ("debug", "info", "warn", "error")


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    login: Mapped[Optional[str]] = mapped_column(String(255))
    password_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    twofa_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    api_id: Mapped[int] = mapped_column(Integer, nullable=False)
    api_hash_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    session_blob: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    last_success_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_session_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="account")
    action_logs: Mapped[list["ActionLog"]] = relationship("ActionLog", back_populates="account")
    error_logs: Mapped[list["ErrorLog"]] = relationship("ErrorLog", back_populates="account")
    rulesets: Mapped[list["BotRuleset"]] = relationship("BotRuleset", back_populates="account")


class ActionCatalog(Base):
    __tablename__ = "actions_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    input_schema: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class BotRuleset(Base):
    __tablename__ = "bot_rulesets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegram_accounts.id", onupdate="CASCADE", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(255))
    rule_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    allow_parallel_for_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    account: Mapped[Optional[TelegramAccount]] = relationship("TelegramAccount", back_populates="rulesets")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="ruleset")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_worker", "worker_id"),
        Index("ix_jobs_heartbeat", "heartbeat_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ruleset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bot_rulesets.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("telegram_accounts.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    action_code: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    context_in: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    context_out: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    current_step: Mapped[Optional[int]] = mapped_column(Integer)
    worker_id: Mapped[Optional[str]] = mapped_column(String(64))
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    account: Mapped[TelegramAccount] = relationship("TelegramAccount", back_populates="jobs")
    ruleset: Mapped[Optional[BotRuleset]] = relationship("BotRuleset", back_populates="jobs")
    steps: Mapped[list["JobStep"]] = relationship("JobStep", back_populates="job", cascade="all, delete-orphan")
    action_logs: Mapped[list["ActionLog"]] = relationship("ActionLog", back_populates="job")
    error_logs: Mapped[list["ErrorLog"]] = relationship("ErrorLog", back_populates="job")


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "step_order", name="uq_job_step_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    action_code: Mapped[str] = mapped_column(String(64), nullable=False)
    input: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    job: Mapped[Job] = relationship("Job", back_populates="steps")
    action_logs: Mapped[list["ActionLog"]] = relationship("ActionLog", back_populates="step")
    error_logs: Mapped[list["ErrorLog"]] = relationship("ErrorLog", back_populates="step")


class ActionLog(Base):
    __tablename__ = "action_logs"
    __table_args__ = (
        Index("ix_action_logs_account", "account_id"),
        Index("ix_action_logs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id", onupdate="CASCADE", ondelete="RESTRICT"))
    step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_steps.id", onupdate="CASCADE", ondelete="SET NULL"))
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegram_accounts.id", onupdate="CASCADE", ondelete="SET NULL"))
    action_code: Mapped[Optional[str]] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    job: Mapped[Optional[Job]] = relationship("Job", back_populates="action_logs")
    step: Mapped[Optional[JobStep]] = relationship("JobStep", back_populates="action_logs")
    account: Mapped[Optional[TelegramAccount]] = relationship("TelegramAccount", back_populates="action_logs")


class ErrorLog(Base):
    __tablename__ = "error_logs"
    __table_args__ = (
        Index("ix_error_logs_account", "account_id"),
        Index("ix_error_logs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id", onupdate="CASCADE", ondelete="SET NULL"))
    step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_steps.id", onupdate="CASCADE", ondelete="SET NULL"))
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegram_accounts.id", onupdate="CASCADE", ondelete="SET NULL"))
    error_code: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack: Mapped[Optional[str]] = mapped_column(Text)
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    job: Mapped[Optional[Job]] = relationship("Job", back_populates="error_logs")
    step: Mapped[Optional[JobStep]] = relationship("JobStep", back_populates="error_logs")
    account: Mapped[Optional[TelegramAccount]] = relationship("TelegramAccount", back_populates="error_logs")


# Ensure enums via CHECK constraints
TelegramAccount.__table__.append_constraint(
    CheckConstraint(TelegramAccount.status.in_(account_status_enum), name="ck_account_status")
)
Job.__table__.append_constraint(CheckConstraint(Job.status.in_(job_status_enum), name="ck_job_status"))
JobStep.__table__.append_constraint(CheckConstraint(JobStep.status.in_(job_step_status_enum), name="ck_job_step_status"))
ActionLog.__table__.append_constraint(CheckConstraint(ActionLog.level.in_(log_level_enum), name="ck_action_log_level"))
