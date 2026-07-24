const app = document.querySelector("#app");
const header = document.querySelector("#app-header");
const nav = document.querySelector("#app-nav");
const memberControls = document.querySelector("#member-controls");
const globalMessage = document.querySelector("#global-message");
const chatLauncher = document.querySelector("#ai-chat-launcher");
const chatPanel = document.querySelector("#ai-chat-panel");
const chatMessages = document.querySelector("#ai-chat-messages");
const chatSuggestions = document.querySelector("#ai-chat-suggestions");

const state = {
  view: "landing",
  projectId: localStorage.getItem("relay_project_id"),
  project: null,
  memberId: localStorage.getItem("relay_member_id"),
  memberName: localStorage.getItem("relay_member_name"),
  availableTasks: [],
  currentTask: null,
  submissionText: "",
  submissionResult: null,
  handoffResult: null,
  combinedResult: null,
  projectStatistics: [],
  newAssignmentMemberName: null,
  chatHistory: [],
  chatProjectId: null,
  lastClickedSuggestion: null,
  workloadWarning: null,
  highlightedTaskIds: [],
  loading: false,
  assignment: { title: "", deadline: "", assignment_brief: "", rubric_text: "" },
  analysisResult: null,
  workflowWarnings: [],
  aiStatus: null,
  workflowGenerationMode: null,
  autoRefreshTimer: null,
  countdownTimer: null,
  files: {
    assignment: { name: "", status: "", tone: "" },
    rubric: { name: "", status: "", tone: "" },
  },
};

const statusLabels = {
  available: "Available",
  waiting: "Waiting",
  in_progress: "In progress",
  needs_revision: "Needs revision",
  completed: "Completed",
};

const demoSubmissions = {
  "task-problem-research": `Source 1:
Link: https://example.edu/group-starting
Summary: University research explains that unclear ownership delays the beginning of student group assignments and increases coordination overhead.
Relevance: Relay gives each student one specific action they can claim immediately.

Source 2:
Link: https://example.edu/dependency-awareness
Summary: This study finds that teams lose time when members cannot see which work is blocked by an unfinished dependency.
Relevance: Relay makes task dependencies visible and unlocks work only when it is ready.

Source 3:
Link: https://example.edu/context-handoffs
Summary: Educational research shows that informal handoffs often lose decisions, evidence, and context between group members.
Relevance: Relay automatically passes accepted work into the next dependent task.`,
  "task-tool-research": `Source 1:
Link: https://example.edu/tool-one
Summary: This project board lets users create cards manually but does not interpret assignment requirements or prepare executable next actions.
Relevance: Relay begins with task readiness and dependency-aware execution.

Source 2:
Link: https://example.edu/tool-two
Summary: This collaboration tool tracks ownership but relies on students to coordinate every handoff and resend completed research.
Relevance: Relay passes accepted work directly into dependent task context.

Source 3:
Link: https://example.edu/tool-three
Summary: This planning tool visualises deadlines but does not validate required output before unlocking downstream work.
Relevance: Relay checks minimum submission structure before work moves forward.`,
  "task-problem-analysis": `Causes:
The supplied research evidence shows that students stall when nobody owns the first action, responsibilities are vague, and dependency blockers are invisible. Source summaries connect unclear ownership with avoidable coordination overhead.

Impact:
The research also shows that delays propagate into dependent work and context is lost during informal handoffs. Relay addresses this evidence by making work claimable, checking the required output, and passing accepted context forward automatically.`,
  "task-solution-comparison": `Comparison:
The supplied tool research shows that existing project boards record tasks and owners, but students still translate the brief, decide dependencies, and coordinate handoffs manually.

Limitations and opportunity:
Evidence from the researched tools shows that accepted work is not automatically attached to the next dependent action. Relay fills this gap by validating minimum output, unlocking eligible work, and transferring context.`,
  "task-solution-requirements": `1. Relay must show only tasks whose dependencies are complete.
Acceptance check: A waiting task does not appear until every dependency is completed.

2. Relay must let a member claim a ready task using only their name.
Acceptance check: A second claim is rejected and the first owner remains visible.

3. Relay must pass accepted submission context into newly unlocked work.
Acceptance check: The dependent task displays the source task, submitting member, and exact content from both analysis branches.`,
  "task-prototype-plan": `Screens:
The prototype needs a join view, available-task view, focused next-action view, handoff result, and workflow overview.

Data flow:
A member claims an available task, submits required output, and the backend validates and stores the result.

Handoff acceptance:
When validation succeeds, the dependent task unlocks and displays the prior submission context and member name.`,
  "task-prototype-build": `Implementation record:
The claim flow stores one owner and changes the task to in progress. The submission flow sends the member and content to backend validation. The unlock flow checks every dependency before changing waiting work to available. The context handoff stores and displays the completed submission, source task, and submitting member. These implemented steps create the complete Relay demonstration.`,
  "task-handoff-test": `Scenario: Complete research and open the dependent analysis task.

Expected result: The research task becomes completed, the analysis task becomes available, and its dependency context contains the accepted content and member name.

Actual result: The handoff test passed. The unlocked task displayed the exact prior context submitted by Ping, matching the expected automatic transfer.`,
  "task-final-presentation": `Problem:
Student groups lose time deciding where to begin and coordinating dependent work.

Solution:
Relay creates claimable next actions and passes accepted work forward.

Demo:
Ping completes research, then Kian claims the unlocked analysis and sees Ping's context.

Testing:
Automated and manual tests verify validation, unlocking, and handoff.

Limitations:
The current workflow is deterministic and stored in memory.`,
};

