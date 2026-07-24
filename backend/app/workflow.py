import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import ceil

from .models import (
    DependencyContext,
    Member,
    Project,
    RubricCriterion,
    Submission,
    Task,
    TaskStatus,
)


WORKLOAD_WARNING_GAP_MINUTES = 45


@dataclass
class ValidationResult:
    complete: bool
    missing_items: list[str]
    feedback: str


def task_map(project: Project) -> dict[str, Task]:
    return {task.id: task for task in project.tasks}


def validate_dependency_references(project: Project) -> None:
    tasks = task_map(project)
    for task in project.tasks:
        for dependency_id in task.dependencies:
            if dependency_id not in tasks:
                raise ValueError(
                    f"Task '{task.id}' references missing dependency '{dependency_id}'."
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError("Workflow contains a circular dependency.")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency_id in tasks[task_id].dependencies:
            visit(dependency_id)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)


def dependencies_complete(project: Project, task: Task) -> bool:
    tasks = task_map(project)
    return all(
        dependency_id in tasks
        and tasks[dependency_id].status == TaskStatus.COMPLETED
        for dependency_id in task.dependencies
    )


def is_task_available(project: Project, task: Task) -> bool:
    return (
        task.status == TaskStatus.AVAILABLE
        and task.claimed_by is None
        and dependencies_complete(project, task)
    )


def available_tasks(project: Project) -> list[Task]:
    validate_dependency_references(project)
    return [task for task in project.tasks if is_task_available(project, task)]


def schedule_project_tasks(project: Project, auto_claim_seconds: int) -> None:
    """Attach readable task dates and auto-claim timers to a new workflow."""
    today = date.today()
    deadline = date.fromisoformat(project.deadline) if project.deadline else None
    total_days = max(0, (deadline - today).days) if deadline else 0
    count = max(1, len(project.tasks))
    now = datetime.now(timezone.utc)
    for index, task in enumerate(project.tasks):
        if deadline:
            offset = ceil(total_days * (index + 1) / count)
            task.due_date = min(deadline, today + timedelta(days=offset)).isoformat()
        else:
            task.due_date = None
        if task.status == TaskStatus.AVAILABLE:
            task.available_since = now
            task.auto_claim_at = now + timedelta(seconds=auto_claim_seconds)


def auto_claim_overdue_tasks(project: Project, auto_claim_seconds: int) -> list[Task]:
    """Lazily distribute overdue ready work to the lowest-workload members."""
    if not project.members:
        return []
    now = datetime.now(timezone.utc)
    claimed: list[Task] = []
    for task in project.tasks:
        if not is_task_available(project, task):
            continue
        if task.available_since is None:
            task.available_since = now
        if task.auto_claim_at is None:
            task.auto_claim_at = task.available_since + timedelta(seconds=auto_claim_seconds)
        if now < task.auto_claim_at:
            continue
        member = lowest_workload_member(project)
        if member is None:
            break
        claim_task(project, task, member)
        claimed.append(task)
    return claimed


def calculate_member_workload(project: Project, member_id: str) -> int:
    return sum(
        task.estimated_minutes
        for task in project.tasks
        if task.claimed_by == member_id and task.status != TaskStatus.COMPLETED
    )


def refresh_member_workloads(project: Project) -> None:
    for member in project.members:
        member.total_estimated_minutes = calculate_member_workload(project, member.id)


def lowest_workload_member(project: Project) -> Member | None:
    if not project.members:
        return None
    refresh_member_workloads(project)
    return min(
        enumerate(project.members),
        key=lambda item: (item[1].total_estimated_minutes, item[0]),
    )[1]


