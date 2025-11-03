const sessionsList = document.getElementById("sessions");
const createSessionBtn = document.getElementById("create-session");
const sessionNameInput = document.getElementById("session-name");
const sessionImageInput = document.getElementById("session-image");
const imageListEl = document.getElementById("image-list");
const refreshImagesBtn = document.getElementById("refresh-images");
const refreshSessionsBtn = document.getElementById("refresh-sessions");
const fileTreeEl = document.getElementById("file-tree");
const refreshFilesBtn = document.getElementById("refresh-files");
const editorTabsEl = document.getElementById("editor-tabs");
const editorContainerEl = document.getElementById("editor-container");
const terminalTabsEl = document.getElementById("terminal-tabs");
const terminalContainerEl = document.getElementById("terminal-container");
const newTerminalBtn = document.getElementById("new-terminal");

let currentSessionId = null;
let sessions = [];
let availableImages = [];
const openEditors = new Map();
const openTerminals = new Map();

async function apiRequest(path, options = {}) {
  if (!path.startsWith("/")) {
    throw new Error("API path should start with '/'");
  }
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) {
    return null;
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "요청 실패");
  }
  return res.json();
}

async function loadSessions() {
  const data = await apiRequest("/api/sessions");
  sessions = data.sessions || [];
  renderSessions();
}

async function loadImages() {
  try {
    const data = await apiRequest("/api/images");
    availableImages = data.images || [];
    renderImages();
  } catch (error) {
    console.error("이미지 목록을 불러오지 못했습니다.", error);
    availableImages = [];
    const message = error instanceof Error && error.message
      ? `이미지를 불러오는 중 오류: ${error.message}`
      : "이미지를 불러오지 못했습니다.";
    renderImageMessage(message);
  }
}

function renderImageMessage(message) {
  if (!imageListEl) return;
  imageListEl.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.textContent = message;
  imageListEl.appendChild(empty);
  updateImageSelection();
}

function renderImages() {
  if (!imageListEl) return;
  imageListEl.innerHTML = "";
  if (!availableImages.length) {
    renderImageMessage("사용 가능한 이미지가 없습니다.");
    return;
  }
  availableImages.forEach((image) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "image-item";
    button.dataset.reference = image.reference;
    button.title = `${image.reference}\n${image.id}`;

    const title = document.createElement("strong");
    title.textContent = image.reference;
    const meta = document.createElement("span");
    meta.className = "meta";
    const metaParts = [];
    if (image.size) metaParts.push(image.size);
    if (image.created) metaParts.push(image.created);
    meta.textContent = metaParts.join(" · ") || "정보 없음";

    button.append(title, meta);
    button.addEventListener("click", () => {
      sessionImageInput.value = image.reference;
      updateImageSelection();
    });
    imageListEl.appendChild(button);
  });
  updateImageSelection();
}

function updateImageSelection() {
  if (!imageListEl) return;
  const value = sessionImageInput.value.trim();
  const items = imageListEl.querySelectorAll(".image-item");
  items.forEach((item) => {
    item.classList.toggle("active", Boolean(value) && item.dataset.reference === value);
  });
}

function renderSessions() {
  sessionsList.innerHTML = "";
  if (sessions.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "생성된 세션이 없습니다.";
    sessionsList.appendChild(empty);
    return;
  }

  sessions.forEach((session) => {
    const li = document.createElement("li");
    li.dataset.id = session.id;
    li.classList.toggle("active", currentSessionId === session.id);

    const info = document.createElement("div");
    info.className = "info";

    const nameEl = document.createElement("strong");
    nameEl.textContent = session.name || "(이름 없음)";
    const imageEl = document.createElement("span");
    imageEl.className = "image";
    imageEl.textContent = session.image || "이미지 정보 없음";
    const statusEl = document.createElement("span");
    statusEl.className = "status";
    statusEl.textContent = session.status || "상태 정보 없음";

    info.append(nameEl, imageEl, statusEl);

    const actions = document.createElement("div");
    actions.className = "actions";

    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.textContent = "열기";
    openBtn.addEventListener("click", () => selectSession(session.id));

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "종료";
    removeBtn.addEventListener("click", async () => {
      if (!confirm("세션을 종료할까요?")) return;
      await apiRequest(`/api/sessions/${session.id}`, { method: "DELETE" });
      if (currentSessionId === session.id) {
        setActiveSession(null);
      }
      await loadSessions();
    });

    actions.append(openBtn, removeBtn);
    li.append(info, actions);
    sessionsList.appendChild(li);
  });
}

