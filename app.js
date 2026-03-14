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
  };
}

function setStatus(message, isError = false) {
  if (!projectStatus) {
    return;
  }

  projectStatus.textContent = message;
  projectStatus.style.color = isError ? "#b13b2f" : "";
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
      renderPaperTiles();
      renderPaperDetail();
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

  paperDetailCard.innerHTML = `
    <p class="section-label">Paper contents</p>
    <h3>${paper.paperName}</h3>
    <p>Uploaded ${paper.uploadedAt}. The storage structure is internal; for now this panel shows the generated paper assets available under the paper record.</p>
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
      appState.projectSlug = payload.project.project_slug;
      appState.projectRoot = payload.project.root_dir;
      appState.papers = (payload.papers || []).map(normalizePaperRecord);
      appState.selectedPaperId = appState.papers[0]?.id ?? null;

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
  renderPaperTiles();
  renderPaperDetail();
  setStatus(`Uploading ${file.name}... this may take a moment.`);

  uploadPaper(appState.projectName, file)
    .then((payload) => {
      appState.projectName = payload.project.project_name;
      appState.projectSlug = payload.project.project_slug;
      appState.projectRoot = payload.project.root_dir;
      appState.papers = (payload.papers || []).map(normalizePaperRecord);
      appState.selectedPaperId = payload.paper.paper_slug;
      renderProjectSummary();
      renderPaperTiles();
      renderPaperDetail();
      setStatus(`Ingest complete: ${payload.paper.root_dir}`);
    })
    .catch((error) => {
      setStatus(error.message, true);
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
setStatus("Start the local backend and create a project.");
fetchLlmConfig()
  .then((payload) => {
    renderLlmConfig(payload);
  })
  .catch((error) => {
    setLlmStatus(error.message, true);
  });