const incompleteSubmissions = {
  "task-problem-research": "Source 1:\nLink: https://example.edu/one",
  "task-tool-research": "Source 1:\nLink: https://example.edu/tool",
  default: "This short draft is intentionally incomplete for the Relay demo.",
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function list(items, className = "") {
  if (!items?.length) return "";
  return `<ul class="${className}">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function apiErrorMessage(payload, fallback) {
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg?.replace(/^Value error, /, "")).filter(Boolean).join(" ");
  }
  return fallback;
}

async function apiRequest(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 60000);
  const isFormData = options.body instanceof FormData;
  const { timeoutMs, ...fetchOptions } = options;
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      headers: {
        ...(options.body && !isFormData ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error("Relay received an unexpected response from the backend.");
      }
    }
    if (!response.ok) {
      throw new Error(apiErrorMessage(payload, "Relay could not complete that request."));
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Relay took too long to respond. Check that the backend is running.");
    }
    if (error instanceof TypeError) {
      throw new Error("Relay could not connect to the backend.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function setLoading(message) {
  state.loading = true;
  app.innerHTML = `<section class="loading-screen" aria-live="polite">
    <span class="spinner" aria-hidden="true"></span><p>${escapeHtml(message)}</p>
  </section>`;
}

function showMessage(message, tone = "success") {
  globalMessage.textContent = message;
  globalMessage.className = `global-message ${tone}`;
  globalMessage.hidden = false;
  clearTimeout(showMessage.timer);
  showMessage.timer = setTimeout(() => {
    globalMessage.hidden = true;
  }, 3600);
}

function setStoredMember(member = null) {
  if (member) {
    state.memberId = member.id;
    state.memberName = member.name;
    localStorage.setItem("relay_member_id", member.id);
    localStorage.setItem("relay_member_name", member.name);
  } else {
    state.memberId = null;
    state.memberName = null;
    localStorage.removeItem("relay_member_id");
    localStorage.removeItem("relay_member_name");
  }
}

function clearCurrentSession() {
  localStorage.removeItem("relay_project_id");
  setStoredMember(null);
  state.projectId = null;
  state.project = null;
  state.availableTasks = [];
  state.currentTask = null;
  state.submissionText = "";
  state.submissionResult = null;
  state.handoffResult = null;
  state.highlightedTaskIds = [];
  state.workloadWarning = null;
  state.workflowWarnings = [];
  state.workflowGenerationMode = null;
}

function projectTask(taskId) {
  return state.project?.tasks.find((task) => task.id === taskId);
}

function memberName(memberId) {
  return state.project?.members.find((member) => member.id === memberId)?.name || "Unclaimed";
}

function taskTitle(taskId) {
  return projectTask(taskId)?.title || "A dependent task";
}

function renderHeader() {
  if (state.view !== "tasks") {
    clearTimeout(state.autoRefreshTimer);
    clearInterval(state.countdownTimer);
  }
  const hasProject = Boolean(state.projectId);
  header.hidden = !hasProject;
  chatLauncher.hidden = !hasProject;
  if (!hasProject) return;

  const items = [];
  if (state.memberId) {
    items.push(["work", "My Work"]);
  }
  items.push(
    ["workflow", "Workflow"],
    ["statistics", "Statistics"],
    ["assignments", "Assignments"],
  );
  nav.innerHTML = `<button class="nav-link back-link" id="global-back" aria-label="Go back">← Back</button>` + items
    .map(([view, label]) => `<button class="nav-link ${(view === "work" ? ["action", "tasks"].includes(state.view) : state.view === view) ? "active" : ""}" data-view="${view}">${label}</button>`)
    .join("");

  memberControls.innerHTML = state.memberName ? `
    <button class="account-button" id="switch-member" title="Switch member">
      <span aria-hidden="true">${escapeHtml(state.memberName[0].toUpperCase())}</span>
      <span>${escapeHtml(state.memberName)}</span>
    </button>` : "";

  nav.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.view));
  });
  document.querySelector("#global-back")?.addEventListener("click", goBack);
  document.querySelector("#switch-member")?.addEventListener("click", switchMember);
}

async function loadProject() {
  if (!state.projectId) return null;
  state.project = await apiRequest(`/api/projects/${state.projectId}`);
  return state.project;
}

async function navigate(view) {
  state.view = view;
  state.submissionResult = null;
  try {
    if (view === "tasks") {
      await showAvailableTasks();
    } else if (view === "work") {
      await showNextAction();
    } else if (view === "action") {
      await showNextAction();
    } else if (view === "workflow") {
      await showWorkflow();
    } else if (view === "statistics") {
      await showStatistics();
    } else if (view === "assignments") {
      await showAssignments();
    } else if (view === "join") {
      await showJoin();
    } else {
      renderLanding();
    }
  } catch (error) {
    renderError(error.message, () => navigate(view));
  }
}

function startNewAssignment() {
  state.newAssignmentMemberName = state.memberName;
  state.assignment = { title: "", deadline: "", assignment_brief: "", rubric_text: "" };
  state.analysisResult = null;
  state.files = {
    assignment: { name: "", status: "", tone: "" },
    rubric: { name: "", status: "", tone: "" },
  };
  showAssignmentInput();
}

async function showAssignments() {
  state.view = "assignments";
  setLoading("Loading your assignments...");
  state.projectStatistics = await apiRequest("/api/projects");
  renderAssignments();
}

function renderAssignments() {
  state.view = "assignments";
  state.loading = false;
  renderHeader();
  app.className = "app-main";
  app.innerHTML = `
    <section class="wide-view assignments-view" aria-labelledby="assignments-title">
      <div class="view-heading"><div><p class="eyebrow">Assignment menu</p>
        <h1 id="assignments-title">What do you want to work on?</h1>
        <p class="lead">Start something new or switch assignments without losing previous work, members, or statistics.</p>
      </div></div>
      <section class="assignment-menu-actions" aria-label="Create an assignment">
        <button class="assignment-menu-card" id="menu-new-assignment">
          <span aria-hidden="true">+</span><strong>New Assignment</strong>
          <small>Upload a brief and rubric to build a fresh workflow.</small>
        </button>
        <button class="assignment-menu-card" id="menu-start-demo">
          <span aria-hidden="true">R</span><strong>Start Demo</strong>
          <small>Open a clean Relay sample while preserving other assignments.</small>
        </button>
      </section>
      <section class="existing-assignments" aria-labelledby="existing-title">
        <h2 id="existing-title">Existing assignments</h2>
        <div class="assignment-switch-list">
          ${state.projectStatistics.length ? state.projectStatistics.map((project) => `
            <article class="assignment-switch-card ${project.project_id === state.projectId ? "current" : ""}">
              <div><span class="status-badge ${project.is_complete ? "completed" : "in_progress"}">${project.is_complete ? "Finished" : `${project.progress_percent}% complete`}</span>
                <h3>${escapeHtml(project.title)}</h3>
                <p>${project.completed_tasks} of ${project.total_tasks} tasks · ${project.member_count} member${project.member_count === 1 ? "" : "s"}</p>
              </div>
              ${project.project_id === state.projectId
                ? `<button class="button secondary" disabled>Current Assignment</button>`
                : `<button class="button primary" data-switch-assignment="${escapeHtml(project.project_id)}">Switch to Assignment</button>`}
            </article>`).join("") : `<div class="empty-state card"><p>No existing assignments yet.</p></div>`}
        </div>
      </section>
    </section>`;
  document.querySelector("#menu-new-assignment").addEventListener("click", startNewAssignment);
  document.querySelector("#menu-start-demo").addEventListener("click", startDemo);
  document.querySelectorAll("[data-switch-assignment]").forEach((button) => {
    button.addEventListener("click", () => switchAssignment(button.dataset.switchAssignment));
  });
  app.focus();
}

async function switchAssignment(projectId) {
  const accountName = state.memberName;
  state.projectId = projectId;
  localStorage.setItem("relay_project_id", projectId);
  state.currentTask = null;
  state.availableTasks = [];
  state.submissionText = "";
  setLoading("Switching assignments...");
  await loadProject();
  const matchingMember = accountName
    ? state.project.members.find((member) => member.name.toLowerCase() === accountName.toLowerCase())
    : null;
  setStoredMember(matchingMember || null);
  if (matchingMember) {
    await continueAfterMemberSelection();
  } else {
    await showJoin();
  }
}

function goBack() {
  const destinations = {
    action: "tasks",
    tasks: "workflow",
    workflow: "landing",
    statistics: "workflow",
    assignments: "workflow",
    "combined-result": "workflow",
    handoff: "workflow",
    join: "landing",
  };
  navigate(destinations[state.view] || "landing");
}

function renderLanding() {
  state.view = "landing";
  state.loading = false;
  header.hidden = true;
  chatLauncher.hidden = true;
  chatPanel.hidden = true;
  chatLauncher.setAttribute("aria-expanded", "false");
  app.className = "landing-page";
  app.innerHTML = `
    <section class="landing-shell" aria-labelledby="relay-title">
      <p class="eyebrow">HackXperience 2026 · Workflow Automation</p>
      <div class="hero-mark" aria-hidden="true">R</div>
      <h1 id="relay-title">Relay</h1>
      <p class="tagline">From assignment brief to next action.</p>
      <p class="hero-description">One group member uploads the assignment and rubric. Relay extracts the requirements, divides the project into dependency-aware tasks, then lets every member join by name and choose ready work.</p>
      <p id="ai-status" class="ai-status" role="status" aria-live="polite">Checking workflow mode…</p>
      <div class="hero-actions">
        <button class="button primary large" id="create-assignment">Create From Assignment <span aria-hidden="true">→</span></button>
        ${state.projectId ? `<button class="button secondary large" id="continue-project">Continue Current Project</button>` : ""}
        <button class="button secondary large" id="start-demo">Start Demo</button>
      </div>
      <div class="path-explanation">
        <p><strong>Create From Assignment</strong><span>Paste your own assignment brief and rubric.</span></p>
        <p><strong>Start Demo</strong><span>Use Relay’s fixed sample project to see claiming and automatic handoffs immediately.</span></p>
      </div>
      <button class="text-button" id="check-connection">Check Connection</button>
      <p id="connection-result" class="inline-status" role="status" aria-live="polite">Try the complete handoff in under two minutes.</p>
      <div class="demo-preview" aria-label="Relay workflow">
        <div><span>1</span><strong>Upload</strong><small>Add the brief and rubric</small></div>
        <i aria-hidden="true">→</i>
        <div><span>2</span><strong>Divide</strong><small>AI prepares the workflow</small></div>
        <i aria-hidden="true">→</i>
        <div><span>3</span><strong>Choose</strong><small>Members claim ready tasks</small></div>
      </div>
    </section>`;
  document.querySelector("#create-assignment").addEventListener("click", () => showAssignmentInput());
  document.querySelector("#continue-project")?.addEventListener("click", continueSavedProject);
  document.querySelector("#start-demo").addEventListener("click", startDemo);
  document.querySelector("#check-connection").addEventListener("click", checkConnection);
  loadAIStatus();
  app.focus();
}

async function continueSavedProject() {
  setLoading("Opening your current project...");
  try {
    await loadProject();
    if (state.memberId && state.project.members.some((member) => member.id === state.memberId)) {
      await continueAfterMemberSelection();
    } else {
      setStoredMember(null);
      await showJoin();
    }
  } catch {
    localStorage.removeItem("relay_project_id");
    state.projectId = null;
    setStoredMember(null);
    renderLanding();
    showMessage("The saved project is no longer available. Upload an assignment to begin.", "error");
  }
}

async function loadAIStatus() {
  const display = document.querySelector("#ai-status");
  if (!display) return;
  try {
    state.aiStatus = await apiRequest("/api/ai/status", { timeoutMs: 10000 });
    display.textContent = state.aiStatus.mode === "real"
      ? "AI workflow generation ready"
      : state.aiStatus.mode === "unavailable"
        ? "AI configuration needs attention — deterministic fallback remains available"
        : "Fallback mode available";
    display.className = `ai-status ${state.aiStatus.mode}`;
  } catch {
    display.textContent = "Workflow mode will be checked when you begin.";
  }
}

function assignmentField(name, label, value, options = {}) {
  const textarea = options.textarea;
  const max = options.max || 160;
  const required = options.required ? "required" : "";
  const describedBy = `${name}-error${textarea ? ` ${name}-count` : ""}`;
  return `<div class="field-group">
    <label for="${name}">${label}${options.optional ? " <span>(optional)</span>" : ""}</label>
    ${textarea
      ? `<textarea id="${name}" name="${name}" rows="${options.rows || 8}" maxlength="${max}" ${required} aria-describedby="${describedBy}">${escapeHtml(value)}</textarea>
         <div class="field-meta"><span id="${name}-count">${value.length.toLocaleString()} / ${max.toLocaleString()}</span></div>`
      : `<input id="${name}" name="${name}" type="${options.type || "text"}" maxlength="${max}" value="${escapeHtml(value)}" ${options.min ? `min="${escapeHtml(options.min)}"` : ""} ${required} aria-describedby="${describedBy}">`}
    <p id="${name}-error" class="form-error" role="alert"></p>
  </div>`;
}

function uploadZone(type, label) {
  const file = state.files[type];
  return `<section class="upload-section" aria-labelledby="${type}-upload-title">
    <div class="section-heading compact"><div>
      <h2 id="${type}-upload-title">${label}</h2>
      <p>Upload a file or paste the text below.</p>
    </div></div>
    <div class="drop-zone" id="${type}-drop-zone" tabindex="0" role="button"
      aria-label="Upload ${type} file" aria-describedby="${type}-upload-help">
      <strong>Drop ${type} file here</strong>
      <span>or</span>
      <button class="button tertiary" type="button" id="browse-${type}">Browse Files</button>
      <small id="${type}-upload-help">Supported formats: PDF, DOCX, TXT · Maximum 10 MB</small>
      <input class="visually-hidden" id="${type}-file" type="file" accept=".pdf,.docx,.txt">
    </div>
    <div id="${type}-file-result" class="file-result ${escapeHtml(file.tone)}" aria-live="polite">
      ${file.name ? `<strong>${escapeHtml(file.name)}</strong>` : ""}
      ${file.status ? `<span>${escapeHtml(file.status)}</span>` : ""}
      ${file.name ? `<button class="text-button" type="button" id="remove-${type}-file">Remove file</button>` : ""}
    </div>
  </section>`;
}

function showAssignmentInput() {
  state.view = "assignment";
  state.loading = false;
  header.hidden = true;
  app.className = "app-main";
  const data = state.assignment;
  app.innerHTML = `<section class="assignment-view" aria-labelledby="assignment-title">
    <p class="eyebrow">Create From Assignment</p>
    <h1 id="assignment-title">Add your assignment</h1>
    <p class="lead">Paste the assignment brief and marking rubric. Relay will identify the deliverables, requirements, and work that can begin immediately.</p>
    <form id="assignment-form" class="card assignment-form" novalidate>
      <div class="two-column-fields">
        ${assignmentField("assignment-title-input", "Assignment title", data.title, { optional: true, max: 160 })}
        ${assignmentField("assignment-deadline", "Deadline", data.deadline, { optional: true, type: "date", min: localToday() })}
      </div>
      ${uploadZone("assignment", "Assignment")}
      ${assignmentField("assignment-brief", "Assignment brief", data.assignment_brief, { textarea: true, required: true, max: 30000, rows: 11 })}
      ${uploadZone("rubric", "Marking rubric")}
      ${assignmentField("rubric-text", "Marking rubric", data.rubric_text, { textarea: true, required: true, max: 20000, rows: 8 })}
      <p class="privacy-copy">Your assignment content is processed to generate the workflow. Do not upload documents containing passwords, private identification documents, or API keys.</p>
      <p id="assignment-request-error" class="form-error" role="alert"></p>
      <div class="form-actions">
        <button class="button primary" type="submit">Analyse Assignment</button>
        <button class="button secondary" type="button" id="fill-sample">Fill Sample Assignment</button>
        <button class="text-button" type="button" id="assignment-back">Back</button>
      </div>
    </form>
  </section>`;
  const sync = () => {
    state.assignment = {
      title: document.querySelector("#assignment-title-input").value,
      deadline: document.querySelector("#assignment-deadline").value,
      assignment_brief: document.querySelector("#assignment-brief").value,
      rubric_text: document.querySelector("#rubric-text").value,
    };
    document.querySelector("#assignment-brief-count").textContent = `${state.assignment.assignment_brief.length.toLocaleString()} / 30,000`;
    document.querySelector("#rubric-text-count").textContent = `${state.assignment.rubric_text.length.toLocaleString()} / 20,000`;
  };
  document.querySelectorAll("#assignment-form input, #assignment-form textarea").forEach((field) => field.addEventListener("input", sync));
  document.querySelector("#assignment-form").addEventListener("submit", analyseAssignment);
  document.querySelector("#fill-sample").addEventListener("click", fillSampleAssignment);
  document.querySelector("#assignment-back").addEventListener("click", () => {
    state.newAssignmentMemberName = null;
    renderLanding();
  });
  bindUploadZone("assignment");
  bindUploadZone("rubric");
  document.querySelector("#assignment-title-input").focus();
}

function bindUploadZone(type) {
  const zone = document.querySelector(`#${type}-drop-zone`);
  const input = document.querySelector(`#${type}-file`);
  const browse = document.querySelector(`#browse-${type}`);
  const openPicker = () => input.click();
  browse.addEventListener("click", (event) => { event.stopPropagation(); openPicker(); });
  zone.addEventListener("click", (event) => {
    if (event.target !== browse && event.target !== input) openPicker();
  });
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  });
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.add("drag-over");
  }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.remove("drag-over");
  }));
  zone.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (file) extractDocumentFile(type, file);
  });
  input.addEventListener("change", () => {
    if (input.files?.[0]) extractDocumentFile(type, input.files[0]);
  });
  document.querySelector(`#remove-${type}-file`)?.addEventListener("click", () => {
    state.files[type] = { name: "", status: "", tone: "" };
    showAssignmentInput();
  });
}

