from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import EncryptionService
from app.models.models import ActionLog, ErrorLog, Job, JobStep, TelegramAccount
from app.utils.context import merge_context, resolve_placeholders
from app.workers.exceptions import ActionError
from app.workers.telegram_actions import ActionOutcome, TelegramActionExecutor


class JobExecutor:
    def __init__(self, session: Session, encryptor: EncryptionService):
        self.session = session
        self.encryptor = encryptor
        self.telegram_executor = TelegramActionExecutor(encryptor)
        self.worker_id = f"executor-{uuid4()}"

    def execute_job(self, job_id: int) -> Job:
        job = self._lock_job(job_id)
        if not job:
            raise ActionError("JOB_NOT_FOUND", f"Job {job_id} not found")
        if job.status not in {"pending", "failed"}:
            raise ActionError("INVALID_JOB_STATE", f"Job {job.id} is in state {job.status}")

        now = datetime.utcnow()
        job.status = "running"
        job.worker_id = self.worker_id
        job.heartbeat_at = now
        job.started_at = job.started_at or now
        job.current_step = job.current_step or 0

        plan = self._build_plan(job)
        context = dict(job.context_in or {})
        completed_outputs: Dict[str, Any] = {}
        for step in sorted(job.steps, key=lambda s: s.step_order):
            if step.status == "success":
                save_as = plan[step.step_order].get("saveAs")
                if save_as:
                    completed_outputs[save_as] = step.output

        step: Optional[JobStep] = None
        try:
            for idx in range(job.current_step, len(plan)):
                step_plan = plan[idx]
                step = self._get_or_create_step(job, idx, step_plan)
                context_for_step = merge_context(context, completed_outputs)
                try:
                    input_payload = resolve_placeholders(step_plan.get("input", {}), context_for_step)
                except KeyError as exc:
                    raise ActionError("CONTEXT_KEY_MISSING", f"Missing context value for {exc.args[0]}") from exc
                step.input = input_payload
                step.status = "running"
                step.started_at = datetime.utcnow()
                self.session.flush()

                output = self._run_step(job, step, input_payload)

                step.output = output
                step.status = "success"
                step.finished_at = datetime.utcnow()
                completed_outputs[step_plan.get("saveAs") or f"step_{idx}"] = output
                job.current_step = idx + 1
                job.heartbeat_at = datetime.utcnow()
                self.session.add(
                    ActionLog(
                        job_id=job.id,
                        step_id=step.id,
                        account_id=job.account_id,
                        action_code=step.action_code,
                        message=f"Step {idx} succeeded",
                        level="info",
                        payload={"output": output},
                    )
                )
                self.session.flush()

            result = self._compute_result(job, plan, context, completed_outputs)
            job.context_out = result
            job.status = "success"
            job.finished_at = datetime.utcnow()
            return job
        except ActionError as exc:
            self._mark_job_failed(job, step, exc)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            action_exc = ActionError("EXECUTION_ERROR", str(exc))
            self._mark_job_failed(job, step, action_exc, exc)
            raise

    def _lock_job(self, job_id: int) -> Optional[Job]:
        stmt: Select[tuple[Job]] = (
            select(Job)
            .where(Job.id == job_id)
            .options(joinedload(Job.steps), joinedload(Job.account), joinedload(Job.ruleset))
            .with_for_update(skip_locked=True)
        )
        job = self.session.execute(stmt).scalars().first()
        if job:
            return job
        exists = self.session.get(Job, job_id)
        if exists:
            raise ActionError("JOB_LOCKED", "Job is locked by another worker", retryable=True)
        return None

    def _build_plan(self, job: Job) -> List[Dict[str, Any]]:
        if job.ruleset is not None:
            data = job.ruleset.rule_json or {}
            steps = data.get("steps", [])
            plan: List[Dict[str, Any]] = []
            for index, step in enumerate(steps):
                plan.append(
                    {
                        "index": index,
                        "action": step.get("action"),
                        "input": step.get("input", {}),
                        "saveAs": step.get("saveAs"),
                    }
                )
            return plan
        # single action job
        if not job.action_code:
            raise ActionError("MISSING_ACTION", "Job has no action code")
        plan_step = {
            "index": 0,
            "action": job.action_code,
            "input": job.steps[0].input if job.steps else {},
            "saveAs": "result",
        }
        return [plan_step]

    def _get_or_create_step(self, job: Job, index: int, plan_step: Dict[str, Any]) -> JobStep:
        for step in job.steps:
            if step.step_order == index:
                return step
        step = JobStep(job_id=job.id, step_order=index, action_code=plan_step.get("action"))
        self.session.add(step)
        self.session.flush()
        job.steps.append(step)
        return step

    def _run_step(self, job: Job, step: JobStep, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        attempts = 0
        while True:
            attempts += 1
            lock_key = None
            try:
                lock_key = self._acquire_account_lock(job.account_id)
                account = self._load_account(job.account_id)
                outcome = self.telegram_executor.execute(account, step.action_code, input_payload)
                self._apply_account_updates(account, outcome)
                self.session.flush()
                return outcome.output
            except ActionError as exc:
                step.retry_count = attempts
                self._log_step_error(job, step, exc)
                if exc.retryable and attempts < 3:
                    step.status = "pending"
                    continue
                step.status = "failed"
                step.finished_at = datetime.utcnow()
                raise
            finally:
                if lock_key:
                    self._release_account_lock(lock_key)

    def _acquire_account_lock(self, account_id: int) -> str:
        lock_name = f"tg_acc_{account_id}"
        result = self.session.execute(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": lock_name, "timeout": settings.account_lock_timeout_s},
        ).scalar_one_or_none()
        if result != 1:
            raise ActionError("ACCOUNT_BUSY", "Account is busy", retryable=True)
        return lock_name

    def _release_account_lock(self, lock_name: str) -> None:
        self.session.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})

    def _load_account(self, account_id: int) -> TelegramAccount:
        account = (
            self.session.execute(
                select(TelegramAccount).where(TelegramAccount.id == account_id).with_for_update()
            )
            .scalars()
            .first()
        )
        if not account:
            raise ActionError("ACCOUNT_NOT_FOUND", f"Account {account_id} not found")
        return account

    def _apply_account_updates(self, account: TelegramAccount, outcome: ActionOutcome) -> None:
        if outcome.session_changed:
            old_version = account.session_version
            account.session_blob = outcome.session_blob
            account.session_version = old_version + 1
            account.last_session_updated_at = datetime.utcnow()
        if outcome.status:
            account.status = outcome.status
        if outcome.last_success_login_at:
            account.last_success_login_at = outcome.last_success_login_at
        account.updated_at = datetime.utcnow()

    def _compute_result(
        self,
        job: Job,
        plan: List[Dict[str, Any]],
        base_context: Dict[str, Any],
        outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        if job.ruleset is None:
            return next(iter(outputs.values()), {})
        rule_json = job.ruleset.rule_json or {}
        result_template = rule_json.get("result", {})
        context = merge_context(base_context, outputs)
        return resolve_placeholders(result_template, context)

    def _mark_job_failed(self, job: Job, step: JobStep, error: ActionError, exc: Optional[Exception] = None) -> None:
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.heartbeat_at = datetime.utcnow()
        if step:
            step.status = "failed"
            step.finished_at = datetime.utcnow()
        message = error.message
        stack = traceback.format_exc() if exc else None
        self.session.add(
            ActionLog(
                job_id=job.id,
                step_id=step.id if step else None,
                account_id=job.account_id,
                action_code=step.action_code if step else None,
                message=f"Step failed: {message}",
                level="error",
                payload={"code": error.code, "details": error.details},
            )
        )
        self.session.add(
            ErrorLog(
                job_id=job.id,
                step_id=step.id if step else None,
                account_id=job.account_id,
                error_code=error.code,
                message=message,
                stack=stack,
                context=error.details,
            )
        )
        if job.account:
            job.account.last_error_at = datetime.utcnow()
            job.account.last_error_message = message

    def _log_step_error(self, job: Job, step: JobStep, error: ActionError) -> None:
        self.session.add(
            ActionLog(
                job_id=job.id,
                step_id=step.id,
                account_id=job.account_id,
                action_code=step.action_code,
                message=f"Retry {step.retry_count} failed: {error.message}",
                level="warn" if error.retryable else "error",
                payload={"code": error.code, "details": error.details},
            )
        )
