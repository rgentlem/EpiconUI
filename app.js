const promptInput = document.querySelector("#prompt");
const injectButton = document.querySelector("#inject-context");
const sendButton = document.querySelector("#send-prompt");
const chatThread = document.querySelector(".chat-thread");
const promptForm = document.querySelector("#prompt-form");
const projectForm = document.querySelector("#project-form");
const projectNameInput = document.querySelector("#project-name");
const projectSelect = document.querySelector("#project-select");
const headerProjectName = document.querySelector("#header-project-name");
const importPapersButton = document.querySelector("#import-papers");
const paperUploadInput = document.querySelector("#paper-upload");
const paperTileGrid = document.querySelector("#paper-tile-grid");
const paperDetailCard = document.querySelector("#paper-detail-card");
const paperCount = document.querySelector("#paper-count");
const projectStatus = document.querySelector("#project-status");
const paperActionSummary = document.querySelector("#paper-action-summary");
const paperActionStatusHero = document.querySelector("#paper-action-status-hero");
const paperActionStatus = document.querySelector("#paper-action-status");
const statusLogList = document.querySelector("#status-log-list");
const llmConfigForm = document.querySelector("#llm-config-form");
const llmBaseUrlInput = document.querySelector("#llm-base-url");
const llmModelInput = document.querySelector("#llm-model");
const llmApiKeyInput = document.querySelector("#llm-api-key");
const llmSystemPromptInput = document.querySelector("#llm-system-prompt");
const clearLlmConfigButton = document.querySelector("#clear-llm-config");
const llmConfigStatus = document.querySelector("#llm-config-status");
const toggleLlmConfigButton = document.querySelector("#toggle-llm-config");
const chatEmpty = document.querySelector("#chat-empty");

const selectedChunks =
  "Selected context:\n- Chunk 014: cohort design\n- Chunk 027: exposure metrics\n- Chunk 052: regression summary";

const appState = {
  projectName: "",
  projectSlug: "",
  projectRoot: "",
  papers: [],
  selectedPaperId: null,
  actionBusy: false,
  paperActionStatusMessage: "",
  statusLog: [],
  llmConfigured: false,
  llmEditorOpen: true,
  projectCatalog: [],
};

function slugify(value) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "project";
}

function getProjectRoot() {
  if (!appState.projectSlug) {
    return "";
  }

  return `~/.EpiMind/Projects/${appState.projectSlug}`;
}

function buildPaperRecord(fileName) {
  const paperName = fileName.replace(/\.pdf$/i, "");
  const paperSlug = slugify(paperName);
  const projectRoot = getProjectRoot();
  const paperRoot = `${projectRoot}/papers/${paperSlug}`;

  return {
    id: `${paperSlug}-${Date.now()}`,
    fileName,
    paperName,
    paperSlug,
    projectRoot,
    paperRoot,
    paperPath: `${paperRoot}/paper/${fileName}`,
    chunksPath: `${paperRoot}/chunks`,
    markdownPath: `${paperRoot}/markdown/${paperSlug}.md`,
    captionsPath: `${paperRoot}/captions/captions.json`,
    figuresPath: `${paperRoot}/figures`,
    tablesPath: `${paperRoot}/tables`,
    manifestPath: `${paperRoot}/manifest.json`,
    uploadedAt: new Date().toLocaleString(),
    rag: {},
  };
}

function setStatus(message, isError = false) {
  if (!projectStatus) {
    return;
  }

  projectStatus.textContent = message;
  projectStatus.style.color = isError ? "#b13b2f" : "";
}

function addStatusLog(message, level = "info", paperSlug = appState.selectedPaperId) {
  appState.statusLog.unshift({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    message,
    level,
    paperSlug: paperSlug || "",
    timestamp: new Date().toLocaleTimeString(),
  });
  appState.statusLog = appState.statusLog.slice(0, 12);
}

function setLlmStatus(message, isError = false) {
  if (!llmConfigStatus) {
    return;
  }

  llmConfigStatus.textContent = message;
  llmConfigStatus.style.color = isError ? "#b13b2f" : "";
}

function renderLlmBadge() {
  if (!toggleLlmConfigButton) {
    return;
  }

  toggleLlmConfigButton.textContent = appState.llmConfigured ? "LLM Settings" : "Configure LLM";
}

function renderLlmPanels() {
  if (!llmConfigForm) {
    return;
  }

  const shouldShowEditor = !appState.llmConfigured || appState.llmEditorOpen;
  llmConfigForm.classList.toggle("hidden", !shouldShowEditor);
}