async function extractDocumentFile(type, file) {
  const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
  if (![".pdf", ".docx", ".txt"].includes(extension)) {
    state.files[type] = { name: file.name, status: "Supported file types are PDF, DOCX, and TXT.", tone: "error" };
    showAssignmentInput();
    return;
  }
  if (!file.size || file.size > 10_485_760) {
    state.files[type] = { name: file.name, status: file.size ? "This file exceeds the 10 MB limit." : "This file is empty.", tone: "error" };
    showAssignmentInput();
    return;
  }
  state.files[type] = { name: file.name, status: "Extracting text...", tone: "checking" };
  showAssignmentInput();
  const form = new FormData();
  form.append("file", file);
  form.append("document_type", type);
  try {
    const result = await apiRequest("/api/files/extract", {
      method: "POST",
      body: form,
      timeoutMs: 60000,
    });
    const key = type === "assignment" ? "assignment_brief" : "rubric_text";
    state.assignment[key] = result.text;
    state.files[type] = {
      name: result.filename,
      status: `Text extracted successfully — ${result.character_count.toLocaleString()} characters`,
      tone: "success",
    };
  } catch (error) {
    state.files[type] = {
      name: file.name,
      status: `${error.message} Paste the text below instead.`,
      tone: "error",
    };
  }
  showAssignmentInput();
}

function validateAssignmentInput() {
  const errors = {};
  const data = {
    title: state.assignment.title.trim(),
    deadline: state.assignment.deadline || null,
    assignment_brief: state.assignment.assignment_brief.trim(),
    rubric_text: state.assignment.rubric_text.trim(),
  };
  if (data.title.length > 160) errors["assignment-title-input"] = "Keep the title to 160 characters or fewer.";
  if (data.deadline && data.deadline < localToday()) errors["assignment-deadline"] = "Deadline cannot be earlier than today.";
  if (data.assignment_brief.length < 80) errors["assignment-brief"] = "Add at least 80 characters from the assignment brief.";
  if (data.rubric_text.length < 30) errors["rubric-text"] = "Add at least 30 characters from the marking rubric.";
  document.querySelectorAll(".form-error").forEach((element) => { if (element.id !== "assignment-request-error") element.textContent = ""; });
  document.querySelectorAll("[aria-invalid]").forEach((element) => element.removeAttribute("aria-invalid"));
  Object.entries(errors).forEach(([id, message]) => {
    document.querySelector(`#${id}-error`).textContent = message;
    document.querySelector(`#${id}`).setAttribute("aria-invalid", "true");
  });
  if (Object.keys(errors).length) document.querySelector(`#${Object.keys(errors)[0]}`).focus();
  return { valid: !Object.keys(errors).length, data };
}

