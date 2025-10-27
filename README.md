# workspace

안드로이드 개발 dev container 관리 프로젝트

## Docker 이미지

루트의 `Dockerfile` 은 Ubuntu 22.04 기반 안드로이드 개발 이미지다. 다음이 포함되어 있다.

- OpenJDK 17
- Android SDK (platform-tools, build-tools 34/35, platforms android-35/36, NDK 29.0.13113456, CMake 3.18.1/3.22.1)
- Node.js 18 및 npm 글로벌 패키지: `@openai/codex@0.46.0`, `opencode-ai`, `@qwen-code/qwen-code@0.0.15-nightly.8`
- `OPENAI_BASE_URL=https://api.openai.com/v1`, `OPENAI_MODEL=gpt-5-mini`

이미지 빌드:

```bash
docker build -t android-dev-base .
```

## OPENAI 환경 변수

호스트에서 `OPENAI_API_KEY` 를 설정하면 dev container 안으로 전달된다.

```bash
export OPENAI_API_KEY="sk-..."
```

스크립트를 실행해 세션을 만들면 컨테이너 내부에서 동일한 키를 사용할 수 있다.

## 외부 ADB 사용

컨테이너는 기본적으로 `ADB_SERVER_SOCKET=tcp:host.docker.internal:5037` 를 설정하여 호스트의 ADB 서버에 연결한다. 호스트에서 다음을 실행해 장치를 인식시킨 뒤 사용한다.

```bash
adb start-server
adb devices
```

Linux 호스트에서는 Docker 가 `host.docker.internal` 이름을 제공하지 않는 경우 `--add-host=host.docker.internal:host-gateway` 를 지원하는 최신 버전을 사용해야 한다.

## 새 프로젝트 스크립트

`scripts/code_new_project.sh` 와 `scripts/fleet_new_project.sh` 는 각각 VS Code 와 JetBrains Fleet 으로 새 세션을 연다.

```bash
./scripts/code_new_project.sh [git-url] [project-name]
./scripts/fleet_new_project.sh [git-url] [project-name]
```

- 인자를 생략하면 실행 중 입력을 받아 설정할 수 있다.
- Git URL 을 비워 두면 빈 프로젝트가 생성된다.
- 프로젝트 이름을 비워 두면 타임스탬프만 사용한다.
- `session/<timestamp>-<project>` 폴더 아래 `.devcontainer/devcontainer.json` 이 자동 생성된다.
- VS Code CLI(`code`) 또는 JetBrains Fleet CLI(`fleet`/`jetbrains-fleet`) 가 설치되어 있으면 자동으로 폴더가 열린다.

macOS 의 Fleet 앱만 설치되어 CLI 가 없으면 `open -a "JetBrains Fleet"` 으로 실행을 시도한다.
