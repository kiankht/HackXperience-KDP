# Relay

**From assignment brief to next action.**

Relay is a focused HackXperience 2026 workflow-automation MVP for student group
assignments. Students often lose time deciding how to begin, dividing vague work,
understanding dependencies, and passing completed work to the next person.

Relay turns an assignment brief into specific, claimable, dependency-aware actions.
Each member receives one clear next action, and completed submissions can be checked
and passed automatically into the context of dependent work.

## Current Stage 5 capabilities

- Create a project by uploading or pasting an assignment brief and marking rubric
- Text extraction from PDF, DOCX, and UTF-8 TXT files
- Real OpenAI assignment analysis, workflow generation, and submission checking when configured
- Strict structured-output parsing with Pydantic models
- Validated AI task graphs with one repair attempt and deterministic fallback
- Rule-based analysis, workflow generation, and submission checking without an API key
- Editable confirmation of every extracted project detail
- Assignment-specific dependency-aware generation of 6 to 12 executable tasks in AI mode
- Tailored prototype, report, presentation, and repository phases when relevant
- A safe generic workflow fallback when a tailored workflow cannot be validated
- The complete fixed Stage 3 demo remains available through **Start Demo**

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

The fixed demo is always deterministic. Custom projects use OpenAI when configured
and safely fall back to Stage 4 rules when AI is unavailable in `auto` mode.

## AI configuration

Relay uses the official OpenAI Python SDK and the Responses API structured-output
helper:

```python
client.responses.parse(
    model=settings.openai_model,
    instructions=system_prompt,
    input=untrusted_document_text,
    text_format=PydanticResponseModel,
)
```

