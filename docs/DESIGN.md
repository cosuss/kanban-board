# 설계 결정 (과제#7 — 간반 보드 백엔드 + CLI + Codex 스킬)

작성일 2026-10-19. 이 문서는 구현 전에 확정한 결정이다. 구현·문서 작성 시 이 결정을 재논의하지 않는다.

## 0. 과제 요구사항 (수업 자료 "바이브코딩 1편" p.39)

1. 과제#5에서 만든 **팀 공유 간반 보드 DB**(Supabase Postgres, 테이블 6개)에 기반해서 백엔드 시스템을 만든다.
2. CLI도 만든다.
3. Codex에서 CLI와 API를 이용해 팀 업무를 실제 간반 보드에 저장하고 공유한다.
   - Codex가 하는 작업을 간반 보드에 등록하게 하는 **스킬**도 만든다.
4. 2026-10-20 09:00까지 발표자료 제출(팀당 3분).

수업 실습 흐름(스펙 → 하네스 → 구현 → 감사 → CLI → E2E → 문서)과 레퍼런스 저장소
`Gachon-Cocone-School/team-todo-codex`의 구조를 따른다.

## 1. 저장소와 스택

- 위치: `cocone-school/kanban-board/` (단일 Git 저장소, 패키지 이름 `kanban-board`, 파이썬 패키지 `app/`).
- Python 3.11 고정(`requires-python = ">=3.11,<3.12"`), 패키지·가상환경은 `uv`.
- 백엔드: FastAPI + SQLAlchemy 2.x + psycopg 3(`psycopg[binary]`) + Alembic + pydantic-settings + uvicorn.
- CLI: Typer + httpx + rich(표 출력). CLI 이름은 `kanban`, 진입점 `kanban = "app.cli:app"`.
- 품질: ruff(`select = ["ALL"]`, preview) + pytest. `scripts/check.sh`가 단일 검증 진입점.
  `.githooks/pre-commit`이 이 스크립트를 호출하고 `.github/workflows/quality.yml`(Postgres service 포함)이 CI에서 같은 스크립트를 돌린다.
- DB는 **PostgreSQL만** 지원한다(SQLite 없음). 과제#5 DB가 Postgres(Supabase)이기 때문이다.

## 2. 데이터베이스 — 과제#5 v3 스키마를 그대로 쓴다

