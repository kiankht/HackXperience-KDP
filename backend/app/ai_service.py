import json
from dataclasses import dataclass

from openai import OpenAI

from .ai_models import (
    AIAssignmentAnalysis,
    AISubmissionValidation,
    AIWorkflowDefinition,
    AIProjectChatResponse,
)
from .analysis import analyze_assignment
from .config import Settings
from .models import (
    AssignmentAnalysisRequest,
    AssignmentAnalysisResult,
    AssignmentSourceSummary,
    ConfirmedProjectRequest,
    Project,
    Submission,
    Task,
)
from .project_builder import build_project, build_project_from_ai
from .prompts import (
    ASSIGNMENT_ANALYSIS_PROMPT,
    SUBMISSION_VALIDATION_PROMPT,
    WORKFLOW_GENERATION_PROMPT,
    PROJECT_CHAT_PROMPT,
)
from .workflow import ValidationResult, validate_submission


class AIServiceError(RuntimeError):
    pass


class AIConfigurationError(AIServiceError):
    pass


@dataclass
class ProjectGenerationResult:
    project: Project
    mode: str
    warnings: list[str]


@dataclass
class SubmissionCheckResult:
    validation: AISubmissionValidation
    mode: str


class AIService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self.settings = settings or Settings.from_environment()
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.settings.openai_api_key)

    @property
    def real_enabled(self) -> bool:
        return self.settings.ai_mode != "fallback" and self.configured

    def status(self) -> dict[str, object]:
        if self.settings.ai_mode == "real" and not self.configured:
            mode = "unavailable"
        elif self.real_enabled:
            mode = "real"
        else:
            mode = "fallback"
        return {
            "mode": mode,
            "provider": "openai",
            "configured": self.configured,
            "model": self.settings.openai_model,
            "fallback_available": True,
        }

    def _require_or_fallback(self) -> bool:
        if self.settings.ai_mode == "real" and not self.configured:
            raise AIConfigurationError(
                "Real AI mode requires OPENAI_API_KEY in the backend environment."
            )
        return self.real_enabled

    def _openai_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.ai_timeout_seconds,
                max_retries=0,
            )
        return self._client

    def _parse(self, *, instructions: str, content: str, schema: type):
        response = self._openai_client().responses.parse(
            model=self.settings.openai_model,
            instructions=instructions,
            input=content,
            text_format=schema,
            timeout=self.settings.ai_timeout_seconds,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise AIServiceError("The AI provider did not return valid structured output.")
        return parsed

    def analyze_assignment(
        self,
        payload: AssignmentAnalysisRequest,
    ) -> tuple[AssignmentAnalysisResult, str]:
        if not self._require_or_fallback():
            return analyze_assignment(payload), "fallback"
        content = (
            "USER-PROVIDED TITLE:\n"
            f"{payload.title or '(none)'}\n\nUSER-PROVIDED DEADLINE:\n"
            f"{payload.deadline or '(none)'}\n\nUNTRUSTED ASSIGNMENT DOCUMENT:\n"
            f"{payload.assignment_brief}\n\nUNTRUSTED RUBRIC DOCUMENT:\n{payload.rubric_text}"
        )
        try:
            parsed: AIAssignmentAnalysis = self._parse(
                instructions=ASSIGNMENT_ANALYSIS_PROMPT,
                content=content,
                schema=AIAssignmentAnalysis,
            )
        except Exception as error:
            if self.settings.ai_mode == "real":
                raise AIServiceError(
                    "Relay could not complete AI assignment analysis. Check the backend AI configuration and try again."
                ) from error
            result = analyze_assignment(payload)
            result.extraction_warnings.append(
                "AI analysis was unavailable, so Relay used deterministic fallback analysis."
            )
            return result, "fallback"
        return AssignmentAnalysisResult(
            suggested_title=payload.title or parsed.suggested_title,
            suggested_deadline=payload.deadline or parsed.suggested_deadline,
            deliverables=parsed.deliverables,
            requirements=parsed.requirements,
            rubric=parsed.rubric,
            extraction_warnings=parsed.extraction_warnings,
            analysis_notes=parsed.analysis_notes,
            source_summary=AssignmentSourceSummary(
                assignment_character_count=len(payload.assignment_brief),
                rubric_character_count=len(payload.rubric_text),
            ),
        ), "ai"

    def generate_project(
        self,
        payload: ConfirmedProjectRequest,
    ) -> ProjectGenerationResult:
        if not self._require_or_fallback():
            project, warnings = build_project(payload)
            return ProjectGenerationResult(project, "fallback", warnings)
        content = json.dumps(
            {
                "confirmed_title": payload.title,
                "confirmed_deadline": payload.deadline,
                "confirmed_deliverables": payload.deliverables,
                "confirmed_requirements": payload.requirements,
                "confirmed_rubric": [item.model_dump() for item in payload.rubric],
                "untrusted_original_assignment": payload.original_assignment_brief,
                "untrusted_original_rubric": payload.original_rubric_text,
            },
            ensure_ascii=False,
        )
        validation_error = ""
        for attempt in range(2):
            try:
                instructions = WORKFLOW_GENERATION_PROMPT
                if attempt:
                    instructions += (
                        "\n\nREPAIR THE PREVIOUS WORKFLOW. Validation error: "
                        f"{validation_error}. Return a complete corrected workflow only."
                    )
                parsed: AIWorkflowDefinition = self._parse(
                    instructions=instructions,
                    content=content,
                    schema=AIWorkflowDefinition,
                )
            except Exception as error:
                if self.settings.ai_mode == "real":
                    raise AIServiceError(
                        "Relay could not complete AI workflow generation. Check the backend AI configuration and try again."
                    ) from error
                validation_error = str(error)[:500]
                continue
            try:
                return ProjectGenerationResult(
                    build_project_from_ai(payload, parsed.tasks),
                    "ai",
                    [],
                )
            except ValueError as error:
                validation_error = str(error)[:500]
        project, warnings = build_project(payload)
        warnings.append(
            "AI workflow generation was unavailable, so Relay created a safe fallback workflow."
        )
        return ProjectGenerationResult(project, "fallback", list(dict.fromkeys(warnings)))

    def validate_submission(
        self,
        *,
        task: Task,
        content: str,
        force_fallback: bool = False,
    ) -> SubmissionCheckResult:
        use_real = False if force_fallback else self._require_or_fallback()
        if not use_real:
            fallback: ValidationResult = validate_submission(task, content)
            return SubmissionCheckResult(
                AISubmissionValidation(
                    complete=fallback.complete,
                    missing_items=fallback.missing_items,
                    feedback=fallback.feedback,
                    evidence_found=[],
                    should_unlock_dependents=fallback.complete,
                ),
                "fallback",
            )
        payload = json.dumps(
            {
                "task_title": task.title,
                "objective": task.objective,
                "description": task.description,
                "required_outputs": task.required_output,
                "execution_steps": task.execution_steps,
                "dependency_context": [
                    {
                        "source_task_title": item.source_task_title,
                        "submitted_by": item.submitted_by,
                        "content": item.content,
                    }
                    for item in task.dependency_context
                ],
                "untrusted_student_submission": content,
            },
            ensure_ascii=False,
        )
        try:
            validation: AISubmissionValidation = self._parse(
                instructions=SUBMISSION_VALIDATION_PROMPT,
                content=payload,
                schema=AISubmissionValidation,
            )
            return SubmissionCheckResult(validation, "ai")
        except Exception as error:
            if self.settings.ai_mode == "real":
                raise AIServiceError(
                    "Relay could not complete AI submission checking. Try again or use fallback mode."
                ) from error
            fallback = validate_submission(task, content)
            return SubmissionCheckResult(
                AISubmissionValidation(
                    complete=fallback.complete,
                    missing_items=fallback.missing_items,
                    feedback=fallback.feedback,
                    evidence_found=[],
                    should_unlock_dependents=fallback.complete,
                ),
                "fallback",
            )

    def chat_about_project(
        self,
        *,
        project: Project,
        submissions: dict[str, Submission],
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[AIProjectChatResponse, str]:
        history = history or []
        lowered = question.casefold()
        scope_words = {
            "relay", "assignment", "task", "workflow", "rubric", "deadline",
            "submission", "member", "progress", "requirement", "deliverable",
            "project", "next", "work", "answer", "combine", "report",
            "presentation", "research", "dependency", "status",
        }
        project_words = {
            word.casefold().strip(".,:;!?()")
            for text in [project.title, *project.deliverables, *project.requirements,
                         *(task.title for task in project.tasks)]
            for word in text.split()
            if len(word) >= 4
        }
        in_scope = any(word in lowered for word in scope_words | project_words)
        available_titles = [
            task.title for task in project.tasks if task.status.value == "available"
        ]
        suggestions = [
            "What should I work on next?",
            "How much of this assignment is complete?",
            "Which rubric criteria should we focus on?",
        ]
        if available_titles:
            suggestions[0] = f"How do I start “{available_titles[0]}”?"
        refusal = AIProjectChatResponse(
            in_scope=False,
            answer=(
                f"I can connect that back to “{project.title}” instead. "
                "Try one of these project-focused questions:"
            ),
            suggested_questions=suggestions,
        )
        repeated = any(
            item.get("role") == "user"
            and item.get("content", "").casefold().strip() == lowered.strip()
            for item in history
        )
        if not in_scope:
            if repeated:
                refusal.answer = (
                    "It looks like that question still is not getting you unstuck. "
                    f"Let’s bring it back to “{project.title}” with one small next step."
                )
            return refusal, "scope-filter"

        completed = [task for task in project.tasks if task.status.value == "completed"]
        available = [task for task in project.tasks if task.status.value == "available"]
        active = [
            task for task in project.tasks
            if task.status.value in {"in_progress", "needs_revision"}
        ]
        if not self._require_or_fallback():
            if "rubric" in lowered:
                answer = "Rubric coverage:\n" + "\n".join(
                    f"- {item.criterion}: {item.marks} marks — {item.description}"
                    for item in project.rubric
                )
            elif any(word in lowered for word in ("progress", "status", "finished", "complete")):
                answer = (
                    f"{len(completed)} of {len(project.tasks)} tasks are complete. "
                    f"{len(active)} are in progress and {len(available)} are available."
                )
            elif any(word in lowered for word in ("next", "available", "start")):
                answer = "Ready work:\n" + (
                    "\n".join(f"- {task.title}: {task.first_action}" for task in available)
                    or "No unclaimed task is currently ready. Check the workflow for blockers."
                )
            elif "deadline" in lowered:
                answer = (
                    f"The assignment deadline is {project.deadline}."
                    if project.deadline else "No deadline is currently set for this assignment."
                )
            elif any(word in lowered for word in ("member", "team", "owner")):
                answer = "Project members: " + (
                    ", ".join(member.name for member in project.members)
                    or "No members have joined yet."
                )
            else:
                matching = [
                    task for task in project.tasks
                    if any(word in lowered for word in task.title.casefold().split() if len(word) > 3)
                ]
                if matching:
                    task = matching[0]
                    answer = (
                        f"{task.title}: {task.objective}\n"
                        f"Start with: {task.first_action}\n"
                        f"Required output: {', '.join(task.required_output)}"
                    )
                else:
                    answer = (
                        f"This Relay project is “{project.title}”. It has "
                        f"{len(project.tasks)} tasks and {len(completed)} are complete. "
                        "Ask me about a task, the rubric, progress, or what to do next."
                    )
            if repeated:
                first_ready = available[0] if available else None
                answer = (
                    "You asked this again, so let’s make it more concrete. "
                    + (
                        f"Open “{first_ready.title}” and do only this first: "
                        f"{first_ready.first_action}"
                        if first_ready
                        else "Open Workflow, identify the first waiting task, and check which dependency blocks it."
                    )
                )
            elif history:
                answer += "\n\nA useful next move is to choose one suggestion below and narrow the question."
            return AIProjectChatResponse(
                in_scope=True,
                answer=answer,
                suggested_questions=suggestions,
            ), "fallback"

        context = {
            "project": project.model_dump(mode="json"),
            "accepted_submissions": [
                {
                    "task_id": submission.task_id,
                    "content": submission.content[:4_000],
                }
                for submission in submissions.values()
                if submission.validation_status == "complete"
                and any(
                    task.id == submission.task_id for task in project.tasks
                )
            ],
            "question": question,
            "conversation_history": history[-12:],
        }
        try:
            response: AIProjectChatResponse = self._parse(
                instructions=PROJECT_CHAT_PROMPT,
                content=json.dumps(context, ensure_ascii=False),
                schema=AIProjectChatResponse,
            )
            if not response.in_scope:
                return refusal, "ai"
            if not response.suggested_questions:
                response.suggested_questions = suggestions
            return response, "ai"
        except Exception as error:
            if self.settings.ai_mode == "real":
                raise AIServiceError("RelyRelay.ai could not answer right now.") from error
            return AIProjectChatResponse(
                in_scope=True,
                answer="AI chat is temporarily unavailable. Try asking about progress, the rubric, or ready tasks.",
                suggested_questions=suggestions,
            ), "fallback"
