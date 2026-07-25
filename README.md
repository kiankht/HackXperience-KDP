# Relay

**From assignment brief to next action.**

Relay is a collaborative assignment workflow app built for HackXperience 2026.
It reads an assignment brief and marking rubric, identifies what the group must
produce, and divides the work into small dependency-aware tasks. Members claim
ready tasks, submit their part, and pass accepted work into the next task. Relay
combines the completed parts into one final assignment result.

## What Relay currently does

- Creates assignments from pasted text or uploaded PDF, DOCX, and TXT files.
- Analyses briefs and rubrics with Azure OpenAI or OpenAI.
- Generates an editable draft rubric when no official rubric is available.
- Lets users review and correct the extracted details before creating a workflow.
- Produces 6–12 assignment-specific tasks with objectives, steps, outputs,
  estimates, dependencies, and rubric links.
- Lets members join by name, claim available work, and switch between members.
- Checks submissions before unlocking dependent tasks.
- Passes accepted answers and context to the next member automatically.
- Combines all accepted task answers into one final result.
- Keeps multiple assignments in the same running Relay session.
- Provides an Assignment menu for creating, demoing, and switching projects.
- Shows statistics for current and previous assignments.
- Includes **RelyRelay.ai**, a resizable assignment-focused chatbot with rotating
  suggested questions and project-aware responses.
- Includes a deterministic demo and fallback workflow when live AI is unavailable.
- Provides Back controls throughout the main workflow.
- Provides **Reset Everything** for clearing all assignments, members, and work.
- Runs as one FastAPI service that serves both the website and API.

## Main workflow

1. Open **Assignments** and choose **New Assignment**, or select
   **Create From Assignment** on the home screen.
2. Upload or paste the assignment brief.
3. Upload or paste the marking rubric. If there is no rubric, select
   **Generate Rubric** and review Relay’s draft.
4. Select **Analyse Assignment**.
5. Review the title, deadline, deliverables, requirements, rubric criteria, and
   marks on **Check what Relay found**.
6. Select **Confirm and Build Workflow**.
7. Join the assignment using a member name.
8. Claim an available task and complete its required output.
9. Submit the answer. Relay either requests revisions or accepts it and unlocks
   the next work.
10. Open **Combined Result** after work has been accepted to view the assembled
    assignment draft.

## Main areas

- **My Work** — the current member’s next action and submission area.
- **Workflow** — every task, owner, dependency, status, and rubric connection.
- **Statistics** — progress summaries across all assignments in the running app.
- **Assignments** — create a new assignment, start the demo, or switch projects.
- **RelyRelay.ai** — help based on the current assignment, workflow, rubric,
  submissions, and Relay features.

## AI providers

Relay supports:

- Azure OpenAI
- OpenAI API
- Deterministic fallback mode

Configuration is backend-only. Never place an API key in `frontend/app.js`,
share it in screenshots, or commit it to GitHub.

Create `.env` from `.env.example` and use one of the following configurations.

### Azure OpenAI

```dotenv
AI_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=YOUR_PRIVATE_KEY
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
AI_MODE=auto
AI_TIMEOUT_SECONDS=120
MAX_UPLOAD_BYTES=10485760
AUTO_CLAIM_SECONDS=300
```

The deployment name must match the name shown under **Deployments** in Microsoft
Foundry. It is not necessarily the same as the model family name.

