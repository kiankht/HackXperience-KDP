from pydantic import BaseModel, Field, field_validator, model_validator

from .models import RubricCriterion


class AIAssignmentAnalysis(BaseModel):
    suggested_title: str
    suggested_deadline: str | None = None
    deliverables: list[str] = Field(min_length=1, max_length=20)
    requirements: list[str] = Field(min_length=1, max_length=30)
    rubric: list[RubricCriterion] = Field(min_length=1, max_length=20)
    extraction_warnings: list[str] = Field(default_factory=list)
    analysis_notes: list[str] = Field(default_factory=list, max_length=10)


class AITaskDefinition(BaseModel):
    id: str
    title: str
    description: str
    objective: str
    estimated_minutes: int = Field(ge=5, le=480)
    work_style: str
    required_output: list[str] = Field(min_length=1, max_length=12)
    first_action: str
    execution_steps: list[str] = Field(min_length=1, max_length=12)
    rubric_id: str
    dependencies: list[str] = Field(default_factory=list)
    unlocks: list[str] = Field(default_factory=list)

    @field_validator("id", "title", "description", "objective", "work_style", "first_action", "rubric_id")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task text fields must not be empty.")
        return cleaned

    @model_validator(mode="after")
    def reject_self_dependency(self) -> "AITaskDefinition":
        if self.id in self.dependencies or self.id in self.unlocks:
            raise ValueError(f"Task '{self.id}' cannot depend on or unlock itself.")
        return self


class AIWorkflowDefinition(BaseModel):
    tasks: list[AITaskDefinition] = Field(min_length=6, max_length=12)


class AISubmissionValidation(BaseModel):
    complete: bool
    missing_items: list[str] = Field(default_factory=list)
    feedback: str
    evidence_found: list[str] = Field(default_factory=list)
    should_unlock_dependents: bool

    @model_validator(mode="after")
    def normalise_completion(self) -> "AISubmissionValidation":
        if self.complete and (self.missing_items or not self.should_unlock_dependents):
            self.complete = False
            self.should_unlock_dependents = False
        if not self.complete:
            self.should_unlock_dependents = False
        return self
