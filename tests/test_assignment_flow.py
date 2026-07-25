import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.app.analysis import analyze_assignment
from backend.app.main import app, store
from backend.app.models import AssignmentAnalysisRequest, TaskStatus
from backend.app.project_builder import validate_generated_workflow


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_storage() -> None:
    store.reset_demo()


def sample() -> dict:
    response = client.get("/api/samples/assignment")
    assert response.status_code == 200
    return response.json()


def analysed_sample() -> tuple[dict, dict]:
    source = sample()
    response = client.post("/api/assignments/analyze", json=source)
    assert response.status_code == 200
    return source, response.json()


def confirmed_payload(source: dict, analysis: dict) -> dict:
    return {
        "title": analysis["suggested_title"],
        "deadline": analysis["suggested_deadline"],
        "deliverables": analysis["deliverables"],
        "requirements": analysis["requirements"],
        "rubric": analysis["rubric"],
        "original_assignment_brief": source["assignment_brief"],
        "original_rubric_text": source["rubric_text"],
    }


def create_custom_project() -> tuple[str, dict]:
    source, analysis = analysed_sample()
    response = client.post(
        "/api/projects/from-analysis",
        json=confirmed_payload(source, analysis),
    )
    assert response.status_code == 201
    return response.json()["project_id"], response.json()


def test_sample_assignment_endpoint_returns_usable_content() -> None:
    payload = sample()
    assert payload["title"] == "Agentic Workflow Automation Prototype"
    assert len(payload["assignment_brief"]) >= 80
    assert len(payload["rubric_text"]) >= 30


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assignment_brief", ""),
        ("assignment_brief", " " * 100),
        ("rubric_text", ""),
        ("assignment_brief", "Too short"),
        ("rubric_text", "Short"),
    ],
)
def test_analysis_rejects_empty_and_short_text(field: str, value: str) -> None:
    payload = sample()
    payload[field] = value
    assert client.post("/api/assignments/analyze", json=payload).status_code == 422


def test_entered_title_and_deadline_are_preserved() -> None:
    payload = sample()
    payload.update({"title": "  My Project  ", "deadline": "2026-09-01"})
    result = client.post("/api/assignments/analyze", json=payload).json()
    assert result["suggested_title"] == "My Project"
    assert result["suggested_deadline"] == "2026-09-01"


def test_past_deadline_is_rejected() -> None:
    payload = sample()
    payload["deadline"] = "2020-01-01"
    response = client.post("/api/assignments/analyze", json=payload)
    assert response.status_code == 422
    assert "Deadline cannot be earlier than today" in response.text


def test_heading_and_labelled_deadline_are_extracted() -> None:
    result = analyze_assignment(AssignmentAnalysisRequest(
        assignment_brief=(
            "Community Accessibility Website\n"
            "Due date: 3 September 2026\n"
            "The team must research accessibility barriers and build a useful website. "
            "The final submission should include testing and a presentation."
        ),
        rubric_text=(
            "Research quality — 30 marks\nImplementation (40%)\n"
            "Testing and presentation | 30 marks"
        ),
    ))
    assert result.suggested_title == "Community Accessibility Website"
    assert result.suggested_deadline == "2026-09-03"


def test_missing_deadline_produces_warning() -> None:
    payload = sample()
    payload["deadline"] = None
    payload["assignment_brief"] = payload["assignment_brief"].replace(
        "Deadline: 15 August 2026", ""
    )
    result = client.post("/api/assignments/analyze", json=payload).json()
    assert "No explicit deadline was found." in result["extraction_warnings"]


