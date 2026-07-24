from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    AssignmentAnalysisRequest,
    ClaimTaskRequest,
    ConfirmedProjectRequest,
    JoinProjectRequest,
    ProjectChatRequest,
    SubmitTaskRequest,
    TaskStatus,
)
from .ai_service import AIConfigurationError, AIService, AIServiceError
from .config import Settings
from .file_extraction import FileExtractionError, extract_uploaded_text
from .sample_inputs import SAMPLE_ASSIGNMENT
from .sample_data import DEMO_PROJECT_ID
from .storage import InMemoryStorage
from .workflow import (
    auto_claim_overdue_tasks,
    available_tasks,
    build_combined_result,
    claim_task,
    build_combined_result,
    criterion_for_task,
    refresh_member_workloads,
    rubric_coverage,
    schedule_project_tasks,
    unlock_dependents,
    validate_dependency_references,
    validate_submission,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
store = InMemoryStorage()
settings = Settings.from_environment()
ai_service = AIService(settings)

app = FastAPI(
    title="Relay API",
    description="From assignment brief to next action.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "Relay"}


@app.get("/api/samples/assignment")
def sample_assignment() -> dict[str, str]:
    return SAMPLE_ASSIGNMENT


@app.get("/api/ai/status")
def ai_status() -> dict[str, object]:
    return ai_service.status()


@app.post("/api/files/extract")
async def extract_file(
    file: UploadFile = File(...),
    document_type: str = Form(...),
) -> dict[str, object]:
    if document_type not in {"assignment", "rubric"}:
        raise HTTPException(
            status_code=422,
            detail="Document type must be assignment or rubric.",
        )
    try:
        content = await file.read(settings.max_upload_bytes + 1)
        filename, file_type, text = extract_uploaded_text(
            filename=file.filename,
            content_type=file.content_type,
            content=content,
            max_bytes=settings.max_upload_bytes,
        )
    except FileExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        await file.close()
    text_limit = (
        30_000 if document_type == "assignment" else 20_000
    )
    if len(text) > text_limit:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Extracted {document_type} text exceeds the "
                f"{text_limit:,}-character limit."
            ),
        )
    return {
        "filename": filename,
        "document_type": document_type,
        "file_type": file_type,
        "character_count": len(text),
        "text": text,
        "warnings": [],
    }


@app.post("/api/assignments/analyze")
def analyse_assignment(payload: AssignmentAnalysisRequest) -> dict[str, object]:
    try:
        result, mode = ai_service.analyze_assignment(payload)
    except (AIConfigurationError, AIServiceError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        **result.model_dump(mode="json"),
        "analysis_mode": mode,
    }


@app.post("/api/projects/from-analysis", status_code=status.HTTP_201_CREATED)
def create_project_from_analysis(
    payload: ConfirmedProjectRequest,
) -> dict[str, object]:
    try:
        generation = ai_service.generate_project(payload)
        project = generation.project
        warnings = generation.warnings
        validate_dependency_references(project)
        schedule_project_tasks(project, settings.auto_claim_seconds)
        store.add_project(project)
    except (AIConfigurationError, AIServiceError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=f"Relay could not build a valid workflow: {error}",
        ) from error
    return {
        "project_id": project.id,
        "title": project.title,
        "task_count": len(project.tasks),
        "available_task_count": len(available_tasks(project)),
        "deliverables": project.deliverables,
        "requirements": project.requirements,
        "rubric": [item.model_dump(mode="json") for item in project.rubric],
        "workflow_warnings": warnings,
        "workflow_generation_mode": generation.mode,
    }


