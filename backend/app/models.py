from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


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