def test_rubric_can_be_generated_from_assignment_without_rubric_file() -> None:
    source = sample()
    response = client.post(
        "/api/assignments/generate-rubric",
        json={
            "title": source["title"],
            "assignment_brief": source["assignment_brief"],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["generation_mode"] == "fallback"
    assert 3 <= len(result["rubric"]) <= 8
    assert sum(item["marks"] for item in result["rubric"]) == 100
    assert "not an official lecturer rubric" in result["disclaimer"]


def test_deliverables_and_requirements_are_clean_and_deduplicated() -> None:
    payload = sample()
    payload["assignment_brief"] += (
        "\n- Build a working prototype.\n- Build a working prototype."
        "\nThe team must submit source code."
    )
    result = client.post("/api/assignments/analyze", json=payload).json()
    assert len(result["deliverables"]) == len(set(result["deliverables"]))
    assert any("Build a working" in item for item in result["requirements"])
    assert any("must submit" in item for item in result["requirements"])


def test_rubric_marks_percentages_and_slash_values_are_extracted() -> None:
    payload = sample()
    payload["rubric_text"] = (
        "Research quality — 20 marks\n"
        "Critical analysis: 25\n"
        "Implementation (35%)\n"
        "Presentation /20"
    )
    result = client.post("/api/assignments/analyze", json=payload).json()
    assert [item["marks"] for item in result["rubric"]] == [20, 25, 35, 20]
    assert sum(item["marks"] for item in result["rubric"]) == 100


def test_non_100_rubric_warns_and_unrecognised_rubric_falls_back() -> None:
    payload = sample()
    payload["rubric_text"] = "Research — 40 marks\nImplementation — 50 marks"
    result = client.post("/api/assignments/analyze", json=payload).json()
    assert "Rubric marks total 90 rather than 100." in result["extraction_warnings"]

    payload["rubric_text"] = "Lecturer feedback will explain the marking approach."
    fallback = client.post("/api/assignments/analyze", json=payload).json()
    assert sum(item["marks"] for item in fallback["rubric"]) == 100
    assert any("fallback rubric" in warning for warning in fallback["extraction_warnings"])


def test_confirmed_analysis_creates_valid_dependency_aware_project() -> None:
    project_id, metadata = create_custom_project()
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    project = store.get_project(project_id)

    assert 6 <= metadata["task_count"] <= 10
    assert metadata["available_task_count"] >= 2
    assert len([task for task in project.tasks if task.status == TaskStatus.AVAILABLE]) >= 2
    validate_generated_workflow(project)
    assert all(task.required_output and task.first_action and task.execution_steps for task in project.tasks)
    assert {task.rubric_id for task in project.tasks} <= {item.id for item in project.rubric}
    task_text = " ".join(
        text
        for task in project.tasks
        for text in [task.title, task.description, *task.required_output]
    )
    for deliverable in project.deliverables:
        assert deliverable.rstrip(".") in task_text
    assert all(task.due_date for task in project.tasks)
    assert max(task.due_date for task in project.tasks) <= project.deadline


def test_overdue_unclaimed_task_is_automatically_assigned() -> None:
    project_id, _ = create_custom_project()
    first = client.post(f"/api/projects/{project_id}/members", json={"name": "Ari"}).json()
    client.post(f"/api/projects/{project_id}/members", json={"name": "Bea"})
    project = store.get_project(project_id)
    task = next(item for item in project.tasks if item.status == TaskStatus.AVAILABLE)
    task.auto_claim_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    client.get(f"/api/projects/{project_id}/available-tasks")

    assert task.claimed_by == first["id"]
    assert task.status == TaskStatus.IN_PROGRESS


def test_custom_project_supports_join_claim_submit_and_handoff() -> None:
    project_id, _ = create_custom_project()
    member = client.post(
        f"/api/projects/{project_id}/members", json={"name": "Kian"}
    ).json()
    tasks = client.get(f"/api/projects/{project_id}/available-tasks").json()
    research = next(task for task in tasks if "Research" in task["title"])

    claim = client.post(
        f"/api/tasks/{research['id']}/claim", json={"member_id": member["id"]}
    )
    assert claim.status_code == 200
    content = (
        "Completed output: Three credible sources were reviewed and summarised. "
        "Each source includes a relevance explanation connecting the evidence to "
        "the assignment problem, existing approaches, and the recommended direction."
    )
    submitted = client.post(
        f"/api/tasks/{research['id']}/submit",
        json={"member_id": member["id"], "content": content},
    )
    assert submitted.status_code == 200
    assert submitted.json()["complete"] is True
    assert submitted.json()["newly_unlocked_tasks"]

    unlocked_id = submitted.json()["newly_unlocked_tasks"][0]["id"]
    second = client.post(
        f"/api/projects/{project_id}/members", json={"name": "Ping"}
    ).json()
    assert client.post(
        f"/api/tasks/{unlocked_id}/claim", json={"member_id": second["id"]}
    ).status_code == 200
    action = client.get(f"/api/members/{second['id']}/next-action").json()
    assert action["dependency_context"][0]["content"] == content
    assert action["dependency_context"][0]["submitted_by"] == "Kian"


def test_demo_reset_remains_available_after_custom_project_creation() -> None:
    create_custom_project()
    reset = client.post("/api/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["project_id"] == "project-relay-demo"
    assert reset.json()["available_task_count"] == 2
