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
FastAPI 기반 포털 서버를 이용하면 브라우저에서 Git 저장소 URL과 프로젝트 이름만으로 VS Code Web(UI)에 접속할 수 있습니다.

### Docker / Podman으로 실행하기 (권장)
Python을 로컬에 설치할 필요 없이 컨테이너로 포털을 실행할 수 있습니다.

1. `android-dev-base` 이미지를 먼저 빌드합니다. (위 "사전 준비" 참고)
2. `docker compose up --build portal` 명령으로 포털을 실행합니다. Podman을 사용할 경우에도 Docker 호환 API를 통해 제어하므로, 추가 환경 변수를 지정할 필요 없이 아래 방법 중 편한 것을 사용하세요.
   - Podman 4.4 이상: `podman compose up --build portal`
   - Podman 4 미만: `pip install podman-compose` 후 `podman-compose up --build portal`
   - 위 명령이 `compose provider` 오류로 실패한다면 Podman Compose 플러그인이 설치되지 않은 상태이므로, 배포판 패키지(`dnf install podman-compose`, `apt install podman-compose` 등)나 `pip install podman-compose` 로 플러그인을 준비한 뒤 다시 실행하세요.
   - Docker를 사용할 때는 호스트의 Docker 소켓(`/var/run/docker.sock`)과 현재 디렉터리의 `session/` 폴더가 컨테이너에 마운트됩니다. (권장: 실행 전에 `mkdir -p session` 으로 폴더를 만들어 두세요.)
   - Podman을 사용할 경우에도 Podman의 Docker 호환 API 소켓을 `/var/run/docker.sock` 에 마운트하면 컨테이너 내부 Docker CLI가 그대로 동작합니다.
3. 브라우저에서 `http://127.0.0.1:1539` 에 접속하면 자동으로 컨테이너가 할당되고 VS Code Web이 표시됩니다.

필요하다면 다음과 같이 단일 컨테이너 명령으로 실행할 수도 있습니다.

```bash
docker build -t android-dev-portal -f portal/Dockerfile .
docker run --rm -it \
  -e PORTAL_ACCESS_HOST=127.0.0.1 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/session:/app/session \
  -p 1539:1539 \
  --name android-dev-portal \
  android-dev-portal
```

Podman을 사용할 때는 이미지 짧은 이름이 차단되지 않도록 태그를 `localhost/` 접두사와 함께 빌드하고 실행하세요. 포털 컨테이너 내부에서는 Docker CLI로 Podman의 Docker 호환 API에 연결하므로, 짧은 이름 이슈만 해결하면 동일한 명령으로 세션을 띄울 수 있습니다.

```bash
podman build -t localhost/android-dev-portal -f portal/Dockerfile .
# Podman 원격 API 소켓이 없으면 먼저 활성화해야 합니다.
#   - systemd(루트리스): systemctl --user enable --now podman.socket
#     (필요시 `loginctl enable-linger $USER` 로 사용자 세션을 유지)
#   - 비 systemd 환경:   podman system service --time=0 --socket-path unix://$(podman info --format '{{.Host.RemoteSocket.Path}}')
# 소켓 파일이 존재하는지 반드시 확인하세요.
PODMAN_SOCKET=$(podman info --format '{{.Host.RemoteSocket.Path}}')
if [ ! -S "$PODMAN_SOCKET" ]; then
  echo "Podman API 소켓을 찾을 수 없습니다: $PODMAN_SOCKET" >&2
  echo "위 주석에 안내된 명령으로 소켓을 활성화한 뒤 다시 시도하세요." >&2
  exit 1
fi
podman run --rm -it \
  -e PORTAL_ACCESS_HOST=127.0.0.1 \
  -v ${PODMAN_SOCKET}:/var/run/docker.sock \
  -v $(pwd)/session:/app/session \
  -p 1539:1539 \
  --name android-dev-portal \
  localhost/android-dev-portal
```

> **참고**: Podman 기본 설정에서는 짧은 이미지 이름 사용을 허용하지 않으므로, 이미지를 `localhost/이미지명` 형태로 태그하거나 `registries.conf` 에 신뢰할 수 있는 레지스트리를 등록해야 합니다.

### 로컬 Python 환경에서 실행하기
가상환경 등 로컬 Python 환경에서 실행하려면 기존과 동일하게 진행하면 됩니다.

1. Python 의존성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
2. 포털 서버를 실행합니다.
   ```bash
   uvicorn portal.main:app --host 0.0.0.0 --port 1539
   ```

### 환경 변수
- `DEV_CONTAINER_IMAGE`: 세션 실행에 사용할 컨테이너 이미지(기본값 `android-dev-base:latest`).
- `PORTAL_ACCESS_HOST`: 포털이 링크를 생성할 때 사용할 호스트명(기본값 `127.0.0.1`). 리버스 프록시 뒤에서 실행한다면 외부에서 접근 가능한 호스트명을 지정하세요.
- `CONTAINER_CLI`: 컨테이너 실행에 사용할 CLI 명령어(`docker`, `podman` 등, 기본값 `docker`).
- `CONTAINER_CLI_ARGS`: 컨테이너 CLI에 추가로 전달할 인자(예: `--log-level debug`).

  > Podman을 백엔드로 사용하더라도 포털 컨테이너에는 Docker CLI만 포함되어 있습니다. Podman의 Docker 호환 API 소켓을 마운트하면 `CONTAINER_CLI` 를 바꾸지 않아도 그대로 동작합니다.

> **참고**: 포털은 컨테이너 엔진 CLI(Docker 또는 Podman 호환)가 사용 가능한 환경에서 동작합니다. 세션을 만들기 전에 `android-dev-base` 이미지를 빌드해 두어야 하며, 새 컨테이너는 포트 `20000-20999` 구간을 순차적으로 사용합니다.

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
