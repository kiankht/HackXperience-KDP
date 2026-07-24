import re
from datetime import datetime, timezone
from uuid import uuid4

from .ai_models import AITaskDefinition
from .models import ConfirmedProjectRequest, Project, RubricCriterion, Task, TaskStatus
from .workflow import validate_dependency_references


def _rubric_id(rubric: list[RubricCriterion], keywords: tuple[str, ...]) -> str:
    for item in rubric:
        text = f"{item.criterion} {item.description}".casefold()
        if any(keyword in text for keyword in keywords):
            return item.id
    return rubric[0].id


def _phase(
    key: str,
    title: str,
    description: str,
    minutes: int,
    output: list[str],
    first: str,
    steps: list[str],
    category: str,
    dependencies: list[str],
) -> dict[str, object]:
    return locals()


def _templates(payload: ConfirmedProjectRequest) -> list[dict[str, object]]:
    def short(value: str, limit: int = 72) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip().rstrip(".")
        return cleaned if len(cleaned) <= limit else f"{cleaned[:limit - 1].rstrip()}…"

    deliverables = [short(item) for item in payload.deliverables if item.strip()]
    requirements = [short(item, 110) for item in payload.requirements if item.strip()]
    deliverable_summary = "; ".join(deliverables)
    requirement_summary = "; ".join(requirements[:4])

    phases = [
        _phase("review", f"Map the brief for {short(payload.title, 48)}",
               f"Turn the uploaded brief into a shared checklist for: {deliverable_summary}.", 25,
               [f"A checklist for: {deliverable_summary}", f"Constraints and open questions from: {requirement_summary}"],
               f"Start by mapping the requirement “{requirements[0]}” to its deliverable.",
               [f"Review these requirements: {requirement_summary}.", "Map each requirement to a named deliverable.", "Record constraints and open questions."],
               "planning", []),
        _phase("research", f"Research evidence for {short(payload.title, 52)}",
               f"Find evidence that directly supports the required work: {deliverable_summary}.", 40,
               ["Three credible sources", "A summary and relevance note for each source"],
               f"Find one credible source relevant to “{deliverables[0]}”.",
               ["Find three assignment-relevant sources.", "Summarise each source.", f"Explain how each source supports: {deliverable_summary}."],
               "research", []),
        _phase("analyse", f"Turn research into decisions for {short(deliverables[0], 48)}",
               f"Convert the gathered evidence into decisions that guide: {deliverable_summary}.", 35,
               ["At least three evidence-based findings", "A comparison of alternatives", "A recommended direction"],
               "Review the passed research and identify the strongest recurring finding.",
               ["Identify patterns in the handed-off evidence.", "Compare relevant alternatives.", f"Recommend a direction for: {deliverable_summary}."],
               "analysis", ["research"]),
        _phase("requirements", f"Create acceptance checks for {short(payload.title, 48)}",
               f"Turn the assignment's own requirements into measurable checks: {requirement_summary}.", 35,
               [f"Acceptance checks covering: {requirement_summary}", "A named owner or target deliverable for every check"],
               f"Turn “{requirements[0]}” into a measurable acceptance check.",
               ["Review the brief checklist and handed-off research.", f"Write checks for: {requirement_summary}.", "Connect every check to a named deliverable."],
               "planning", ["review", "analyse"]),
    ]
    major: list[str] = []
    for index, deliverable in enumerate(deliverables[:5], start=1):
        key = f"deliverable-{index}"
        category = (
            "documentation"
            if re.search(r"\b(report|presentation|slides?|poster|video|documentation)\b", deliverable.casefold())
            else "implementation"
        )
        phases.append(
            _phase(
                key,
                f"Create: {deliverable}",
                f"Produce the assignment-specific deliverable “{deliverable}” using the accepted evidence and checks.",
                70,
                [f"A complete draft of “{deliverable}”", "Evidence showing which confirmed requirements it covers", "A short limitations or outstanding-work note"],
                f"Create the structure and first section/component of “{deliverable}”.",
                [f"Plan the parts of “{deliverable}”.", "Use the handed-off evidence and acceptance checks.", f"Produce and self-check “{deliverable}” against the brief."],
                category,
                ["requirements"],
            )
        )
        major.append(key)

    phases.append(
        _phase("finalise", f"Combine and submit: {short(payload.title, 48)}",
               f"Combine the completed work and check every requirement before submission: {deliverable_summary}.", 35,
               [f"Submission-ready versions of: {deliverable_summary}", "A completed requirement-coverage checklist", "Resolved issues or an explicit limitations list"],
               f"Collect the handed-off versions of: {deliverable_summary}.",
               [f"Combine and check: {deliverable_summary}.", f"Verify coverage of: {requirement_summary}.", "Resolve issues and confirm submission readiness."],
               "testing", list(dict.fromkeys(major)))
    )
    return phases[:10]


