const promptInput = document.querySelector("#prompt");
const injectButton = document.querySelector("#inject-context");
const sendButton = document.querySelector("#send-prompt");
const chatThread = document.querySelector(".chat-thread");

const selectedChunks =
  "Selected context:\n- Chunk 014: cohort design\n- Chunk 027: exposure metrics\n- Chunk 052: regression summary";

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