function normalizePaperRecord(record) {
  const manifest = record.manifest || {};
  return {
    id: record.paper_slug,
    fileName: record.source_pdf ? record.source_pdf.split("/").pop() : `${record.paper_name}.pdf`,
    paperName: record.paper_name,
    paperSlug: record.paper_slug,
    projectRoot: appState.projectRoot,
    paperRoot: record.paper_dir,
    paperPath: record.source_pdf,
    chunksPath: record.chunks_dir,
    markdownPath: manifest.paper_markdown || record.markdown_dir,
    captionsPath: manifest.captions_json || record.captions_dir,
    figuresPath: record.figures_dir,
    tablesPath: record.tables_dir,
    manifestPath: `${record.paper_dir}/manifest.json`,
    uploadedAt: record.ingested_at || "Available",
    rag: record.rag || {},
  };
}

async function createProject(projectName) {
  const response = await fetch("/api/projects", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ project_name: projectName }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to create project.");
  }
  return payload;
}

async function fetchProjects() {
  const response = await fetch("/api/projects");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to load projects.");
  }
  return payload.projects || [];
}

async function uploadPaper(projectName, file) {
  const formData = new FormData();
  formData.append("project_name", projectName);
  formData.append("file", file);

  const response = await fetch("/api/upload", {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to upload paper.");
  }
  return payload;
}

async function fetchLlmConfig() {
  const response = await fetch("/api/llm/config");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to load LLM configuration.");
  }
  return payload;
}

async function saveLlmConfig(payload) {
  const response = await fetch("/api/llm/config", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to save LLM configuration.");
  }
  return body;
}

async function clearLlmConfig() {
  const response = await fetch("/api/llm/config", {
    method: "DELETE",
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to clear LLM configuration.");
  }
  return body;
}

async function sendPrompt(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      project_name: appState.projectName,
      paper_slug: appState.selectedPaperId,
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Chat request failed.");
  }
  return payload;
}

async function runPaperAction(action) {
  const response = await fetch("/api/paper-actions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action,
      project_name: appState.projectName,
      paper_slug: appState.selectedPaperId,
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Paper action failed.");
  }
  return payload;
}

function renderLlmConfig(config) {
  if (llmBaseUrlInput) {
    llmBaseUrlInput.value = config.base_url || "";
  }
  if (llmModelInput) {
    llmModelInput.value = config.model || "";
  }
  if (llmSystemPromptInput) {
    llmSystemPromptInput.value = config.system_prompt || "";
  }
  if (llmApiKeyInput) {
    llmApiKeyInput.value = "";
    llmApiKeyInput.placeholder = config.has_api_key
      ? `${
          config.api_key_source === "environment" ? "Using OPENAI_API_KEY" : "Stored server-side"
        } (${config.api_key_masked}) - leave blank to keep`
      : "Stored server-side; leave blank to keep current key";
  }

  appState.llmConfigured = Boolean(config.configured);
  appState.llmEditorOpen = !config.configured;
  setLlmStatus(
    config.configured
      ? `Configured for ${config.model} at ${config.base_url}`
      : config.base_url && config.model
        ? config.has_api_key
          ? `Connection settings saved. API key available from ${config.api_key_source === "environment" ? "OPENAI_API_KEY" : "stored config"}.`
          : "Connection settings saved, but no API key is available yet. Set OPENAI_API_KEY or enter a key and save again."
        : config.has_api_key
          ? `API key available from ${config.api_key_source === "environment" ? "OPENAI_API_KEY" : "stored config"}. Save base URL and model to enable the research console.`
          : "Save API base URL, model, and API key to enable the research console."
  );
  renderLlmBadge();
  renderLlmPanels();
}

function appendMessage(role, text) {
  if (!chatThread) {
    return;
  }

  chatEmpty?.classList.add("hidden");

  const message = document.createElement("div");
  message.className = `message message-${role}`;

  const roleLabel = document.createElement("span");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "Researcher" : role === "assistant" ? "Assistant" : "System";

  const body = document.createElement("p");
  body.textContent = text;
  body.style.whiteSpace = "pre-line";

  message.append(roleLabel, body);
  chatThread.append(message);
  chatThread.scrollTop = chatThread.scrollHeight;
}

function renderProjectSummary() {
  if (headerProjectName) {
    headerProjectName.textContent = appState.projectName || "None selected";
  }
}

function selectedPaper() {
  return appState.papers.find((item) => item.id === appState.selectedPaperId) || null;
}

