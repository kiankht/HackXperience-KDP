import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, store
from backend.app.models import TaskStatus
from backend.app.sample_data import create_demo_project
from backend.app.workflow import (
    available_tasks,
    lowest_workload_member,
    rubric_coverage,
    validate_dependency_references,
)


client = TestClient(app)
PROJECT_ID = "project-relay-demo"


def research_submission(topic: str = "student group work") -> str:
    sections = []
    for number in range(1, 4):
        sections.append(
            f"""Source {number}:
Link: https://example.edu/{topic.replace(" ", "-")}/{number}
Summary: This credible university source explains a distinct barrier affecting {topic}, including coordination delay, uncertainty, and unclear ownership.
Relevance: The evidence supports Relay because students need a specific executable action and an automatic way to pass completed work forward."""
        )
    return "\n\n".join(sections)


def analysis_submission(subject: str = "research evidence") -> str:
    return f"""Causes:
The supplied {subject} shows that students delay starting when ownership is vague and the first action is unclear. Source summaries repeatedly connect uncertainty with coordination overhead, so this analysis uses the completed dependency research directly.

Impact:
The research evidence also shows that delays propagate through dependent work. A specific claimable action reduces ambiguity, while automatic context handoff prevents the next member from waiting for information that has already been produced."""


def join(name: str) -> dict:
    response = client.post(f"/api/projects/{PROJECT_ID}/members", json={"name": name})
    assert response.status_code == 201
    return response.json()


def claim(task_id: str, member_id: str) -> dict:
    response = client.post(
        f"/api/tasks/{task_id}/claim", json={"member_id": member_id}
    )
    assert response.status_code == 200
    return response.json()


def submit(task_id: str, member_id: str, content: str) -> dict:
    response = client.post(
        f"/api/tasks/{task_id}/submit",
        json={"member_id": member_id, "content": content},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture(autouse=True)
def reset_storage() -> None:
    store.reset_demo()


def test_demo_reset_creates_repeatable_project() -> None:
    response = client.post("/api/demo/reset")

    assert response.status_code == 200
    assert response.json() == {
        "project_id": PROJECT_ID,
        "title": "Student Group Project Workflow",
        "task_count": 9,
        "available_task_count": 2,
    }


def test_two_starting_tasks_are_available() -> None:
    response = client.get(f"/api/projects/{PROJECT_ID}/available-tasks")

    assert response.status_code == 200
    assert {task["id"] for task in response.json()} == {
        "task-problem-research",
        "task-tool-research",
    }


def test_member_joins_using_only_trimmed_name() -> None:
    response = client.post(
        f"/api/projects/{PROJECT_ID}/members", json={"name": "  Kian  "}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Kian"
    assert set(response.json()) == {
        "id",
        "name",
        "claimed_task_ids",
        "total_estimated_minutes",
    }


def test_empty_member_name_is_rejected() -> None:
    response = client.post(
        f"/api/projects/{PROJECT_ID}/members", json={"name": "   "}
    )

    assert response.status_code == 422


def test_duplicate_member_name_is_rejected_case_insensitively() -> None:
    join("Kian")
    response = client.post(
        f"/api/projects/{PROJECT_ID}/members", json={"name": "kIaN"}
    )

    assert response.status_code == 409
    assert "already joined" in response.json()["detail"]


def test_available_task_can_be_claimed() -> None:
    member = join("Kian")
    result = claim("task-problem-research", member["id"])

    assert result["task"]["status"] == "in_progress"
    assert result["task"]["claimed_by"] == member["id"]


def test_task_cannot_be_claimed_twice() -> None:
    first = join("Kian")
    second = join("Ping")
    claim("task-problem-research", first["id"])

    response = client.post(
        "/api/tasks/task-problem-research/claim",
        json={"member_id": second["id"]},
    )

    assert response.status_code == 409
    assert "already been claimed" in response.json()["detail"]


def test_waiting_task_cannot_be_claimed() -> None:
    member = join("Kian")
    response = client.post(
        "/api/tasks/task-problem-analysis/claim",
        json={"member_id": member["id"]},
    )

    assert response.status_code == 409
    assert "blocked" in response.json()["detail"]


def test_member_workload_increases_after_claim() -> None:
    member = join("Kian")
    result = claim("task-problem-research", member["id"])

    assert result["member_workload_minutes"] == 30
    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    assert project["members"][0]["total_estimated_minutes"] == 30


def test_next_action_returns_claimed_task() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])

    response = client.get(f"/api/members/{member['id']}/next-action")

    assert response.status_code == 200
    assert response.json()["has_active_task"] is True
    assert response.json()["task_id"] == "task-problem-research"
    assert response.json()["first_action"]


def test_next_action_is_clear_when_member_has_no_task() -> None:
    member = join("Kian")
    response = client.get(f"/api/members/{member['id']}/next-action")

    assert response.status_code == 200
    assert response.json()["has_active_task"] is False


def test_empty_submission_is_rejected() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])
    response = client.post(
        "/api/tasks/task-problem-research/submit",
        json={"member_id": member["id"], "content": "   "},
    )

    assert response.status_code == 422


def test_incomplete_submission_sets_needs_revision() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])
    result = submit("task-problem-research", member["id"], "Source 1: Link: one")

    assert result["complete"] is False
    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    task = next(item for item in project["tasks"] if item["id"] == "task-problem-research")
    assert task["status"] == "needs_revision"
    assert result["missing_items"]


def test_incomplete_submission_does_not_unlock_dependent() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])
    result = submit("task-problem-research", member["id"], "Too short")

    assert result["newly_unlocked_tasks"] == []
    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    dependent = next(
        item for item in project["tasks"] if item["id"] == "task-problem-analysis"
    )
    assert dependent["status"] == "waiting"