def _build(payload: ConfirmedProjectRequest, project_id: str) -> Project:
    category_keywords = {
        "research": ("research", "evidence", "problem", "investigation"),
        "analysis": ("analysis", "evaluation", "comparison", "discussion"),
        "planning": ("design", "architecture", "requirements", "innovation"),
        "implementation": ("implementation", "prototype", "functionality", "development"),
        "testing": ("testing", "validation", "quality"),
        "documentation": ("documentation", "communication", "presentation", "repository"),
    }
    templates = _templates(payload)
    id_map = {str(item["key"]): f"{project_id}-{item['key']}" for item in templates}
    tasks: list[Task] = []
    for item in templates:
        dependencies = [id_map[key] for key in item["dependencies"] if key in id_map]
        tasks.append(Task(
            id=id_map[str(item["key"])],
            project_id=project_id,
            title=str(item["title"]),
            description=str(item["description"]),
            objective=str(item["description"]),
            estimated_minutes=int(item["minutes"]),
            work_style="independent",
            required_output=list(item["output"]),
            first_action=str(item["first"]),
            execution_steps=list(item["steps"]),
            rubric_id=_rubric_id(payload.rubric, category_keywords[str(item["category"])]),
            dependencies=dependencies,
            unlocks=[],
            status=TaskStatus.AVAILABLE if not dependencies else TaskStatus.WAITING,
        ))
    task_lookup = {task.id: task for task in tasks}
    for task in tasks:
        for dependency in task.dependencies:
            task_lookup[dependency].unlocks.append(task.id)
    project = Project(
        id=project_id,
        title=payload.title,
        deadline=payload.deadline,
        deliverables=payload.deliverables,
        requirements=payload.requirements,
        rubric=payload.rubric,
        tasks=tasks,
        created_at=datetime.now(timezone.utc),
    )
    validate_generated_workflow(project, minimum_tasks=6, maximum_tasks=10)
    return project


def validate_generated_workflow(
    project: Project,
    *,
    minimum_tasks: int = 6,
    maximum_tasks: int = 12,
) -> None:
    validate_dependency_references(project)
    rubric_ids = {criterion.id for criterion in project.rubric}
    if len(project.tasks) < minimum_tasks or len(project.tasks) > maximum_tasks:
        raise ValueError(
            f"Generated workflow must contain {minimum_tasks} to {maximum_tasks} tasks."
        )
    if not any(task.status == TaskStatus.AVAILABLE for task in project.tasks):
        raise ValueError("Generated workflow must have at least one starting task.")
    for task in project.tasks:
        if task.rubric_id not in rubric_ids:
            raise ValueError(f"Task '{task.id}' references a missing rubric criterion.")
        if not task.required_output or not task.first_action or not task.execution_steps:
            raise ValueError(f"Task '{task.id}' is missing executable instructions.")
        expected_unlocks = {candidate.id for candidate in project.tasks if task.id in candidate.dependencies}
        if set(task.unlocks) != expected_unlocks:
            raise ValueError(f"Task '{task.id}' has inconsistent unlock relationships.")
    if minimum_tasks == 6 and maximum_tasks == 10:
        if sum(task.status == TaskStatus.AVAILABLE for task in project.tasks) < 2:
            raise ValueError("Deterministic workflow must have at least two starting tasks.")
        if not any(len(task.dependencies) >= 2 for task in project.tasks):
            raise ValueError("Deterministic workflow must include a task with two dependencies.")


def build_project(payload: ConfirmedProjectRequest) -> tuple[Project, list[str]]:
    project_id = f"project-custom-{uuid4().hex[:10]}"
    try:
        return _build(payload, project_id), []
    except (ValueError, KeyError):
        # A compact generic input forces the safe base phases while preserving confirmed data.
        fallback = payload.model_copy(update={
            "deliverables": ["Final assignment submission"],
            "requirements": ["Review, research, plan, produce, test, and finalise the assignment."],
        })
        project = _build(fallback, project_id)
        project.deliverables = payload.deliverables
        project.requirements = payload.requirements
        return project, ["Relay used a safe generic workflow because the tailored workflow could not be validated."]


def build_project_from_ai(
    payload: ConfirmedProjectRequest,
    task_definitions: list[AITaskDefinition],
) -> Project:
    raw_ids = [task.id for task in task_definitions]
    if len(raw_ids) != len(set(raw_ids)):
        raise ValueError("AI workflow contains duplicate task IDs.")
    raw_lookup = set(raw_ids)
    for task in task_definitions:
        for dependency in task.dependencies:
            if dependency not in raw_lookup:
                raise ValueError(f"Task '{task.id}' references missing dependency '{dependency}'.")
        for unlocked in task.unlocks:
            if unlocked not in raw_lookup:
                raise ValueError(f"Task '{task.id}' references missing unlock '{unlocked}'.")
        expected = {
            candidate.id
            for candidate in task_definitions
            if task.id in candidate.dependencies
        }
        if set(task.unlocks) != expected:
            raise ValueError(f"Task '{task.id}' has mismatched unlock relationships.")

    project_id = f"project-custom-{uuid4().hex[:10]}"
    internal_ids = {
        raw_id: f"{project_id}-{re.sub(r'[^a-z0-9]+', '-', raw_id.casefold()).strip('-')}"
        for raw_id in raw_ids
    }
    rubric_ids = {criterion.id for criterion in payload.rubric}
    tasks: list[Task] = []
    for definition in task_definitions:
        if definition.rubric_id not in rubric_ids:
            raise ValueError(
                f"Task '{definition.id}' references invalid rubric ID '{definition.rubric_id}'."
            )
        dependencies = [internal_ids[item] for item in definition.dependencies]
        tasks.append(Task(
            id=internal_ids[definition.id],
            project_id=project_id,
            title=definition.title,
            description=definition.description,
            objective=definition.objective,
            estimated_minutes=definition.estimated_minutes,
            work_style=definition.work_style,
            required_output=definition.required_output,
            first_action=definition.first_action,
            execution_steps=definition.execution_steps,
            rubric_id=definition.rubric_id,
            dependencies=dependencies,
            unlocks=[internal_ids[item] for item in definition.unlocks],
            status=TaskStatus.AVAILABLE if not dependencies else TaskStatus.WAITING,
        ))
    project = Project(
        id=project_id,
        title=payload.title,
        deadline=payload.deadline,
        deliverables=payload.deliverables,
        requirements=payload.requirements,
        rubric=payload.rubric,
        tasks=tasks,
        created_at=datetime.now(timezone.utc),
    )
    validate_generated_workflow(project)
    return project
