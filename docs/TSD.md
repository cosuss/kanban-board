# 간반 보드 백엔드 기술 설계 (TSD)

> 문서 목적: 백엔드의 기술 스택, 구조, 설정, API 계약 전체, 서비스 규칙(의사코드), 마이그레이션·테스트·품질 게이트 전략을 정의한다.

## 1. 기술 스택

| 영역 | 선택 |
|---|---|
| 언어 | Python 3.11 (`requires-python = ">=3.11,<3.12"`, `.python-version`에 `3.11`) |
| 패키지·가상환경 | `uv` (`uv.lock` 포함, `.venv`는 저장소에 넣지 않음) |
| 웹 | FastAPI + uvicorn |
| 검증·설정 | Pydantic v2, pydantic-settings |
| ORM·드라이버 | SQLAlchemy 2.x, psycopg 3 (`psycopg[binary]`) |
| 마이그레이션 | Alembic |
| DB | PostgreSQL만 지원 (과제#5 DB가 Supabase Postgres). SQLite 없음 |
| 품질 | ruff (`select = ["ALL"]`, preview), pytest |
| CLI | Typer + httpx + rich (`TSD_CLI.md`) |

패키지 이름은 `kanban-board`, 파이썬 패키지는 `app/`이다.

## 2. 구성

```text
클라이언트 (kanban CLI / Codex / Swagger UI)
          |
       FastAPI
          |
  api/routes -> services (규칙·검증)
          |
 SQLAlchemy 세션 (풀)
          |
 PostgreSQL (Supabase 또는 로컬)
```

## 3. 디렉터리 구조

```text
app/
  main.py              # FastAPI 앱, 라우터·예외 처리 연결, /health
  cli/                 # kanban CLI (TSD_CLI.md)
  core/config.py       # pydantic-settings 환경 설정
  db/session.py        # 엔진, 풀, 요청 단위 세션 의존성
  models/              # SQLAlchemy 모델 (스키마 v3와 1:1)
  schemas/             # Pydantic 요청·응답 모델
  services/            # 자동 채움·이름 해석·삭제 규칙 등 쓰기 규칙
  core/errors.py       # 도메인 예외(NotFoundError, ConflictError, InvalidRequestError)와 변환
  api/routes/          # boards.py, members.py, stages.py, milestones.py, cards.py, comments.py, health.py
alembic/               # versions/0001_kanban_v3.py
tests/                 # API, 서비스, CLI, 마이그레이션 테스트
scripts/               # check.sh, fix.sh, install-git-hooks.sh
.githooks/pre-commit   # scripts/check.sh 호출
.github/workflows/quality.yml
skills/kanban-log/     # Codex 스킬 원본 (CODEX.md)
.env.example
```

원칙: 라우터는 얇게(입력 파싱 → 서비스 호출 → 응답 모델), 규칙은 모두 `services/`에 둔다. 서비스는 도메인 예외(`NotFoundError`, `ConflictError`, `InvalidRequestError`)를 던지고, `core/errors.py`의 핸들러가 각각 404/409/422의 `{"detail": "..."}`로 변환한다.

## 4. 개발 환경과 실행

| 작업 | 명령 |
|---|---|
| 설치·동기화 | `uv sync --all-groups` |
| 마이그레이션 | `uv run alembic upgrade head` (또는 `kanban db upgrade`) |
| 개발 서버 | `uv run uvicorn app.main:app --reload` (또는 `kanban serve --reload`) |
| 테스트 | `uv run pytest` |
| 전체 품질 게이트 | `./scripts/check.sh` |
| 자동 수정 | `./scripts/fix.sh` |
| git hook 켜기 | `./scripts/install-git-hooks.sh` |
| 의존성 추가 | `uv add <pkg>` / 개발용 `uv add --dev <pkg>` |

기본 주소는 `http://127.0.0.1:8000`이다. Swagger `/docs`, ReDoc `/redoc`, 스키마 `/openapi.json`은 FastAPI 기본 경로다.

## 5. 설정과 환경 변수

`.env`는 커밋하지 않고 `.env.example`만 둔다. 설정은 `app/core/config.py`의 pydantic-settings가 읽는다.

| 이름 | 기본값 | 용도 |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://localhost/kanban` | 서버·alembic. `postgresql://`로 시작하면 `postgresql+psycopg://`로 바꿔 쓴다(Supabase 연결 문자열을 그대로 붙이기 위함) |
| `TEST_DATABASE_URL` | `postgresql+psycopg://localhost/kanban_test` | pytest. 테스트마다 6개 테이블 `TRUNCATE ... RESTART IDENTITY CASCADE` |
| `DATABASE_POOL_SIZE` | 5 | SQLAlchemy 풀 크기 |
| `DATABASE_MAX_OVERFLOW` | 10 | 풀 초과 허용 연결 수 |
| `DATABASE_POOL_TIMEOUT` | 30 | 풀 대기 시간(초) |
| `KANBAN_API_URL` | `http://127.0.0.1:8000` | CLI가 호출할 서버 주소 |
| `KANBAN_BOARD` | `1` | CLI의 기본 보드 id |

풀 크기는 Supabase 무료 플랜 세션 풀러의 동시 연결 한도를 넘지 않도록 작게 둔다.

URL 정규화 의사코드:

```text
def normalize(url):
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url
```

## 6. API 계약

### 6.1 공통

- Base path: `/api/v1`. 헬스 체크는 `/api/v1/health`와 편의용 `/health`(루트, Swagger 문서에는 숨김) 둘 다 같은 응답을 준다.
- 요청·응답은 JSON(`Content-Type: application/json`). 인증 없음.
- 시각은 ISO 8601 문자열이다. 서버가 `now(UTC)`로 채워 저장하지만(`timestamptz`), 응답은 DB 세션 시간대의 오프셋으로 나올 수 있다(예: `2026-10-19T03:28:23.570294+09:00`). 같은 순간이므로 비교할 때는 파싱해서 쓴다. 날짜는 `YYYY-MM-DD`.
- 성공 코드: 조회·수정·이동 `200`, 생성 `201`, 삭제 `204`(본문 없음).
- 모든 id는 양의 정수. 경로의 id가 숫자가 아니면 `422`.
- 부분 수정(PATCH)은 보낸 필드만 바꾼다. 보내지 않은 필드는 유지한다. nullable 값은 `null`을 명시해 지운다.
- 요청 본문에 알 수 없는 필드를 보내면 **조용히 무시한다**(`extra = forbid`가 아니다). `created_at`, `closed_at`, `issue_number`(PATCH) 같은 필드를 보내도 오류 없이 무시되며 값은 바뀌지 않는다.

### 6.2 엔드포인트 목록 (32개)

| # | 메서드 | 경로 | 설명 | 성공 |
|---|---|---|---|---|
| 1 | GET | /api/v1/health (및 /health) | 헬스 체크 | 200 |
| 2 | GET | /api/v1/boards | 보드 목록 | 200 |
| 3 | POST | /api/v1/boards | 보드 생성 | 201 |
| 4 | GET | /api/v1/boards/{board_id} | 보드 단건 | 200 |
| 5 | PATCH | /api/v1/boards/{board_id} | 보드 수정 | 200 |
| 6 | DELETE | /api/v1/boards/{board_id} | 보드 삭제 | 204 |
| 7 | GET | /api/v1/boards/{board_id}/view | 보드 뷰 | 200 |
| 8 | GET | /api/v1/boards/{board_id}/members | 팀원 목록 | 200 |
| 9 | POST | /api/v1/boards/{board_id}/members | 팀원 생성 | 201 |
| 10 | GET | /api/v1/members/{member_id} | 팀원 단건 | 200 |
| 11 | PATCH | /api/v1/members/{member_id} | 팀원 수정 | 200 |
| 12 | DELETE | /api/v1/members/{member_id} | 팀원 삭제 | 204 |
| 13 | GET | /api/v1/boards/{board_id}/stages | 단계 목록 | 200 |
| 14 | POST | /api/v1/boards/{board_id}/stages | 단계 생성 | 201 |
| 15 | GET | /api/v1/stages/{stage_id} | 단계 단건 | 200 |
| 16 | PATCH | /api/v1/stages/{stage_id} | 단계 수정 | 200 |
| 17 | DELETE | /api/v1/stages/{stage_id} | 단계 삭제 | 204 |
| 18 | GET | /api/v1/boards/{board_id}/milestones | 마일스톤 목록 | 200 |
| 19 | POST | /api/v1/boards/{board_id}/milestones | 마일스톤 생성 | 201 |
| 20 | GET | /api/v1/milestones/{milestone_id} | 마일스톤 단건 | 200 |
| 21 | PATCH | /api/v1/milestones/{milestone_id} | 마일스톤 수정 | 200 |
| 22 | DELETE | /api/v1/milestones/{milestone_id} | 마일스톤 삭제 | 204 |
| 23 | GET | /api/v1/boards/{board_id}/cards | 카드 목록(필터·페이지) | 200 |
| 24 | POST | /api/v1/boards/{board_id}/cards | 카드 생성 | 201 |
| 25 | GET | /api/v1/cards/{card_id} | 카드 단건 | 200 |
| 26 | PATCH | /api/v1/cards/{card_id} | 카드 수정 | 200 |
| 27 | DELETE | /api/v1/cards/{card_id} | 카드 삭제 | 204 |
| 28 | POST | /api/v1/cards/{card_id}/move | 카드 이동 | 200 |
| 29 | GET | /api/v1/cards/{card_id}/comments | 코멘트 목록 | 200 |
| 30 | POST | /api/v1/cards/{card_id}/comments | 코멘트 생성 | 201 |
| 31 | GET | /api/v1/comments/{comment_id} | 코멘트 단건 | 200 |
| 32 | DELETE | /api/v1/comments/{comment_id} | 코멘트 삭제 | 204 |

코멘트 수정(PATCH)은 제공하지 않는다.

### 6.3 응답 모델

```json
// BoardOut
{"id": 1, "name": "ASPS TEAM 01", "repo_url": "https://github.com/JooJeongwon/asps-1"}

// MemberOut
{"id": 5, "board_id": 1, "github_login": "codex", "name": "Codex 에이전트", "role": "AI 에이전트"}

// StageOut
{"id": 2, "board_id": 1, "name": "In Progress", "position": 2}

// MilestoneOut
{"id": 1, "board_id": 1, "title": "MVP", "due_on": "2026-11-01"}

// CardOut
{
  "id": 31, "board_id": 1,
  "stage_id": 2, "stage": "In Progress",
  "assignee_id": 5, "assignee": "codex", "assignee_name": "Codex 에이전트",
  "milestone_id": 1, "milestone": "MVP",
  "issue_number": 28, "title": "로그인 API 구현", "body": "계획 요약",
  "position": 4,
  "created_at": "2026-10-19T09:00:00Z", "closed_at": null
}

// CommentOut
{
  "id": 11, "card_id": 31,
  "author_id": 5, "author": "codex", "author_name": "Codex 에이전트",
  "body": "구현 완료, pytest 12개 통과",
  "created_at": "2026-10-19T10:30:00Z"
}
```

`CardOut.board_id`는 카드가 속한 단계의 보드에서 계산한다. 담당자·마일스톤이 없으면 `assignee_id`, `assignee`, `assignee_name`, `milestone_id`, `milestone`은 모두 `null`이다. 코멘트 작성자가 없거나 삭제된 팀원이면 `author_id`, `author`, `author_name`이 `null`이다.

카드 목록(`GET /boards/{id}/cards`)을 포함해 모든 목록 응답은 **JSON 배열**이다. `{"items": ...}` 같은 감싸기 객체는 없고, 전체 개수 필드도 없다. 시각 필드(`created_at`, `closed_at`, `comments.created_at`)는 위 6.1의 ISO 8601 형식이다.

### 6.4 오류 형식

```json
{"detail": "card 999 not found"}
```

| 상태 코드 | 언제 | detail 예시 |
|---|---|---|
| 404 | 경로 id 없음, 이름·id 참조 대상이 이 보드에 없음 | `board 99 not found`, `stage 'Review' not found on board`, `member 999 not found on board` |
| 409 | 유일성 충돌, 삭제 불가 | `a card with this issue_number already exists`, `stage 1 still has 2 card(s); move or delete them first` |
| 422 | 검증 실패 | (아래 설명) |
| 503 | `/health`의 DB 연결 실패 | `database unavailable` |

422는 두 종류다. (1) Pydantic 검증(필수 누락, 타입 오류, 범위 밖 값, 이름·id 동시 지정 등)은 FastAPI 기본 형식 `{"detail": [{"type": "...", "loc": [...], "msg": "...", "input": ...}]}`다. 이름·id 동시 지정의 `msg`는 `Value error, give either stage or stage_id, not both`, 이동 대상 오류는 `Value error, give exactly one of stage or stage_id`다. (2) 서비스가 직접 던지는 오류(예: `board has no stages; create a stage first`)는 문자열 `detail`이다. 404·409도 문자열 `detail`이다. 테스트는 메시지 문구보다 상태 코드와 `detail` 존재 여부를 확인한다. CLI는 목록형 `detail`의 첫 항목만 `Error: github_login: String should have at least 1 character (422)` 꼴로 보여 준다.

### 6.5 Health

`GET /api/v1/health` (편의용 별칭 `GET /health`, 문서에는 숨김)

```json
200 {"status": "ok", "database": "ok"}
503 {"detail": "database unavailable"}
```

`select 1`로 DB를 확인하고, SQLAlchemy 오류가 나면 503이다. 503 본문은 다른 오류와 같은 `{"detail": ...}` 형식이다.

### 6.6 보드

`GET /api/v1/boards` → `200`, `id` 순 배열

```json
[{"id": 1, "name": "ASPS TEAM 01", "repo_url": "https://github.com/JooJeongwon/asps-1"}]
```

`POST /api/v1/boards`

```json
요청 {"name": "Team A", "repo_url": "https://github.com/acme/team-a", "with_default_stages": true}
201  {"id": 2, "name": "Team A", "repo_url": "https://github.com/acme/team-a"}
```

- `name` 필수(빈 문자열 불가). `repo_url` 선택(없으면 `null`). `with_default_stages` 선택(기본 `true`).
- `with_default_stages`가 true면 같은 트랜잭션에서 `Todo(1)`, `In Progress(2)`, `Done(3)`를 만든다. false면 단계 없이 생성된다.
- `repo_url`이 이미 있으면 `409`(`a board with this repo_url already exists`). `name`이 없으면 `422`.

`GET /api/v1/boards/{board_id}` → `200` BoardOut, 없으면 `404`.

`PATCH /api/v1/boards/{board_id}`

```json
요청 {"name": "Team A (2026)", "repo_url": null}
200  {"id": 2, "name": "Team A (2026)", "repo_url": null}
```

- 수정 가능: `name`, `repo_url`(`null`로 비움). `name`에 `null`을 보내면 "변경 없음"이다(이름은 비울 수 없다). 빈 본문 `{}`은 아무것도 바꾸지 않고 현재 값을 `200`으로 돌려준다. `repo_url` 중복은 `409`.

`DELETE /api/v1/boards/{board_id}` → `204`. 보드의 카드(와 그 코멘트)를 먼저 지운 뒤 보드를 지운다. 팀원·단계·마일스톤은 DB cascade로 함께 지워진다. 없으면 `404`.

### 6.7 보드 뷰

`GET /api/v1/boards/{board_id}/view`

```json
200
{
  "board": {"id": 1, "name": "ASPS TEAM 01", "repo_url": "https://github.com/JooJeongwon/asps-1"},
  "stages": [
    {"id": 1, "name": "Todo", "position": 1, "cards": [
      {"id": 3, "board_id": 1, "stage_id": 1, "stage": "Todo", "assignee_id": 2, "assignee": "JooJeongwon",
       "assignee_name": "주정원", "milestone_id": null, "milestone": null, "issue_number": 7,
       "title": "회원가입 화면", "body": null, "position": 1,
       "created_at": "2026-10-01T00:00:00Z", "closed_at": null}
    ]},
    {"id": 2, "name": "In Progress", "position": 2, "cards": []},
    {"id": 3, "name": "Done", "position": 3, "cards": []}
  ]
}
```

단계는 `position` 오름차순, 각 단계의 카드는 `position` 오름차순(같으면 `id`)이다. 카드가 없는 단계도 `cards: []`로 포함한다. 보드가 없으면 `404`. 단계 목록 한 번, 카드 목록 한 번(조인으로 단계·담당자·마일스톤 포함)을 읽고 파이썬에서 묶는다(N+1 쿼리 없음).

### 6.8 팀원

`GET /api/v1/boards/{board_id}/members` → `200` 배열(`id` 순). 보드가 없으면 `404`.

`POST /api/v1/boards/{board_id}/members`

```json
요청 {"github_login": "codex", "name": "Codex 에이전트", "role": "AI 에이전트"}
201  {"id": 5, "board_id": 1, "github_login": "codex", "name": "Codex 에이전트", "role": "AI 에이전트"}
```

- `github_login`, `name` 필수. `role` 선택. `github_login`은 **전체 테이블에서** 유일하므로(스키마의 UNIQUE) 이미 있으면 `409`. 보드 없음 `404`.

`GET /api/v1/members/{member_id}` → `200` MemberOut, 없으면 `404`.

`PATCH /api/v1/members/{member_id}`

```json
요청 {"name": "Codex", "role": null}
200  {"id": 5, "board_id": 1, "github_login": "codex", "name": "Codex", "role": null}
```

수정 가능: `github_login`, `name`, `role`(`null`로 비움). `github_login`·`name`에 `null`을 보내면 "변경 없음"이다. `github_login` 중복은 `409`(`a member with this github_login already exists`). 소속 보드는 바꿀 수 없다.

`DELETE /api/v1/members/{member_id}` → `204`. 그 팀원이 담당자였던 카드의 `assignee_id`, 작성한 코멘트의 `author_id`는 `null`이 된다(DB `set null`).

### 6.9 단계

`GET /api/v1/boards/{board_id}/stages` → `200`, `position` 오름차순 배열.

`POST /api/v1/boards/{board_id}/stages`

```json
요청 {"name": "Review"}
201  {"id": 4, "board_id": 1, "name": "Review", "position": 4}
```

- `name` 필수. `position` 선택(없으면 보드의 `max(position)+1`, 단계가 없으면 1). `position >= 1`.
- 같은 보드에 같은 `name` 또는 같은 `position`이 있으면 `409`(`a stage with this name or position already exists on the board`). 단계 사이에 끼워 넣는 기능은 제공하지 않는다(비어 있는 번호만 쓸 수 있다).

`GET /api/v1/stages/{stage_id}` → `200` StageOut.

`PATCH /api/v1/stages/{stage_id}`

```json
요청 {"name": "Code Review", "position": 5}
200  {"id": 4, "board_id": 1, "name": "Code Review", "position": 5}
```

수정 가능: `name`, `position`(둘 다 `null`은 "변경 없음"). 중복이면 `409`. 단계의 position이 바뀌어도 이미 채워진 카드의 `closed_at`은 다시 계산하지 않는다(카드가 이동하거나 생성될 때만 판정한다).

`DELETE /api/v1/stages/{stage_id}` → `204`. 카드가 하나라도 남아 있으면 `409`(`stage 1 still has 2 card(s); move or delete them first`).

### 6.10 마일스톤

`GET /api/v1/boards/{board_id}/milestones` → `200` 배열(`id` 순).

`POST /api/v1/boards/{board_id}/milestones`

```json
요청 {"title": "MVP", "due_on": "2026-11-01"}
201  {"id": 1, "board_id": 1, "title": "MVP", "due_on": "2026-11-01"}
```

- `title` 필수, `due_on` 선택(`YYYY-MM-DD`). 같은 보드에 같은 `title`이 있으면 `409`(`a milestone with this title already exists on the board`). 날짜 형식 오류 `422`.

`GET /api/v1/milestones/{milestone_id}` → `200` MilestoneOut.

`PATCH /api/v1/milestones/{milestone_id}` → 수정 가능 `title`(`null`은 "변경 없음"), `due_on`(`null`로 비움). 제목 중복 `409`.

`DELETE /api/v1/milestones/{milestone_id}` → `204`. 카드의 `milestone_id`는 `null`이 된다.

### 6.11 카드

`GET /api/v1/boards/{board_id}/cards`

| 쿼리 | 설명 |
|---|---|
| `stage` | 단계 이름 완전 일치 |
| `assignee` | 담당자 github_login 완전 일치 |
| `milestone` | 마일스톤 제목 완전 일치 |
| `q` | 제목·본문 부분 일치(대소문자 무시, `%`·`_` 같은 와일드카드 문자는 글자 그대로 취급) |
| `limit` | 1~200, 기본 50 |
| `offset` | 0 이상, 기본 0 |

필터는 AND로 적용한다. 정렬은 단계 `position` → 카드 `position` → `id`. 없는 보드는 `404`지만, 목록 필터의 이름(`stage`, `assignee`, `milestone`)이 일치하는 대상이 없으면 오류가 아니라 빈 배열 `[]`이다. `limit`·`offset` 범위를 벗어나면 `422`다.

```json
GET /api/v1/boards/1/cards?stage=In%20Progress&assignee=codex&limit=20
200
[ { ...CardOut... } ]
```

`POST /api/v1/boards/{board_id}/cards`

| 필드 | 필수 | 설명 |
|---|---|---|
| `title` | O | 빈 문자열 불가 |
| `body` | | 본문 |
| `stage` / `stage_id` | | 둘 중 하나. 없으면 보드의 첫 단계 |
| `assignee` / `assignee_id` | | 둘 중 하나. 없으면 담당자 없음 |
| `milestone` / `milestone_id` | | 둘 중 하나. 없으면 마일스톤 없음 |
| `issue_number` | | 없으면 `max+1` 자동(1 이상). 있는데 중복이면 409 |

카드 생성에는 `position`이 없다. 새 카드는 항상 대상 단계의 맨 끝에 붙는다(`position`을 지정해 끼워 넣으려면 생성 뒤 `move`를 쓴다).

```json
요청 {"title": "로그인 API 구현", "body": "계획 요약", "stage": "In Progress", "assignee": "codex", "milestone": "MVP"}
201  {"id": 31, "board_id": 1, "stage_id": 2, "stage": "In Progress", "assignee_id": 5, "assignee": "codex",
      "assignee_name": "Codex 에이전트", "milestone_id": 1, "milestone": "MVP", "issue_number": 28,
      "title": "로그인 API 구현", "body": "계획 요약", "position": 4,
      "created_at": "2026-10-19T09:00:00Z", "closed_at": null}
```

- 이름과 id를 **둘 다 null이 아니게** 주면 `422`(한쪽이 `null`이면 안 준 것으로 본다). 이름이 보드에 없으면 `404`. id가 다른 보드의 것이면 `404`.
- 마지막 단계에 만들면 `closed_at`이 현재 시각으로 채워진다.
- 보드에 단계가 하나도 없는데 단계를 안 주면 `422`(`board has no stages; create a stage first`).
- `created_at`, `closed_at`, `position`을 보내도 무시된다(오류 아님).

`GET /api/v1/cards/{card_id}` → `200` CardOut.

`PATCH /api/v1/cards/{card_id}`

```json
요청 {"title": "로그인 API 구현 (v2)", "assignee": "cosuss", "milestone_id": null}
200  {...CardOut...}
```

- 수정 가능: `title`, `body`, `stage`/`stage_id`, `assignee`/`assignee_id`, `milestone`/`milestone_id`. `position`은 PATCH로 바꿀 수 없다(위치는 `move`로).
- `null` 처리: `body`는 `null`을 보내면 비운다. `assignee`·`assignee_id`가 `null`이면 담당자를 지운다(둘 중 아무 필드나 `null`이면 된다). `milestone`·`milestone_id`도 같다. `title`에 `null`은 "변경 없음"이다. `stage`·`stage_id`에 `null`은 `422`(`stage cannot be null`). 필드를 아예 보내지 않으면 항상 "변경 없음"이다.
- `issue_number`, `created_at`, `closed_at`은 수정할 수 없다. 보내도 오류 없이 무시된다.
- 단계를 바꾸면(다른 단계일 때만) 이동과 같은 규칙(`closed_at`, 맨 끝 `position`)을 적용한다. 이름+id를 둘 다 non-null로 주면 `422`, 없는 이름 `404`.

`DELETE /api/v1/cards/{card_id}` → `204`. 코멘트는 cascade로 함께 지워진다.

### 6.12 카드 이동

`POST /api/v1/cards/{card_id}/move`

```json
요청 {"stage": "Done"}
200  {...CardOut..., "stage_id": 3, "stage": "Done", "position": 6, "closed_at": "2026-10-19T11:00:00Z"}
```

```json
요청 {"stage_id": 1, "position": 1}
200  {...CardOut..., "stage_id": 1, "stage": "Todo", "position": 1, "closed_at": null}
```

- `stage` 또는 `stage_id` 중 **정확히 하나** 필수. 둘 다 없거나 둘 다 있으면 `422`(`give exactly one of stage or stage_id`). 이름이 없으면 `404`. `position`은 1 이상(0이면 `422`).
- `position`이 없으면 대상 단계 맨 끝, 있으면 그 자리에 삽입하고 같은 단계의 `position >= 값`인 다른 카드를 +1 민다.
- 같은 단계로의 이동도 허용한다(순서만 바꿈).

### 6.13 코멘트

`GET /api/v1/cards/{card_id}/comments` → `200`, `created_at` 오름차순(같으면 `id`) 배열. 카드 없음 `404`.

`POST /api/v1/cards/{card_id}/comments`

```json
요청 {"body": "구현 완료, pytest 12개 통과", "author": "codex"}
201  {"id": 11, "card_id": 31, "author_id": 5, "author": "codex", "author_name": "Codex 에이전트",
      "body": "구현 완료, pytest 12개 통과", "created_at": "2026-10-19T10:30:00Z"}
```

- `body` 필수(빈 문자열 불가). `author`(github_login) 또는 `author_id` 중 하나는 선택, 둘 다 non-null이면 `422`. 둘 다 없으면 작성자 없음(`null`). 작성자는 카드가 속한 보드의 팀원이어야 하며 없으면 `404`(`member 'zzz' not found on board`).
- `created_at`은 서버가 채운다.

`GET /api/v1/comments/{comment_id}` → `200` CommentOut. `DELETE /api/v1/comments/{comment_id}` → `204`.

## 7. 서비스 규칙 (의사코드)

### 7.1 issue_number

```text
def next_issue_number(session):
    m = select(max(cards.issue_number))
    return (m or 0) + 1

def resolve_issue_number(session, requested):
    lock_advisory(7001)           # 트랜잭션이 끝날 때 자동 해제
    if requested is None:
        return next_issue_number(session)
    if exists(cards.issue_number == requested):
        raise Conflict("a card with this issue_number already exists")
    return requested
```

`issue_number`는 테이블 전체에서 유일하다(보드별이 아니다). 자동 번호와 `position` 계산은 Postgres 트랜잭션 수준 advisory lock(`pg_advisory_xact_lock(7001)`)으로 직렬화한다. 그래서 동시에 여러 카드를 만들어도 번호가 겹치지 않고, 재시도 로직은 없다. 번호를 직접 지정했는데 이미 있으면 `409`다.

### 7.2 이름·id 참조 해석

```text
def resolve_ref(session, board_id, name, id_, kind):
    if name is not None and id_ is not None:      # 스키마 검증에서 이미 422 (둘 다 non-null일 때만)
        raise Invalid("give either {kind} or {kind}_id, not both")
    if name is not None:
        row = find_by_name_in_board(kind, board_id, name)   # stage.name / member.github_login / milestone.title
        if row is None: raise NotFound("{kind} '{name}' not found in board {board_id}")
        return row
    if id_ is not None:
        row = get(kind, id_)
        if row is None or row.board_id != board_id: raise NotFound(...)
        return row
    return UNSET        # 아무것도 안 줌 (PATCH에서는 "변경 없음")
```

PATCH에서 `assignee_id: null`(또는 `assignee: null`)은 "지움"이고, 필드를 생략한 것은 "변경 없음"이다. 구현은 `model_fields_set`으로 둘을 구분한다. 다만 `title: null`은 지울 수 없는 필드라서 "변경 없음"으로 처리하고, `stage: null`은 `422`다.

### 7.3 position 삽입

```text
def place(session, stage_id, position, moving_card_id=None):
    others = cards in stage_id, excluding moving_card_id
    if position is None:
        return (max(c.position for c in others) if others else 0) + 1
    update cards set position = position + 1
        where stage_id = :stage_id and position >= :position and id != :moving_card_id
    return position
```

`position`은 순서를 정하는 키일 뿐 빈틈없는 연번이 아니다. 카드가 빠져나가거나 삭제돼도 남은 카드를 다시 번호 매기지 않는다. `cards.position`에는 UNIQUE가 없으므로 밀기 중 충돌은 없다.

### 7.4 closed_at

```text
def closed_at_for(session, stage, previous_closed_at=None):
    last = select stage with max(position) where board_id == stage.board_id
    if stage.id == last.id:
        return previous_closed_at or utc_now()   # 이미 닫힌 카드를 같은 마지막 단계로 다시 옮겨도 시각 유지
    return None
```

- 카드 생성 시: `closed_at = closed_at_for(stage)`.
- 이동·단계 변경 시: `card.closed_at = closed_at_for(new_stage, card.closed_at)`. 마지막 단계에서 다른 단계로 나가면 `None`.
- 단계 이름(`Done`)이 아니라 `position` 최대값으로 판단한다.

### 7.5 보드·단계 삭제

```text
def delete_board(session, board_id):
    board = get_or_404(board_id)
    delete cards where stage_id in (select id from stages where board_id = board_id)  # comments는 cascade
    delete board                                                                   # members/stages/milestones cascade
    commit    # 하나의 트랜잭션

def delete_stage(session, stage_id):
    if exists(cards where stage_id = stage_id): raise Conflict("stage {id} still has {n} card(s); move or delete them first")
    delete stage
```

### 7.6 보드 생성

```text
def create_board(session, name, repo_url, with_default_stages=True):
    board = insert boards(name, repo_url)           # repo_url 중복이면 Conflict
    if with_default_stages:
        insert stages (board.id, "Todo", 1), (board.id, "In Progress", 2), (board.id, "Done", 3)
    commit
```

## 8. 마이그레이션 전략

- Alembic 리비전 `0001_kanban_v3` 하나가 과제#5 v3 스키마를 만든다. `side-projects/kanban-db/sql/001_schema.sql`에서 상단의 `drop` 구문을 **빼고** 아래를 모두 멱등으로 옮긴다.

| 객체 | 멱등 방식 |
|---|---|
| 테이블 6개 | `create table if not exists` |
| 인덱스 5개 | `create index if not exists` |
| 뷰 `v_board` | `create or replace view ... with (security_invoker = true)` |
| RLS | `alter table ... enable row level security` (이미 켜져 있어도 안전) |
| 테이블 설명 | `comment on table ...` (반복 실행 안전) |

- 이유: Supabase에는 같은 테이블이 이미 있다. `alembic upgrade head`는 기존 DB(변경 없음)와 빈 로컬 DB(새로 생성) 양쪽에서 같은 결과여야 한다. 기존 데이터는 절대 지우지 않는다.
- `downgrade`: 뷰를 지운 뒤 테이블을 자식 → 부모 순으로 `drop table if exists ... cascade`. **공존 중인 Supabase에서는 실행하지 않는다.**
- 이미 테이블이 있어 SQL이 건너뛰어져도 `alembic_version`에는 리비전이 기록되므로 이후 `upgrade head`는 no-op이다.
- 앱은 시작 시 자동으로 마이그레이션하지 않는다(`kanban db upgrade` 또는 `alembic upgrade head`를 명시적으로 실행).
- 시드(`002_seed.sql`)는 저장소에 복사하지 않는다. `README.md`에서 경로만 안내한다.

## 9. 테스트 전략

| 항목 | 내용 |
|---|---|
| DB | `TEST_DATABASE_URL`의 Postgres. 서버 DB와 분리된 `kanban_test` |
| 준비 | 세션 시작 시 `alembic upgrade head`(멱등)로 스키마 준비 |
| 격리 | 각 테스트 전에 6개 테이블 `TRUNCATE boards, members, stages, milestones, cards, comments RESTART IDENTITY CASCADE` |
| 클라이언트 | FastAPI `TestClient` + `get_db` 의존성 오버라이드 |
| 데이터 | 각 테스트가 fixture로 직접 만든다(보드·팀원·카드 팩토리). 시드 파일에 의존하지 않는다 |
| 범위 | `TEST_CASE.md`의 모든 케이스 + 마이그레이션 멱등성 + 풀 설정 단위 테스트 |
| CLI | `TSD_CLI.md`·`TEST_CASE_CLI.md` 참조. 단위는 ASGITransport, E2E는 uvicorn 서브프로세스 |

실행: `uv run pytest`. 테스트는 `DATABASE_URL`이 아니라 `TEST_DATABASE_URL`(없으면 기본값 `postgresql+psycopg://localhost/kanban_test`)만 사용하므로 개발·운영 DB에 TRUNCATE가 가지 않는다. `TEST_DATABASE_URL`을 운영 DB로 지정하지 않도록 주의한다. 현재 테스트는 83개다(API 47, CLI 33 — 단위 31 + E2E 2, 마이그레이션 3).

## 10. 품질 게이트

| 구성 | 내용 |
|---|---|
| `scripts/check.sh` | 단일 검증 진입점: `ruff check` → `ruff format --check` → `pytest` |
| `scripts/fix.sh` | 안전한 lint·포맷 자동 수정 |
| `.githooks/pre-commit` | `scripts/check.sh` 호출. `scripts/install-git-hooks.sh`로 `core.hooksPath` 설정 |
| `.github/workflows/quality.yml` | Postgres service 컨테이너를 띄우고 `TEST_DATABASE_URL`을 지정한 뒤 같은 `scripts/check.sh` 실행 |
| ruff | `select = ["ALL"]`, preview. 무시 규칙은 `pyproject.toml`에 이유와 함께 기록 |

로컬, 훅, CI가 모두 같은 스크립트를 실행하므로 "내 컴퓨터에서는 통과"가 생기지 않는다.