def test_valid_submission_completes_task_and_clears_active_workload() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])
    result = submit(
        "task-problem-research", member["id"], research_submission()
    )

    assert result["complete"] is True
    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    completed = next(
        item for item in project["tasks"] if item["id"] == "task-problem-research"
    )
    assert completed["status"] == "completed"
    assert project["members"][0]["total_estimated_minutes"] == 0
    assert project["members"][0]["claimed_task_ids"] == []


def test_completing_task_unlocks_single_dependency_task() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])
    result = submit(
        "task-problem-research", member["id"], research_submission()
    )

    assert result["newly_unlocked_tasks"] == [
        {"id": "task-problem-analysis", "title": "Analyse the student pain point"}
    ]


def test_completed_submission_is_transferred_with_member_name_and_content() -> None:
    member = join("Ping")
    content = research_submission("student coordination")
    claim("task-problem-research", member["id"])
    submit("task-problem-research", member["id"], content)

    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    dependent = next(
        item for item in project["tasks"] if item["id"] == "task-problem-analysis"
    )
    context = dependent["dependency_context"][0]
    assert context["submitted_by"] == "Ping"
    assert context["content"] == content
    assert context["source_task_id"] == "task-problem-research"


def test_two_dependency_task_waits_after_only_one_branch_completes() -> None:
    member = join("Kian")
    claim("task-problem-research", member["id"])
    submit("task-problem-research", member["id"], research_submission())
    claim("task-problem-analysis", member["id"])
    result = submit(
        "task-problem-analysis", member["id"], analysis_submission()
    )

    assert result["newly_unlocked_tasks"] == []
    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    requirements = next(
        item for item in project["tasks"] if item["id"] == "task-solution-requirements"
    )
    assert requirements["status"] == "waiting"


def test_two_dependency_task_unlocks_with_context_after_both_branches() -> None:
    first = join("Kian")
    second = join("Ping")

    claim("task-problem-research", first["id"])
    submit("task-problem-research", first["id"], research_submission("pain point"))
    claim("task-problem-analysis", first["id"])
    submit("task-problem-analysis", first["id"], analysis_submission("source research"))

    claim("task-tool-research", second["id"])
    submit("task-tool-research", second["id"], research_submission("project tools"))
    claim("task-solution-comparison", second["id"])
    result = submit(
        "task-solution-comparison",
        second["id"],
        analysis_submission("tool research"),
    )

    assert result["newly_unlocked_tasks"] == [
        {
            "id": "task-solution-requirements",
            "title": "Define measurable Relay requirements",
        }
    ]
    project = client.get(f"/api/projects/{PROJECT_ID}").json()
    requirements = next(
        item for item in project["tasks"] if item["id"] == "task-solution-requirements"
    )
    assert requirements["status"] == "available"
    assert {item["submitted_by"] for item in requirements["dependency_context"]} == {
        "Kian",
        "Ping",
    }
    assert len(requirements["dependency_context"]) == 2


def test_submission_by_non_owner_is_rejected() -> None:
    owner = join("Kian")
    other = join("Ping")
    claim("task-problem-research", owner["id"])

    response = client.post(
        "/api/tasks/task-problem-research/submit",
        json={"member_id": other["id"], "content": research_submission()},
    )

    assert response.status_code == 403


def test_unclaimed_task_submission_is_rejected() -> None:
    member = join("Kian")
    response = client.post(
        "/api/tasks/task-problem-research/submit",
        json={"member_id": member["id"], "content": research_submission()},
    )

    assert response.status_code == 409
    assert "claimed" in response.json()["detail"]


def test_fair_assignment_selects_lowest_workload_with_stable_tie_break() -> None:
    first = join("Kian")
    second = join("Ping")
    join("Ari")
    claim("task-problem-research", first["id"])

    project = store.get_project(PROJECT_ID)
    selected = lowest_workload_member(project)

    assert selected is not None
    assert selected.id == second["id"]


def test_workload_warning_does_not_block_claim() -> None:
    busy = join("Kian")
    join("Ping")
    claim("task-problem-research", busy["id"])
    result = claim("task-tool-research", busy["id"])

    assert result["task"]["status"] == "in_progress"
    assert result["member_workload_minutes"] == 60
    assert "unbalanced" in result["workload_warning"]


def test_rubric_marks_are_not_double_counted() -> None:
    project = store.get_project(PROJECT_ID)
    coverage = rubric_coverage(project)

    status_total = (
        coverage["available_marks"]
        + coverage["in_progress_marks"]
        + coverage["completed_marks"]
        + coverage["waiting_marks"]
    )
    assert coverage["total_marks"] == 100
    assert coverage["covered_marks"] == 100
    assert status_total == 100
    assert coverage["uncovered_criteria"] == []


def test_invalid_dependency_reference_is_rejected() -> None:
    project = create_demo_project()
    project.tasks[0].dependencies = ["task-does-not-exist"]
    project.tasks[0].status = TaskStatus.WAITING

    with pytest.raises(ValueError, match="missing dependency"):
        validate_dependency_references(project)
    with pytest.raises(ValueError, match="missing dependency"):
        available_tasks(project)


def test_invalid_ids_return_useful_404_responses() -> None:
    assert client.get("/api/projects/missing").status_code == 404
    assert client.get("/api/members/missing/next-action").status_code == 404
    response = client.post(
        "/api/tasks/missing/claim", json={"member_id": "member-missing"}
    )
    assert response.status_code == 404
