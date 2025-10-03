from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.core.security import EncryptionService
from app.models.models import ActionLog, BotRuleset, Job, JobStep, TelegramAccount
from app.schemas.common import JobResponse, JobStatus, JobStepModel
from app.workers.exceptions import ActionError
from app.workers.job_executor import JobExecutor


class JobService:
    def __init__(self, session: Session, encryptor: EncryptionService):
        self.session = session
        self.encryptor = encryptor

    def enqueue_action(self, account_id: int, action_code: str, payload: Dict[str, Any]) -> JobResponse:
        account = self._require_account(account_id)
        job = Job(
            account_id=account.id,
            action_code=action_code,
            status="pending",
            trigger_type="api",
            context_in=payload,
        )
        self.session.add(job)
        self.session.flush()

        step = JobStep(
            job_id=job.id,
            step_order=0,
            action_code=action_code,
            input={**payload, "accountId": account_id},
            status="pending",
        )
        self.session.add(step)
        self.session.flush()
        self.session.add(
            ActionLog(
                job_id=job.id,
                step_id=step.id,
                account_id=account.id,
                action_code=action_code,
                message=f"Enqueued action {action_code}",
                level="info",
                payload=payload,
            )
        )
        self.session.flush()
        return JobResponse(job_id=job.id)

    def enqueue_ruleset(self, ruleset: BotRuleset, account_id: int, context: Dict[str, Any]) -> JobResponse:
        if not ruleset.is_enabled:
            raise ServiceError(code="RULESET_DISABLED", message="Ruleset is disabled")
        self._require_account(account_id)
        job = Job(
            ruleset_id=ruleset.id,
            account_id=account_id,
            status="pending",
            trigger_type="api",
            context_in=context,
        )
        self.session.add(job)
        self.session.flush()
        self.session.add(
            ActionLog(
                job_id=job.id,
                account_id=account_id,
                action_code="RULESET",
                message=f"Enqueued ruleset {ruleset.id}",
                level="info",
                payload={"context": context},
            )
        )
        self.session.flush()
        return JobResponse(job_id=job.id)

    def get_job_status(self, job_id: int) -> JobStatus:
        job = self.session.get(Job, job_id)
        if not job:
            raise ServiceError(code="JOB_NOT_FOUND", message="Job not found", http_status=404)
        return JobStatus(
            id=job.id,
            status=job.status,
            account_id=job.account_id,
            ruleset_id=job.ruleset_id,
            action_code=job.action_code,
            worker_id=job.worker_id,
            current_step=job.current_step,
            context_in=job.context_in or {},
            context_out=job.context_out,
            started_at=job.started_at.isoformat() if job.started_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
        )

    def get_job_steps(self, job_id: int) -> List[JobStepModel]:
        job = self.session.get(Job, job_id)
        if not job:
            raise ServiceError(code="JOB_NOT_FOUND", message="Job not found", http_status=404)
        steps = self.session.scalars(select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.step_order)).all()
        return [
            JobStepModel(
                id=step.id,
                job_id=step.job_id,
                step_order=step.step_order,
                action_code=step.action_code,
                status=step.status,
                input=step.input or {},
                output=step.output,
                retry_count=step.retry_count,
                started_at=step.started_at.isoformat() if step.started_at else None,
                finished_at=step.finished_at.isoformat() if step.finished_at else None,
            )
            for step in steps
        ]

    def execute_job(self, job_id: int) -> JobStatus:
        executor = JobExecutor(self.session, self.encryptor)
        try:
            job = executor.execute_job(job_id)
        except ActionError as exc:
            raise ServiceError(code=exc.code, message=exc.message)
        return self.get_job_status(job.id)

    def _require_account(self, account_id: int) -> TelegramAccount:
        account = self.session.get(TelegramAccount, account_id)
        if not account:
            raise ServiceError(code="ACCOUNT_NOT_FOUND", message="Account not found", http_status=404)
        if not account.is_active:
            raise ServiceError(code="ACCOUNT_INACTIVE", message="Account is inactive")
        return account