### OpenAI API

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=YOUR_PRIVATE_KEY
OPENAI_MODEL=gpt-5.6-sol
AI_MODE=auto
AI_TIMEOUT_SECONDS=120
MAX_UPLOAD_BYTES=10485760
AUTO_CLAIM_SECONDS=300
```

### AI modes

- `auto` — use the configured live provider and fall back safely if it fails.
- `real` — require live AI and return an error when the provider is unavailable.
- `fallback` — never contact an AI provider.

## Share Relay as a website

Relay includes [render.yaml](render.yaml), which deploys the frontend and FastAPI
backend together as one Render web service.

1. Push the current repository to GitHub.
2. Open [Render Blueprints](https://dashboard.render.com/blueprints).
3. Select **New Blueprint Instance**.
4. Connect `kiankht/HackXperience-KDP`.
5. Enter `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` when Render requests
   the secret values.
6. Select **Deploy Blueprint**.
7. Share the generated `onrender.com` address.

Use the Render address—not a GitHub Pages address. GitHub Pages can host the
interface but cannot run Relay’s Python backend.

Render automatically deploys new commits from the connected branch. The free
service sleeps after inactivity, so its first visit can take around one minute.
The current data store is in memory, so assignments reset whenever the server
restarts, redeploys, or sleeps.

## Run locally

Requirements:

- Python 3.12+
- Internet access for live AI

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

Virtual-environment activation is optional because the commands use its Python
executable directly.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests force fallback mode so they do not use paid AI quota.

## File uploads

Supported:

- Text-based PDF
- DOCX
- UTF-8 TXT
- Maximum 10 MB by default

Relay validates file type, size, and basic format signatures. Uploaded documents
are processed in memory and are not saved as permanent files. Image-only PDFs
and image files are not OCR-processed; paste their text instead.

Do not upload passwords, API keys, private identification documents, or other
sensitive information.

## API

Interactive API documentation is available at `/docs` while Relay is running.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check whether the backend is running |
| `GET` | `/api/ai/status` | Read non-secret AI readiness |
| `GET` | `/api/samples/assignment` | Load the sample assignment |
| `POST` | `/api/files/extract` | Extract text from PDF, DOCX, or TXT |
| `POST` | `/api/assignments/analyze` | Analyse an assignment and rubric |
| `POST` | `/api/assignments/generate-rubric` | Draft a rubric from a brief |
| `POST` | `/api/projects/from-analysis` | Create an assignment workflow |
| `GET` | `/api/projects` | List statistics for every assignment |
| `GET` | `/api/projects/{project_id}` | Read an assignment and workflow |
| `GET` | `/api/projects/{project_id}/combined-result` | Assemble accepted answers |
| `POST` | `/api/projects/{project_id}/chat` | Ask RelyRelay.ai |
| `POST` | `/api/projects/{project_id}/members` | Join by name |
| `GET` | `/api/projects/{project_id}/available-tasks` | List claimable tasks |
| `POST` | `/api/tasks/{task_id}/claim` | Claim a task |
| `GET` | `/api/members/{member_id}/next-action` | Read a member’s current task |
| `POST` | `/api/tasks/{task_id}/submit` | Check and submit work |
| `POST` | `/api/demo/reset` | Restart the demo only |
| `POST` | `/api/reset-all` | Clear all Relay data |

## Task statuses

- **Available** — all dependencies are complete and the task can be claimed.
- **Waiting** — one or more dependencies are incomplete.
- **In progress** — a member has claimed the task.
- **Needs revision** — the submission is missing required components.
- **Completed** — the answer was accepted and passed forward.

## Project structure

```text
.
├── backend/
│   ├── app/
│   │   ├── ai_models.py
│   │   ├── ai_service.py
│   │   ├── analysis.py
│   │   ├── config.py
│   │   ├── file_extraction.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── project_builder.py
│   │   ├── prompts.py
│   │   ├── reports.py
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
├── .env.example
├── render.yaml
└── README.md
```

## Current limitations

- Assignment history is stored in server memory, not a permanent database.
- Render restarts and free-tier sleep erase current assignments and submissions.
- There is no password-based authentication or private account system.
- Anyone with the shared website link can use the running Relay instance.
- Joining by name is intended for demonstrations and trusted student groups.
- AI-generated analysis, rubrics, workflows, and feedback can be imperfect and
  must be reviewed by students.
- A generated rubric is a draft, not an official lecturer rubric.
- Submission checking verifies required structure and completion; it does not
  guarantee factual accuracy, academic quality, or grades.
- Uploaded files are limited to extractable text; OCR is not included.

## Troubleshooting

### The website briefly shows “Not Found”

Wait for the free Render service to wake, then refresh. Confirm the address ends
in `onrender.com`. The current server sends the homepage with no-cache headers
and restores Relay for refreshed browser routes.

### Relay says the deployment is out of date

Push the latest commit to GitHub, open the Render service, and confirm the newest
deployment succeeded.

### Live AI is unavailable

Open `/api/ai/status` on the running website. Confirm the provider is `azure`,
`configured` is `true`, and the deployment name matches Microsoft Foundry.
Check the Render environment values without exposing them publicly.

### PowerShell cannot find Python

Install Python 3.12 or use the full path to a known Python executable when
creating `.venv`. After creation, use:

```powershell
.\.venv\Scripts\python.exe
```

### The saved assignment disappeared

The current storage is intentionally in memory. A server restart, redeploy, or
free-tier sleep clears it. Permanent cross-device history requires a database,
which is not implemented yet.