async function fillSampleAssignment() {
  const button = document.querySelector("#fill-sample");
  button.disabled = true;
  button.textContent = "Loading sample…";
  try {
    const sample = await apiRequest("/api/samples/assignment");
    state.assignment = { ...sample };
    showAssignmentInput();
    showMessage("Sample assignment added.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Fill Sample Assignment";
    document.querySelector("#assignment-request-error").textContent = error.message;
  }
}

async function analyseAssignment(event) {
  event.preventDefault();
  const result = validateAssignmentInput();
  if (!result.valid) return;
  setLoading("Reading your assignment...");
  try {
    state.analysisResult = await apiRequest("/api/assignments/analyze", {
      method: "POST",
      body: JSON.stringify(result.data),
    });
    if (!state.analysisResult?.rubric?.length || !state.analysisResult?.deliverables?.length) {
      throw new Error("Relay received an incomplete analysis response.");
    }
    showAnalysisReview();
  } catch (error) {
    showAssignmentInput();
    document.querySelector("#assignment-request-error").textContent = error.message;
  }
}

function editableList(items, type) {
  return items.map((item, index) => `<div class="editable-row">
    <input type="text" value="${escapeHtml(item)}" data-${type}-index="${index}" aria-label="${type} ${index + 1}">
    <button class="icon-button" type="button" data-remove-${type}="${index}" aria-label="Remove ${type} ${index + 1}">×</button>
  </div>`).join("");
}

function showAnalysisReview() {
  const result = state.analysisResult;
  state.view = "analysis-review";
  header.hidden = true;
  app.className = "app-main";
  const total = result.rubric.reduce((sum, item) => sum + Number(item.marks || 0), 0);
  app.innerHTML = `<section class="review-view" aria-labelledby="review-title">
    <p class="eyebrow">Assignment analysis</p>
    <h1 id="review-title">Check what Relay found</h1>
    <p class="lead">Review the assignment details before Relay builds the workflow.</p>
    <p class="mode-badge ${result.analysis_mode === "ai" ? "ai" : "fallback"}">${result.analysis_mode === "ai" ? "Analysed with AI" : "Created with fallback analysis"}</p>
    ${result.analysis_notes?.length ? `<section class="notice info"><strong>Analysis notes</strong>${list(result.analysis_notes)}</section>` : ""}
    ${result.extraction_warnings.length ? `<section class="notice warning review-warning"><strong>Review suggested</strong>${list(result.extraction_warnings)}</section>` : ""}
    <form id="review-form" novalidate>
      <section class="card review-section"><h2>Project details</h2><div class="two-column-fields">
        ${assignmentField("review-title-input", "Title", result.suggested_title, { max: 160, required: true })}
        ${assignmentField("review-deadline", "Deadline", result.suggested_deadline || "", { optional: true, type: "date", min: localToday() })}
      </div></section>
      <section class="card review-section"><div class="section-heading"><div><h2>Deliverables</h2><p>What the group must produce.</p></div><button class="button tertiary" type="button" id="add-deliverable">Add deliverable</button></div>
        <div id="deliverables-list">${editableList(result.deliverables, "deliverable")}</div></section>
      <section class="card review-section"><div class="section-heading"><div><h2>Requirements</h2><p>What the work must demonstrate or include.</p></div><button class="button tertiary" type="button" id="add-requirement">Add requirement</button></div>
        <div id="requirements-list">${editableList(result.requirements, "requirement")}</div></section>
      <section class="card review-section"><div class="section-heading"><div><h2>Rubric</h2><p>Edit criteria and marks before building.</p></div><button class="button tertiary" type="button" id="add-rubric">Add criterion</button></div>
        <div id="rubric-list">${result.rubric.map((item, index) => rubricRow(item, index)).join("")}</div>
        <p id="rubric-total" class="rubric-total ${total === 100 ? "" : "warning-text"}">Total marks: ${total}${total === 100 ? "" : " — review before continuing"}</p>
      </section>
      <p id="review-error" class="form-error" role="alert"></p>
      <div class="form-actions sticky-actions"><button class="button primary large" type="submit">Confirm and Build Workflow</button>
        <button class="button secondary" type="button" id="back-to-assignment">Back to Edit Assignment</button></div>
    </form>
  </section>`;
  bindReviewEvents();
}

function rubricRow(item, index) {
  return `<div class="rubric-row" data-rubric-row="${index}">
    <div><label for="criterion-${index}">Criterion</label><input id="criterion-${index}" data-rubric-field="criterion" value="${escapeHtml(item.criterion)}"></div>
    <div><label for="description-${index}">Description</label><input id="description-${index}" data-rubric-field="description" value="${escapeHtml(item.description)}"></div>
    <div><label for="marks-${index}">Marks</label><input id="marks-${index}" data-rubric-field="marks" type="number" min="0" max="100" value="${Number(item.marks)}"></div>
    <button class="icon-button" type="button" data-remove-rubric="${index}" aria-label="Remove rubric criterion ${index + 1}">×</button>
  </div>`;
}

function syncReviewState() {
  const result = state.analysisResult;
  result.suggested_title = document.querySelector("#review-title-input").value;
  result.suggested_deadline = document.querySelector("#review-deadline").value || null;
  result.deliverables = [...document.querySelectorAll("[data-deliverable-index]")].map((input) => input.value);
  result.requirements = [...document.querySelectorAll("[data-requirement-index]")].map((input) => input.value);
  result.rubric = [...document.querySelectorAll("[data-rubric-row]")].map((row, index) => ({
    id: result.rubric[index]?.id || `rubric-custom-${Date.now()}-${index}`,
    criterion: row.querySelector("[data-rubric-field='criterion']").value,
    description: row.querySelector("[data-rubric-field='description']").value,
    marks: Number(row.querySelector("[data-rubric-field='marks']").value || 0),
  }));
}

function bindReviewEvents() {
  document.querySelector("#review-form").addEventListener("input", () => {
    const total = [...document.querySelectorAll("[data-rubric-field='marks']")].reduce((sum, input) => sum + Number(input.value || 0), 0);
    const display = document.querySelector("#rubric-total");
    display.textContent = `Total marks: ${total}${total === 100 ? "" : " — review before continuing"}`;
    display.classList.toggle("warning-text", total !== 100);
  });
  document.querySelector("#review-form").addEventListener("submit", buildCustomProject);
  document.querySelector("#back-to-assignment").addEventListener("click", () => { syncReviewState(); showAssignmentInput(); });
  document.querySelector("#add-deliverable").addEventListener("click", () => { syncReviewState(); state.analysisResult.deliverables.push(""); showAnalysisReview(); document.querySelectorAll("[data-deliverable-index]")[state.analysisResult.deliverables.length - 1].focus(); });
  document.querySelector("#add-requirement").addEventListener("click", () => { syncReviewState(); state.analysisResult.requirements.push(""); showAnalysisReview(); document.querySelectorAll("[data-requirement-index]")[state.analysisResult.requirements.length - 1].focus(); });
  document.querySelector("#add-rubric").addEventListener("click", () => { syncReviewState(); state.analysisResult.rubric.push({ id: `rubric-custom-${Date.now()}`, criterion: "", description: "", marks: 0 }); showAnalysisReview(); });
  ["deliverable", "requirement", "rubric"].forEach((type) => {
    document.querySelectorAll(`[data-remove-${type}]`).forEach((button) => button.addEventListener("click", () => {
      syncReviewState();
      const index = Number(button.dataset[`remove${type[0].toUpperCase()}${type.slice(1)}`]);
      state.analysisResult[type === "rubric" ? "rubric" : `${type}s`].splice(index, 1);
      showAnalysisReview();
    }));
  });
}

async function buildCustomProject(event) {
  event.preventDefault();
  syncReviewState();
  const result = state.analysisResult;
  const deliverables = result.deliverables.map((item) => item.trim()).filter(Boolean);
  const requirements = result.requirements.map((item) => item.trim()).filter(Boolean);
  const rubric = result.rubric.filter((item) => item.criterion.trim());
  if (result.suggested_deadline && result.suggested_deadline < localToday()) {
    document.querySelector("#review-error").textContent = "Deadline cannot be earlier than today.";
    document.querySelector("#review-deadline").focus();
    return;
  }
  if (!result.suggested_title.trim() || !deliverables.length || !requirements.length || !rubric.length) {
    document.querySelector("#review-error").textContent = "Keep a title and at least one deliverable, requirement, and rubric criterion.";
    return;
  }
  const returningMemberName = state.newAssignmentMemberName;
  setLoading("Building an assignment-specific workflow...");
  try {
    const created = await apiRequest("/api/projects/from-analysis", {
      method: "POST",
      body: JSON.stringify({
        title: result.suggested_title.trim(),
        deadline: result.suggested_deadline || null,
        deliverables, requirements, rubric,
        original_assignment_brief: state.assignment.assignment_brief.trim(),
        original_rubric_text: state.assignment.rubric_text.trim(),
      }),
    });
    state.projectId = created.project_id;
    state.workflowWarnings = created.workflow_warnings || [];
    state.workflowGenerationMode = created.workflow_generation_mode;
    localStorage.setItem("relay_project_id", state.projectId);
    setStoredMember(null);
    state.currentTask = null;
    state.availableTasks = [];
    state.submissionText = "";
    state.submissionResult = null;
    state.handoffResult = null;
    await loadProject();
    if (returningMemberName) {
      const returningMember = await apiRequest(
        `/api/projects/${state.projectId}/members`,
        {
          method: "POST",
          body: JSON.stringify({ name: returningMemberName }),
        },
      );
      setStoredMember(returningMember);
      state.newAssignmentMemberName = null;
      await showAvailableTasks();
    } else {
      await showJoin();
    }
    showMessage(`Your workflow is ready. ${created.workflow_generation_mode === "ai" ? "AI-generated tasks." : "Fallback-generated tasks."}`);
  } catch (error) {
    showAnalysisReview();
    document.querySelector("#review-error").textContent = error.message;
  }
}

async function checkConnection() {
  const button = document.querySelector("#check-connection");
  const result = document.querySelector("#connection-result");
  button.disabled = true;
  result.className = "inline-status checking";
  result.textContent = "Checking Relay backend…";
  try {
    const health = await apiRequest("/api/health");
    if (health?.status !== "ok" || health?.app !== "Relay") {
      throw new Error("Relay received an unexpected health response.");
    }
    result.className = "inline-status success";
    result.textContent = "Relay backend connected.";
  } catch {
    result.className = "inline-status error";
    result.textContent = "Relay could not connect to the backend.";
  } finally {
    button.disabled = false;
  }
}

async function startDemo() {
  const accountName = state.memberName;
  setLoading("Preparing Relay demo...");
  try {
    const reset = await apiRequest("/api/demo/reset", { method: "POST" });
    state.projectId = reset.project_id;
    localStorage.setItem("relay_project_id", state.projectId);
    setStoredMember(null);
    state.currentTask = null;
    state.handoffResult = null;
    await loadProject();
    showMessage("Demo prepared successfully.");
    if (accountName) {
      const member = await apiRequest(`/api/projects/${state.projectId}/members`, {
        method: "POST",
        body: JSON.stringify({ name: accountName }),
      });
      setStoredMember(member);
      await showAvailableTasks();
    } else {
      await showJoin();
    }
  } catch {
    renderLanding();
    const result = document.querySelector("#connection-result");
    result.className = "inline-status error";
    result.textContent = "Relay could not prepare the demo. Check that the backend is running.";
  }
}

async function showJoin(errorMessage = "") {
  state.view = "join";
  state.loading = false;
  await loadProject();
  renderHeader();
  app.className = "app-main";
  const members = state.project?.members || [];
  app.innerHTML = `
    <section class="narrow-view" aria-labelledby="join-title">
      <p class="eyebrow">Student Group Project Workflow</p>
      <h1 id="join-title">Join the group project</h1>
      <p class="lead">Enter your name to see work that can begin now.</p>
      <form id="join-form" class="card form-card" novalidate>
        <label for="member-name">Your name</label>
        <input id="member-name" name="name" type="text" autocomplete="name" maxlength="80" placeholder="e.g. Ping" aria-describedby="join-error">
        <p id="join-error" class="form-error" role="alert">${escapeHtml(errorMessage)}</p>
        <button class="button primary full" type="submit">Join Project</button>
        <p class="privacy-note">That’s all Relay needs — no skills, personality, or role questionnaire.</p>
      </form>
      ${members.length ? `<section class="joined-members" aria-labelledby="joined-title">
        <h2 id="joined-title">Already joined</h2>
        <div class="member-list">${members.map((member) => `
          <button class="continue-member" data-member-id="${escapeHtml(member.id)}" data-member-name="${escapeHtml(member.name)}">
            <span class="avatar">${escapeHtml(member.name[0].toUpperCase())}</span>
            <span><strong>Continue as ${escapeHtml(member.name)}</strong><small>${member.total_estimated_minutes} active minutes</small></span>
            <span aria-hidden="true">→</span>
          </button>`).join("")}</div>
      </section>` : ""}
    </section>`;
  document.querySelector("#join-form").addEventListener("submit", joinProject);
  document.querySelectorAll(".continue-member").forEach((button) => {
    button.addEventListener("click", async () => {
      setStoredMember({ id: button.dataset.memberId, name: button.dataset.memberName });
      state.currentTask = null;
      await continueAfterMemberSelection();
    });
  });
  document.querySelector("#member-name").focus();
}

async function joinProject(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const input = form.elements.name;
  const error = document.querySelector("#join-error");
  const name = input.value.trim();
  if (!name) {
    error.textContent = "Enter your name to join the project.";
    input.setAttribute("aria-invalid", "true");
    input.focus();
    return;
  }
  const button = form.querySelector("button[type='submit']");
  button.disabled = true;
  button.textContent = "Joining project…";
  error.textContent = "";
  input.removeAttribute("aria-invalid");
  try {
    const member = await apiRequest(`/api/projects/${state.projectId}/members`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    setStoredMember(member);
    await continueAfterMemberSelection();
  } catch (requestError) {
    button.disabled = false;
    button.textContent = "Join Project";
    error.textContent = requestError.message;
    input.setAttribute("aria-invalid", "true");
    input.focus();
  }
}

async function continueAfterMemberSelection() {
  setLoading(`Finding ready work for ${state.memberName}…`);
  try {
    const nextAction = await apiRequest(`/api/members/${state.memberId}/next-action`);
    if (nextAction.has_active_task) {
      state.currentTask = nextAction;
      renderNextAction();
    } else {
      await showAvailableTasks();
    }
  } catch (error) {
    renderError(error.message, () => showJoin());
  }
}

async function showAvailableTasks() {
  state.view = "tasks";
  setLoading("Loading tasks that are ready…");
  const [tasks] = await Promise.all([
    apiRequest(`/api/projects/${state.projectId}/available-tasks`),
    loadProject(),
  ]);
  state.availableTasks = tasks;
  renderAvailableTasks();
}

function renderAvailableTasks() {
  state.loading = false;
  renderHeader();
  app.className = "app-main";
  const activeMemberTask = state.project?.tasks.find(
    (task) => task.claimed_by === state.memberId && ["in_progress", "needs_revision"].includes(task.status),
  );
  app.innerHTML = `
    <section class="wide-view" aria-labelledby="tasks-title">
      <div class="view-heading">
        <div><p class="eyebrow">Ready for ${escapeHtml(state.memberName)}</p>
          <h1 id="tasks-title">Choose something you can start now</h1>
          <p class="lead">Relay has already identified which tasks are ready and what each one will unlock.</p>
        </div>
        <button class="button secondary" id="refresh-tasks">Refresh Tasks</button>
      </div>
      ${state.workloadWarning ? `<aside class="notice warning"><strong>Workload note</strong><p>${escapeHtml(state.workloadWarning)}</p></aside>` : ""}
      ${activeMemberTask ? `<aside class="notice info"><strong>You already have an active task</strong>
        <p>${escapeHtml(activeMemberTask.title)}</p><button class="text-link" id="return-action">Return to My Next Action →</button></aside>` : ""}
      <div class="task-grid">
        ${state.availableTasks.length ? state.availableTasks.map(renderTaskCard).join("") : `
          <div class="empty-state card"><span aria-hidden="true">⌛</span><h2>No task is ready to claim right now</h2>
            <p>Another group member may need to complete a blocking task first.</p>
            <button class="button secondary" id="empty-workflow">View Workflow</button></div>`}
      </div>
    </section>`;
  document.querySelector("#refresh-tasks").addEventListener("click", showAvailableTasks);
  document.querySelector("#return-action")?.addEventListener("click", showNextAction);
  document.querySelector("#empty-workflow")?.addEventListener("click", showWorkflow);
  document.querySelectorAll("[data-claim-task]").forEach((button) => {
    button.addEventListener("click", () => claimTask(button.dataset.claimTask, button));
  });
  scheduleAutoClaimRefresh();
  app.focus();
}

function autoClaimText(value) {
  if (!value) return "Timer starts when this task becomes ready";
  const seconds = Math.max(0, Math.ceil((new Date(value).getTime() - Date.now()) / 1000));
  if (seconds === 0) return "Auto-assignment is due now";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `Auto-assigns in ${minutes ? `${minutes}m ` : ""}${remainder}s if unclaimed`;
}

function scheduleAutoClaimRefresh() {
  clearTimeout(state.autoRefreshTimer);
  clearInterval(state.countdownTimer);
  if (state.view !== "tasks" || !state.availableTasks.length) return;
  const updateCountdowns = () => {
    document.querySelectorAll("[data-auto-claim-at]").forEach((element) => {
      element.textContent = autoClaimText(element.dataset.autoClaimAt);
    });
  };
  updateCountdowns();
  state.countdownTimer = setInterval(updateCountdowns, 1000);
  const next = Math.min(...state.availableTasks.map(
    (task) => task.auto_claim_at ? new Date(task.auto_claim_at).getTime() : Infinity,
  ));
  const delay = Number.isFinite(next)
    ? Math.max(250, next - Date.now() + 250)
    : 10000;
  state.autoRefreshTimer = setTimeout(() => {
    if (state.view === "tasks") showAvailableTasks();
  }, delay);
}

function renderTaskCard(task) {
  const rubric = task.rubric_criterion;
  const highlighted = state.highlightedTaskIds.includes(task.id);
  return `<article class="task-card ${highlighted ? "highlighted" : ""}">
    ${highlighted ? `<div class="newly-unlocked">Just unlocked</div>` : ""}
    <div class="task-card-top"><span class="status-badge available">Available</span><span>${task.estimated_minutes} min</span></div>
    <h2>${escapeHtml(task.title)}</h2>
    <p>${escapeHtml(task.description)}</p>
    <dl class="task-meta">
      <div><dt>Work style</dt><dd>${escapeHtml(capitalise(task.work_style))}</dd></div>
      <div><dt>Rubric</dt><dd>${rubric ? `${escapeHtml(rubric.criterion)} — ${rubric.marks} marks` : "Not linked"}</dd></div>
      <div><dt>Submit</dt><dd>${escapeHtml(task.required_output.join(" · "))}</dd></div>
      <div><dt>Due</dt><dd>${task.due_date ? formatDate(task.due_date) : "No project deadline"}</dd></div>
      <div><dt>Claim timer</dt><dd><span data-auto-claim-at="${escapeHtml(task.auto_claim_at || "")}">${escapeHtml(autoClaimText(task.auto_claim_at))}</span></dd></div>
      <div><dt>Unlocks</dt><dd>${task.unlocks.length ? task.unlocks.map(taskTitle).map(escapeHtml).join(", ") : "Final task"}</dd></div>
    </dl>
    <button class="button primary full" data-claim-task="${escapeHtml(task.id)}">Claim Task</button>
  </article>`;
}

async function claimTask(taskId, button) {
  button.disabled = true;
  button.textContent = "Claiming task…";
  try {
    const result = await apiRequest(`/api/tasks/${taskId}/claim`, {
      method: "POST",
      body: JSON.stringify({ member_id: state.memberId }),
    });
    state.workloadWarning = result.workload_warning;
    state.currentTask = null;
    state.submissionText = "";
    await showNextAction();
  } catch (error) {
    showMessage(error.message, "error");
    await showAvailableTasks();
  }
}

async function showNextAction() {
  state.view = "action";
  setLoading("Loading your next action…");
  const [task] = await Promise.all([
    apiRequest(`/api/members/${state.memberId}/next-action`),
    loadProject(),
  ]);
  if (!task.has_active_task) {
    await showAvailableTasks();
    return;
  }
  state.currentTask = task;
  renderNextAction();
}

function renderNextAction() {
  state.view = "action";
  state.loading = false;
  renderHeader();
  app.className = "app-main";
  const task = state.currentTask;
  const isRevision = task.status === "needs_revision" || state.submissionResult?.complete === false;
  const context = task.dependency_context || [];
  app.innerHTML = `
    <section class="action-view" aria-labelledby="action-title">
      <div class="action-heading">
        <div><p class="eyebrow">Your next action</p><h1 id="action-title">${escapeHtml(task.task_title)}</h1></div>
        <div class="action-time"><strong>${task.estimated_minutes}</strong><span>minutes · due ${task.due_date ? formatDate(task.due_date) : "not set"}</span></div>
      </div>
      ${state.workloadWarning ? `<aside class="notice warning"><strong>Workload note</strong><p>${escapeHtml(state.workloadWarning)}</p></aside>` : ""}
      ${isRevision ? renderRevisionResult() : ""}
      <article class="action-card">
        <section class="objective-block"><span class="section-number">01</span><div><h2>Objective</h2><p>${escapeHtml(task.objective)}</p></div></section>
        <section class="start-block"><p class="card-label">Start here</p><p>${escapeHtml(task.first_action)}</p></section>
        <div class="action-columns">
          <section><h2>Steps</h2><ol>${task.execution_steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol></section>
          <section><h2>Required output</h2>${list(task.required_output, "check-list")}</section>
        </div>
        <footer class="action-footer">
          <div><span>Rubric</span><strong>${task.rubric_criterion ? `${escapeHtml(task.rubric_criterion.criterion)} — ${task.rubric_criterion.marks} marks` : "Not linked"}</strong></div>
          <div><span>This unlocks</span><strong>${task.unlocks?.length ? task.unlocks.map((item) => escapeHtml(item.title)).join(", ") : "Final task"}</strong></div>
        </footer>
      </article>
      ${context.length ? renderDependencyContext(context) : `<p class="starting-note">This starting task does not depend on earlier work.</p>`}
      <section class="submission-card card" aria-labelledby="submission-title">
        <div class="submission-heading"><div><p class="card-label">Hand off your work</p><h2 id="submission-title">Submit the required output</h2></div>
          <span class="status-badge ${escapeHtml(task.status)}">${escapeHtml(statusLabels[task.status] || task.status)}</span></div>
        <label for="submission-content">Your submission</label>
        <textarea id="submission-content" rows="15" aria-describedby="submission-help submission-error" placeholder="${escapeHtml(submissionPlaceholder(task.task_id))}">${escapeHtml(state.submissionText)}</textarea>
        <div class="textarea-meta"><span id="submission-help">Relay checks the minimum required structure, not academic quality.</span><span id="character-count">${state.submissionText.length} characters</span></div>
        <p id="submission-error" class="form-error" role="alert"></p>
        <div class="demo-helper">
          <div><strong>Demo helpers</strong><small>Sample content only — not genuine student work.</small></div>
          <button class="button tertiary" id="fill-incomplete">Fill Incomplete Example</button>
          <button class="button tertiary" id="fill-valid">Fill Demo Submission</button>
        </div>
        <button class="button primary full submit-button" id="submit-task">${isRevision ? "Update and Resubmit" : "Submit and Hand Off"} <span aria-hidden="true">→</span></button>
      </section>
    </section>`;
  const textarea = document.querySelector("#submission-content");
  textarea.addEventListener("input", () => {
    state.submissionText = textarea.value;
    document.querySelector("#character-count").textContent = `${textarea.value.length} characters`;
  });
  document.querySelector("#fill-incomplete").addEventListener("click", () => fillSubmission(false));
  document.querySelector("#fill-valid").addEventListener("click", () => fillSubmission(true));
  document.querySelector("#submit-task").addEventListener("click", submitCurrentTask);
  app.focus();
}

function renderRevisionResult() {
  const result = state.submissionResult;
  if (!result) return "";
  return `<aside class="revision-result" tabindex="-1" id="revision-result">
    <span class="result-icon" aria-hidden="true">!</span>
    <div><p class="card-label">Needs revision</p><h2>A little more is needed</h2>
      <p class="mode-badge ${result.validation_mode}">${result.validation_mode === "ai" ? "Checked with AI" : "Checked with fallback rules"}</p>
      <p>${escapeHtml(result.feedback)}</p><h3>Missing:</h3>${list(result.missing_items)}</div>
  </aside>`;
}

function renderDependencyContext(context) {
  return `<section class="context-section" aria-labelledby="context-title">
    <div class="context-heading"><span class="handoff-symbol" aria-hidden="true">↓</span>
      <div><p class="eyebrow">Automatic handoff</p><h2 id="context-title">Work passed to you</h2>
        <p>Relay attached the completed work this task depends on.</p></div></div>
    <div class="context-list">${context.map((item) => `<article class="context-card">
      <div class="context-meta"><div><span>From task</span><h3>${escapeHtml(item.source_task_title)}</h3></div>
        <div><span>Submitted by</span><strong>${escapeHtml(item.submitted_by)}</strong></div>
        <time datetime="${escapeHtml(item.submitted_at)}">${formatDate(item.submitted_at)}</time></div>
      <pre>${escapeHtml(item.content)}</pre>
    </article>`).join("")}</div>
  </section>`;
}

function submissionPlaceholder(taskId) {
  if (taskId.includes("research")) {
    return "Source 1:\\nLink:\\nSummary:\\nRelevance:\\n\\nSource 2:\\nLink:\\nSummary:\\nRelevance:\\n\\nSource 3:\\nLink:\\nSummary:\\nRelevance:";
  }
  return "Add the required sections and enough detail for Relay to check the handoff.";
}

function fillSubmission(valid) {
  const taskId = state.currentTask.task_id;
  state.submissionText = valid
    ? demoSubmissions[taskId] || `Completed output:
This submission documents the completed task in enough detail for the next group member to continue. It addresses each required output, records the main decisions made, and explains how the result supports the confirmed assignment requirements. The team can use this accepted context when completing dependent work.`
    : incompleteSubmissions[taskId] || incompleteSubmissions.default;
  const textarea = document.querySelector("#submission-content");
  textarea.value = state.submissionText;
  document.querySelector("#character-count").textContent = `${state.submissionText.length} characters`;
  textarea.focus();
}

async function submitCurrentTask() {
  const textarea = document.querySelector("#submission-content");
  const error = document.querySelector("#submission-error");
  const button = document.querySelector("#submit-task");
  const content = textarea.value.trim();
  if (!content) {
    error.textContent = "Add your submission before handing off the task.";
    textarea.setAttribute("aria-invalid", "true");
    textarea.focus();
    return;
  }
  error.textContent = "";
  textarea.removeAttribute("aria-invalid");
  button.disabled = true;
  button.textContent = "Checking your submission...";
  state.submissionText = textarea.value;
  try {
    const result = await apiRequest(`/api/tasks/${state.currentTask.task_id}/submit`, {
      method: "POST",
      body: JSON.stringify({ member_id: state.memberId, content }),
    });
    state.submissionResult = result;
    if (!result.complete) {
      state.currentTask.status = "needs_revision";
      renderNextAction();
      document.querySelector("#revision-result")?.focus();
      return;
    }
    state.handoffResult = {
      ...result,
      completedBy: state.memberName,
      completedTaskTitle: state.currentTask.task_title,
    };
    state.highlightedTaskIds = result.newly_unlocked_tasks.map((task) => task.id);
    state.submissionText = "";
    state.currentTask = null;
    await loadProject();
    renderHandoffSuccess();
  } catch (requestError) {
    button.disabled = false;
    button.innerHTML = `${state.currentTask.status === "needs_revision" ? "Update and Resubmit" : "Submit and Hand Off"} <span aria-hidden="true">→</span>`;
    error.textContent = requestError.message;
  }
}

function renderHandoffSuccess() {
  state.view = "handoff";
  renderHeader();
  app.className = "app-main";
  const result = state.handoffResult;
  const unlocked = result.newly_unlocked_tasks;
  app.innerHTML = `
    <section class="handoff-view" aria-labelledby="handoff-title">
      <div class="success-check" aria-hidden="true">✓</div>
      <p class="eyebrow">Handoff complete</p>
      <h1 id="handoff-title">Task completed</h1>
      <p class="success-lead">Your work has been accepted and passed forward.</p>
      <p class="mode-badge ${result.validation_mode}">${result.validation_mode === "ai" ? "Checked with AI" : "Checked with fallback rules"}</p>
      <div class="handoff-flow">
        <article class="handoff-node completed"><span class="status-badge completed">Completed</span>
          <h2>${escapeHtml(result.completedTaskTitle)}</h2><p>Completed by ${escapeHtml(result.completedBy)}</p></article>
        <div class="flow-arrow"><span aria-hidden="true">↓</span><strong>Work passed forward</strong></div>
        ${unlocked.length ? unlocked.map((task) => `<article class="handoff-node available">
          <span class="status-badge available">Now available</span><h2>${escapeHtml(task.title)}</h2>
          <p>Accepted work is attached as context.</p></article>`).join("") : `
          <article class="handoff-node completed"><h2>Workflow advanced</h2><p>No additional task was unlocked by this completion.</p></article>`}
      </div>
      <p class="validation-note">${escapeHtml(result.feedback)}</p>
      <div class="handoff-actions">
        ${result.workflow_complete ? `<button class="button primary large" id="view-combined">View Combined Result</button>` : ""}
        ${unlocked.length ? `<button class="button primary large" id="view-unlocked">View Unlocked Task</button>` : ""}
        <button class="button secondary large" id="handoff-workflow">Return to Workflow</button>
        <button class="text-button" id="handoff-switch">Switch Member</button>
      </div>
    </section>`;
  document.querySelector("#view-unlocked")?.addEventListener("click", showAvailableTasks);
  document.querySelector("#view-combined")?.addEventListener("click", showCombinedResult);
  document.querySelector("#handoff-workflow").addEventListener("click", showWorkflow);
  document.querySelector("#handoff-switch").addEventListener("click", switchMember);
  app.focus();
}

async function showCombinedResult() {
  setLoading("Combining every accepted answer...");
  state.combinedResult = await apiRequest(`/api/projects/${state.projectId}/combined-result`);
  renderCombinedResult();
}

function renderCombinedResult() {
  state.view = "combined-result";
  renderHeader();
  app.className = "app-main";
  const result = state.combinedResult;
  app.innerHTML = `
    <section class="wide-view combined-result-view" aria-labelledby="combined-title">
      <div class="view-heading"><div>
        <p class="eyebrow">${result.is_complete ? "Workflow complete" : "Combined draft"}</p>
        <h1 id="combined-title">Your mega result</h1>
        <p class="lead">${result.completed_task_count} of ${result.total_task_count} task answers combined in workflow order.</p>
      </div><button class="button secondary" id="combined-back">Return to Workflow</button></div>
      <div class="combined-actions">
        <button class="button primary" id="copy-combined">Copy everything</button>
        <span id="copy-status" role="status" aria-live="polite"></span>
      </div>
      <article class="combined-document"><pre>${escapeHtml(result.combined_content)}</pre></article>
    </section>`;
  document.querySelector("#combined-back").addEventListener("click", showWorkflow);
  document.querySelector("#copy-combined").addEventListener("click", async () => {
    await navigator.clipboard.writeText(result.combined_content);
    document.querySelector("#copy-status").textContent = "Copied.";
  });
  app.focus();
}

async function showStatistics() {
  state.view = "statistics";
  setLoading("Loading assignment statistics...");
  state.projectStatistics = await apiRequest("/api/projects");
  renderStatistics();
}

function renderStatistics() {
  state.view = "statistics";
  state.loading = false;
  renderHeader();
  app.className = "app-main";
  const projects = state.projectStatistics;
  const completedAssignments = projects.filter((project) => project.is_complete).length;
  const completedTasks = projects.reduce((sum, project) => sum + project.completed_tasks, 0);
  const totalTasks = projects.reduce((sum, project) => sum + project.total_tasks, 0);
  app.innerHTML = `
    <section class="wide-view statistics-view" aria-labelledby="statistics-title">
      <div class="view-heading"><div>
        <p class="eyebrow">All assignments</p>
        <h1 id="statistics-title">Statistics summary</h1>
        <p class="lead">Check finished and active assignments without leaving your current workflow.</p>
      </div></div>
      <section class="stats-overview" aria-label="Overall statistics">
        <article><span>Assignments</span><strong>${projects.length}</strong></article>
        <article><span>Finished</span><strong>${completedAssignments}</strong></article>
        <article><span>Tasks completed</span><strong>${completedTasks} / ${totalTasks}</strong></article>
      </section>
      <section class="stats-projects" aria-label="Assignment statistics">
        ${projects.length ? projects.map((project) => `
          <article class="stats-card ${project.project_id === state.projectId ? "current" : ""}">
            <div class="stats-card-heading"><div>
              <span class="status-badge ${project.is_complete ? "completed" : "in_progress"}">${project.is_complete ? "Finished" : "Active"}</span>
              <h2>${escapeHtml(project.title)}</h2>
              <p>${project.project_id === state.projectId ? "Current assignment" : "Other assignment"}${project.deadline ? ` · due ${formatDate(project.deadline)}` : ""}</p>
            </div><strong class="progress-number">${project.progress_percent}%</strong></div>
            <div class="progress-track" aria-label="${project.progress_percent}% complete"><i style="width:${project.progress_percent}%"></i></div>
            <dl>
              <div><dt>Completed</dt><dd>${project.completed_tasks}</dd></div>
              <div><dt>In progress</dt><dd>${project.in_progress_tasks}</dd></div>
              <div><dt>Available</dt><dd>${project.available_tasks}</dd></div>
              <div><dt>Waiting</dt><dd>${project.waiting_tasks}</dd></div>
              <div><dt>Members</dt><dd>${project.member_count}</dd></div>
              <div><dt>Planned time</dt><dd>${project.estimated_minutes} min</dd></div>
            </dl>
            <p class="stats-members"><strong>Member history:</strong> ${project.members.length ? project.members.map(escapeHtml).join(", ") : "No members joined yet"}</p>
          </article>`).join("") : `<div class="empty-state card"><h2>No assignments yet</h2><p>Create an assignment to begin tracking progress.</p></div>`}
      </section>
    </section>`;
  app.focus();
}

async function showWorkflow() {
  state.view = "workflow";
  setLoading("Refreshing the workflow…");
  await loadProject();
  renderWorkflow();
}

function renderWorkflow() {
  state.loading = false;
  renderHeader();
  app.className = "app-main";
  const coverage = state.project.rubric_coverage;
  const rubricMap = Object.fromEntries(state.project.rubric.map((item) => [item.id, item]));
  app.innerHTML = `
    <section class="wide-view workflow-view" aria-labelledby="workflow-title">
      <div class="view-heading"><div><p class="eyebrow">Dependency-aware plan</p><h1 id="workflow-title">${escapeHtml(state.project.title)}</h1>
        <p class="lead">${state.project.deadline ? `Deadline ${formatDate(state.project.deadline)}` : "No deadline set"} · ${state.project.tasks.length} executable tasks</p></div>
        <div class="workflow-heading-actions">
          ${state.project.tasks.some((task) => task.status === "completed") ? `<button class="button secondary" id="workflow-combined">View Combined Result</button>` : ""}
          ${state.memberId ? `<button class="button primary" id="workflow-tasks">Choose Available Work</button>` : `<button class="button primary" id="workflow-join">Join Project</button>`}
        </div>
      </div>
      <section class="workflow-summary" aria-labelledby="coverage-title">
        <div><p class="card-label">Rubric coverage</p><h2 id="coverage-title">${coverage.covered_marks} of ${coverage.total_marks} marks connected</h2></div>
        <dl>
          <div><dt>Completed</dt><dd>${coverage.completed_marks}</dd></div>
          <div><dt>In progress</dt><dd>${coverage.in_progress_marks}</dd></div>
          <div><dt>Available</dt><dd>${coverage.available_marks}</dd></div>
          <div><dt>Waiting</dt><dd>${coverage.waiting_marks}</dd></div>
        </dl>
        ${coverage.uncovered_criteria.length ? `<p class="form-error">Uncovered: ${coverage.uncovered_criteria.map((item) => escapeHtml(item.criterion)).join(", ")}</p>` : `<p class="coverage-note">Every rubric criterion is connected to workflow tasks.</p>`}
      </section>
      <section class="workflow-list" aria-label="Project workflow">
        ${state.project.tasks.map((task, index) => `<article class="workflow-item">
          <div class="workflow-rail"><span>${index + 1}</span>${index < state.project.tasks.length - 1 ? "<i></i>" : ""}</div>
          <div class="workflow-card">
            <div class="workflow-top"><span class="status-badge ${escapeHtml(task.status)}">${escapeHtml(statusLabels[task.status])}</span><span>${task.estimated_minutes} min</span></div>
            <h2>${escapeHtml(task.title)}</h2><p>${escapeHtml(task.description)}</p>
            <dl class="workflow-meta">
              <div><dt>Owner</dt><dd>${escapeHtml(memberName(task.claimed_by))}</dd></div>
              <div><dt>Rubric</dt><dd>${escapeHtml(rubricMap[task.rubric_id]?.criterion || "Not linked")}</dd></div>
              <div><dt>Due</dt><dd>${task.due_date ? formatDate(task.due_date) : "No project deadline"}</dd></div>
              <div><dt>Depends on</dt><dd>${task.dependencies.length ? task.dependencies.map(taskTitle).map(escapeHtml).join(", ") : "Can begin immediately"}</dd></div>
              <div><dt>Unlocks</dt><dd>${task.unlocks.length ? task.unlocks.map(taskTitle).map(escapeHtml).join(", ") : "Final task"}</dd></div>
            </dl>
          </div>
        </article>`).join("")}
      </section>
      ${state.project.members.length ? `<section class="workflow-members"><h2>Group members</h2><div>${state.project.members.map((member) => `<span class="member-chip"><span>${escapeHtml(member.name[0])}</span>${escapeHtml(member.name)} · ${member.total_estimated_minutes} min</span>`).join("")}</div></section>` : ""}
    </section>`;
  document.querySelector("#workflow-tasks")?.addEventListener("click", showAvailableTasks);
  document.querySelector("#workflow-combined")?.addEventListener("click", showCombinedResult);
  document.querySelector("#workflow-join")?.addEventListener("click", showJoin);
  app.focus();
}

async function switchMember() {
  setStoredMember(null);
  state.currentTask = null;
  state.submissionText = "";
  state.submissionResult = null;
  state.workloadWarning = null;
  await showJoin();
}

async function resetDemoWithConfirmation() {
  if (!window.confirm("Reset the demo? This clears all members, claims, and completed work.")) return;
  setLoading("Resetting Relay demo…");
  try {
    await apiRequest("/api/demo/reset", { method: "POST" });
    clearCurrentSession();
    renderLanding();
    showMessage("Reset complete. Upload an assignment to start a new project.");
  } catch (error) {
    renderError(error.message, resetDemoWithConfirmation);
  }
}

function renderError(message, retry) {
  state.loading = false;
  renderHeader();
  app.className = "app-main";
  app.innerHTML = `<section class="error-state card"><span aria-hidden="true">!</span>
    <h1>Relay hit a blocker</h1><p>${escapeHtml(message)}</p>
    <button class="button primary" id="retry-action">Try Again</button>
    <button class="button secondary" id="error-home">Return Home</button></section>`;
  document.querySelector("#retry-action").addEventListener("click", retry);
  document.querySelector("#error-home").addEventListener("click", renderLanding);
  app.focus();
}

function capitalise(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: value.includes("T") ? "short" : undefined }).format(date);
}

