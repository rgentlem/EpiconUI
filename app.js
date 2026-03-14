const promptInput = document.querySelector("#prompt");
const injectButton = document.querySelector("#inject-context");
const sendButton = document.querySelector("#send-prompt");
const chatThread = document.querySelector(".chat-thread");
const projectForm = document.querySelector("#project-form");
const projectNameInput = document.querySelector("#project-name");
const projectRootDisplay = document.querySelector("#project-root-display");
const importPapersButton = document.querySelector("#import-papers");
const paperUploadInput = document.querySelector("#paper-upload");
const paperTileGrid = document.querySelector("#paper-tile-grid");
const paperDetailCard = document.querySelector("#paper-detail-card");
const paperCount = document.querySelector("#paper-count");
const projectStatus = document.querySelector("#project-status");

const selectedChunks =
  "Selected context:\n- Chunk 014: cohort design\n- Chunk 027: exposure metrics\n- Chunk 052: regression summary";

const appState = {
  projectName: "",
  projectSlug: "",
  projectRoot: "",
  papers: [],
  selectedPaperId: null,
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

function renderProjectSummary() {
  projectRootDisplay.textContent = appState.projectRoot || "No project selected";
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
  promptInput.value = `${promptInput.value}${spacer}${selectedChunks}`;
  promptInput.focus();
});

sendButton?.addEventListener("click", () => {
  if (!promptInput || !chatThread) {
    return;
  }

  const prompt = promptInput.value.trim();
  if (!prompt) {
    promptInput.focus();
    return;
  }

  const userMessage = document.createElement("div");
  userMessage.className = "message message-user";

  const userRole = document.createElement("span");
  userRole.className = "message-role";
  userRole.textContent = "Researcher";

  const userBody = document.createElement("p");
  userBody.textContent = prompt;
  userBody.style.whiteSpace = "pre-line";

  userMessage.append(userRole, userBody);

  const assistantMessage = document.createElement("div");
  assistantMessage.className = "message message-assistant";

  const assistantRole = document.createElement("span");
  assistantRole.className = "message-role";
  assistantRole.textContent = "Assistant";

  const assistantBody = document.createElement("p");
  assistantBody.textContent =
    "Prompt queued for model delivery. In a production integration, this panel can post the selected document chunks and prompt text to ChatGPT or another LLM endpoint, then route the response into output tiles or an RStudio handoff.";

  assistantMessage.append(assistantRole, assistantBody);

  chatThread.append(userMessage, assistantMessage);
  chatThread.scrollTop = chatThread.scrollHeight;
  promptInput.value = "";
});

projectForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = projectNameInput?.value.trim() ?? "";
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
      renderPaperTiles();
      renderPaperDetail();
      setStatus(`Project ready: ${payload.project.root_dir}`);
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
renderPaperTiles();
renderPaperDetail();
setStatus("Start the local backend and create a project.");
