# 인수인계 검증 — 2026-10-24

## 로컬 검증 완료

- `./scripts/check.sh`: Ruff lint/format 통과, pytest 93개 통과.
- 별도로 생성한 빈 PostgreSQL DB에서 `alembic upgrade head` 성공.
- 실제 uvicorn HTTP 서버에서 health, 예제 준비 2회(중복 없음), 카드 생성·본문 수정·
  완료 단계 이동·재조회·삭제·삭제 후 404 및 브라우저 CORS preflight 통과.
- 정적 `docs/openapi.json`과 실제 FastAPI 명세 일치 테스트 포함.
- 새 회귀 테스트: CORS 허용/거부, 예제 재실행 시 기존 메모 보존, 명세 일치.
- Git 이력 5개 커밋/112개 고유 blob의 개인키·토큰·JWT·비밀번호 포함 URL 패턴 검사.
  후보 4건은 CI 테스트용 값 또는 문서 예시로 확인. 실제 비밀값은 발견되지 않음.
  `.env`는 추적되지 않으며 Docker 빌드 컨텍스트에서도 제외.

## GitHub CI

`.github/workflows/quality.yml`은 다음 두 경로를 검사한다:

1. Ubuntu + PostgreSQL 16에서 Ruff와 전체 pytest.
2. 새 Docker 이미지·DB에서 Compose 시작 → 예제 준비 2회 → 중복 없는 데이터·
   health·브라우저 CORS·OpenAPI 일치 확인 → 컨테이너 종료.

[GitHub 검증 실행 #40090531408](https://github.com/cosuss/kanban-board/actions/runs/40090531408)에서
Docker quickstart와 전체 품질 검사 단계가 통과했다. Docker 경로는 Linux의 새 환경에서
실제 빌드·실행으로 확인했다. 로컬 Mac에서는 Docker 엔진이 꺼져 있어 컨테이너를
실행하지 않았고, 네이티브 경로를 실제 HTTP로 검증했다.

## 팀원 환경에서 필요한 것

- Docker 실행 환경 또는 Python 3.11/uv/PostgreSQL.
- 두 디자인 가이드와 프론트 구현.
- 여러 컴퓨터에서 실제 업무를 공유할 경우 별도로 전달받은 팀 개발용 DB 접속 정보와
  동일 보드 ID. 이 저장소에는 공용 API 배포나 DB 비밀번호가 포함되지 않는다.
- 프론트가 아직 없으므로 프론트 화면·테마·공유 DB 데모 QA는 팀원이 이어서 수행한다.