function runIndexSelectedPaper() {
  const paper = selectedPaper();
  if (!paper || !appState.projectName || appState.actionBusy) {
    return;
  }

  appState.actionBusy = true;
  appState.paperActionStatusMessage = `Embedding ${paper.paperName}...`;
  addStatusLog(`Started embedding ${paper.paperName}.`, "running", paper.id);
  renderPaperDetail();
  renderPaperActionPanel();

  runPaperAction("index_rag")
    .then((payload) => {
      syncProjectPayload(payload);
      appState.selectedPaperId = payload.paper?.paper_slug || paper.id;
      appState.paperActionStatusMessage = `Indexed ${payload.paper.paper_name}.`;
      addStatusLog(`Indexed ${payload.paper.paper_name}.`, "success", payload.paper?.paper_slug || paper.id);
      renderProjectSummary();
      renderPaperTiles();
      renderPaperDetail();
      renderPaperActionPanel();
    })
    .catch((error) => {
      appState.paperActionStatusMessage = error.message;
      addStatusLog(`Embedding failed: ${error.message}`, "error", paper.id);
    })
    .finally(() => {
      appState.actionBusy = false;
      renderPaperDetail();
      renderPaperActionPanel();
    });
}

function renderPaperActionPanel() {
  if (!paperActionSummary || !paperActionStatusHero || !paperActionStatus || !statusLogList) {
    return;
  }

  const paper = selectedPaper();
  if (!paper) {
    paperActionSummary.innerHTML = `
      <p class="section-label">No paper selected</p>
      <h3>Select a paper on the left</h3>
      <p>The selected paper's indexing details will appear here.</p>
    `;
    paperActionStatusHero.innerHTML = `
      <p class="section-label">Current state</p>
      <h3>No paper selected</h3>
      <p>Choose a paper to see indexing state.</p>
    `;
    paperActionStatus.textContent = "Choose a paper to enable actions.";
    statusLogList.innerHTML = '<p class="status-log-empty">No actions yet.</p>';
    return;
  }

  const rag = paper.rag || {};
  const indexed = Boolean(rag.indexed_at);
  paperActionSummary.innerHTML = `
    <p class="section-label">Active paper</p>
    <h3>${paper.paperName}</h3>
    <p>Selected for vector indexing.</p>
    <div class="action-meta-grid">
      <div class="action-meta-item">
        <span class="section-label">Vector status</span>
        <strong>${indexed ? "Indexed" : "Not indexed"}</strong>
      </div>
      <div class="action-meta-item">
        <span class="section-label">Embedding model</span>
        <strong>${rag.embedding_model || "Not set"}</strong>
      </div>
      <div class="action-meta-item">
        <span class="section-label">Chunks</span>
        <strong>${rag.chunk_count || "Unknown"}</strong>
      </div>
      <div class="action-meta-item">
        <span class="section-label">Last indexed</span>
        <strong>${rag.indexed_at || "Not yet run"}</strong>
      </div>
    </div>
  `;
  paperActionStatusHero.innerHTML = `
    <p class="section-label">Current state</p>
    <h3>${indexed ? "Indexed" : "Not indexed"}</h3>
    <p>${
      appState.actionBusy
        ? `Embedding ${paper.paperName} now.`
        : indexed
          ? `${paper.paperName} is present in Postgres.`
          : `${paper.paperName} has not been embedded yet.`
    }</p>
  `;

  if (appState.actionBusy) {
    paperActionStatus.textContent = appState.paperActionStatusMessage || `Running action for ${paper.paperName}...`;
  } else {
    paperActionStatus.textContent =
      appState.paperActionStatusMessage ||
      (indexed ? `Vector index ready for ${paper.paperName}.` : `Vector index not created yet for ${paper.paperName}.`);
  }

  const visibleEntries = appState.statusLog.filter((entry) => !entry.paperSlug || entry.paperSlug === paper.id).slice(0, 6);
  statusLogList.innerHTML = visibleEntries.length
    ? visibleEntries
        .map(
          (entry) => `
            <div class="status-log-item status-${entry.level}">
              <span class="section-label">${entry.timestamp}</span>
              <p>${entry.message}</p>
            </div>
          `
        )
        .join("")
    : '<p class="status-log-empty">No actions yet.</p>';
}

function renderProjectCatalog() {
  if (!projectSelect) {
    return;
  }

  const selectedName = appState.projectName || projectSelect.value;
  projectSelect.innerHTML = '<option value="">Choose existing project</option>';
  appState.projectCatalog.forEach((project) => {
    const option = document.createElement("option");
    option.value = project.project_name;
    option.textContent = project.project_name;
    if (project.project_name === selectedName) {
      option.selected = true;
    }
    projectSelect.append(option);
  });
}

