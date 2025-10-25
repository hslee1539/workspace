# __PROJECT_TITLE__

이 프로젝트는 Android 개발을 위한 dev container 템플릿에서 생성되었습니다.

## 기본 정보
- 생성 시각: __PROJECT_TIMESTAMP__
- 워크스페이스 슬러그: `__PROJECT_SLUG__`
- 컨테이너 런타임: `__PROJECT_RUNTIME__`

## 포함된 구성
- `.devcontainer/devcontainer.json`: Android SDK가 포함된 dev container 설정
- `.devcontainer/Dockerfile`: 커스텀 빌드 정의
- `.fleet/settings.json`: JetBrains Fleet를 위한 기본 워크스페이스 설정

## 시작하기
1. VS Code 또는 JetBrains Fleet로 이 폴더를 엽니다.
2. 에디터에서 dev container를 빌드/연결하라는 메시지가 나오면 승인합니다.
3. 컨테이너 내부에서 `gradle tasks` 등을 실행하여 환경을 확인할 수 있습니다.