def claim_task(project: Project, task: Task, member: Member) -> str | None:
    validate_dependency_references(project)
    if task.status == TaskStatus.COMPLETED:
        raise ValueError("Task has already been completed.")
    if task.claimed_by is not None or task.status in {
        TaskStatus.IN_PROGRESS,
        TaskStatus.NEEDS_REVISION,
    }:
        raise ValueError("Task has already been claimed.")
    if not dependencies_complete(project, task):
        raise ValueError("Task is still blocked by incomplete dependencies.")
    if task.status != TaskStatus.AVAILABLE:
        raise ValueError("Task is not available to claim.")

    task.claimed_by = member.id
    task.status = TaskStatus.IN_PROGRESS
    if task.id not in member.claimed_task_ids:
        member.claimed_task_ids.append(task.id)
    refresh_member_workloads(project)

    lowest = min(
        (candidate.total_estimated_minutes for candidate in project.members),
        default=member.total_estimated_minutes,
    )
    if member.total_estimated_minutes - lowest >= WORKLOAD_WARNING_GAP_MINUTES:
        return (
            f"Your active work totals approximately {member.total_estimated_minutes} "
            f"minutes, while the lowest member workload is {lowest} minutes. "
            "You can keep the task, but the workload may be unbalanced."
        )
    return None


def _has_numbered_items(content: str, minimum: int) -> bool:
    matches = re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", content)
    return len(matches) >= minimum


def _section_count(content: str) -> int:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    headings = re.findall(r"(?m)^\s*(?:#{1,3}\s+|[A-Za-z][^:\n]{2,30}:)\s*", content)
    return max(len(paragraphs), len(headings))


def validate_submission(task: Task, content: str) -> ValidationResult:
    lowered = content.casefold()
    missing: list[str] = []

    if task.id in {"task-problem-research", "task-tool-research"}:
        for number in range(1, 4):
            source_pattern = rf"source\s*{number}\s*:"
            source_match = re.search(source_pattern, content, flags=re.IGNORECASE)
            next_match = re.search(
                rf"source\s*{number + 1}\s*:",
                content,
                flags=re.IGNORECASE,
            )
            section = content[
                source_match.end() if source_match else 0 :
                next_match.start() if next_match else len(content)
            ]
            if source_match is None:
                missing.append(f"Source {number}")
                continue
            for label in ("Link:", "Summary:", "Relevance:"):
                if label.casefold() not in section.casefold():
                    missing.append(f"{label[:-1]} for Source {number}")
        if len(content) < 240:
            missing.append("Enough detail to describe three credible sources")

    elif task.id in {"task-problem-analysis", "task-solution-comparison"}:
        if len(content) < 220:
            missing.append("A sufficiently detailed analysis of at least 220 characters")
        if _section_count(content) < 2:
            missing.append("At least two paragraphs or labelled sections")
        if not task.dependency_context:
            missing.append("Completed dependency context")
        if not any(word in lowered for word in ("source", "research", "evidence", "tool")):
            missing.append("A clear reference to the supplied dependency research")

    elif task.id == "task-solution-requirements":
        if len(content) < 220:
            missing.append("A sufficiently detailed requirements definition")
        if not _has_numbered_items(content, 3):
            missing.append("At least three numbered requirements")
        if lowered.count("acceptance") < 3:
            missing.append("An acceptance check for each requirement")
        if len(task.dependency_context) < 2:
            missing.append("Context from both completed analysis branches")

    elif task.id == "task-prototype-plan":
        for term, label in (
            ("screen", "A screen list"),
            ("data flow", "A data-flow description"),
            ("handoff", "Automatic handoff acceptance criteria"),
        ):
            if term not in lowered:
                missing.append(label)
        if len(content) < 180:
            missing.append("A sufficiently detailed prototype plan")

    elif task.id == "task-prototype-build":
        for term, label in (
            ("claim", "Implemented claim flow"),
            ("submission", "Implemented submission flow"),
            ("unlock", "Implemented unlock flow"),
            ("context", "Implemented context handoff"),
        ):
            if term not in lowered:
                missing.append(label)
        if len(content) < 200:
            missing.append("Implementation notes of at least 200 characters")

    elif task.id == "task-handoff-test":
        for term, label in (
            ("scenario", "A named test scenario"),
            ("expected", "The expected result"),
            ("actual", "The actual result"),
            ("context", "Evidence of context transfer"),
        ):
            if term not in lowered:
                missing.append(label)
        if len(content) < 180:
            missing.append("A sufficiently detailed test record")

    elif task.id == "task-final-presentation":
        for term, label in (
            ("problem", "The problem narrative"),
            ("solution", "The solution narrative"),
            ("demo", "The live demo sequence"),
            ("test", "Testing evidence"),
            ("limitation", "Known limitations"),
        ):
            if term not in lowered:
                missing.append(label)
        if len(content) < 200:
            missing.append("A sufficiently detailed presentation plan")

    else:
        if len(content) < 120:
            missing.append("A submission of at least 120 characters")

    if missing:
        return ValidationResult(
            complete=False,
            missing_items=missing,
            feedback="Add the missing minimum components before handing this work forward.",
        )
    return ValidationResult(
        complete=True,
        missing_items=[],
        feedback=(
            "The submission contains the minimum required components. "
            "Relay has accepted it for workflow handoff."
        ),
    )