function localToday() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function openRelayChat() {
  if (!state.projectId) return;
  if (state.chatProjectId !== state.projectId) {
    state.chatProjectId = state.projectId;
    state.chatHistory = [];
    state.lastClickedSuggestion = null;
    chatMessages.innerHTML = `<div class="chat-message assistant">Ask me about this assignment, its tasks, rubric, workflow, submissions, or progress.</div>`;
    renderChatSuggestions([
      "What should I work on next?",
      "How is our assignment progressing?",
      "What does the rubric require?",
    ]);
  }
  chatPanel.hidden = false;
  chatLauncher.setAttribute("aria-expanded", "true");
  document.querySelector("#ai-chat-input").focus();
}

function closeRelayChat() {
  chatPanel.hidden = true;
  chatLauncher.setAttribute("aria-expanded", "false");
  chatLauncher.focus();
}

function beginChatResize(event) {
  event.preventDefault();
  const startX = event.clientX;
  const startY = event.clientY;
  const startWidth = chatPanel.offsetWidth;
  const startHeight = chatPanel.offsetHeight;
  const handle = event.currentTarget;
  handle.setPointerCapture(event.pointerId);
  chatPanel.classList.add("resizing");

  const resize = (moveEvent) => {
    const maximumWidth = window.innerWidth - 28;
    const maximumHeight = window.innerHeight - 95;
    chatPanel.style.width = `${Math.min(maximumWidth, Math.max(300, startWidth - (moveEvent.clientX - startX)))}px`;
    chatPanel.style.height = `${Math.min(maximumHeight, Math.max(390, startHeight - (moveEvent.clientY - startY)))}px`;
  };
  const finish = () => {
    chatPanel.classList.remove("resizing");
    handle.removeEventListener("pointermove", resize);
    handle.removeEventListener("pointerup", finish);
    handle.removeEventListener("pointercancel", finish);
  };
  handle.addEventListener("pointermove", resize);
  handle.addEventListener("pointerup", finish);
  handle.addEventListener("pointercancel", finish);
}

