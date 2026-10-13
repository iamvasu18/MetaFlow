"""Durable operations with structured job logging.

Redis hints never carry credentials or business context.
Interrupted jobs are reconciled without automatically repeating
AI generation or Salesforce submissions.
"""

from contextvars import ContextVar
from copy import deepcopy
import json
import logging
import os
import time
from uuid import uuid4

from fastapi import HTTPException

from Backend.AI.app.services.observability import (
    job_id_context,
    log_event,
)


logger = logging.getLogger(__name__)
executing_job = ContextVar("executing_background_job", default=False)


def enabled():
    return (
        os.getenv("APP_BACKGROUND_JOBS", "false").lower() == "true"
        and not executing_job.get()
    )


def ticket(row):
    return {
        "backgroundJob": True,
        "jobId": row["id"],
        "state": row["state"],
        "operation": row["kind"],
        "targetOrg": row["org_id"],
    }


def enqueue(kind, payload, key=None, package=None):
    """Allow parallel chats, but reject another active generation in the same chat."""
    conversation = payload.get('conversation_id') if kind == 'generate' else None
    if not conversation:
        return _enqueue(kind, payload, key=key, package=package)
    from Backend.AI.app.account_api import current_account, current_org, db
    from Backend.AI.app.services.shared_plan_lock import shared_plan_lock
    owner, org = current_account.get(), current_org.get()
    if not owner or not org:
        raise HTTPException(401, 'An authenticated org is required.')
    with shared_plan_lock('chat-generate:' + owner + ':' + org + ':' + conversation):
        with db() as connection:
            prior = connection.execute(
                'SELECT id FROM background_jobs WHERE user_id=? AND org_id=? AND request_key=?',
                (owner, org, key)).fetchone() if key else None
            if not prior:
                rows = connection.execute(
                    "SELECT payload FROM background_jobs WHERE user_id=? AND org_id=? AND kind='generate' AND state IN ('queued','running')",
                    (owner, org)).fetchall()
                if any(json.loads(row['payload']).get('conversation_id') == conversation for row in rows):
                    raise HTTPException(409, 'This chat already has an active generation. Continue in another chat or wait for this request to finish.')
        return _enqueue(kind, payload, key=key, package=package)


