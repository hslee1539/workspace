# workspace

안드로이드 개발 dev container 관리 프로젝트입니다.

## 새 프로젝트 만들기

새 워크스페이스는 `new_project.sh` 스크립트를 통해 생성합니다. 기본적으로 `workspace/` 하위에 `YYYYMMDD-HHMMSS-프로젝트슬러그` 형태의 폴더가 만들어지고 Android 개발에 필요한 dev container 구성이 함께 복사됩니다.

```bash
./new_project.sh "My App"
```

옵션:
- `--editor <code|fleet>`: 생성 직후 VS Code 또는 JetBrains Fleet을 실행합니다.
- `--runtime <docker|podman>`: 사용할 컨테이너 런타임을 강제로 지정합니다(기본값은 자동 감지).
- `--template <name>`: 다른 템플릿을 사용할 때 지정합니다. 현재는 `android` 템플릿이 기본으로 제공됩니다.

### 에디터별 단축 스크립트
- `./code_new_project.sh "프로젝트 이름"`
- `./fleet_new_project.sh "프로젝트 이름"`

각 스크립트는 내부적으로 `new_project.sh`를 호출하여 동일한 디렉터리 구조를 생성한 뒤 지정한 에디터를 실행합니다.

## 템플릿 구조

`templates/android/` 디렉터리에는 다음 파일이 포함되어 있습니다.

- `.devcontainer/devcontainer.json`: Android SDK, Gradle 캐시 볼륨, 기본 확장 프로그램 등을 정의한 구성
- `.devcontainer/Dockerfile`: 베이스 이미지를 바탕으로 추가 패키지를 설치하는 Dockerfile
- `.devcontainer/scripts/post-create.sh`: 컨테이너 생성 직후 Android SDK 라이선스 동의 및 업데이트 스크립트
- `.fleet/settings.json`: JetBrains Fleet 기본 설정
- `README.md`: 생성된 프로젝트에서 확인 가능한 안내 문서

생성된 프로젝트의 파일들은 `__PROJECT_*__` 플레이스홀더가 실제 프로젝트 정보로 치환된 상태로 제공됩니다.

## 준비 사항

- Docker 또는 Podman 중 하나가 설치되어 있어야 합니다.
- dev container CLI(`devcontainer`)가 설치되어 있다면 스크립트가 자동으로 컨테이너를 빌드해 줍니다. 설치되어 있지 않더라도 에디터에서 dev container 확장을 통해 컨테이너를 열 수 있습니다.

## 라이선스

MIT