function appendChatMessage(content, role) {
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  message.textContent = content;
  chatMessages.appendChild(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return message;
}

function renderChatSuggestions(questions = []) {
  const uniqueQuestions = [...new Set(questions)]
    .filter((question) => question !== state.lastClickedSuggestion);
  chatSuggestions.innerHTML = uniqueQuestions.slice(0, 4)
    .map((question) => `<button type="button">${escapeHtml(question)}</button>`)
    .join("");
}

function rotateChatSuggestions(clickedQuestion) {
  const alternatives = [
    "Which task is blocking the workflow?",
    "Summarise the assignment requirements.",
    "What output does my current task need?",
    "How can we improve our rubric coverage?",
    "Which tasks can the team do in parallel?",
    "What has the team completed so far?",
    "What should we check before final submission?",
  ];
  const visible = [...chatSuggestions.querySelectorAll("button")]
    .map((button) => button.textContent)
    .filter((question) => question !== clickedQuestion);
  renderChatSuggestions([
    ...visible,
    ...alternatives.filter((question) => !visible.includes(question)),
  ]);
}

async function sendRelayChat(event) {
  event.preventDefault();
  const input = document.querySelector("#ai-chat-input");
  const button = event.currentTarget.querySelector("button[type='submit']");
  const question = input.value.trim();
  if (!question || !state.projectId) return;
  appendChatMessage(question, "user");
  const priorHistory = state.chatHistory.slice(-12);
  state.chatHistory.push({ role: "user", content: question });
  input.value = "";
  button.disabled = true;
  const pending = appendChatMessage("Thinking about your Relay project...", "assistant pending");
  try {
    const response = await apiRequest(`/api/projects/${state.projectId}/chat`, {
      method: "POST",
      body: JSON.stringify({ question, history: priorHistory }),
    });
    pending.className = `chat-message assistant${response.in_scope ? "" : " redirected"}`;
    pending.textContent = response.answer;
    state.chatHistory.push({ role: "assistant", content: response.answer });
    state.chatHistory = state.chatHistory.slice(-12);
    const fallbackQuestions = [
      "Which task is blocking the workflow?",
      "What should we check before final submission?",
      "Summarise our progress so far.",
    ];
    renderChatSuggestions([
      ...(response.suggested_questions || []),
      ...fallbackQuestions,
    ]);
    state.lastClickedSuggestion = null;
  } catch (error) {
    pending.className = "chat-message assistant chat-error";
    pending.textContent = error.message;
    state.lastClickedSuggestion = null;
  } finally {
    button.disabled = false;
    input.focus();
  }
}

chatLauncher.addEventListener("click", openRelayChat);
document.querySelector("#ai-chat-close").addEventListener("click", closeRelayChat);
document.querySelector("#ai-chat-resize").addEventListener("pointerdown", beginChatResize);
document.querySelector("#ai-chat-form").addEventListener("submit", sendRelayChat);
chatSuggestions.addEventListener("click", (event) => {
  const suggestion = event.target.closest("button");
  if (!suggestion) return;
  state.lastClickedSuggestion = suggestion.textContent;
  rotateChatSuggestions(suggestion.textContent);
  document.querySelector("#ai-chat-input").value = state.lastClickedSuggestion;
  document.querySelector("#ai-chat-form").requestSubmit();
});

document.querySelector("#brand-home").addEventListener("click", (event) => {
  event.preventDefault();
  renderLanding();
});

async function restoreSession() {
  // Always begin at the product entry point. Saved progress remains available
  // through "Continue Current Project", but never bypasses assignment upload.
  renderLanding();
}

restoreSession();

// A browser can revive the last visible screen from its page cache. Treat that
// the same as a refresh and show the assignment-upload home screen.
window.addEventListener("pageshow", () => {
  renderLanding();
});