def build_dependency_context(
    project: Project,
    task: Task,
    submissions: dict[str, Submission],
) -> list[DependencyContext]:
    tasks = task_map(project)
    members = {member.id: member for member in project.members}
    context: list[DependencyContext] = []
    for dependency_id in task.dependencies:
        dependency = tasks[dependency_id]
        if dependency.submission_id is None:
            continue
        submission = submissions.get(dependency.submission_id)
        if submission is None or submission.validation_status != "complete":
            continue
        member = members.get(submission.member_id)
        context.append(
            DependencyContext(
                source_task_id=dependency.id,
                source_task_title=dependency.title,
                submitted_by=member.name if member else "Unknown member",
                content=submission.content,
                submitted_at=submission.submitted_at,
            )
        )
    return context


def build_combined_result(
    project: Project,
    submissions: dict[str, Submission],
) -> dict[str, object]:
    """Combine every accepted task answer into one ordered project document."""
    members = {member.id: member.name for member in project.members}
    sections: list[dict[str, str]] = []
    for task in project.tasks:
        if task.status != TaskStatus.COMPLETED or task.submission_id is None:
            continue
        submission = submissions.get(task.submission_id)
        if submission is None or submission.validation_status != "complete":
            continue
        sections.append({
            "task_id": task.id,
            "task_title": task.title,
            "submitted_by": members.get(submission.member_id, "Unknown member"),
            "content": submission.content,
        })

    combined = f"# {project.title}\n\n" + "\n\n".join(
        f"## {index}. {section['task_title']}\n\n"
        f"_Completed by {section['submitted_by']}_\n\n{section['content']}"
        for index, section in enumerate(sections, start=1)
    )
    return {
        "project_id": project.id,
        "project_title": project.title,
        "is_complete": bool(project.tasks)
        and all(task.status == TaskStatus.COMPLETED for task in project.tasks),
        "completed_task_count": len(sections),
        "total_task_count": len(project.tasks),
        "sections": sections,
        "combined_content": combined.rstrip(),
    }


def build_combined_result(
    project: Project,
    submissions: dict[str, Submission],
) -> dict[str, object]:
    """Combine every accepted task answer into one ordered project document."""
    members = {member.id: member.name for member in project.members}
    sections: list[dict[str, str]] = []
    for task in project.tasks:
        if task.status != TaskStatus.COMPLETED or task.submission_id is None:
            continue
        submission = submissions.get(task.submission_id)
        if submission is None or submission.validation_status != "complete":
            continue
        sections.append({
            "task_id": task.id,
            "task_title": task.title,
            "submitted_by": members.get(submission.member_id, "Unknown member"),
            "content": submission.content,
        })

    combined = f"# {project.title}\n\n" + "\n\n".join(
        f"## {index}. {section['task_title']}\n\n"
        f"_Completed by {section['submitted_by']}_\n\n{section['content']}"
        for index, section in enumerate(sections, start=1)
    )
    return {
        "project_id": project.id,
        "project_title": project.title,
        "is_complete": bool(project.tasks)
        and all(task.status == TaskStatus.COMPLETED for task in project.tasks),
        "completed_task_count": len(sections),
        "total_task_count": len(project.tasks),
        "sections": sections,
        "combined_content": combined.rstrip(),
    }