스키마 원본: `side-projects/kanban-db/sql/001_schema.sql` (과제#5 v3, 2026-10-05). 테이블 6개, 1:N 관계 8개.

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| boards | id, name, repo_url(UK, null 가능) | 보드–GitHub 저장소 1:1 |
| members | id, board_id(FK cascade), github_login(UK), name, role | 팀원 |
| stages | id, board_id(FK cascade), name, position; UNIQUE(board_id,name), UNIQUE(board_id,position) | 세로 칸(Todo/In Progress/Done) |
| milestones | id, board_id(FK cascade), title, due_on; UNIQUE(board_id,title) | |
| cards | id, stage_id(FK restrict), assignee_id(FK set null), milestone_id(FK set null), issue_number(UK, NOT NULL), title, body, position, created_at, closed_at | 카드 = GitHub 이슈 |
| comments | id, card_id(FK cascade), author_id(FK set null), body, created_at | |
| v_board (뷰) | stage, issue_number, title, assignee, milestone | security_invoker |

- 모든 PK는 `bigint generated always as identity`. 타임스탬프는 `timestamptz`, 마감일은 `date`.
- 6개 테이블 RLS 켜짐(정책 없음) → PostgREST/anon 키로는 접근 불가, **백엔드는 DB 연결 문자열(DATABASE_URL)로 직접 접속**한다.
- 스키마를 바꾸지 않는다(컬럼 추가 없음). 과제#7은 "DB에 기반한 백엔드"이므로 DB는 과제#5 결과물 그대로 둔다.
- Alembic 마이그레이션 `0001_kanban_v3`는 위 스키마를 **raw SQL + `IF NOT EXISTS`**(`create table if not exists`, `create index if not exists`, `create or replace view`, RLS는 `alter table ... enable row level security`)로 만든다.
  이유: Supabase에는 이미 같은 테이블이 있으므로 `alembic upgrade head`가 기존 DB에도, 빈 로컬 DB에도 안전해야 한다. downgrade는 뷰 → 자식 → 부모 순 `drop ... if exists`.
- 시드 데이터(실제 GitHub 데이터 47행)는 `side-projects/kanban-db/sql/002_seed.sql`에 있다. 저장소에는 복사하지 않고 README에서 경로만 안내한다. 테스트는 자체 fixture로 데이터를 만든다.

### 자동 채움 규칙 (스키마를 안 바꾸는 대신 서비스 계층이 책임진다)

- `cards.issue_number`: 요청에 없으면 `max(issue_number)+1`(테이블 전체, 비어 있으면 1). 요청에 있는데 중복이면 409.
- `cards.position`: 생성 시 대상 단계의 `max(position)+1`(비어 있으면 1). 이동 시 `position`을 주지 않으면 대상 단계 맨 끝에 붙인다. `position`을 주면 그 자리 이상인 카드들을 +1 밀고 삽입한다.
- `cards.created_at`, `comments.created_at`: 서버가 UTC now로 채운다. 클라이언트가 보낼 수 없다.
- `cards.closed_at`: 카드가 보드의 **마지막 단계(position 최대)** 로 이동하거나 그 단계에 생성되면 now로 채우고, 다른 단계로 이동하면 null로 되돌린다. 단계 이름이 아니라 순서로 판단한다(이름은 팀마다 다를 수 있음).
- 보드 생성 시 `with_default_stages`(기본 true)면 `Todo(1) / In Progress(2) / Done(3)`를 함께 만든다.
- 보드 삭제: cards.stage_id가 RESTRICT라서 DB cascade만으로는 실패한다. 서비스가 보드의 카드를 먼저 지우고 보드를 지운다(members/stages/milestones/comments는 cascade).
- 단계 삭제: 카드가 남아 있으면 409.

## 3. API 설계 (FastAPI, prefix `/api/v1`)

공통: JSON. 오류는 `{"detail": "..."}`. 404(없음), 409(유일성 충돌·삭제 불가), 422(검증). 인증 없음(수업 전제: 로컬 배포, 소규모 팀).
입력 한도(넘으면 422): 이름·제목·`github_login`·`author` 류 문자열 255자, `body`(카드·코멘트) 10,000자, URL(`repo_url`) 2,048자, `issue_number`·`position` 1 ~ 2^63-1.
Swagger `/docs`, ReDoc `/redoc`, `/openapi.json`은 FastAPI 기본.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /health | `{"status":"ok","database":"ok"}` (DB `select 1` 실패 시 503) |
| GET/POST | /boards | 목록 / 생성 `{name, repo_url?, with_default_stages?=true}` |
| GET/PATCH/DELETE | /boards/{board_id} | 단건 / 부분 수정 / 삭제(카드 포함 전부) |
| GET | /boards/{board_id}/view | 보드 화면: `{board, stages:[{id,name,position,cards:[CardOut...]}]}` 단계 순서 → 카드 순서 |
| GET/POST | /boards/{board_id}/members | 목록 / 생성 `{github_login, name, role?}` |
| GET/PATCH/DELETE | /members/{member_id} | |
| GET/POST | /boards/{board_id}/stages | 목록(position 순) / 생성 `{name, position?}` (position 없으면 max+1) |
| GET/PATCH/DELETE | /stages/{stage_id} | 삭제는 카드 있으면 409 |
| GET/POST | /boards/{board_id}/milestones | 목록 / 생성 `{title, due_on?}` |
| GET/PATCH/DELETE | /milestones/{milestone_id} | |
| GET/POST | /boards/{board_id}/cards | 목록(필터 `stage`(이름), `assignee`(github_login), `milestone`(제목), `q`(제목·본문 ilike), `limit`(기본 50, 최대 200), `offset`) / 생성 |
| GET/PATCH/DELETE | /cards/{card_id} | |
| POST | /cards/{card_id}/move | `{stage?: 이름, stage_id?: id, position?}` 둘 중 하나 필수 |
| GET/POST | /cards/{card_id}/comments | 목록(created_at 순) / 생성 `{body, author?: github_login, author_id?}` |
| GET/DELETE | /comments/{comment_id} | |

카드 생성·수정 요청은 **이름으로도 id로도** 참조할 수 있다: `stage`(이름) 또는 `stage_id`, `assignee`(github_login) 또는 `assignee_id`,
`milestone`(제목) 또는 `milestone_id`. 둘 다 주면 422. 이름이 보드 안에 없으면 404. 생성 시 단계를 안 주면 보드의 첫 단계(position 최소).
담당자·마일스톤을 지우려면 PATCH에 `assignee_id: null` / `milestone_id: null`.

`CardOut`: `{id, board_id, stage_id, stage, assignee_id, assignee(github_login|null), assignee_name(|null), milestone_id, milestone(|null), issue_number, title, body, position, created_at, closed_at}`.
`CommentOut`: `{id, card_id, author_id, author(github_login|null), author_name, body, created_at}`.

이유: Codex와 CLI가 "In Progress로 옮겨" "codex에게 할당"처럼 사람 말 그대로 쓰게 하려면 서버가 이름을 풀어야 한다.

## 4. CLI 설계 (`kanban`)

- 비개발자용. 대화형 모드 없음. macOS/Linux/Windows. `uvx --from <repo경로> kanban ...` 또는 `uv tool install --editable <repo경로>` 후 `kanban ...`.
- 전역 옵션: `--api-url`(env `KANBAN_API_URL`, 기본 `http://127.0.0.1:8000`), `--json`(기계용 출력), `--board`(env `KANBAN_BOARD`, 기본 1).
- 명령: `health`, `serve [--host --port --reload]`(uvicorn 실행), `db upgrade`(alembic upgrade head),
  `board list|add|show|update|delete`, `member ...`, `stage ...`, `milestone ...`,
  `card list|add|show|update|move|delete`, `comment list|add|show|delete`, `view`(보드를 단계별 열로 표시).
- 모든 API 엔드포인트에 명령이 1:1로 대응해야 한다(수업 요구). 도움말은 쉬운 영어 plain English.
- 출력: 기본은 rich 표/문장, `--json`이면 API 응답 JSON 그대로. 종료 코드 0 성공 / 1 API·연결 오류(메시지 1줄) / 2 사용법 오류.
- CLI는 API 클라이언트일 뿐 DB에 직접 접근하지 않는다(`serve`, `db upgrade` 제외).
- 테스트: CLI 단위 테스트는 httpx `ASGITransport`로 앱에 직접 연결(서버 불필요). E2E는 실제 uvicorn 서브프로세스를 띄워 명령을 순서대로 실행.

## 5. Codex 스킬 (`skills/kanban-log/SKILL.md`)

- 저장소 `skills/kanban-log/`가 원본, `~/.codex/skills/kanban-log` → 심볼릭 링크.
- 보드에 팀원 `codex`(github_login `codex`, name `Codex 에이전트`, role `AI 에이전트`)를 등록하고 Codex 작업 카드는 이 담당자로 만든다.
- 흐름: 작업 시작 → `kanban card add "<작업 제목>" --stage "In Progress" --assignee codex --body "<계획 요약>" --json`으로 카드 생성(id 기억) →
  작업 끝 → `kanban comment add <id> "<무엇을 바꿨고 어떻게 검증했는지>" --author codex` → `kanban card move <id> Done`.
  막히면 코멘트 남기고 `Todo`로 되돌린다. 서버가 안 떠 있으면(`kanban health` 실패) 사용자에게 `kanban serve`를 안내한다.

## 6. 환경 변수

| 이름 | 기본값 | 용도 |
|---|---|---|
| DATABASE_URL | `postgresql+psycopg://localhost/kanban` | 서버·alembic. `postgresql://`로 시작하면 `postgresql+psycopg://`로 바꿔 쓴다(Supabase 연결 문자열 그대로 붙이기 위함). |
| TEST_DATABASE_URL | `postgresql+psycopg://localhost/kanban_test` | pytest. 테스트마다 6개 테이블 TRUNCATE ... RESTART IDENTITY CASCADE. |
| DATABASE_POOL_SIZE / DATABASE_MAX_OVERFLOW / DATABASE_POOL_TIMEOUT | 5 / 10 / 30 | SQLAlchemy 풀. Supabase 무료 플랜 세션 풀러 한도를 넘지 않게 작게 둔다. |
| DATABASE_POOL_PRE_PING | true | 풀에서 꺼낼 때 `select 1`로 연결 생존 확인. 풀 크기만큼만 동시에 DB 요청을 받고, 그 이상은 `DATABASE_POOL_TIMEOUT`초까지 기다린 뒤 503 `database busy`(부하 테스트로 확인한 교착 방지, `docs/PERFORMANCE_AUDIT.md` §2). |
| KANBAN_API_URL, KANBAN_BOARD | 위 CLI 절 | |

`.env`는 커밋하지 않는다. `.env.example`만 둔다.

## 7. 문서 목록 (수업 형식)

`docs/PRD.md`, `TSD.md`, `DATABASE.md`, `TEST_CASE.md`(백엔드), `PRD_CLI.md`, `TSD_CLI.md`, `TEST_CASE_CLI.md`, `CLI_GUIDE.md`,
`SECURITY_AUDIT.md`, `PERFORMANCE_AUDIT.md`(부하 테스트 결과 포함), `CODEX.md`(Codex에서 CLI/API/스킬 쓰는 법). 모두 한국어, 레퍼런스 저장소 톤.
