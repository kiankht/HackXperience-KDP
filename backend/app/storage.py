from collections import defaultdict
from datetime import datetime, timezone

from .models import Member, Project, Submission, Task
from .sample_data import create_demo_project


class InMemoryStorage:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.submissions: dict[str, Submission] = {}
        self._member_sequence = 0
        self._submission_sequence = 0
        self.reset_demo()

    def reset_demo(self, *, preserve_other_projects: bool = False) -> Project:
        project = create_demo_project()
        if preserve_other_projects:
            previous_demo = self.projects.get(project.id)
            demo_submission_ids = {
                task.submission_id
                for task in previous_demo.tasks
                if task.submission_id is not None
            } if previous_demo else set()
            self.projects[project.id] = project
            self.submissions = {
                submission_id: submission
                for submission_id, submission in self.submissions.items()
                if submission_id not in demo_submission_ids
            }
        else:
            self.projects = {project.id: project}
            self.submissions = {}
            self._member_sequence = 0
            self._submission_sequence = 0
        return project

    def clear_all(self) -> None:
        self.projects = {}
        self.submissions = {}
        self._member_sequence = 0
        self._submission_sequence = 0

    def get_project(self, project_id: str) -> Project:
        project = self.projects.get(project_id)
        if project is None:
            raise KeyError("Project not found.")
        return project

    def add_project(self, project: Project) -> Project:
        if project.id in self.projects:
            raise ValueError("A project with this ID already exists.")
        self.projects[project.id] = project
        return project

    def get_task(self, task_id: str) -> tuple[Project, Task]:
        for project in self.projects.values():
            for task in project.tasks:
                if task.id == task_id:
                    return project, task
        raise KeyError("Task not found.")

    def get_member(self, member_id: str) -> tuple[Project, Member]:
        for project in self.projects.values():
            for member in project.members:
                if member.id == member_id:
                    return project, member
        raise KeyError("Member not found.")

    def add_member(self, project: Project, name: str) -> Member:
        if any(member.name.casefold() == name.casefold() for member in project.members):
            raise ValueError("A member with this name has already joined the project.")
        self._member_sequence += 1
        member = Member(id=f"member-{self._member_sequence}", name=name)
        project.members.append(member)
        return member

    def save_submission(
        self,
        *,
        task: Task,
        member: Member,
        content: str,
        complete: bool,
        feedback: str,
        missing_items: list[str],
    ) -> Submission:
        self._submission_sequence += 1
        submission = Submission(
            id=f"submission-{self._submission_sequence}",
            task_id=task.id,
            member_id=member.id,
            content=content,
            submitted_at=datetime.now(timezone.utc),
            validation_status="complete" if complete else "needs_revision",
            validation_feedback=feedback,
            missing_items=missing_items,
        )
        self.submissions[submission.id] = submission
        task.submission_id = submission.id
        return submission

    def completed_submission_for(self, task: Task) -> Submission | None:
        if task.submission_id is None:
            return None
        submission = self.submissions.get(task.submission_id)
        if submission and submission.validation_status == "complete":
            return submission
        return None

    def submissions_by_task(self) -> dict[str, list[Submission]]:
        grouped: dict[str, list[Submission]] = defaultdict(list)
        for submission in self.submissions.values():
            grouped[submission.task_id].append(submission)
        return grouped
