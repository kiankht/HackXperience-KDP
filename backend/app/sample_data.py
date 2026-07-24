from datetime import datetime, timezone

from .models import Project, RubricCriterion, Task, TaskStatus


DEMO_PROJECT_ID = "project-relay-demo"


def _task(
    *,
    task_id: str,
    title: str,
    description: str,
    objective: str,
    minutes: int,
    required_output: list[str],
    first_action: str,
    steps: list[str],
    rubric_id: str,
    dependencies: list[str],
    unlocks: list[str],
) -> Task:
    return Task(
        id=task_id,
        project_id=DEMO_PROJECT_ID,
        title=title,
        description=description,
        objective=objective,
        estimated_minutes=minutes,
        work_style="independent",
        required_output=required_output,
        first_action=first_action,
        execution_steps=steps,
        rubric_id=rubric_id,
        dependencies=dependencies,
        unlocks=unlocks,
        status=TaskStatus.AVAILABLE if not dependencies else TaskStatus.WAITING,
    )


def create_demo_project() -> Project:
    rubric = [
        RubricCriterion(
            id="rubric-problem",
            criterion="Problem understanding",
            description="Clear, evidence-based understanding of the student problem",
            marks=20,
        ),
        RubricCriterion(
            id="rubric-evaluation",
            criterion="Critical evaluation",
            description="Thoughtful comparison of existing approaches and limitations",
            marks=25,
        ),
        RubricCriterion(
            id="rubric-design",
            criterion="Solution design and implementation",
            description="A coherent design translated into a working prototype",
            marks=35,
        ),
        RubricCriterion(
            id="rubric-testing",
            criterion="Testing and presentation",
            description="Evidence of testing and a clear final demonstration",
            marks=20,
        ),
    ]

    tasks = [
        _task(
            task_id="task-problem-research",
            title="Research the student pain point",
            description=(
                "Find three credible sources explaining why students struggle to "
                "begin group assignments."
            ),
            objective="Build an evidence base for Relay's core student problem.",
            minutes=30,
            required_output=[
                "Three source links",
                "A summary for each source",
                "A relevance explanation for each source",
            ],
            first_action="Find one credible source about barriers to starting group work.",
            steps=[
                "Find three credible sources.",
                "Record the title and link for each source.",
                "Summarise each source.",
                "Explain how each source relates to the student pain point.",
            ],
            rubric_id="rubric-problem",
            dependencies=[],
            unlocks=["task-problem-analysis"],
        ),
        _task(
            task_id="task-tool-research",
            title="Research existing group-project tools",
            description=(
                "Review three existing tools and record how each handles task setup, "
                "dependencies, and handoffs."
            ),
            objective="Identify where current tools leave coordination work to students.",
            minutes=30,
            required_output=[
                "Three tool or source links",
                "A summary for each tool",
                "A relevance explanation for Relay",
            ],
            first_action="Choose one widely used group-project tool to review.",
            steps=[
                "Select three existing tools.",
                "Record a credible link for each.",
                "Summarise each tool's workflow.",
                "Explain the gap that remains for students.",
            ],
            rubric_id="rubric-evaluation",
            dependencies=[],
            unlocks=["task-solution-comparison"],
        ),
        _task(
            task_id="task-problem-analysis",
            title="Analyse the student pain point",
            description="Turn the completed research into a structured problem analysis.",
            objective="Explain the causes and consequences of stalled group assignments.",
            minutes=35,
            required_output=[
                "A causes section",
                "An impact section",
                "Evidence drawn from the supplied research context",
            ],
            first_action="Review the research submission passed into this task.",
            steps=[
                "Review all supplied source summaries.",
                "Group evidence into causes and impacts.",
                "Write at least two structured sections.",
                "Reference evidence from the dependency context.",
            ],
            rubric_id="rubric-problem",
            dependencies=["task-problem-research"],
            unlocks=["task-solution-requirements"],
        ),
        _task(
            task_id="task-solution-comparison",
            title="Compare existing solutions",
            description="Compare the researched tools and identify the unmet workflow need.",
            objective="Show why automatic handoff is meaningfully different.",
            minutes=35,
            required_output=[
                "A comparison section",
                "A limitations section",
                "Evidence drawn from the supplied tool research",
            ],
            first_action="Review the three tool summaries passed into this task.",
            steps=[
                "Compare task creation and ownership.",
                "Compare dependency and handoff support.",
                "Identify repeated limitations.",
                "State the opportunity for Relay.",
            ],
            rubric_id="rubric-evaluation",
            dependencies=["task-tool-research"],
            unlocks=["task-solution-requirements"],
        ),
        _task(
            task_id="task-solution-requirements",
            title="Define measurable Relay requirements",
            description=(
                "Combine both analyses into a concise set of prototype requirements "
                "and acceptance checks."
            ),
            objective="Define exactly what the Relay prototype must prove.",
            minutes=30,
            required_output=[
                "At least three numbered requirements",
                "An acceptance check for each requirement",
                "Use of context from both analysis branches",
            ],
            first_action="Read both completed analyses in the dependency context.",
            steps=[
                "Extract the strongest user needs.",
                "Translate them into numbered requirements.",
                "Add a measurable acceptance check to each.",
                "Confirm automatic handoff is included.",
            ],
            rubric_id="rubric-design",
            dependencies=["task-problem-analysis", "task-solution-comparison"],
            unlocks=["task-prototype-plan"],
        ),
        _task(
            task_id="task-prototype-plan",
            title="Plan the Relay prototype",
            description="Create a build plan covering screens, data flow, and handoff acceptance.",
            objective="Turn the confirmed requirements into an executable prototype plan.",
            minutes=35,
            required_output=[
                "A screen list",
                "A data-flow description",
                "Automatic handoff acceptance criteria",
            ],
            first_action="Turn the first confirmed requirement into a screen and data step.",
            steps=[
                "List the minimum screens.",
                "Map the task and submission data flow.",
                "Describe the handoff transition.",
                "Define acceptance criteria for the demo.",
            ],
            rubric_id="rubric-design",
            dependencies=["task-solution-requirements"],
            unlocks=["task-prototype-build"],
        ),
        _task(
            task_id="task-prototype-build",
            title="Build the Relay prototype",
            description="Implement the planned claim, submit, unlock, and context flow.",
            objective="Produce a working prototype that demonstrates the execution relay.",
            minutes=90,
            required_output=[
                "Implemented claim flow",
                "Implemented submission and unlock flow",
                "Implemented context handoff",
            ],
            first_action="Implement the first acceptance criterion from the prototype plan.",
            steps=[
                "Implement task claiming.",
                "Implement submission validation.",
                "Implement dependent-task unlocking.",
                "Show passed dependency context.",
            ],
            rubric_id="rubric-design",
            dependencies=["task-prototype-plan"],
            unlocks=["task-handoff-test"],
        ),
        _task(
            task_id="task-handoff-test",
            title="Test the automatic handoff",
            description="Run and document the full completion-to-unlock demonstration.",
            objective="Verify that completed work reaches the correct dependent task.",
            minutes=40,
            required_output=[
                "A named test scenario",
                "Expected and actual results",
                "Evidence that dependency context was transferred",
            ],
            first_action="Reset the demo and write down the expected handoff result.",
            steps=[
                "Reset and join the demo project.",
                "Claim and complete a starting task.",
                "Confirm the dependent task unlocks.",
                "Confirm the prior submission appears in its context.",
            ],
            rubric_id="rubric-testing",
            dependencies=["task-prototype-build"],
            unlocks=["task-final-presentation"],
        ),
        _task(
            task_id="task-final-presentation",
            title="Prepare the final presentation",
            description="Create the final problem, solution, prototype, and testing narrative.",
            objective="Present Relay's value and prove the automatic handoff clearly.",
            minutes=50,
            required_output=[
                "Problem and solution narrative",
                "Live demo sequence",
                "Testing result and limitations",
            ],
            first_action="Draft the one-sentence problem and solution statements.",
            steps=[
                "Explain the student problem.",
                "Introduce Relay's execution handoff.",
                "Script the live demo.",
                "Include testing evidence and limitations.",
            ],
            rubric_id="rubric-testing",
            dependencies=["task-solution-requirements", "task-handoff-test"],
            unlocks=[],
        ),
    ]

    return Project(
        id=DEMO_PROJECT_ID,
        title="Student Group Project Workflow",
        deadline="2026-08-15",
        deliverables=["Working Relay prototype", "Testing evidence", "Final presentation"],
        requirements=[
            "Tasks must be specific and claimable.",
            "Dependencies must control task availability.",
            "Completed work must be passed to dependent tasks.",
        ],
        rubric=rubric,
        tasks=tasks,
        created_at=datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc),
    )