async function selectSession(sessionId) {
  setActiveSession(sessionId);
  await refreshFileTree();
}

function setActiveSession(sessionId) {
  currentSessionId = sessionId;
  document.querySelectorAll(".session-list li").forEach((li) => {
    li.classList.toggle("active", li.dataset.id === sessionId);
  });
  closeAllEditors();
  closeAllTerminals();
}

async function refreshFileTree() {
  fileTreeEl.innerHTML = "";
  if (!currentSessionId) {
    const msg = document.createElement("li");
    msg.textContent = "세션을 먼저 선택하세요.";
    fileTreeEl.appendChild(msg);
    return;
  }
  const data = await apiRequest(
    `/api/sessions/${currentSessionId}/files?path=.`,
    { method: "GET" }
  );
  renderFileTree(fileTreeEl, data.items);
}

function renderFileTree(container, items) {
  container.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.textContent = `${item.isDir ? "📁" : "📄"} ${item.name}`;
    li.appendChild(button);

    if (item.isDir) {
      const childList = document.createElement("ul");
      childList.className = "nested";
      childList.style.display = "none";
      li.appendChild(childList);
      button.addEventListener("click", () => toggleDirectory(item.path, childList));
    } else {
      button.addEventListener("click", () => openFile(item.path));
    }
    container.appendChild(li);
  });
}

async function toggleDirectory(path, container) {
  if (container.dataset.loaded === "true") {
    container.style.display = container.style.display === "none" ? "block" : "none";
    return;
  }
  const data = await apiRequest(
    `/api/sessions/${currentSessionId}/files?path=${encodeURIComponent(path)}`
  );
  renderFileTree(container, data.items);
  container.dataset.loaded = "true";
  container.style.display = "block";
}

async function openFile(path) {
  if (!currentSessionId) return;
  if (openEditors.has(path)) {
    activateEditor(path);
    return;
  }
  const data = await apiRequest(
    `/api/sessions/${currentSessionId}/files/content?path=${encodeURIComponent(path)}`
  );
  const editorId = `editor-${crypto.randomUUID()}`;
  const tab = document.createElement("div");
  tab.className = "tab";
  const title = document.createElement("span");
  title.textContent = path.split("/").pop();
  const closeBtn = document.createElement("button");
  closeBtn.className = "close";
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", (ev) => {
    ev.stopPropagation();
    closeEditor(path);
  });
  tab.append(title, closeBtn);
  tab.addEventListener("click", () => activateEditor(path));

  const view = document.createElement("div");
  view.className = "editor-view";
  const toolbar = document.createElement("div");
  toolbar.className = "toolbar";
  const pathLabel = document.createElement("span");
  pathLabel.textContent = path;
  const saveBtn = document.createElement("button");
  saveBtn.className = "primary";
  saveBtn.textContent = "저장";
  toolbar.append(pathLabel, saveBtn);

  const editorHost = document.createElement("div");
  editorHost.className = "editor-host";
  view.append(toolbar, editorHost);

  editorContainerEl.appendChild(view);
  editorTabsEl.appendChild(tab);
  editorTabsEl.querySelector(".placeholder")?.remove();

  const cm = CodeMirror(editorHost, {
    value: data.content,
    mode: "javascript",
    lineNumbers: true,
    tabSize: 2,
  });

  let dirty = false;
  cm.on("change", () => {
    dirty = true;
    tab.classList.add("dirty");
  });

  saveBtn.addEventListener("click", async () => {
    await apiRequest(`/api/sessions/${currentSessionId}/files/content`, {
      method: "PUT",
      body: JSON.stringify({ path, content: cm.getValue() }),
    });
    dirty = false;
    tab.classList.remove("dirty");
  });

  openEditors.set(path, { tab, view, cm, dirty });
  activateEditor(path);
}

function activateEditor(path) {
  openEditors.forEach(({ tab, view }, key) => {
    const active = key === path;
    tab.classList.toggle("active", active);
    view.classList.toggle("active", active);
    if (active) {
      setTimeout(() => {
        const editor = openEditors.get(path).cm;
        editor.refresh();
        editor.focus();
      }, 0);
    }
  });
}

