# Android Dev Container Workspace

안드로이드 앱 개발 환경을 Dev Container로 빠르게 구성하기 위한 템플릿입니다. 컨테이너에서 Android SDK, adb, Gradle을 바로 사용할 수 있도록 사전 설정된 이미지를 제공합니다.

## 준비물
- Docker 24 이상 (Linux에서는 `--add-host=host.docker.internal:host-gateway` 옵션 사용을 권장)
- VS Code + Dev Containers 확장 (CLI `code` 명령 포함)
- OpenAI API 키 (`OPENAI_API_KEY`, 선택)

## 사전 준비: Docker 이미지 빌드
Dev Container에서 사용하는 `android-dev-base` 이미지는 자동으로 만들어지지 않습니다. 작업을 시작하기 전에 한 번만 다음 명령으로 이미지를 빌드하세요.

```bash
git clone <this-repo-url>
cd workspace
docker build -t android-dev-base .
```

## 빠른 시작 (새 프로젝트)
1. 스크립트에 실행 권한을 부여합니다.
   ```bash
   chmod +x scripts/*.sh
   ```
2. 새 세션을 생성합니다. 인자를 생략하면 프롬프트에서 값을 입력할 수 있습니다.
   ```bash
   ./scripts/code_new_project.sh [git-url] [project-name]
   ```
   - Git URL을 지정하면 해당 저장소가 `session/<timestamp>-<project>/` 아래에 복제됩니다.
   - URL을 비우면 빈 프로젝트 골격이 준비됩니다.
3. VS Code가 세션 폴더를 열면 Dev Containers 확장에서 "Reopen in Container" 알림이 표시됩니다. 확인을 누르면 앞서 빌드한 `android-dev-base` 이미지를 기반으로 컨테이너가 시작됩니다.
4. 컨테이너가 준비되면 VS Code 터미널에서 Android SDK, `adb`, Gradle 등을 바로 사용할 수 있습니다.

## 기존 프로젝트 열기
이미 클론해 둔 프로젝트가 있다면 VS Code 명령 팔레트에서 `Dev Containers: Reopen in Container` 를 실행하거나, `Dev Containers: Clone Repository in Container Volume...` 명령으로 직접 복제해도 됩니다. 이때도 `android-dev-base` 이미지가 미리 빌드되어 있어야 합니다.

## 환경 변수
OpenAI API 연동이 필요하다면 컨테이너 실행 전에 키를 내보내세요.

```bash
export OPENAI_API_KEY="sk-..."
```

## ADB 연동
컨테이너는 기본적으로 `ADB_SERVER_SOCKET=tcp:host.docker.internal:5037` 으로 호스트 ADB 서버에 연결합니다. 실행 전 호스트에서 다음을 확인하세요.

```bash
adb start-server
adb devices
```

Linux에서 `host.docker.internal` 이 동작하지 않는다면 Docker를 최신 버전으로 업데이트하고 컨테이너 실행 시 `--add-host=host.docker.internal:host-gateway` 를 추가하세요.

## 문제 해결
- ADB가 연결되지 않으면 포트 5037과 방화벽 설정을 확인하세요.
- VS Code가 자동으로 열리지 않으면 CLI 설치를 확인하고 세션 폴더를 수동으로 여세요.
- `android-dev-base` 이미지가 없다는 오류가 뜨면 README의 빌드 단계를 다시 수행하세요.
- OpenAI API를 사용하려면 컨테이너 실행 전에 환경 변수를 설정해야 합니다.

## TODO
- [ ] JetBrains Fleet Dev Container 자동화 스크립트 및 가이드 공개 (준비 중)

## 웹 기반 세션 관리 서버
스크립트를 직접 실행하지 않고도 세션을 만들 수 있도록 간단한 웹 서버를 제공합니다. 서버는 `127.0.0.1:1539`에서 Git 저장소 주소와 프로젝트 이름을 입력받아 기존 스크립트와 동일한 방식으로 세션을 생성하고, 필요할 때 목록에서 VS Code / VS Code Insiders / code-server 등을 선택해 실행할 수 있습니다.

### Python으로 직접 실행
```bash
python -m server.app
```

실행 후 브라우저에서 `http://127.0.0.1:1539` 에 접속하면 됩니다.

1. 메인 화면에서 Git 저장소 주소와 프로젝트 이름을 입력해 세션을 생성합니다.
2. 로컬 에디터를 사용하고 싶다면 세션 목록의 **에디터 실행 / 상태** 열에서 원하는 항목을 선택한 뒤 **실행**을 누르세요. (선택하지 않으면 아무 에디터도 자동으로 실행되지 않습니다.)
3. 생성된 세션 목록의 **웹 IDE 열기** 링크를 누르면 브라우저 기반 코드 편집기와 터미널이 열립니다.
4. 좌측 탐색기에서 파일을 선택해 수정·저장할 수 있으며, 하단 터미널 영역에서는 일반 쉘 명령을 실시간으로 실행할 수 있습니다.

> ℹ️ 터미널 입력창에 포커스를 두고 키를 입력하면 바로 세션 디렉터리에서 쉘이 실행됩니다. `Ctrl+C`, `Ctrl+D`, 방향키 등 기본 키 조합을 지원합니다. 파일 탐색기와 터미널은 로딩/오류 상태를 표시하므로 문제가 있을 경우 화면 메시지를 확인하세요.

### Docker로 실행
```bash
docker build -f docker/server.Dockerfile -t android-dev-server .
docker run --rm -it \
  -p 1539:1539 \
  -v "$(pwd)/session:/workspace/session" \
  android-dev-server
```

### Podman으로 실행
```bash
podman build -f docker/server.Dockerfile -t android-dev-server .
podman run --rm -it \
  -p 1539:1539 \
  -v "$(pwd)/session:/workspace/session" \
  android-dev-server
```

컨테이너를 사용할 때도 호스트의 `session/` 폴더를 마운트하면 Dev Container와 동일한 구조로 세션을 재사용할 수 있습니다.
