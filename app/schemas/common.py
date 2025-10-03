from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class AccountSummary(APIModel):
    id: int
    label: str
    phone: Optional[str]
    login: Optional[str]
    is_active: bool
    status: str
    last_success_login_at: Optional[str]
    last_session_updated_at: Optional[str]
    last_error_at: Optional[str]
    last_error_message: Optional[str]
    meta: Optional[Dict[str, Any]]
    last_job: Optional[int]
    last_action_at: Optional[str]
    pending_jobs: int


class AccountDetails(AccountSummary):
    actions: list[Dict[str, Any]]
    errors: list[Dict[str, Any]]


class JobResponse(APIModel):
    job_id: int


class JobStatus(APIModel):
    id: int
    status: str
    account_id: int
    ruleset_id: Optional[int]
    action_code: Optional[str]
    worker_id: Optional[str]
    current_step: Optional[int]
    context_in: Dict[str, Any]
    context_out: Optional[Dict[str, Any]]
    started_at: Optional[str]
    finished_at: Optional[str]


class JobStepModel(APIModel):
    id: int
    job_id: int
    step_order: int
    action_code: str
    status: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    retry_count: int
    started_at: Optional[str]
    finished_at: Optional[str]


class RulesetResponse(APIModel):
    id: int
    name: str
    account_id: Optional[int]
    allow_parallel_for_account: bool
    schedule_cron: Optional[str]
    is_enabled: bool
    rule_json: Dict[str, Any]
