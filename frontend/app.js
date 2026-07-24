const app = document.querySelector("#app");
const header = document.querySelector("#app-header");
const nav = document.querySelector("#app-nav");
const memberControls = document.querySelector("#member-controls");
const globalMessage = document.querySelector("#global-message");

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
  workloadWarning: null,
  highlightedTaskIds: [],
  loading: false,
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
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
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
  const hasProject = Boolean(state.projectId);
  header.hidden = !hasProject;
  if (!hasProject) return;

  const items = [];
  if (state.memberId) {
    items.push(["action", "My Next Action"], ["tasks", "Available Tasks"]);
  }
  items.push(["workflow", "Workflow"]);
  nav.innerHTML = items
    .map(([view, label]) => `<button class="nav-link ${state.view === view ? "active" : ""}" data-view="${view}">${label}</button>`)
    .join("");

  memberControls.innerHTML = `
    ${state.memberName ? `<span class="member-chip"><span aria-hidden="true">${escapeHtml(state.memberName[0].toUpperCase())}</span>${escapeHtml(state.memberName)}</span>
      <button class="text-button" id="switch-member">Switch Member</button>` : ""}
    <button class="text-button danger-text" id="reset-demo">Reset Demo</button>`;

  nav.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.view));
  });
  document.querySelector("#switch-member")?.addEventListener("click", switchMember);
  document.querySelector("#reset-demo")?.addEventListener("click", resetDemoWithConfirmation);
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
    } else if (view === "action") {
      await showNextAction();
    } else if (view === "workflow") {
      await showWorkflow();
    } else if (view === "join") {
      await showJoin();
    } else {
      renderLanding();
    }
  } catch (error) {
    renderError(error.message, () => navigate(view));
  }
}

function renderLanding() {
  state.view = "landing";
  state.loading = false;
  header.hidden = true;
  app.className = "landing-page";
  app.innerHTML = `
    <section class="landing-shell" aria-labelledby="relay-title">
      <p class="eyebrow">HackXperience 2026 · Workflow Automation</p>
      <div class="hero-mark" aria-hidden="true">R</div>
      <h1 id="relay-title">Relay</h1>
      <p class="tagline">From assignment brief to next action.</p>
      <p class="hero-description">Relay turns group assignments into claimable, dependency-aware actions and automatically passes completed work to whoever needs it next.</p>
      <div class="hero-actions">
        <button class="button primary large" id="start-demo">Start Demo <span aria-hidden="true">→</span></button>
        <button class="button secondary large" id="check-connection">Check Connection</button>
      </div>
      <p id="connection-result" class="inline-status" role="status" aria-live="polite">Try the complete handoff in under two minutes.</p>
      <div class="demo-preview" aria-label="Demo steps">
        <div><span>1</span><strong>Claim</strong><small>Choose ready work</small></div>
        <i aria-hidden="true">→</i>
        <div><span>2</span><strong>Complete</strong><small>Meet the output</small></div>
        <i aria-hidden="true">→</i>
        <div><span>3</span><strong>Hand off</strong><small>Unlock what follows</small></div>
      </div>
    </section>`;
  document.querySelector("#start-demo").addEventListener("click", startDemo);
  document.querySelector("#check-connection").addEventListener("click", checkConnection);
  app.focus();
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
    await showJoin();
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
  app.focus();
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
        <div class="action-time"><strong>${task.estimated_minutes}</strong><span>minutes</span></div>
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
          <button class="button tertiary" id="fill-valid" ${demoSubmissions[task.task_id] ? "" : "disabled"}>Fill Demo Submission</button>
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
    ? demoSubmissions[taskId] || ""
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
        ${unlocked.length ? `<button class="button primary large" id="view-unlocked">View Unlocked Task</button>` : ""}
        <button class="button secondary large" id="handoff-workflow">Return to Workflow</button>
        <button class="text-button" id="handoff-switch">Switch Member</button>
      </div>
    </section>`;
  document.querySelector("#view-unlocked")?.addEventListener("click", showAvailableTasks);
  document.querySelector("#handoff-workflow").addEventListener("click", showWorkflow);
  document.querySelector("#handoff-switch").addEventListener("click", switchMember);
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
        ${state.memberId ? `<button class="button primary" id="workflow-tasks">Choose Available Work</button>` : `<button class="button primary" id="workflow-join">Join Project</button>`}
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
              <div><dt>Depends on</dt><dd>${task.dependencies.length ? task.dependencies.map(taskTitle).map(escapeHtml).join(", ") : "Can begin immediately"}</dd></div>
              <div><dt>Unlocks</dt><dd>${task.unlocks.length ? task.unlocks.map(taskTitle).map(escapeHtml).join(", ") : "Final task"}</dd></div>
            </dl>
          </div>
        </article>`).join("")}
      </section>
      ${state.project.members.length ? `<section class="workflow-members"><h2>Group members</h2><div>${state.project.members.map((member) => `<span class="member-chip"><span>${escapeHtml(member.name[0])}</span>${escapeHtml(member.name)} · ${member.total_estimated_minutes} min</span>`).join("")}</div></section>` : ""}
    </section>`;
  document.querySelector("#workflow-tasks")?.addEventListener("click", showAvailableTasks);
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
    const reset = await apiRequest("/api/demo/reset", { method: "POST" });
    localStorage.clear();
    state.projectId = reset.project_id;
    localStorage.setItem("relay_project_id", reset.project_id);
    setStoredMember(null);
    state.currentTask = null;
    state.submissionText = "";
    state.submissionResult = null;
    state.handoffResult = null;
    state.highlightedTaskIds = [];
    state.workloadWarning = null;
    await loadProject();
    await showJoin();
    showMessage("Demo reset successfully.");
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

document.querySelector("#brand-home").addEventListener("click", (event) => {
  event.preventDefault();
  if (state.memberId) showNextAction();
  else if (state.projectId) showJoin();
  else renderLanding();
});

async function restoreSession() {
  if (!state.projectId) {
    renderLanding();
    return;
  }
  try {
    await loadProject();
    if (state.memberId && state.project.members.some((member) => member.id === state.memberId)) {
      await continueAfterMemberSelection();
    } else {
      setStoredMember(null);
      await showJoin();
    }
  } catch {
    localStorage.clear();
    state.projectId = null;
    setStoredMember(null);
    renderLanding();
  }
}

restoreSession();