The installed SDK is constrained to `openai>=2.8.0,<3`. The model is configured in
one place through `OPENAI_MODEL`; it is not repeated throughout the application.

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Then provide backend-only configuration:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-sol
AI_MODE=auto
AI_TIMEOUT_SECONDS=45
MAX_UPLOAD_BYTES=10485760
```

Never commit `.env` or place the key in frontend JavaScript. `.gitignore` excludes
all `.env` files except the placeholder-only `.env.example`.

`AI_MODE` controls provider behavior:

- `auto`: use OpenAI when a key exists; otherwise fall back safely.
- `real`: require a backend API key and return a clear error when AI is unavailable.
- `fallback`: never call OpenAI and use deterministic behavior.

The prompts treat assignment files and submissions as untrusted data. Document
instructions cannot change Relay's system behavior, reveal secrets, alter the
structured schema, or trigger unrelated tools.

## File upload

Both assignment and rubric sections accept:

- Text-based PDF
- DOCX, including paragraphs and table-cell text
- UTF-8 TXT

The default maximum is 10 MB per file. Files are validated by extension, content
type, size, and basic format signatures, processed in memory, and never stored
permanently. Extracted text is shown in the existing textarea and remains editable.
Pasted text continues to work independently of uploads.

Image files and OCR are not supported. Image-only PDFs return a readable message
asking the student to paste the text or use a text-based PDF.

## Create a Project From Assignment Text

1. Select **Create From Assignment**.
2. Upload or paste the assignment brief.
3. Upload or paste the marking rubric.
4. Select **Analyse Assignment**.
5. Review and edit the extracted deliverables, requirements, and rubric criteria.
6. Select **Confirm and Build Workflow**.
7. Join using only a name.
8. Claim a starting task.

Use **Fill Sample Assignment** for a repeatable quick demonstration. The sample is
served by the backend and describes an original IT assignment for an agentic
workflow prototype.

When AI is ready, Relay returns strict structured findings. In fallback mode,
transparent text rules recognise heading-like titles, labelled dates, common
deliverables, requirement statements, bullets, and rubric marks. Students always
confirm and correct the information before a project is stored.

AI workflows are never stored directly. Relay validates task counts, unique IDs,
rubric links, dependencies, unlock symmetry, cycles, self-dependencies, starting
tasks, outputs, first actions, and execution steps. Server-owned project IDs,
ownership, statuses, submissions, and dependency context are added only after the
graph passes validation.

## Quick Demos

### Custom assignment

1. Configure `.env`, restart Relay, and confirm **AI workflow generation ready**.
2. Select **Create From Assignment**, then upload a supported file or use
   **Fill Sample Assignment**.
3. Analyse the sample and edit any extracted item.
4. Confirm and build the workflow.
5. Join as `Kian`, claim a starting task, and submit the required output.
6. Switch members and claim the newly unlocked task to verify passed context.

When no API key is available, the same journey uses fallback analysis and tasks:

1. Leave `OPENAI_API_KEY` empty and keep `AI_MODE=auto`.
2. Upload or paste the sample assignment and rubric.
3. Confirm the fallback analysis and workflow badges.
4. Join as `Kian`, claim **Research the core problem**, and use the labelled demo
   submission helper.
5. Switch members, join as `Ping`, and claim the newly unlocked analysis task.
6. Confirm Kian's accepted work appears under **Work passed to you**.

### Fixed demo

1. Select **Start Demo**.
2. Join as `Ping` and claim **Research the student pain point**.
3. Use **Fill Incomplete Example** to see specific revision feedback.
4. Use **Fill Demo Submission** and resubmit to unlock the analysis task.
5. Switch members, join as `Kian`, and claim the analysis task.
6. Confirm Ping's exact accepted submission appears as dependency context.

## Technology stack

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic
- Plain HTML, CSS, and JavaScript
- Pytest and HTTPX

## Share Relay as a website

Relay includes a Render Blueprint, so friends can use it through one public
website link without installing Python or running PowerShell.

1. Push the latest repository changes to GitHub.
2. Open [Render Blueprints](https://dashboard.render.com/blueprints).
3. Select **New Blueprint Instance** and connect the
   `kiankht/HackXperience-KDP` repository.
4. When Render asks for secret values, paste:
   - `AZURE_OPENAI_ENDPOINT` from the local `.env`
   - `AZURE_OPENAI_API_KEY` from the local `.env`
5. Select **Deploy Blueprint**.
6. Open the generated `relay-app.onrender.com` address and share that link.

The Azure key stays in Render and is never sent to the browser or committed to
GitHub. New commits to the connected GitHub branch deploy automatically.

Render's free web service sleeps after inactivity. The first request after sleep
can take about a minute, and Relay's current in-memory assignments reset whenever
the service restarts. Use the free deployment for demonstrations and testing;
add a persistent database before relying on it for long-lived assignment history.

## Assignment API

### Get the sample

```http
GET /api/samples/assignment
```

### Analyse pasted text

```http
POST /api/assignments/analyze
Content-Type: application/json
```

```json
{
  "title": "Optional assignment title",
  "deadline": "2026-08-15",
  "assignment_brief": "The complete pasted assignment brief...",
  "rubric_text": "Research quality — 20 marks..."
}
```

The response contains `suggested_title`, `suggested_deadline`, `deliverables`,
`requirements`, `rubric`, `extraction_warnings`, and source character counts.
Analysis is read-only and does not create a project.

### Create from confirmed analysis

```http
POST /api/projects/from-analysis
Content-Type: application/json
```

```json
{
  "title": "Agentic Workflow Automation Prototype",
  "deadline": "2026-08-15",
  "deliverables": ["Working prototype", "Presentation"],
  "requirements": ["Build and test the central workflow"],
  "rubric": [
    {
      "id": "rubric-implementation",
      "criterion": "Technical implementation",
      "description": "Functionality of the prototype",
      "marks": 100
    }
  ],
  "original_assignment_brief": "The complete pasted assignment brief...",
  "original_rubric_text": "Technical implementation — 100 marks"
}
```

The response includes the new project ID, task counts, confirmed information, and
any workflow fallback warning. The project then uses the same join, claim,
submission, unlocking, context-handoff, workflow, and rubric-coverage endpoints as
the fixed demo.

## Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── ai_models.py
│   │   ├── ai_service.py
│   │   ├── analysis.py
│   │   ├── config.py
│   │   ├── file_extraction.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── project_builder.py
│   │   ├── prompts.py
│   │   ├── sample_data.py
│   │   ├── sample_inputs.py
│   │   ├── storage.py
│   │   └── workflow.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/
│   ├── test_assignment_flow.py
│   ├── test_health.py
│   ├── test_stage5.py
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
| `GET` | `/api/ai/status` | Read non-secret AI readiness and fallback status |
| `POST` | `/api/files/extract` | Extract editable text from PDF, DOCX, or TXT |
| `GET` | `/api/samples/assignment` | Get the repeatable sample assignment |
| `POST` | `/api/assignments/analyze` | Analyse pasted text without storing a project |
| `POST` | `/api/projects/from-analysis` | Build a project from confirmed information |
| `POST` | `/api/demo/reset` | Recreate the deterministic demo project |
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

- Real AI requires an API key and internet access.
- AI output can be imperfect and must be reviewed before project creation.
- Complex rubric tables may require manual correction.
- Only text-based PDF, DOCX, and UTF-8 TXT files are supported.
- Image-only PDFs are not OCR-processed; PNG, JPG, and JPEG are not supported.
- Data is stored in memory and resets when the server process restarts.
- There is no authentication or persistent multi-device collaboration.
- AI and fallback submission checks assess required structure and completion, not
  academic correctness, factual accuracy, or grades.
- Relay does not replace lecturer feedback or guarantee grades.
- The fixed Start Demo path deliberately uses deterministic data and validation.

## Environment variables

Copy `.env.example` to `.env` only when environment-specific configuration is
needed. Stage 5 uses OpenAI only when configured and never requires an API key for
the deterministic demo or fallback mode.

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

Both should identify the cloned `HackXperience-KDP` repository. Do not
create `.venv` inside `backend` or `backend\app`.
