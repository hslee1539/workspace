from __future__ import annotations

import base64
import html
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .terminal import TerminalManager
from .workspace_manager import (
    SessionResult,
    WorkspaceError,
    create_session,
    detect_editor_options,
    launch_editor,
)


LOGGER = logging.getLogger("server.app")
HTTP_LOGGER = logging.getLogger("server.http")

HOST = "0.0.0.0"
PORT = 1539


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._order: List[str] = []
        self._sessions: dict[str, SessionResult] = {}

    def add(self, session: SessionResult) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
            if session.session_id not in self._order:
                self._order.append(session.session_id)

    def list(self) -> List[SessionResult]:
        with self._lock:
            return [self._sessions[sid] for sid in self._order if sid in self._sessions]

    def get(self, session_id: str) -> Optional[SessionResult]:
        with self._lock:
            return self._sessions.get(session_id)


SESSION_STORE = SessionStore()
TERMINAL_MANAGER = TerminalManager()


def render_page(message: str = "", error: bool = False) -> str:
    sessions = SESSION_STORE.list()
    detected_options = detect_editor_options()
    rows = []
    for session in sessions:
        session.available_editors = list(detected_options)
        repo = html.escape(session.repo_url or "-", quote=True)
        session_id_safe = html.escape(session.session_id, quote=True)
        action_path = html.escape(f"/sessions/{session.session_id}/launch", quote=True)
        select_id = html.escape(f"editor-{session.session_id}", quote=True)
        if session.available_editors:
            option_tags = ["<option value=\"\">에디터 선택</option>"]
            for option in session.available_editors:
                label_text = option.label
                if option.info:
                    label_text = f"{label_text} · {option.info}"
                option_tags.append(
                    "<option value=\"{value}\">{label}</option>".format(
                        value=html.escape(option.identifier, quote=True),
                        label=html.escape(label_text, quote=True),
                    )
                )
            options_html = "".join(option_tags)
            editor_controls = (
                f"<form method=\"post\" action=\"{action_path}\" class=\"editor-form\">"
                f"<select id=\"{select_id}\" name=\"editor_id\" aria-label=\"에디터 선택\">{options_html}</select>"
                "<button type=\"submit\">실행</button>"
                "</form>"
            )
        else:
            editor_controls = "<div class=\"editor-empty\">사용 가능한 에디터가 없습니다.</div>"
        if session.editor_command:
            command_text = html.escape(session.editor_command, quote=True)
            info_html = ""
            if session.editor_info:
                info_value = session.editor_info
                if info_value.startswith("http://") or info_value.startswith("https://"):
                    info_escaped = html.escape(info_value, quote=True)
                    info_html = (
                        f" · <a href=\"{info_escaped}\" target=\"_blank\" rel=\"noopener\">{info_escaped}</a>"
                    )
                else:
                    info_html = f" · {html.escape(info_value, quote=True)}"
            last_message_html = f"마지막 실행: {command_text}{info_html}"
        else:
            last_message_html = html.escape("아직 에디터를 실행하지 않았습니다.", quote=True)
        editor_status = f"<div class=\"info\">{last_message_html}</div>"
        rows.append(
            """
            <tr>
              <td>{name}</td>
              <td><code>{path}</code></td>
              <td>{repo}</td>
              <td>{controls}{status}</td>
              <td><a href=\"/sessions/{session_id}\">웹 IDE 열기</a></td>
            </tr>
            """.format(
                name=html.escape(session.project_name, quote=True),
                path=html.escape(str(Path(session.session_dir)), quote=True),
                repo=repo,
                controls=editor_controls,
                status=editor_status,
                session_id=session_id_safe,
            )
        )
    rows_html = (
        "\n".join(rows)
        if rows
        else "<tr><td colspan=5>아직 생성된 세션이 없습니다.</td></tr>"
    )
    banner_class = "message error" if error else "message"
    banner = (
        f"<div class=\"{banner_class}\">{html.escape(message, quote=True)}</div>"
        if message
        else ""
    )
    return """
<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <title>Android Dev Container Sessions</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      margin: 2rem auto;
      max-width: 860px;
      color: #1f2933;
    }}
    h1 {{
      font-size: 1.8rem;
      margin-bottom: 1rem;
    }}
    .session-form {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 0.75rem 1rem;
      background: #f8fafc;
      border: 1px solid #d9e2ec;
      padding: 1.5rem;
      border-radius: 12px;
    }}
    .session-form label {{
      font-weight: 600;
      align-self: center;
    }}
    .session-form input[type="text"] {{
      padding: 0.6rem;
      border-radius: 8px;
      border: 1px solid #cbd2d9;
      font-size: 1rem;
    }}
    .session-form button {{
      grid-column: 1 / span 2;
      padding: 0.75rem 1.5rem;
      background: #2563eb;
      color: white;
      border-radius: 8px;
      border: none;
      font-size: 1rem;
      cursor: pointer;
    }}
    .session-form button:hover {{
      background: #1d4ed8;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 2rem;
    }}
    th, td {{
      padding: 0.75rem;
      border-bottom: 1px solid #e4ebf0;
      vertical-align: top;
    }}
    th {{
      text-align: left;
      background: #f0f4f8;
    }}
    code {{
      background: #f5f7fa;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      font-size: 0.9rem;
    }}
    .editor-form {{
      display: flex;
      gap: 0.5rem;
      align-items: center;
      margin-bottom: 0.4rem;
    }}
    .editor-form select {{
      padding: 0.35rem 0.6rem;
      border: 1px solid #cbd2d9;
      border-radius: 6px;
      font-size: 0.85rem;
    }}
    .editor-form button {{
      padding: 0.4rem 0.9rem;
      border-radius: 6px;
      border: none;
      background: #2563eb;
      color: white;
      font-size: 0.85rem;
      cursor: pointer;
    }}
    .editor-form button:hover {{
      background: #1d4ed8;
    }}
    .editor-empty {{
      font-size: 0.85rem;
      color: #9aa5b1;
      margin-bottom: 0.3rem;
    }}
    .message {{
      margin-top: 1rem;
      padding: 0.9rem 1rem;
      border-radius: 8px;
      background: #edf7ed;
      color: #276749;
    }}
    .message.error {{
      background: #fde8e8;
      color: #b91c1c;
    }}
    .info {{
      margin-top: 0.2rem;
      font-size: 0.85rem;
      color: #52606d;
    }}
  </style>
</head>
<body>
  <h1>Android Dev Container Session 생성</h1>
  <p>Git 저장소와 프로젝트 이름을 입력하면 세션이 준비됩니다. 필요하다면 아래 목록에서 원하는 에디터를 선택해 실행할 수 있습니다.</p>
  <form class=\"session-form\" method=\"post\" accept-charset=\"utf-8\">
    <label for=\"repo_url\">Git 주소</label>
    <input type=\"text\" id=\"repo_url\" name=\"repo_url\" placeholder=\"https://github.com/user/repo.git\" />
    <label for=\"project_name\">프로젝트 이름</label>
    <input type=\"text\" id=\"project_name\" name=\"project_name\" placeholder=\"예: my-android-app\" />
    <button type=\"submit\">세션 생성</button>
  </form>
  {banner}
  <h2>생성된 세션</h2>
  <table>
    <thead>
      <tr>
        <th>프로젝트</th>
        <th>경로</th>
        <th>Git 저장소</th>
        <th>에디터 실행 / 상태</th>
        <th>웹 IDE</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
""".format(banner=banner, rows=rows_html)