function renderPaperTiles() {
  if (!paperTileGrid || !paperCount) {
    return;
  }

  paperTileGrid.innerHTML = "";
  paperCount.textContent = `${appState.papers.length} paper${appState.papers.length === 1 ? "" : "s"}`;

  appState.papers.forEach((paper) => {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = `paper-tile${paper.id === appState.selectedPaperId ? " active" : ""}`;
    tile.innerHTML = `
      <p class="section-label">Paper tile</p>
      <h4>${paper.paperName}</h4>
      <div class="paper-tile-meta">
        <p>${paper.uploadedAt}</p>
        <p>Ready for parsing, chunking, and analysis links</p>
      </div>
    `;
    tile.addEventListener("click", () => {
      appState.selectedPaperId = paper.id;
      appState.paperActionStatusMessage = "";
      renderPaperTiles();
      renderPaperDetail();
      renderPaperActionPanel();
    });
    paperTileGrid.append(tile);
  });
}

function renderPaperDetail() {
  if (!paperDetailCard) {
    return;
  }

  const paper = appState.papers.find((item) => item.id === appState.selectedPaperId);
  if (!paper) {
    paperDetailCard.innerHTML = `
      <p class="section-label">Paper contents</p>
      <h3>No paper selected</h3>
      <p>Upload a PDF after naming the project. A tile will be created here and selecting it will show the generated paper assets.</p>
    `;
    return;
  }

  const rag = paper.rag || {};
  const indexed = Boolean(rag.indexed_at);
  paperDetailCard.innerHTML = `
    <p class="section-label">Paper contents</p>
    <h3>${paper.paperName}</h3>
    <div class="paper-inline-tools">
      <div class="paper-inline-state">
        <span class="section-label">Vector DB</span>
        <strong>${appState.actionBusy ? "Working..." : indexed ? "Indexed" : "Not indexed"}</strong>
      </div>
      <button class="primary-button" id="index-paper-inline" type="button" ${appState.actionBusy ? "disabled" : ""}>
        ${appState.actionBusy ? "Embedding..." : indexed ? "Refresh Embedding" : "Embed Paper"}
      </button>
    </div>
    <p>${appState.paperActionStatusMessage || `Uploaded ${paper.uploadedAt}.`}</p>
    <div class="paper-detail-list">
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>captions/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>figures/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>markdown/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>paper/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>tables/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>chunks/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">File</span>
        <code>manifest.json</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">Directory</span>
        <code>metadata/</code>
      </div>
      <div class="paper-path-item">
        <span class="section-label">File</span>
        <code>paper.json</code>
      </div>
    </div>
  `;
  paperDetailCard.querySelector("#index-paper-inline")?.addEventListener("click", runIndexSelectedPaper);
}

function syncProjectPayload(payload) {
  appState.projectName = payload.project.project_name;
  appState.projectSlug = payload.project.project_slug;
  appState.projectRoot = payload.project.root_dir;
  appState.papers = (payload.papers || []).map(normalizePaperRecord);
}

injectButton?.addEventListener("click", () => {
  if (!promptInput) {
    return;
  }

  const spacer = promptInput.value.trim() ? "\n\n" : "";
  const paper = appState.papers.find((item) => item.id === appState.selectedPaperId);
  const selectedContext = paper
    ? `Selected paper: ${paper.paperName}\nAvailable assets: markdown/, chunks/, captions/, figures/, tables/`
    : selectedChunks;
  promptInput.value = `${promptInput.value}${spacer}${selectedContext}`;
  promptInput.focus();
});

promptForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!promptInput || !chatThread) {
    return;
  }

  const prompt = promptInput.value.trim();
  if (!prompt) {
    promptInput.focus();
    return;
  }

  appendMessage("user", prompt);
  promptInput.value = "";
  sendButton.disabled = true;
  sendPrompt(prompt)
    .then((payload) => {
      appendMessage("assistant", payload.answer);
      setLlmStatus(`Response received from ${payload.model}.`);
    })
    .catch((error) => {
      appendMessage("system", error.message);
      setLlmStatus(error.message, true);
    })
    .finally(() => {
      sendButton.disabled = false;
    });
});

promptInput?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey) {
    return;
  }

  event.preventDefault();
  promptForm?.requestSubmit();
});

llmConfigForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = {
    base_url: String(formData.get("llm-base-url") || "").trim(),
    model: String(formData.get("llm-model") || "").trim(),
    api_key: String(formData.get("llm-api-key") || "").trim(),
    system_prompt: String(formData.get("llm-system-prompt") || "").trim(),
  };

  setLlmStatus("Saving LLM connection...");
  saveLlmConfig(payload)
    .then((payload) => {
      renderLlmConfig(payload);
    })
    .catch((error) => {
      setLlmStatus(error.message, true);
    });
});