function closeEditor(path) {
  const entry = openEditors.get(path);
  if (!entry) return;
  entry.tab.remove();
  entry.view.remove();
  openEditors.delete(path);
  if (openEditors.size === 0) {
    const placeholder = document.createElement("span");
    placeholder.className = "placeholder";
    placeholder.textContent = "열린 파일이 없습니다.";
    editorTabsEl.appendChild(placeholder);
  } else {
    const next = Array.from(openEditors.keys())[0];
    activateEditor(next);
  }
}

function closeAllEditors() {
  Array.from(openEditors.keys()).forEach((path) => closeEditor(path));
}

function createTerminal() {
  if (!currentSessionId) {
    alert("세션을 먼저 선택하세요.");
    return;
  }
  const terminalId = `term-${crypto.randomUUID()}`;
  const tab = document.createElement("div");
  tab.className = "tab";
  const title = document.createElement("span");
  title.textContent = `터미널 ${openTerminals.size + 1}`;
  const closeBtn = document.createElement("button");
  closeBtn.className = "close";
  closeBtn.textContent = "×";
  tab.append(title, closeBtn);
  terminalTabsEl.appendChild(tab);

  const view = document.createElement("div");
  view.className = "terminal-view";
  terminalContainerEl.appendChild(view);

  const term = new Terminal({
    convertEol: true,
    fontSize: 14,
    theme: {
      background: "#0f172a",
    },
  });
  term.open(view);

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socketUrl = `${protocol}://${window.location.host}/api/sessions/${currentSessionId}/terminal`;
  const socket = new WebSocket(socketUrl);

  socket.addEventListener("message", (event) => {
    term.write(event.data);
  });

  socket.addEventListener("close", () => {
    term.write("\r\n[터미널이 종료되었습니다]\r\n");
  });

  term.onData((data) => {
    socket.send(JSON.stringify({ type: "input", data }));
  });

  closeBtn.addEventListener("click", (ev) => {
    ev.stopPropagation();
    socket.close();
    closeTerminal(terminalId);
  });

  tab.addEventListener("click", () => activateTerminal(terminalId));

  openTerminals.set(terminalId, { tab, view, term, socket });
  activateTerminal(terminalId);
  requestAnimationFrame(() => resizeTerminal(terminalId));
}

function activateTerminal(id) {
  openTerminals.forEach(({ tab, view }, key) => {
    const active = key === id;
    tab.classList.toggle("active", active);
    view.classList.toggle("active", active);
    if (active) {
      resizeTerminal(id);
      const terminal = openTerminals.get(id).term;
      terminal.focus();
    }
  });
}

function closeTerminal(id) {
  const entry = openTerminals.get(id);
  if (!entry) return;
  entry.tab.remove();
  entry.view.remove();
  entry.socket.close();
  openTerminals.delete(id);
  if (openTerminals.size > 0) {
    activateTerminal(Array.from(openTerminals.keys())[0]);
  }
}

function closeAllTerminals() {
  Array.from(openTerminals.keys()).forEach((id) => closeTerminal(id));
}

function resizeTerminal(id) {
  const entry = openTerminals.get(id);
  if (!entry) return;
  const { term, view, socket } = entry;
  const cols = Math.floor(view.clientWidth / 8) || 80;
  const rows = Math.floor(view.clientHeight / 18) || 24;
  term.resize(cols, rows);
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "resize", cols, rows }));
  }
}

async function createSession() {
  const name = sessionNameInput.value.trim();
  const image = sessionImageInput.value.trim();
  if (!image) {
    alert("컨테이너 이미지를 입력하세요.");
    return;
  }
  await apiRequest("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ name, image }),
  });
  sessionNameInput.value = "";
  await loadSessions();
}

createSessionBtn.addEventListener("click", createSession);
sessionImageInput.addEventListener("input", updateImageSelection);
sessionImageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    createSession();
  }
});

if (refreshSessionsBtn) {
  refreshSessionsBtn.addEventListener("click", loadSessions);
}

if (refreshImagesBtn) {
  refreshImagesBtn.addEventListener("click", loadImages);
}

refreshFilesBtn.addEventListener("click", refreshFileTree);
newTerminalBtn.addEventListener("click", createTerminal);
window.addEventListener("resize", () => {
  openTerminals.forEach((_, id) => resizeTerminal(id));
});

loadSessions();
loadImages();