def render_workspace_page(session: SessionResult) -> str:
    session_title = html.escape(session.project_name or session.session_id, quote=True)
    session_root = html.escape(str(Path(session.session_dir)), quote=True)
    session_id_json = json.dumps(session.session_id)
    return f"""
<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <title>{session_title} · 웹 IDE</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    body {{
      margin: 0;
      background: #f3f4f6;
      color: #0f172a;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: #1f2937;
      color: white;
      padding: 1rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }}
    header h1 {{
      margin: 0;
      font-size: 1.1rem;
      font-weight: 600;
    }}
    header span {{
      font-size: 0.85rem;
      color: rgba(255, 255, 255, 0.75);
    }}
    header a {{
      color: white;
      text-decoration: none;
      background: rgba(255, 255, 255, 0.15);
      padding: 0.4rem 0.9rem;
      border-radius: 6px;
      font-size: 0.85rem;
    }}
    header a:hover {{
      background: rgba(255, 255, 255, 0.25);
    }}
    main {{
      flex: 1;
      display: grid;
      grid-template-columns: 260px 1fr;
      gap: 1px;
      background: #d1d5db;
      min-height: 0;
    }}
    .sidebar, .editor {{
      background: #ffffff;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .sidebar {{
      border-right: 1px solid #e5e7eb;
    }}
    .sidebar-header {{
      padding: 0.9rem 1rem 0.3rem;
      border-bottom: 1px solid #f1f5f9;
    }}
    .sidebar-header h2 {{
      margin: 0 0 0.6rem;
      font-size: 0.95rem;
      font-weight: 600;
      color: #1f2937;
    }}
    .sidebar-header button {{
      padding: 0.3rem 0.6rem;
      font-size: 0.75rem;
      border-radius: 6px;
      border: 1px solid #d1d5db;
      background: #f9fafb;
      cursor: pointer;
    }}
    .sidebar-header button:hover {{
      background: #eef2ff;
    }}
    #current-path {{
      padding: 0.3rem 1rem;
      font-size: 0.78rem;
      color: #6b7280;
      border-bottom: 1px solid #f1f5f9;
    }}
    #file-tree {{
      flex: 1;
      overflow-y: auto;
      padding: 0.6rem 0.3rem 1.2rem;
    }}
    .tree-loading,
    .tree-error {{
      padding: 0.5rem 0.8rem;
      font-size: 0.8rem;
    }}
    .tree-loading {{
      color: #6b7280;
    }}
    .tree-error {{
      color: #b91c1c;
      background: #fef2f2;
      border-radius: 6px;
    }}
    .tree-item {{
      width: 100%;
      text-align: left;
      background: transparent;
      border: none;
      padding: 0.35rem 0.8rem;
      font-size: 0.85rem;
      color: #1f2937;
      border-radius: 6px;
      display: flex;
      gap: 0.5rem;
      align-items: center;
      cursor: pointer;
    }}
    .tree-item:hover {{
      background: #f3f4f6;
    }}
    .tree-item.directory::before {{
      content: '📁';
      font-size: 0.85rem;
    }}
    .tree-item.file::before {{
      content: '📄';
      font-size: 0.85rem;
    }}
    .editor-header {{
      padding: 0.9rem 1.1rem;
      border-bottom: 1px solid #f1f5f9;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }}
    .editor-header span {{
      font-size: 0.9rem;
      color: #1f2937;
    }}
    #editor-status {{
      font-size: 0.78rem;
      color: #059669;
    }}
    .editor-actions button {{
      padding: 0.45rem 1.1rem;
      border-radius: 6px;
      border: none;
      background: #2563eb;
      color: white;
      font-size: 0.85rem;
      cursor: pointer;
    }}
    .editor-actions button:disabled {{
      opacity: 0.4;
      cursor: not-allowed;
    }}
    #editor-content {{
      flex: 1;
      width: 100%;
      border: none;
      resize: none;
      font-family: 'SFMono-Regular', 'Consolas', 'Roboto Mono', monospace;
      font-size: 0.9rem;
      padding: 1rem;
      outline: none;
      background: #f9fafb;
      color: #111827;
    }}
    section.terminal {{
      background: #111827;
      color: #e5e7eb;
      padding: 0.8rem 1rem 1.2rem;
      border-top: 1px solid #1f2937;
      font-family: 'SFMono-Regular', 'Consolas', 'Roboto Mono', monospace;
    }}
    .terminal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }}
    .terminal-header h2 {{
      margin: 0;
      font-size: 0.95rem;
      font-weight: 600;
      color: #f9fafb;
    }}
    #terminal-status {{
      font-size: 0.75rem;
      color: #a5b4fc;
    }}
    #terminal-status.status-error {{
      color: #fca5a5;
    }}
    #terminal-output {{
      background: #0b1120;
      border-radius: 8px;
      padding: 0.75rem;
      min-height: 220px;
      max-height: 320px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
    }}
    #terminal-capture {{
      margin-top: 0.6rem;
      width: 100%;
      border-radius: 6px;
      border: 1px solid #312e81;
      background: #1e1b4b;
      color: #f1f5f9;
      padding: 0.5rem;
      font-family: inherit;
      font-size: 0.85rem;
      height: 2.6rem;
      resize: none;
    }}
    .terminal-hint {{
      margin-top: 0.4rem;
      font-size: 0.75rem;
      color: #94a3b8;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{session_title}</h1>
      <span>{session_root}</span>
    </div>
    <a href=\"/\">세션 목록으로 돌아가기</a>
  </header>
  <main>
    <section class=\"sidebar\">
      <div class=\"sidebar-header\">
        <h2>파일 탐색기</h2>
        <button type=\"button\" id=\"refresh-tree\">새로고침</button>
      </div>
      <div id=\"current-path\">./</div>
      <div id=\"file-tree\"></div>
    </section>
    <section class=\"editor\">
      <div class=\"editor-header\">
        <span id=\"open-file-name\">열린 파일이 없습니다.</span>
        <div class=\"editor-actions\">
          <span id=\"editor-status\"></span>
          <button type=\"button\" id=\"save-file\" disabled>저장</button>
        </div>
      </div>
      <textarea id=\"editor-content\" spellcheck=\"false\" placeholder=\"파일을 선택하면 내용이 표시됩니다.\" disabled></textarea>
    </section>
  </main>
  <section class=\"terminal\">
    <div class=\"terminal-header\">
      <h2>터미널</h2>
      <span id=\"terminal-status\">연결 시도 중...</span>
    </div>
    <pre id=\"terminal-output\"></pre>
    <textarea id=\"terminal-capture\" spellcheck=\"false\" aria-label=\"터미널 입력\"></textarea>
    <p class=\"terminal-hint\">터미널 입력창을 클릭한 뒤 명령을 입력하세요. Ctrl+C, Ctrl+L 등 기본 단축키를 지원합니다.</p>
  </section>
  <script>
    const SESSION_ID = {session_id_json};
    (function() {{
      const treeContainer = document.getElementById('file-tree');
      const currentPathEl = document.getElementById('current-path');
      const openFileNameEl = document.getElementById('open-file-name');
      const editorStatusEl = document.getElementById('editor-status');
      const saveButton = document.getElementById('save-file');
      const editorContent = document.getElementById('editor-content');
      const refreshTree = document.getElementById('refresh-tree');
      const terminalOutput = document.getElementById('terminal-output');
      const terminalCapture = document.getElementById('terminal-capture');
      const terminalStatus = document.getElementById('terminal-status');
      terminalStatus.textContent = '연결 시도 중...';

      let currentTreePath = '';
      let currentFilePath = '';
      let fileDirty = false;
      let terminalOffset = 0;
      let terminalClosed = false;
      let terminalReady = false;
      let terminalErrorNotified = false;

      function toBase64(bytes) {{
        let binary = '';
        bytes.forEach((b) => {{
          binary += String.fromCharCode(b);
        }});
        return window.btoa(binary);
      }}

      async function fetchJSON(url, options = {{}}) {{
        const response = await fetch(url, Object.assign({{
          headers: {{ 'Content-Type': 'application/json' }},
        }}, options));
        if (!response.ok) {{
          const text = await response.text();
          throw new Error(text || '요청에 실패했습니다.');
        }}
        if (response.status === 204) {{
          return null;
        }}
        return response.json();
      }}

      function escapeHtml(value) {{
        const div = document.createElement('div');
        div.textContent = value;
        return div.innerHTML;
      }}

      function updateEditorStatus(message, isError = false) {{
        editorStatusEl.textContent = message;
        editorStatusEl.style.color = isError ? '#dc2626' : '#059669';
        if (message) {{
          setTimeout(() => {{
            if (!fileDirty) {{
              editorStatusEl.textContent = '';
            }}
          }}, 2500);
        }}
      }}

      function renderTree(data) {{
        currentTreePath = data.path || '';
        const label = currentTreePath ? './' + currentTreePath : './';
        currentPathEl.textContent = label;
        treeContainer.innerHTML = '';
        const fragment = document.createDocumentFragment();
        if (data.parent !== null) {{
          const upItem = document.createElement('button');
          upItem.type = 'button';
          upItem.className = 'tree-item directory';
          upItem.textContent = '⬆ ..';
          upItem.addEventListener('click', () => loadTree(data.parent || ''));
          fragment.appendChild(upItem);
        }}
        data.entries.forEach((entry) => {{
          const item = document.createElement('button');
          item.type = 'button';
          item.className = 'tree-item ' + (entry.type === 'dir' ? 'directory' : 'file');
          item.textContent = entry.name;
          if (entry.type === 'dir') {{
            item.addEventListener('click', () => loadTree(entry.path));
          }} else {{
            item.addEventListener('click', () => loadFile(entry.path));
          }}
          fragment.appendChild(item);
        }});
        if (!fragment.childNodes.length) {{
          const empty = document.createElement('div');
          empty.textContent = '비어 있는 디렉터리입니다.';
          empty.style.padding = '0.5rem 0.8rem';
          empty.style.fontSize = '0.8rem';
          empty.style.color = '#9ca3af';
          treeContainer.appendChild(empty);
        }} else {{
          treeContainer.appendChild(fragment);
        }}
      }}

      async function loadTree(path = '') {{
        treeContainer.innerHTML = '<div class="tree-loading">파일 목록을 불러오는 중...</div>';
        try {{
          const query = path ? '?path=' + encodeURIComponent(path) : '';
          const data = await fetchJSON(`/api/sessions/${{SESSION_ID}}/tree${{query}}`, {{ method: 'GET' }});
          renderTree(data);
        }} catch (error) {{
          treeContainer.innerHTML = '<div class="tree-error">파일 목록을 불러오지 못했습니다: ' + escapeHtml(error.message || '알 수 없는 오류') + '</div>';
          console.error(error);
        }}
      }}

      async function loadFile(path) {{
        try {{
          const query = '?path=' + encodeURIComponent(path);
          const data = await fetchJSON(`/api/sessions/${{SESSION_ID}}/file${{query}}`, {{ method: 'GET' }});
          currentFilePath = data.path;
          openFileNameEl.textContent = data.path || '(새 파일)';
          editorContent.value = data.content;
          editorContent.disabled = false;
          saveButton.disabled = false;
          fileDirty = false;
          updateEditorStatus('파일을 불러왔습니다.');
        }} catch (error) {{
          updateEditorStatus(error.message, true);
        }}
      }}

      async function saveCurrentFile() {{
        if (!currentFilePath) {{
          updateEditorStatus('저장할 파일이 없습니다.', true);
          return;
        }}
        try {{
          await fetchJSON(`/api/sessions/${{SESSION_ID}}/file`, {{
            method: 'PUT',
            body: JSON.stringify({{ path: currentFilePath, content: editorContent.value, encoding: 'utf-8' }}),
          }});
          fileDirty = false;
          updateEditorStatus('저장되었습니다.');
        }} catch (error) {{
          updateEditorStatus(error.message, true);
        }}
      }}

      function appendTerminal(text) {{
        if (text) {{
          terminalOutput.textContent += text;
          terminalOutput.scrollTop = terminalOutput.scrollHeight;
        }}
      }}

      async function pollTerminal() {{
        if (terminalClosed) {{
          return;
        }}
        if (!terminalReady) {{
          terminalStatus.classList.remove('status-error');
          terminalStatus.textContent = '연결 시도 중...';
        }}
        try {{
          const query = '?offset=' + terminalOffset;
          const data = await fetchJSON(`/api/sessions/${{SESSION_ID}}/terminal${{query}}`, {{ method: 'GET' }});
          terminalOffset = data.offset;
          appendTerminal(data.output);
          terminalClosed = Boolean(data.closed);
          terminalReady = true;
          terminalErrorNotified = false;
          terminalStatus.classList.remove('status-error');
          terminalStatus.textContent = terminalClosed ? '터미널이 종료되었습니다.' : '연결됨';
        }} catch (error) {{
          terminalReady = false;
          terminalStatus.classList.add('status-error');
          terminalStatus.textContent = '터미널 연결 오류';
          if (!terminalErrorNotified) {{
            appendTerminal('\n[터미널 오류] ' + (error.message || '연결에 실패했습니다.') + '\n');
            terminalErrorNotified = true;
          }}
          console.error(error);
        }} finally {{
          if (!terminalClosed) {{
            setTimeout(pollTerminal, 400);
          }}
        }}
      }}

      async function sendTerminal(data) {{
        if (!data) {{
          return;
        }}
        const encoder = new TextEncoder();
        const bytes = Array.from(encoder.encode(data));
        try {{
          await fetchJSON(`/api/sessions/${{SESSION_ID}}/terminal`, {{
            method: 'POST',
            body: JSON.stringify({{ data: toBase64(bytes) }}),
          }});
        }} catch (error) {{
          terminalStatus.textContent = '입력 오류';
        }}
      }}

      function translateKey(event) {{
        if (event.ctrlKey && !event.altKey && !event.metaKey) {{
          const key = event.key.toLowerCase();
          if (key === 'c') {{
            return '\u0003';
          }}
          if (key === 'd') {{
            return '\u0004';
          }}
          if (key === 'l') {{
            return '\u000c';
          }}
          if (key.length === 1) {{
            const code = key.charCodeAt(0) - 96;
            if (code >= 1 && code <= 26) {{
              return String.fromCharCode(code);
            }}
          }}
        }}
        if (event.key === 'Enter') {{
          return '\r';
        }}
        if (event.key === 'Backspace') {{
          return '\u007f';
        }}
        if (event.key === 'Tab') {{
          return '\t';
        }}
        if (event.key === 'ArrowUp') {{
          return '\u001b[A';
        }}
        if (event.key === 'ArrowDown') {{
          return '\u001b[B';
        }}
        if (event.key === 'ArrowRight') {{
          return '\u001b[C';
        }}
        if (event.key === 'ArrowLeft') {{
          return '\u001b[D';
        }}
        if (event.key.length === 1 && !event.metaKey) {{
          return event.key;
        }}
        return '';
      }}

      terminalCapture.addEventListener('keydown', (event) => {{
        const data = translateKey(event);
        if (data) {{
          event.preventDefault();
          sendTerminal(data);
        }}
      }});

      editorContent.addEventListener('input', () => {{
        if (currentFilePath) {{
          fileDirty = true;
          updateEditorStatus('수정됨');
        }}
      }});

      saveButton.addEventListener('click', saveCurrentFile);
      refreshTree.addEventListener('click', () => loadTree(currentTreePath));

      loadTree();
      pollTerminal();
      terminalCapture.focus();
    }})();
  </script>
</body>
</html>
"""


class WorkspaceRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            content = render_page()
            self._send_html(content)
            return

        if path.startswith("/sessions/"):
            self._handle_session_page(parsed)
            return

        if path.startswith("/api/"):
            self._handle_api_get(parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND.value, "요청한 경로를 찾을 수 없습니다.")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._handle_create_session()
            return

        if path.startswith("/sessions/"):
            self._handle_launch_editor(parsed)
            return

        if path.startswith("/api/"):
            self._handle_api_post(parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND.value, "지원하지 않는 경로입니다.")

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_put(parsed)
            return
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED.value, "허용되지 않은 메서드입니다.")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        HTTP_LOGGER.info(
            "%s - - [%s] %s",
            self.client_address[0],
            self.log_date_time_string(),
            format % args,
        )

    def _handle_create_session(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(content_length).decode("utf-8")
        payload = parse_qs(data)
        repo_url = payload.get("repo_url", [""])[0]
        project_name = payload.get("project_name", [""])[0]
        try:
            LOGGER.info(
                "새 세션 생성 요청: repo_url=%s, project_name=%s",
                repo_url or "(none)",
                project_name or "(none)",
            )
            result = create_session(repo_url, project_name)
        except WorkspaceError as exc:
            LOGGER.error("세션 생성 실패: %s", exc)
            content = render_page(str(exc), error=True)
            self._send_html(content, status=HTTPStatus.BAD_REQUEST)
            return
        SESSION_STORE.add(result)
        message = (
            f"세션이 준비되었습니다: {result.project_name}. 경로: {result.session_dir}"
        )
        LOGGER.info(
            "세션 생성 완료: session_id=%s, available_editors=%s",
            result.session_id,
            [option.identifier for option in result.available_editors] or "(none)",
        )
        content = render_page(message)
        self._send_html(content, status=HTTPStatus.CREATED)

    def _handle_launch_editor(self, parsed) -> None:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) != 3 or segments[0] != "sessions" or segments[2] != "launch":
            self.send_error(HTTPStatus.NOT_FOUND.value, "잘못된 세션 경로입니다.")
            return
        session_id = segments[1]
        session = SESSION_STORE.get(session_id)
        if not session:
            LOGGER.warning("존재하지 않는 세션에 대한 에디터 실행 요청: %s", session_id)
            self.send_error(HTTPStatus.NOT_FOUND.value, "세션을 찾을 수 없습니다.")
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_html(render_page("잘못된 요청입니다.", error=True), status=HTTPStatus.BAD_REQUEST)
            return
        data = self.rfile.read(content_length).decode("utf-8")
        payload = parse_qs(data)
        editor_id = payload.get("editor_id", [""])[0].strip()
        if not editor_id:
            LOGGER.debug("에디터 식별자가 비어 있습니다: session_id=%s", session_id)
            self._send_html(
                render_page("에디터를 선택해 주세요.", error=True),
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        session.available_editors = list(detect_editor_options())
        option = next((opt for opt in session.available_editors if opt.identifier == editor_id), None)
        if not option:
            LOGGER.warning(
                "선택한 에디터를 사용할 수 없습니다: session_id=%s, editor_id=%s",
                session_id,
                editor_id,
            )
            self._send_html(
                render_page("선택한 에디터를 현재 사용할 수 없습니다.", error=True),
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            launch_editor(option, session.session_dir)
        except WorkspaceError as exc:
            LOGGER.error(
                "에디터 실행 실패: session_id=%s, editor=%s, error=%s",
                session.session_id,
                option.identifier,
                exc,
            )
            self._send_html(render_page(str(exc), error=True), status=HTTPStatus.BAD_REQUEST)
            return
        session.editor_command = " ".join(option.args)
        session.editor_info = option.info
        LOGGER.info(
            "에디터 실행 완료: session_id=%s, editor=%s",
            session.session_id,
            option.identifier,
        )
        message = f"{option.label} 에디터를 실행했습니다."
        if option.info:
            message += f" 추가 정보: {option.info}"
        self._send_html(render_page(message))

    def _handle_session_page(self, parsed) -> None:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) != 2 or segments[0] != "sessions":
            self.send_error(HTTPStatus.NOT_FOUND.value, "잘못된 세션 경로입니다.")
            return
        session_id = segments[1]
        session = SESSION_STORE.get(session_id)
        if not session:
            LOGGER.warning("존재하지 않는 세션 페이지 요청: %s", session_id)
            self.send_error(HTTPStatus.NOT_FOUND.value, "세션을 찾을 수 없습니다.")
            return
        session.available_editors = list(detect_editor_options())
        TERMINAL_MANAGER.ensure(session.session_id, session.session_dir)
        LOGGER.info("세션 페이지 열기: session_id=%s", session.session_id)
        content = render_workspace_page(session)
        self._send_html(content)

    def _handle_api_get(self, parsed) -> None:
        session, action = self._extract_api_session(parsed.path)
        if not session:
            return
        query = parse_qs(parsed.query)
        if action == "tree":
            LOGGER.debug("파일 트리 요청: session_id=%s, query=%s", session.session_id, query)
            self._handle_api_tree(session, query)
        elif action == "file":
            LOGGER.debug("파일 읽기 요청: session_id=%s, query=%s", session.session_id, query)
            self._handle_api_read_file(session, query)
        elif action == "terminal":
            LOGGER.debug(
                "터미널 폴링 요청: session_id=%s, query=%s",
                session.session_id,
                query,
            )
            self._handle_api_terminal_poll(session, query)
        else:
            self._send_json({"error": "지원하지 않는 API입니다."}, HTTPStatus.NOT_FOUND)

    def _handle_api_post(self, parsed) -> None:
        session, action = self._extract_api_session(parsed.path)
        if not session:
            return
        if action == "terminal":
            LOGGER.debug("터미널 입력 수신: session_id=%s", session.session_id)
            self._handle_api_terminal_input(session)
            return
        self._send_json({"error": "지원하지 않는 API입니다."}, HTTPStatus.NOT_FOUND)

    def _handle_api_put(self, parsed) -> None:
        session, action = self._extract_api_session(parsed.path)
        if not session:
            return
        if action == "file":
            LOGGER.debug("파일 저장 요청: session_id=%s", session.session_id)
            self._handle_api_write_file(session)
            return
        self._send_json({"error": "지원하지 않는 API입니다."}, HTTPStatus.NOT_FOUND)

    def _extract_api_session(self, path: str) -> tuple[Optional[SessionResult], str]:
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) < 3 or segments[0] != "api" or segments[1] != "sessions":
            self._send_json({"error": "잘못된 API 경로입니다."}, HTTPStatus.NOT_FOUND)
            return None, ""
        session_id = segments[2]
        session = SESSION_STORE.get(session_id)
        if not session:
            self._send_json({"error": "세션을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
            return None, ""
        action = segments[3] if len(segments) > 3 else ""
        return session, action

    def _handle_api_tree(self, session: SessionResult, query: dict) -> None:
        raw_path = query.get("path", [""])[0]
        try:
            target = self._resolve_session_path(session, raw_path)
        except WorkspaceError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if not target.is_dir():
            self._send_json({"error": "디렉터리가 아닙니다."}, HTTPStatus.BAD_REQUEST)
            return
        entries = []
        for child in sorted(
            target.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower()),
        ):
            entry_path = self._relative_path(session, child)
            entries.append(
                {
                    "name": child.name,
                    "path": entry_path,
                    "type": "dir" if child.is_dir() else "file",
                }
            )
        parent = None
        if target != session.session_dir:
            parent = self._relative_path(session, target.parent)
        payload = {
            "path": self._relative_path(session, target),
            "parent": parent,
            "entries": entries,
        }
        self._send_json(payload)

    def _handle_api_read_file(self, session: SessionResult, query: dict) -> None:
        raw_path = query.get("path", [""])[0]
        try:
            target = self._resolve_session_path(session, raw_path)
        except WorkspaceError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if target.is_dir():
            self._send_json({"error": "디렉터리는 열 수 없습니다."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._send_json({"error": f"파일을 읽을 수 없습니다: {exc}"}, HTTPStatus.BAD_REQUEST)
            return
        payload = {
            "path": self._relative_path(session, target),
            "content": content,
            "encoding": "utf-8",
        }
        self._send_json(payload)

    def _handle_api_write_file(self, session: SessionResult) -> None:
        payload = self._read_json_body()
        if payload is None:
            return
        raw_path = payload.get("path", "")
        content = payload.get("content", "")
        encoding = payload.get("encoding", "utf-8")
        try:
            target = self._resolve_session_path(session, raw_path)
        except WorkspaceError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if target.is_dir():
            self._send_json({"error": "디렉터리는 파일로 저장할 수 없습니다."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding=encoding)
        except OSError as exc:
            self._send_json({"error": f"파일 저장에 실패했습니다: {exc}"}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"status": "ok"})

    def _handle_api_terminal_poll(self, session: SessionResult, query: dict) -> None:
        offset_raw = query.get("offset", ["0"])[0]
        try:
            offset = int(offset_raw)
        except ValueError:
            offset = 0
        terminal = TERMINAL_MANAGER.ensure(session.session_id, session.session_dir)
        new_offset, output, closed = terminal.read(offset)
        text = output.decode("utf-8", errors="replace")
        payload = {"offset": new_offset, "output": text, "closed": closed}
        self._send_json(payload)

    def _handle_api_terminal_input(self, session: SessionResult) -> None:
        payload = self._read_json_body()
        if payload is None:
            return
        data_b64 = payload.get("data", "")
        try:
            chunk = base64.b64decode(data_b64.encode("ascii"))
        except (ValueError, UnicodeError):
            self._send_json({"error": "잘못된 인코딩 데이터입니다."}, HTTPStatus.BAD_REQUEST)
            return
        terminal = TERMINAL_MANAGER.ensure(session.session_id, session.session_dir)
        try:
            terminal.write(chunk)
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"status": "ok"})

    def _resolve_session_path(self, session: SessionResult, raw_path: str) -> Path:
        base = session.session_dir.resolve()
        raw = raw_path.strip()
        if not raw:
            return base
        candidate = (base / unquote(raw)).resolve()
        if base not in candidate.parents and candidate != base:
            raise WorkspaceError("세션 디렉터리 밖의 경로는 접근할 수 없습니다.")
        return candidate

    def _relative_path(self, session: SessionResult, path: Path) -> str:
        try:
            relative = path.resolve().relative_to(session.session_dir.resolve())
        except ValueError:
            return ""
        result = str(relative)
        if result == ".":
            return ""
        return result

    def _read_json_body(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "잘못된 본문 길이입니다."}, HTTPStatus.BAD_REQUEST)
            return None
        data = self.rfile.read(length)
        if not data:
            self._send_json({"error": "본문이 비어 있습니다."}, HTTPStatus.BAD_REQUEST)
            return None
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "JSON 파싱에 실패했습니다."}, HTTPStatus.BAD_REQUEST)
            return None
        return payload

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def run_server(host: str = HOST, port: int = PORT) -> None:
    server = ThreadingHTTPServer((host, port), WorkspaceRequestHandler)
    LOGGER.info("서버가 시작되었습니다: http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("서버 종료 요청을 받았습니다. 종료 절차를 진행합니다.")
    finally:
        server.server_close()
        LOGGER.info("서버 리소스를 정리했습니다.")


def main() -> None:
    configure_logging()
    run_server()


if __name__ == "__main__":
    main()