clearLlmConfigButton?.addEventListener("click", () => {
  clearLlmConfig()
    .then(() => {
      renderLlmConfig({
        configured: false,
        base_url: "",
        model: "",
        has_api_key: false,
        api_key_masked: "",
        api_key_source: "",
        system_prompt: "",
      });
      setLlmStatus("Stored LLM credentials cleared.");
    })
    .catch((error) => {
      setLlmStatus(error.message, true);
    });
});

toggleLlmConfigButton?.addEventListener("click", () => {
  appState.llmEditorOpen = true;
  renderLlmPanels();
  setLlmStatus("Edit the stored LLM connection and save again when ready.");
});

projectForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = projectNameInput?.value.trim() || projectSelect?.value.trim() || "";
  if (!value) {
    projectNameInput?.focus();
    return;
  }

  setStatus("Creating project...");

  createProject(value)
    .then((payload) => {
      appState.projectName = payload.project.project_name;
      syncProjectPayload(payload);
      appState.selectedPaperId = appState.papers[0]?.id ?? null;
      appState.paperActionStatusMessage = "";
      addStatusLog(`Opened project ${payload.project.project_name}.`, "info", appState.selectedPaperId);

      renderProjectSummary();
      if (!appState.projectCatalog.some((project) => project.project_name === payload.project.project_name)) {
        appState.projectCatalog.push({
          project_name: payload.project.project_name,
          project_slug: payload.project.project_slug,
          root_dir: payload.project.root_dir,
        });
        appState.projectCatalog.sort((a, b) => a.project_name.localeCompare(b.project_name));
      }
      renderProjectCatalog();
      renderPaperTiles();
      renderPaperDetail();
      renderPaperActionPanel();
      setStatus(`Project ready: ${payload.project.root_dir}`);
      if (projectNameInput) {
        projectNameInput.value = "";
      }
    })
    .catch((error) => {
      setStatus(error.message, true);
    });
});

importPapersButton?.addEventListener("click", () => {
  if (!appState.projectSlug) {
    projectNameInput?.focus();
    return;
  }
  paperUploadInput?.click();
});

paperUploadInput?.addEventListener("change", (event) => {
  const input = event.target;
  const file = input?.files?.[0];
  if (!file || !appState.projectSlug) {
    return;
  }

  const placeholder = buildPaperRecord(file.name);
  appState.papers = [placeholder, ...appState.papers.filter((item) => item.paperSlug !== placeholder.paperSlug)];
  appState.selectedPaperId = placeholder.id;
  appState.paperActionStatusMessage = `Uploading ${file.name}...`;
  renderPaperTiles();
  renderPaperDetail();
  renderPaperActionPanel();
  setStatus(`Uploading ${file.name}... this may take a moment.`);
  addStatusLog(`Started upload for ${placeholder.paperName}.`, "running", placeholder.id);

  uploadPaper(appState.projectName, file)
    .then((payload) => {
      appState.projectName = payload.project.project_name;
      syncProjectPayload(payload);
      appState.selectedPaperId = payload.paper.paper_slug;
      appState.paperActionStatusMessage = payload.rag?.indexed_at || payload.paper?.rag?.indexed_at
        ? `Vector index ready for ${payload.paper.paper_name}.`
        : "";
      addStatusLog(`Ingested ${payload.paper.paper_name}.`, "success", payload.paper.paper_slug);
      renderProjectSummary();
      renderPaperTiles();
      renderPaperDetail();
      renderPaperActionPanel();
      setStatus(`Ingest complete: ${payload.paper.root_dir}`);
    })
    .catch((error) => {
      setStatus(error.message, true);
      appState.paperActionStatusMessage = error.message;
      addStatusLog(`Upload failed: ${error.message}`, "error", placeholder.id);
    })
    .finally(() => {
      input.value = "";
    });
});

renderProjectSummary();
fetchProjects()
  .then((projects) => {
    appState.projectCatalog = projects;
    renderProjectCatalog();
  })
  .catch((error) => {
    setStatus(error.message, true);
  });
renderPaperTiles();
renderPaperDetail();
renderPaperActionPanel();
setStatus("Start the local backend and create a project.");
fetchLlmConfig()
  .then((payload) => {
    renderLlmConfig(payload);
  })
  .catch((error) => {
    setLlmStatus(error.message, true);
  });