@app.post("/api/demo/reset")
def reset_demo() -> dict[str, object]:
    project = store.reset_demo(preserve_other_projects=True)
    validate_dependency_references(project)
    schedule_project_tasks(project, settings.auto_claim_seconds)
    return {
        "project_id": project.id,
        "title": project.title,
        "task_count": len(project.tasks),
        "available_task_count": len(available_tasks(project)),
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, object]:
    try:
        project = store.get_project(project_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error
    if not any(task.due_date or task.available_since for task in project.tasks):
        schedule_project_tasks(project, settings.auto_claim_seconds)
    auto_claim_overdue_tasks(project, settings.auto_claim_seconds)
    refresh_member_workloads(project)
    return {
        **project.model_dump(mode="json"),
        "rubric_coverage": rubric_coverage(project),
    }


@app.get("/api/projects")
def get_project_statistics() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for project in store.projects.values():
        completed = sum(task.status == TaskStatus.COMPLETED for task in project.tasks)
        in_progress = sum(
            task.status in {TaskStatus.IN_PROGRESS, TaskStatus.NEEDS_REVISION}
            for task in project.tasks
        )
        accepted_characters = sum(
            len(submission.content)
            for task in project.tasks
            if (submission := store.completed_submission_for(task)) is not None
        )
        total = len(project.tasks)
        results.append({
            "project_id": project.id,
            "title": project.title,
            "deadline": project.deadline,
            "is_complete": bool(total) and completed == total,
            "progress_percent": round(completed / total * 100) if total else 0,
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "available_tasks": sum(
                task.status == TaskStatus.AVAILABLE for task in project.tasks
            ),
            "waiting_tasks": sum(
                task.status == TaskStatus.WAITING for task in project.tasks
            ),
            "total_tasks": total,
            "member_count": len(project.members),
            "members": [member.name for member in project.members],
            "accepted_answer_characters": accepted_characters,
            "estimated_minutes": sum(task.estimated_minutes for task in project.tasks),
        })
    return results


@app.get("/api/projects/{project_id}/combined-result")
def get_combined_project_result(project_id: str) -> dict[str, object]:
    try:
        project = store.get_project(project_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error
    return build_combined_result(project, store.submissions)


@app.post("/api/projects/{project_id}/chat")
def chat_about_project(
    project_id: str,
    payload: ProjectChatRequest,
) -> dict[str, object]:
    try:
        project = store.get_project(project_id)
        response, mode = ai_service.chat_about_project(
            project=project,
            submissions=store.submissions,
            question=payload.question,
            history=[item.model_dump() for item in payload.history],
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error
    except (AIConfigurationError, AIServiceError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {**response.model_dump(), "mode": mode}


@app.post("/api/projects/{project_id}/members", status_code=status.HTTP_201_CREATED)
def join_project(project_id: str, payload: JoinProjectRequest) -> dict[str, object]:
    try:
        project = store.get_project(project_id)
        member = store.add_member(project, payload.name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return member.model_dump(mode="json")


@app.get("/api/projects/{project_id}/available-tasks")
def get_available_tasks(project_id: str) -> list[dict[str, object]]:
    try:
        project = store.get_project(project_id)
        if not any(task.due_date or task.available_since for task in project.tasks):
            schedule_project_tasks(project, settings.auto_claim_seconds)
        auto_claim_overdue_tasks(project, settings.auto_claim_seconds)
        tasks = available_tasks(project)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error
    except ValueError as error:
        raise HTTPException(status_code=500, detail="Project workflow is invalid.") from error

    return [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "estimated_minutes": task.estimated_minutes,
            "work_style": task.work_style,
            "required_output": task.required_output,
            "rubric_criterion": (
                criterion_for_task(project, task).model_dump(mode="json")
                if criterion_for_task(project, task)
                else None
            ),
            "unlocks": task.unlocks,
            "due_date": task.due_date,
            "auto_claim_at": task.auto_claim_at,
        }
        for task in tasks
    ]


@app.post("/api/tasks/{task_id}/claim")
def claim_available_task(task_id: str, payload: ClaimTaskRequest) -> dict[str, object]:
    try:
        project, task = store.get_task(task_id)
        member_project, member = store.get_member(payload.member_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error

    if project.id != member_project.id:
        raise HTTPException(status_code=400, detail="Member does not belong to this project.")
    try:
        warning = claim_task(project, task, member)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "task": task.model_dump(mode="json"),
        "member_workload_minutes": member.total_estimated_minutes,
        "workload_warning": warning,
    }


@app.get("/api/members/{member_id}/next-action")
def member_next_action(member_id: str) -> dict[str, object]:
    try:
        project, member = store.get_member(member_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error

    auto_claim_overdue_tasks(project, settings.auto_claim_seconds)
    task = next(
        (
            candidate
            for candidate in project.tasks
            if candidate.claimed_by == member.id
            and candidate.status in {TaskStatus.IN_PROGRESS, TaskStatus.NEEDS_REVISION}
        ),
        None,
    )
    if task is None:
        return {
            "has_active_task": False,
            "message": "This member has no active task. Choose an available task to begin.",
        }

    task_lookup = {candidate.id: candidate for candidate in project.tasks}
    return {
        "has_active_task": True,
        "task_id": task.id,
        "task_title": task.title,
        "status": task.status,
        "objective": task.objective,
        "first_action": task.first_action,
        "execution_steps": task.execution_steps,
        "required_output": task.required_output,
        "estimated_minutes": task.estimated_minutes,
        "due_date": task.due_date,
        "rubric_criterion": (
            criterion_for_task(project, task).model_dump(mode="json")
            if criterion_for_task(project, task)
            else None
        ),
        "unlocks": [
            {"id": unlocked_id, "title": task_lookup[unlocked_id].title}
            for unlocked_id in task.unlocks
            if unlocked_id in task_lookup
        ],
        "dependency_context": [
            item.model_dump(mode="json") for item in task.dependency_context
        ],
    }


@app.post("/api/tasks/{task_id}/submit")
def submit_task(task_id: str, payload: SubmitTaskRequest) -> dict[str, object]:
    try:
        project, task = store.get_task(task_id)
        member_project, member = store.get_member(payload.member_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error

    if project.id != member_project.id:
        raise HTTPException(status_code=400, detail="Member does not belong to this project.")
    if task.claimed_by is None:
        raise HTTPException(status_code=409, detail="Task must be claimed before submission.")
    if task.claimed_by != member.id:
        raise HTTPException(status_code=403, detail="Only the task owner can submit this work.")
    if task.status not in {TaskStatus.IN_PROGRESS, TaskStatus.NEEDS_REVISION}:
        raise HTTPException(
            status_code=409,
            detail="Task is not in a state that accepts submissions.",
        )

    try:
        check = ai_service.validate_submission(
            task=task,
            content=payload.content,
            force_fallback=project.id == DEMO_PROJECT_ID,
        )
    except (AIConfigurationError, AIServiceError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    validation = check.validation
    submission = store.save_submission(
        task=task,
        member=member,
        content=payload.content,
        complete=validation.complete,
        feedback=validation.feedback,
        missing_items=validation.missing_items,
    )
    if not validation.complete:
        task.status = TaskStatus.NEEDS_REVISION
        refresh_member_workloads(project)
        return {
            "complete": False,
            "missing_items": validation.missing_items,
            "feedback": validation.feedback,
            "evidence_found": validation.evidence_found,
            "validation_mode": check.mode,
            "submission_id": submission.id,
            "newly_unlocked_tasks": [],
        }

    task.status = TaskStatus.COMPLETED
    if task.id in member.claimed_task_ids:
        member.claimed_task_ids.remove(task.id)
    refresh_member_workloads(project)
    unlocked = unlock_dependents(project, task, store.submissions)
    combined_result = build_combined_result(project, store.submissions)
    return {
        "complete": True,
        "missing_items": [],
        "feedback": validation.feedback,
        "evidence_found": validation.evidence_found,
        "validation_mode": check.mode,
        "submission_id": submission.id,
        "completed_task": {"id": task.id, "title": task.title},
        "newly_unlocked_tasks": [
            {"id": candidate.id, "title": candidate.title}
            for candidate in unlocked
        ],
        "workflow_complete": combined_result["is_complete"],
        "combined_result": (
            combined_result if combined_result["is_complete"] else None
        ),
    }


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