def _enqueue(kind, payload, key=None, package=None):
    from Backend.AI.app.account_api import current_account, current_org, db
    from Backend.AI.app.services.job_notifications import notify

    owner = current_account.get()
    org = current_org.get()

    if not owner or not org:
        raise HTTPException(401, "An authenticated org is required.")

    if kind not in {"generate", "validate", "deploy"}:
        raise ValueError("Unsupported background operation")

    key = key or uuid4().hex
    identifier = "JOB-" + uuid4().hex
    now = time.time()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    queued = None

    with db() as connection:
        owned = connection.execute(
            "SELECT id FROM orgs WHERE id=? AND user_id=?",
            (org, owner),
        ).fetchone()

        if not owned:
            raise HTTPException(403, "Org is no longer connected.")

        prior = connection.execute(
            "SELECT * FROM background_jobs "
            "WHERE user_id=? AND org_id=? AND request_key=?",
            (owner, org, key),
        ).fetchone()

        if prior:
            if prior["payload"] != encoded or prior["kind"] != kind:
                raise HTTPException(
                    409,
                    "This request key belongs to a different operation.",
                )
            return ticket(prior)

        conversation = payload.get("conversation_id")
        if conversation:
            owned_conversation = connection.execute(
                "SELECT id FROM workspace_conversations "
                "WHERE id=? AND user_id=? AND org_id=?",
                (conversation, owner, org),
            ).fetchone()

            if not owned_conversation:
                raise HTTPException(404, "Conversation not found.")

        inserted = connection.execute(
            "INSERT INTO background_jobs VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id,org_id,request_key) DO NOTHING",
            (
                identifier,
                owner,
                org,
                kind,
                "queued",
                encoded,
                None,
                now,
                now,
                key,
            ),
        ).rowcount

        if inserted != 1:
            prior = connection.execute(
                "SELECT * FROM background_jobs "
                "WHERE user_id=? AND org_id=? AND request_key=?",
                (owner, org, key),
            ).fetchone()

            if (
                not prior
                or prior["payload"] != encoded
                or prior["kind"] != kind
            ):
                raise HTTPException(
                    409,
                    "This request key belongs to a different operation.",
                )
            return ticket(prior)

        if package:
            row = connection.execute(
                "SELECT payload FROM workspace_packages "
                "WHERE id=? AND user_id=? AND org_id=?",
                (payload["plan_id"], owner, org),
            ).fetchone()

            if not row:
                raise HTTPException(404, "Saved package not found.")

            snapshot = json.loads(row["payload"])

            if snapshot["package"]["sourceHash"] != payload["source_hash"]:
                raise HTTPException(
                    409,
                    "Saved source changed before queueing.",
                )

            queued = deepcopy(package)
            queued.update(
                state="queued",
                operation=kind,
                backgroundJobId=identifier,
                queuePriorState=package["state"],
                jobId=None,
                error=None,
                nextAction=None,
                lastResult=None,
                operationSeconds=None,
                operationStartedAt=None,
            )
            snapshot["package"] = queued

            connection.execute(
                "UPDATE workspace_packages SET payload=? "
                "WHERE id=? AND user_id=? AND org_id=?",
                (
                    json.dumps(
                        snapshot,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    payload["plan_id"],
                    owner,
                    org,
                ),
            )
            connection.execute(
                "DELETE FROM monitor_jobs WHERE plan_id=?",
                (payload["plan_id"],),
            )

    if queued:
        from Backend.AI.app import main

        main.metadata_spec_store._packages[payload["plan_id"]] = queued

    log_token = job_id_context.set(identifier)
    try:
        log_event(
            logger,
            "background_job_queued",
            operation=kind,
            state="queued",
        )
    finally:
        job_id_context.reset(log_token)

    notify()

    return {
        "backgroundJob": True,
        "jobId": identifier,
        "state": "queued",
        "operation": kind,
        "targetOrg": org,
    }


def get_owned(identifier, owner):
    from Backend.AI.app.account_api import db

    with db() as connection:
        row = connection.execute(
            "SELECT j.* FROM background_jobs j "
            "JOIN orgs o ON o.id=j.org_id AND o.user_id=j.user_id "
            "WHERE j.id=? AND j.user_id=?",
            (identifier, owner),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Background job not found.")

    response = ticket(row)
    if row["result"]:
        response["result"] = json.loads(row["result"])

    return response


def finish(row, state, result):
    from Backend.AI.app.account_api import db

    with db() as connection:
        # Do not overwrite another worker's reconciliation.
        changed = connection.execute(
            "UPDATE background_jobs SET state=?,result=?,updated=? "
            "WHERE id=? AND state=?",
            (
                state,
                json.dumps(result, separators=(",", ":")),
                time.time(),
                row["id"],
                "running",
            ),
        ).rowcount

        if changed != 1:
            return

        payload = json.loads(row["payload"])
        conversation = payload.get("conversation_id")

        if conversation and row["kind"] == "generate":
            owned_conversation = connection.execute(
                "SELECT id FROM workspace_conversations "
                "WHERE id=? AND user_id=? AND org_id=?",
                (conversation, row["user_id"], row["org_id"]),
            ).fetchone()

            if owned_conversation:
                detail = result.get("detail", "")

                if state == "succeeded":
                    content = "A new implementation draft is ready for review."
                    kind = "plan"
                elif isinstance(detail, dict) and detail.get("code") in {
                    "CLARIFICATION_REQUIRED",
                    "NO_CHANGE_REQUIRED",
                }:
                    content = (
                        detail.get("question")
                        or detail.get("message")
                        or "Please clarify the requirement."
                    )
                    kind = (
                        "clarification"
                        if detail["code"] == "CLARIFICATION_REQUIRED"
                        else "no_change"
                    )
                else:
                    content = str((detail.get("message") or "Background generation failed.") if isinstance(detail, dict) else (detail or "Background generation failed."))
                    kind = "error"

                connection.execute(
                    "INSERT OR IGNORE INTO workspace_messages "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (
                        row["id"] + "-reply",
                        conversation,
                        "assistant",
                        content,
                        kind,
                        result.get("planId"),
                        payload["request"]["requirement"],
                        time.time(),
                    ),
                )
                connection.execute(
                    "UPDATE workspace_conversations SET updated=? WHERE id=?",
                    (time.time(), conversation),
                )

    # Log only after the transaction commits.
    log_event(
        logger,
        "background_job_result_saved",
        operation=row["kind"],
        state=state,
        plan_id=result.get("planId"),
    )


def reconcile(row):
    """Recover interrupted work without replaying its operation."""
    from Backend.AI.app import main

    payload = json.loads(row["payload"])

    if row["kind"] != "generate":
        plan = payload["plan_id"]

        with main.layout_workflow.try_plan_lock(plan) as acquired:
            if not acquired:
                return

            main.restore_workspace_package(
                plan,
                row["user_id"],
                row["org_id"],
            )
            package = main.metadata_spec_store.get_package(plan)

            if package and package.get("backgroundJobId") == row["id"]:
                if package.get("jobId") and package.get("state") in {
                    "pending",
                    "validated",
                    "deployed",
                    "failed",
                }:
                    finish(row, "succeeded", {"planId": plan})
                    return

                package.update(
                    state="unknown",
                    validatedHash=None,
                    error=(
                        "The submission worker stopped before confirming "
                        "its outcome. No submission was repeated."
                    ),
                    nextAction=(
                        "Inspect Salesforce Deployment Status before retrying."
                    ),
                )
                main.metadata_spec_store.save_package(package)

        finish(
            row,
            "unknown",
            {
                "planId": plan,
                "detail": (
                    "Submission outcome is unknown. Inspect the saved plan "
                    "and Salesforce Deployment Status."
                ),
            },
        )
    else:
        finish(
            row,
            "failed",
            {
                "detail": (
                    "Plan generation was interrupted. It was not automatically "
                    "repeated. Submit the requirement again when ready."
                ),
                "status": 409,
            },
        )


def execute(row):
    from Backend.AI.app import main
    from Backend.AI.app.account_api import (
        db,
        save_chat,
        record_workflow_response,
    )

    payload = json.loads(row["payload"])

    if row["kind"] == "generate":
        request = main.PlanRequest.model_validate(payload["request"])
        result = main.generate_plan(request)
        plan_id = result["id"]

        with db() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO plans VALUES(?,?,?)",
                (plan_id, row["user_id"], row["org_id"]),
            )

        save_chat(
            row["user_id"],
            row["org_id"],
            plan_id,
            result["requirement"],
        )
        record_workflow_response(
            {"id": row["user_id"]},
            row["org_id"],
            plan_id,
            "/api/plan",
            result,
            200,
        )
        return {"planId": plan_id}

    plan_id = payload["plan_id"]

    with main.layout_workflow.plan_lock(plan_id):
        from Backend.AI.app.services.shared_plan_lock import shared_plan_lock

        with shared_plan_lock(plan_id):
            main.restore_workspace_package(
                plan_id,
                row["user_id"],
                row["org_id"],
            )
            package = main.metadata_spec_store.get_package(plan_id)

            if (
                not package
                or package.get("backgroundJobId") != row["id"]
                or package.get("state") != "queued"
                or package["sourceHash"] != payload["source_hash"]
            ):
                raise HTTPException(
                    409,
                    "The queued package identity changed. "
                    "No operation was submitted.",
                )

            package["state"] = package.pop("queuePriorState")
            main.metadata_spec_store.save_package(package)

            # Recheck ownership, approval, source and validation
            # while holding the shared plan lock.
            result = main.run_default_package(
                plan_id,
                dry_run=row["kind"] == "validate",
            )
            record_workflow_response(
                {"id": row["user_id"]},
                row["org_id"],
                plan_id,
                "/api/plans/" + plan_id + "/" + row["kind"],
                result,
                200,
            )
            return {"planId": plan_id}


def submission_failure(row, error):
    from Backend.AI.app import main
    from Backend.AI.app.services.shared_plan_lock import shared_plan_lock

    payload = json.loads(row["payload"])
    plan = payload["plan_id"]

    with main.layout_workflow.plan_lock(plan), shared_plan_lock(plan):
        main.restore_workspace_package(
            plan,
            row["user_id"],
            row["org_id"],
        )
        package = main.metadata_spec_store.get_package(plan)

        if (
            package
            and package.get("backgroundJobId") == row["id"]
            and package.get("state") in {"queued", "generated", "validated"}
        ):
            message = (
                error.detail
                if isinstance(error.detail, str)
                else error.detail.get(
                    "message",
                    "Queued operation failed before submission.",
                )
            )
            package.update(
                state="failed",
                error=message,
                validatedHash=None,
            )
            main.metadata_spec_store.save_package(package)


def process_jobs(limit=20, stop=None):
    from Backend.AI.app.account_api import db, current_account, current_org
    from Backend.AI.app.services.shared_plan_lock import shared_plan_lock

    with db() as connection:
        rows = connection.execute(
            "SELECT j.* FROM background_jobs j "
            "JOIN orgs o ON o.id=j.org_id AND o.user_id=j.user_id "
            "WHERE j.state IN ('queued','running') "
            "ORDER BY j.created LIMIT ?",
            (limit,),
        ).fetchall()

    for candidate in rows:
        if stop is not None and stop.is_set():
            break

        with shared_plan_lock(
            "background:" + candidate["id"],
            blocking=False,
        ) as acquired:
            if not acquired:
                continue

            with db() as connection:
                row = connection.execute(
                    "SELECT j.* FROM background_jobs j "
                    "JOIN orgs o ON o.id=j.org_id AND o.user_id=j.user_id "
                    "WHERE j.id=?",
                    (candidate["id"],),
                ).fetchone()

                if not row or row["state"] not in {"queued", "running"}:
                    continue

            owner_token = current_account.set(row["user_id"])
            org_token = current_org.set(row["org_id"])
            execute_token = executing_job.set(True)
            log_token = job_id_context.set(row["id"])
            processing_started = None

            try:
                if row["state"] == "running":
                    processing_started = time.perf_counter()
                    log_event(
                        logger,
                        "background_job_recovery_started",
                        operation=row["kind"],
                    )

                    try:
                        reconcile(row)
                    except Exception as error:
                        log_event(
                            logger,
                            "background_job_recovery_failed",
                            level=logging.ERROR,
                            operation=row["kind"],
                            error_type=type(error).__name__,
                        )
                        finish(
                            row,
                            "unknown",
                            {
                                "detail": (
                                    "Saved operation could not be recovered "
                                    "safely. Inspect Salesforce Deployment "
                                    "Status and regenerate from the saved "
                                    "requirement if needed."
                                ),
                                **(
                                    {
                                        "planId": json.loads(
                                            row["payload"]
                                        )["plan_id"]
                                    }
                                    if row["kind"] != "generate"
                                    else {}
                                ),
                            },
                        )
                    continue

                with db() as connection:
                    changed = connection.execute(
                        "UPDATE background_jobs SET state='running',updated=? "
                        "WHERE id=? AND state='queued'",
                        (time.time(), row["id"]),
                    ).rowcount

                if changed != 1:
                    continue

                processing_started = time.perf_counter()
                log_event(
                    logger,
                    "background_job_started",
                    operation=row["kind"],
                    state="running",
                    queue_ms=round(
                        max(0, time.time() - row["created"]) * 1000,
                        3,
                    ),
                )

                try:
                    result = execute(row)
                except HTTPException as error:
                    # Clarifications can use HTTP 422; omit their business text.
                    log_event(
                        logger,
                        "background_job_request_rejected",
                        level=(
                            logging.ERROR
                            if error.status_code >= 500
                            else logging.INFO
                        ),
                        operation=row["kind"],
                        status_code=error.status_code,
                    )

                    if row["kind"] != "generate":
                        try:
                            submission_failure(row, error)
                        except Exception as recovery_error:
                            log_event(
                                logger,
                                "background_job_recovery_failed",
                                level=logging.ERROR,
                                operation=row["kind"],
                                error_type=type(recovery_error).__name__,
                            )
                            finish(
                                row,
                                "unknown",
                                {
                                    "planId": json.loads(
                                        row["payload"]
                                    )["plan_id"],
                                    "detail": (
                                        "Saved package could not be recovered "
                                        "safely. Inspect its saved operation "
                                        "before retrying."
                                    ),
                                },
                            )
                            continue

                    finish(
                        row,
                        "failed",
                        {
                            "detail": error.detail,
                            "status": error.status_code,
                            **(
                                {
                                    "planId": json.loads(
                                        row["payload"]
                                    )["plan_id"]
                                }
                                if row["kind"] != "generate"
                                else {}
                            ),
                        },
                    )
                except Exception as error:
                    log_event(
                        logger,
                        "background_job_execution_failed",
                        level=logging.ERROR,
                        operation=row["kind"],
                        error_type=type(error).__name__,
                    )

                    if row["kind"] == "generate":
                        finish(
                            row,
                            "failed",
                            {
                                "detail": (
                                    "Background generation failed. Inspect "
                                    "server logs; no operation was "
                                    "automatically repeated."
                                ),
                                "status": 500,
                            },
                        )
                    else:
                        try:
                            reconcile(row)
                        except Exception as recovery_error:
                            log_event(
                                logger,
                                "background_job_recovery_failed",
                                level=logging.ERROR,
                                operation=row["kind"],
                                error_type=type(recovery_error).__name__,
                            )
                            finish(
                                row,
                                "unknown",
                                {
                                    "planId": json.loads(
                                        row["payload"]
                                    )["plan_id"],
                                    "detail": (
                                        "Submission outcome could not be "
                                        "recovered safely. Inspect Salesforce "
                                        "Deployment Status before retrying."
                                    ),
                                },
                            )
                else:
                    finish(row, "succeeded", result)
            finally:
                try:
                    if processing_started is not None:
                        log_event(
                            logger,
                            "background_job_processing_finished",
                            operation=row["kind"],
                            duration_ms=round(
                                (
                                    time.perf_counter()
                                    - processing_started
                                ) * 1000,
                                3,
                            ),
                        )
                finally:
                    job_id_context.reset(log_token)
                    executing_job.reset(execute_token)
                    current_account.reset(owner_token)
                    current_org.reset(org_token)