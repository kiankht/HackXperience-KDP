# Relay

**From assignment brief to next action.**

Relay is a focused HackXperience 2026 workflow-automation MVP for student group
assignments. Students often lose time deciding how to begin, dividing vague work,
understanding dependencies, and passing completed work to the next person.

Relay turns an assignment brief into specific, claimable, dependency-aware actions.
Each member receives one clear next action, and completed submissions can be checked
and passed automatically into the context of dependent work.

## Current Stage 3 capabilities

- One-process FastAPI application serving the API and landing page
- Repeatable nine-task demonstration project with parallel branches
- Name-only project joining with case-insensitive duplicate prevention
- Complete browser-based demo flow with no API documentation required
- Available-task cards with estimated time, output, rubric, and unlock information
- One focused next-action view with objective, first action, steps, and output
- Incomplete and valid demo-submission helpers
- Inline revision feedback that preserves editable submission content
- Prominent completion-to-handoff result
- Member switching without resetting project progress
- Visible dependency context containing the prior member and exact submitted work
- Workflow overview with owners, dependencies, statuses, and rubric coverage
- Responsive laptop and mobile layouts
- Dependency-aware task availability and claiming
- One active next action per member
- Transparent, task-specific deterministic submission checks
- Revision feedback for incomplete submissions
- Automatic dependent-task unlocking
- Structured submission context passed into newly unlocked tasks
- Current-workload calculation, advisory imbalance warnings, and fair assignment logic
- Rubric coverage without double-counting criteria
- Focused API and workflow-engine tests

The current workflow is deterministic and does not use an AI provider. Assignment
brief input, rubric parsing, and AI-assisted workflow generation are reserved for
later stages.

## Technology stack

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic
- Plain HTML, CSS, and JavaScript
- Pytest and HTTPX

## Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── sample_data.py
│   │   ├── storage.py
│   │   └── workflow.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/
│   ├── test_health.py
│   └── test_workflow.py
├── .env.example
├── .gitignore
└── README.md
```

## Windows PowerShell setup

Open PowerShell and move to the repository root:

```powershell
Set-Location 'D:\WINDOW FOLDER\Documents\HackXperience 2026'
```

Create one virtual environment at the repository root:

```powershell
py -m venv .venv
```

If `py` is unavailable or points to a broken installation, use a confirmed Python
executable:

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe' -m venv .venv
```

Install dependencies using the virtual environment's Python:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Start Relay:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in a browser.

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Quick Demo

1. Press **Start Demo**.
2. Join as **Ping**.
3. Claim **Research the student pain point**.
4. Press **Fill Incomplete Example**, then submit.
5. Review the missing requirements.
6. Press **Fill Demo Submission**, then resubmit.
7. Observe the prominent automatic handoff.
8. Press **Switch Member**.
9. Join as **Kian**.
10. Claim **Analyse the student pain point**.
11. View Ping's accepted work under **Work passed to you**.
12. Open **Workflow** to see owners, status, dependencies, and rubric coverage.

The demo helpers contain deterministic sample text for presentation convenience.
They are clearly labelled and do not represent genuine student work.

## Task statuses

- **Available:** all dependencies are complete and the task can be claimed.
- **Waiting:** at least one dependency is incomplete.
- **In progress:** a member has claimed the task.
- **Needs revision:** the submitted work is missing minimum required components.
- **Completed:** the submission was accepted and eligible work was handed forward.

## Reset Demo

Use **Reset Demo** in the application header to clear all in-memory members,
claims, submissions, completions, and handoff context. Confirming the reset recreates
the original nine-task project and returns the interface to name-only joining.

## Deterministic demo API

The interactive API documentation is available at
[http://localhost:8000/docs](http://localhost:8000/docs) while Relay is running.

Main endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check the Relay backend |
| `POST` | `/api/demo/reset` | Recreate the deterministic project |
| `GET` | `/api/projects/{project_id}` | Read project, workflow, and rubric coverage |
| `POST` | `/api/projects/{project_id}/members` | Join using only a name |
| `GET` | `/api/projects/{project_id}/available-tasks` | List tasks ready to claim |
| `POST` | `/api/tasks/{task_id}/claim` | Claim an available task |
| `GET` | `/api/members/{member_id}/next-action` | Read the member's active task |
| `POST` | `/api/tasks/{task_id}/submit` | Validate, complete, and hand off work |

Resetting the demo returns the stable project ID `project-relay-demo`. In-memory
data is also reset whenever the server restarts.

## Sample API flow

With Relay running, use a second PowerShell window:

```powershell
$project = Invoke-RestMethod `
  -Method Post `
  -Uri 'http://localhost:8000/api/demo/reset'

$member = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/projects/$($project.project_id)/members" `
  -ContentType 'application/json' `
  -Body '{"name":"Kian"}'

$available = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/projects/$($project.project_id)/available-tasks"

$claim = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/tasks/$($available[0].id)/claim" `
  -ContentType 'application/json' `
  -Body (@{ member_id = $member.id } | ConvertTo-Json)

$nextAction = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/members/$($member.id)/next-action"
```

Research submissions use this predictable minimum structure:

```text
Source 1:
Link: https://example.edu/source-1
Summary: A sufficiently detailed summary.
Relevance: How the evidence relates to Relay.

Source 2:
Link: https://example.edu/source-2
Summary: A sufficiently detailed summary.
Relevance: How the evidence relates to Relay.

Source 3:
Link: https://example.edu/source-3
Summary: A sufficiently detailed summary.
Relevance: How the evidence relates to Relay.
```

Relay checks only the required structure and minimum detail. It does not grade
academic quality or replace lecturer feedback.

## Screenshots

Screenshot placeholders:

- Landing and demo start
- Focused next action
- Incomplete-submission feedback
- Automatic handoff result
- Dependency context received by the next member
- Workflow overview

## Known limitations

- The workflow and validation rules are deterministic rather than AI-generated.
- Data is stored in memory and resets when the server process restarts.
- There is no authentication or persistent multi-device collaboration.
- Submission validation checks minimum structure, not academic quality.
- Assignment and rubric text cannot yet be entered through the UI.
- File upload and document extraction are not included.

## Environment variables

Copy `.env.example` to `.env` only when environment-specific configuration is
needed. Stage 3 does not use an AI provider or require an API key.

## Troubleshooting

### `py` works but `python` does not

Use `py` to create the environment, then use the environment's explicit Python
path for all later commands:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

### Windows Store Python alias problems

If `python` opens the Store or reports an inaccessible installation, disable the
`python.exe` and `python3.exe` App Installer aliases in **Settings → Apps →
Advanced app settings → App execution aliases**. Alternatively, invoke a known
installation by its full path.

### Virtual-environment activation problems

Activation is optional because every command above uses the environment's Python
directly. If activation is preferred and PowerShell blocks it, allow scripts only
for the current process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Commands run from the wrong directory

Confirm the current directory before setup or startup:

```powershell
Get-Location
git rev-parse --show-toplevel
```

Both should identify `D:\WINDOW FOLDER\Documents\HackXperience 2026`. Do not
create `.venv` inside `backend` or `backend\app`.
