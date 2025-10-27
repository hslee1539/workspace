from __future__ import annotations

import html
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List
from urllib.parse import parse_qs

from .workspace_manager import SessionResult, WorkspaceError, create_session

HOST = "0.0.0.0"
PORT = 1539


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: List[SessionResult] = []

    def add(self, session: SessionResult) -> None:
        with self._lock:
            self._sessions.append(session)

    def list(self) -> List[SessionResult]:
        with self._lock:
            return list(self._sessions)


SESSION_STORE = SessionStore()


def render_page(message: str = "", error: bool = False) -> str:
    sessions = SESSION_STORE.list()
    rows = []
    for session in sessions:
        repo = html.escape(session.repo_url or "-", quote=True)
        command = html.escape(session.editor_command or "미실행", quote=True)
        info = html.escape(session.editor_info or "", quote=True)
        info_text = f"<div class=\"info\">{info}</div>" if info else ""
        rows.append(
            """
            <tr>
              <td>{name}</td>
              <td><code>{path}</code></td>
              <td>{repo}</td>
              <td>{command}{info}</td>
            </tr>
            """.format(
                name=html.escape(session.project_name, quote=True),
                path=html.escape(str(Path(session.session_dir)), quote=True),
                repo=repo,
                command=command,
                info=info_text,
            )
        )
    rows_html = "\n".join(rows) if rows else "<tr><td colspan=4>아직 생성된 세션이 없습니다.</td></tr>"
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
    form {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 0.75rem 1rem;
      background: #f8fafc;
      border: 1px solid #d9e2ec;
      padding: 1.5rem;
      border-radius: 12px;
    }}
    label {{
      font-weight: 600;
      align-self: center;
    }}
    input[type="text"] {{
      padding: 0.6rem;
      border-radius: 8px;
      border: 1px solid #cbd2d9;
      font-size: 1rem;
    }}
    button {{
      grid-column: 1 / span 2;
      padding: 0.75rem 1.5rem;
      background: #2563eb;
      color: white;
      border-radius: 8px;
      border: none;
      font-size: 1rem;
      cursor: pointer;
    }}
    button:hover {{
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
  <p>Git 저장소와 프로젝트 이름을 입력하면 세션이 준비되고, 사용 가능한 에디터가 자동으로 열립니다.</p>
  <form method=\"post\" accept-charset=\"utf-8\">
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
        <th>에디터 실행 결과</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
""".format(banner=banner, rows=rows_html)


class WorkspaceRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        content = render_page()
        self._send_html(content)

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(content_length).decode("utf-8")
        payload = parse_qs(data)
        repo_url = payload.get("repo_url", [""])[0]
        project_name = payload.get("project_name", [""])[0]
        try:
            result = create_session(repo_url, project_name)
        except WorkspaceError as exc:
            content = render_page(str(exc), error=True)
            self._send_html(content, status=HTTPStatus.BAD_REQUEST)
            return
        SESSION_STORE.add(result)
        message = (
            f"세션이 준비되었습니다: {result.project_name}. 경로: {result.session_dir}"
        )
        if result.editor_command:
            message += f" · 실행된 명령: {result.editor_command}"
        content = render_page(message)
        self._send_html(content, status=HTTPStatus.CREATED)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(host: str = HOST, port: int = PORT) -> None:
    server = ThreadingHTTPServer((host, port), WorkspaceRequestHandler)
    print(f"서버가 시작되었습니다: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