def build_combined_result(
    project: Project,
    submissions: dict[str, Submission],
) -> dict[str, object]:
    """Combine every accepted task answer into one ordered project document."""
    members = {member.id: member.name for member in project.members}
    sections: list[dict[str, str]] = []
    for task in project.tasks:
        if task.status != TaskStatus.COMPLETED or task.submission_id is None:
            continue
        submission = submissions.get(task.submission_id)
        if submission is None or submission.validation_status != "complete":
            continue
        sections.append(
            {
                "task_id": task.id,
                "task_title": task.title,
                "submitted_by": members.get(submission.member_id, "Unknown member"),
                "content": submission.content,
            }
        )

    combined = f"# {project.title}\n\n"
    combined += "\n\n".join(
        (
            f"## {index}. {section['task_title']}\n\n"
            f"_Completed by {section['submitted_by']}_\n\n"
            f"{section['content']}"
        )
        for index, section in enumerate(sections, start=1)
    )
    return {
        "project_id": project.id,
        "project_title": project.title,
        "is_complete": bool(project.tasks)
        and all(task.status == TaskStatus.COMPLETED for task in project.tasks),
        "completed_task_count": len(sections),
        "total_task_count": len(project.tasks),
        "sections": sections,
        "combined_content": combined.rstrip(),
    }


def build_combined_result(
    project: Project,
    submissions: dict[str, Submission],
) -> dict[str, object]:
    """Combine every accepted task answer into one ordered project document."""
    members = {member.id: member.name for member in project.members}
    sections: list[dict[str, str]] = []
    for task in project.tasks:
        if task.status != TaskStatus.COMPLETED or task.submission_id is None:
            continue
        submission = submissions.get(task.submission_id)
        if submission is None or submission.validation_status != "complete":
            continue
        sections.append(
            {
                "task_id": task.id,
                "task_title": task.title,
                "submitted_by": members.get(submission.member_id, "Unknown member"),
                "content": submission.content,
            }
        )

    combined = f"# {project.title}\n\n"
    combined += "\n\n".join(
        (
            f"## {index}. {section['task_title']}\n\n"
            f"_Completed by {section['submitted_by']}_\n\n"
            f"{section['content']}"
        )
        for index, section in enumerate(sections, start=1)
    )
    return {
        "project_id": project.id,
        "project_title": project.title,
        "is_complete": bool(project.tasks)
        and all(task.status == TaskStatus.COMPLETED for task in project.tasks),
        "completed_task_count": len(sections),
        "total_task_count": len(project.tasks),
        "sections": sections,
        "combined_content": combined.rstrip(),
    }


def unlock_dependents(
    project: Project,
    completed_task: Task,
    submissions: dict[str, Submission],
) -> list[Task]:
    unlocked: list[Task] = []
    for candidate in project.tasks:
        if completed_task.id not in candidate.dependencies:
            continue
        if candidate.status == TaskStatus.WAITING and dependencies_complete(project, candidate):
            candidate.status = TaskStatus.AVAILABLE
            candidate.available_since = datetime.now(timezone.utc)
            candidate.dependency_context = build_dependency_context(
                project, candidate, submissions
            )
            unlocked.append(candidate)
    return unlocked


def rubric_coverage(project: Project) -> dict[str, object]:
    tasks_by_rubric: dict[str, list[Task]] = {
        criterion.id: [
            task for task in project.tasks if task.rubric_id == criterion.id
        ]
        for criterion in project.rubric
    }
    result: dict[str, object] = {
        "total_marks": sum(item.marks for item in project.rubric),
        "covered_marks": 0,
        "available_marks": 0,
        "in_progress_marks": 0,
        "completed_marks": 0,
        "waiting_marks": 0,
        "uncovered_criteria": [],
    }

    for criterion in project.rubric:
        tasks = tasks_by_rubric[criterion.id]
        if not tasks:
            result["uncovered_criteria"].append(criterion.model_dump())
            continue
        result["covered_marks"] += criterion.marks
        if all(task.status == TaskStatus.COMPLETED for task in tasks):
            result["completed_marks"] += criterion.marks
        elif any(
            task.status in {TaskStatus.IN_PROGRESS, TaskStatus.NEEDS_REVISION}
            for task in tasks
        ):
            result["in_progress_marks"] += criterion.marks
        elif any(task.status == TaskStatus.AVAILABLE for task in tasks):
            result["available_marks"] += criterion.marks
        else:
            result["waiting_marks"] += criterion.marks
    return result


def criterion_for_task(project: Project, task: Task) -> RubricCriterion | None:
    return next(
        (criterion for criterion in project.rubric if criterion.id == task.rubric_id),
        None,
    )
