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

## VS Code Web 포털 서버 실행
로컬에서 컨테이너 세션을 생성하고 VS Code Web(UI)으로 접속하고 싶다면 FastAPI 기반 포털 서버를 사용할 수 있습니다.

1. Python 의존성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
2. 포털 서버를 실행합니다.
   ```bash
   uvicorn portal.main:app --host 0.0.0.0 --port 1539
   ```
3. 브라우저에서 `http://127.0.0.1:1539` 에 접속해 Git 저장소 URL과 프로젝트 이름을 입력하면 자동으로 컨테이너가 할당되고 VS Code Web이 표시됩니다.

### 환경 변수
- `DEV_CONTAINER_IMAGE`: 세션 실행에 사용할 Docker 이미지(기본값 `android-dev-base:latest`).
- `PORTAL_ACCESS_HOST`: 포털이 링크를 생성할 때 사용할 호스트명(기본값 `127.0.0.1`). 리버스 프록시 뒤에서 실행한다면 외부에서 접근 가능한 호스트명을 지정하세요.

> **참고**: 포털은 Docker CLI가 사용 가능한 환경에서 동작합니다. 세션을 만들기 전에 `android-dev-base` 이미지를 빌드해 두어야 하며, 새 컨테이너는 포트 `20000-20999` 구간을 순차적으로 사용합니다.

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
