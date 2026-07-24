from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    ClaimTaskRequest,
    JoinProjectRequest,
    SubmitTaskRequest,
    TaskStatus,
)
from .storage import InMemoryStorage
from .workflow import (
    available_tasks,
    claim_task,
    criterion_for_task,
    refresh_member_workloads,
    rubric_coverage,
    unlock_dependents,
    validate_dependency_references,
    validate_submission,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
store = InMemoryStorage()

app = FastAPI(
    title="Relay API",
    description="From assignment brief to next action.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "Relay"}


@app.post("/api/demo/reset")
def reset_demo() -> dict[str, object]:
    project = store.reset_demo()
    validate_dependency_references(project)
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
    refresh_member_workloads(project)
    return {
        **project.model_dump(mode="json"),
        "rubric_coverage": rubric_coverage(project),
    }


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

    validation = validate_submission(task, payload.content)
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
            "submission_id": submission.id,
            "newly_unlocked_tasks": [],
        }

    task.status = TaskStatus.COMPLETED
    if task.id in member.claimed_task_ids:
        member.claimed_task_ids.remove(task.id)
    refresh_member_workloads(project)
    unlocked = unlock_dependents(project, task, store.submissions)
    return {
        "complete": True,
        "missing_items": [],
        "feedback": validation.feedback,
        "submission_id": submission.id,
        "completed_task": {"id": task.id, "title": task.title},
        "newly_unlocked_tasks": [
            {"id": candidate.id, "title": candidate.title}
            for candidate in unlocked
        ],
    }


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
