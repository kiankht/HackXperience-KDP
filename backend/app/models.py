from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, ValidationInfo, field_validator


ASSIGNMENT_BRIEF_MIN_LENGTH = 80
ASSIGNMENT_BRIEF_MAX_LENGTH = 30_000
RUBRIC_TEXT_MIN_LENGTH = 30
RUBRIC_TEXT_MAX_LENGTH = 20_000
PROJECT_TITLE_MAX_LENGTH = 160


class TaskStatus(str, Enum):
    AVAILABLE = "available"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    NEEDS_REVISION = "needs_revision"
    COMPLETED = "completed"


class RubricCriterion(BaseModel):
    id: str
    criterion: str
    description: str
    marks: int = Field(ge=0)

    @field_validator("id", "criterion")
    @classmethod
    def validate_required_rubric_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Rubric IDs and criterion names must not be empty.")
        return cleaned


class DependencyContext(BaseModel):
    source_task_id: str
    source_task_title: str
    submitted_by: str
    content: str
    submitted_at: datetime


class Member(BaseModel):
    id: str
    name: str
    claimed_task_ids: list[str] = Field(default_factory=list)
    total_estimated_minutes: int = 0


class Task(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    objective: str
    estimated_minutes: int = Field(gt=0)
    work_style: str
    required_output: list[str]
    first_action: str
    execution_steps: list[str]
    rubric_id: str
    dependencies: list[str] = Field(default_factory=list)
    unlocks: list[str] = Field(default_factory=list)
    status: TaskStatus
    claimed_by: str | None = None
    submission_id: str | None = None
    dependency_context: list[DependencyContext] = Field(default_factory=list)
    due_date: str | None = None
    available_since: datetime | None = None
    auto_claim_at: datetime | None = None


class Submission(BaseModel):
    id: str
    task_id: str
    member_id: str
    content: str
    submitted_at: datetime
    validation_status: str
    validation_feedback: str
    missing_items: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    title: str
    deadline: str | None
    deliverables: list[str]
    requirements: list[str]
    rubric: list[RubricCriterion]
    members: list[Member] = Field(default_factory=list)
    tasks: list[Task]
    created_at: datetime


class JoinProjectRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name must not be empty.")
        return cleaned


class ClaimTaskRequest(BaseModel):
    member_id: str


class SubmitTaskRequest(BaseModel):
    member_id: str
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Submission content must not be empty.")
        return cleaned


class AssignmentAnalysisRequest(BaseModel):
    title: str | None = Field(default=None, max_length=PROJECT_TITLE_MAX_LENGTH)
    deadline: str | None = None
    assignment_brief: str = Field(
        min_length=ASSIGNMENT_BRIEF_MIN_LENGTH,
        max_length=ASSIGNMENT_BRIEF_MAX_LENGTH,
    )
    rubric_text: str = Field(
        min_length=RUBRIC_TEXT_MIN_LENGTH,
        max_length=RUBRIC_TEXT_MAX_LENGTH,
    )

    @field_validator("title", "deadline", mode="before")
    @classmethod
    def clean_optional_text(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("assignment_brief", "rubric_text")
    @classmethod
    def clean_required_text(cls, value: str, info: ValidationInfo) -> str:
        cleaned = value.strip()
        minimum = (
            ASSIGNMENT_BRIEF_MIN_LENGTH
            if info.field_name == "assignment_brief"
            else RUBRIC_TEXT_MIN_LENGTH
        )
        if len(cleaned) < minimum:
            raise ValueError(f"{info.field_name.replace('_', ' ').title()} is too short.")
        return cleaned

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                parsed = date.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Deadline must use YYYY-MM-DD format.") from error
            if parsed < date.today():
                raise ValueError("Deadline cannot be earlier than today.")
        return value


class AssignmentSourceSummary(BaseModel):
    assignment_character_count: int
    rubric_character_count: int


class AssignmentAnalysisResult(BaseModel):
    suggested_title: str
    suggested_deadline: str | None
    deliverables: list[str]
    requirements: list[str]
    rubric: list[RubricCriterion]
    extraction_warnings: list[str]
    analysis_notes: list[str] = Field(default_factory=list)
    source_summary: AssignmentSourceSummary


class ConfirmedProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=PROJECT_TITLE_MAX_LENGTH)
    deadline: str | None = None
    deliverables: list[str] = Field(min_length=1, max_length=20)
    requirements: list[str] = Field(min_length=1, max_length=30)
    rubric: list[RubricCriterion] = Field(min_length=1, max_length=20)
    original_assignment_brief: str = Field(
        min_length=ASSIGNMENT_BRIEF_MIN_LENGTH,
        max_length=ASSIGNMENT_BRIEF_MAX_LENGTH,
    )
    original_rubric_text: str = Field(
        min_length=RUBRIC_TEXT_MIN_LENGTH,
        max_length=RUBRIC_TEXT_MAX_LENGTH,
    )

    @field_validator(
        "title",
        "original_assignment_brief",
        "original_rubric_text",
    )
    @classmethod
    def clean_confirmed_text(cls, value: str, info: ValidationInfo) -> str:
        cleaned = value.strip()
        minimums = {
            "title": 1,
            "original_assignment_brief": ASSIGNMENT_BRIEF_MIN_LENGTH,
            "original_rubric_text": RUBRIC_TEXT_MIN_LENGTH,
        }
        if len(cleaned) < minimums[info.field_name]:
            raise ValueError(f"{info.field_name.replace('_', ' ').title()} is too short.")
        return cleaned

    @field_validator("deadline")
    @classmethod
    def validate_confirmed_deadline(cls, value: str | None) -> str | None:
        if value:
            try:
                parsed = date.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Deadline must use YYYY-MM-DD format.") from error
            if parsed < date.today():
                raise ValueError("Deadline cannot be earlier than today.")
        return value or None

    @field_validator("deliverables", "requirements")
    @classmethod
    def validate_text_items(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty item is required.")
        return list(dict.fromkeys(cleaned))
