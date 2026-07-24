from collections import Counter
from datetime import datetime, timezone

from .models import Project, Submission, TaskStatus
from .workflow import rubric_coverage


def compile_project_reports(
    project: Project,
    submissions: dict[str, Submission],
) -> dict[str, object]:
    completed_count = sum(
        task.status == TaskStatus.COMPLETED for task in project.tasks
    )
    if not project.tasks or completed_count != len(project.tasks):
        raise ValueError(
            "Reports unlock after every task is completed "
            f"({completed_count}/{len(project.tasks)} complete)."
        )

    members = {member.id: member.name for member in project.members}
    accepted = []
    for task in project.tasks:
        submission = submissions.get(task.submission_id or "")
        if submission is None or submission.validation_status != "complete":
            raise ValueError(
                f"Completed task '{task.title}' has no accepted submission."
            )
        accepted.append((task, submission))

    accepted.sort(key=lambda item: item[1].submitted_at)
    attempts = Counter(item.task_id for item in submissions.values())
    contributions = Counter(
        members.get(submission.member_id, "Unknown member")
        for _, submission in accepted
    )
    coverage = rubric_coverage(project)
    handoff_count = sum(len(task.dependencies) for task in project.tasks)

    return {
        "project_id": project.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_report": {
            "title": f"{project.title} — Consolidated Assignment Report",
            "deadline": project.deadline,
            "deliverables": project.deliverables,
            "requirements": project.requirements,
            "sections": [
                {
                    "heading": task.title,
                    "owner": members.get(
                        submission.member_id, "Unknown member"
                    ),
                    "completed_at": submission.submitted_at.isoformat(),
                    "due_date": task.due_date,
                    "content": submission.content,
                }
                for task, submission in accepted
            ],
        },
        "progression_report": {
            "title": (
                f"{project.title} — Progression and Workflow Analysis"
            ),
            "summary": {
                "tasks_completed": len(project.tasks),
                "members": len(project.members),
                "submission_attempts": sum(attempts.values()),
                "dependency_handoffs": handoff_count,
                "rubric_marks_covered": coverage["completed_marks"],
                "rubric_marks_total": coverage["total_marks"],
            },
            "member_contributions": [
                {"member": name, "completed_tasks": count}
                for name, count in contributions.items()
            ],
            "workflow_analysis": (
                f"The group completed {len(project.tasks)} dependency-aware "
                f"tasks through {handoff_count} workflow handoffs. Work began "
                f"in {sum(not task.dependencies for task in project.tasks)} "
                "parallel starting tasks and converged as prerequisite "
                "submissions unlocked later work."
            ),
            "sections": [
                {
                    "heading": f"{index}. {task.title}",
                    "content": (
                        f"Completed by "
                        f"{members.get(submission.member_id, 'Unknown member')} "
                        f"on {submission.submitted_at.isoformat()}. Required "
                        f"{attempts[task.id]} submission attempt"
                        f"{'' if attempts[task.id] == 1 else 's'}. "
                        f"Dependencies: {len(task.dependencies)}; "
                        f"unlocked tasks: {len(task.unlocks)}."
                    ),
                }
                for index, (task, submission) in enumerate(
                    accepted, start=1
                )
            ],
        },
    }
