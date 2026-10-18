# 간반 보드 백엔드 제품 요구사항 (PRD)

> 문서 목적: 과제#5 간반 DB 위에 올리는 팀 공유 보드 백엔드 API가 무엇을 해야 하는지(무엇을·왜)를 정의한다. 구현 방법은 `TSD.md`, 검증은 `TEST_CASE.md`를 본다.

## 1. 개요

팀이 GitHub 이슈 칸반처럼 쓰는 **보드(board)** 를 한 곳(Supabase Postgres)에 모아 두고, 팀원과 Codex 에이전트가 같은 보드를 읽고 쓸 수 있게 하는 백엔드 API를 만든다. 데이터 모델은 과제#5에서 만든 간반 DB(v3, 테이블 6개)를 **그대로** 사용한다. 이 백엔드는 그 DB를 HTTP로 여는 얇은 계층이며, 스키마는 바꾸지 않는다.

API 문서는 FastAPI가 제공하는 Swagger UI(`/docs`)와 `/openapi.json`으로 확인한다.

## 2. 목표

- 팀의 업무를 보드, 팀원(member), 단계(stage), 마일스톤(milestone), 카드(card), 코멘트(comment) 단위로 한 곳에서 관리한다.
- 모든 리소스에 대해 생성·조회·수정·삭제(CRUD)를 제공한다.
- 보드를 단계별 열로 한눈에 보는 보드 뷰(`/boards/{id}/view`)를 제공한다.
- 사람이 쓰는 말 그대로(`"In Progress"`, `codex`) 단계·담당자·마일스톤을 가리킬 수 있게 이름 참조를 지원한다.
- `issue_number`, `position`, `created_at`, `closed_at`처럼 스키마가 비워 둔 값은 서버가 규칙대로 채운다.
- Python 3.11, FastAPI, PostgreSQL(Supabase 호환)로 로컬에서 간단히 실행한다.

## 3. 사용자

| 사용자 | 설명 | 주로 하는 일 |
|---|---|---|
| 팀원 | 코딩을 잘 모를 수도 있는 팀 구성원. CLI(`kanban`) 또는 Swagger UI로 접근 | 카드 등록·이동, 코멘트 작성, 보드 확인 |
| Codex 에이전트 | 팀원 `codex`로 보드에 등록된 AI 에이전트. CLI 또는 `openapi.json`을 읽고 API를 직접 호출 | 작업 시작 시 카드 생성, 끝나면 코멘트와 Done 이동 |
| 개발자 | 백엔드를 실행·확장하는 사람 | 마이그레이션, 테스트, 배포 |

## 4. 범위

### 포함

- 보드, 팀원, 단계, 마일스톤, 카드, 코멘트의 CRUD
- 카드 이동(단계 변경 + 순서 지정)
- 카드 목록 필터(단계, 담당자, 마일스톤, 텍스트 검색)와 페이지네이션(`limit`, `offset`)
- 보드 뷰(단계 순서 → 카드 순서)
- 이름 또는 id로 단계·담당자·마일스톤·작성자 참조
- 서비스 계층의 자동 채움 규칙(5.2절)
- 헬스 체크(`/api/v1/health`, 편의용 `/health`)
- Alembic 마이그레이션(기존 Supabase 테이블과 공존)
- Swagger UI, ReDoc, `openapi.json`

### 제외

- 로그인, 인증, 역할·권한 관리 (로컬 배포, 소규모 팀 전제. API에 닿는 사람은 모든 보드를 읽고 쓸 수 있다)
- 실시간 동기화, 푸시 알림, 웹소켓
- GitHub 이슈와의 자동 동기화 (카드의 `issue_number`는 값으로만 저장한다)
- 스키마 변경(컬럼 추가 등), 라벨·체크리스트·활동 이력 같은 v1·v2 시절 개념
- 외부 호스팅·다중 사용자 원격 운영, SQLite 등 Postgres 외 DB

## 5. 기능 요구사항

### 5.1 리소스별 CRUD

| 리소스 | 생성 | 목록 | 단건 | 수정 | 삭제 | 비고 |
|---|---|---|---|---|---|---|
| 보드(board) | O | O | O | O | O | 삭제 시 카드를 포함해 전부 삭제 |
| 팀원(member) | O (보드 하위) | O (보드 하위) | O | O | O | `github_login`은 전체에서 유일 |
| 단계(stage) | O (보드 하위) | O (position 순) | O | O | O | 카드가 남아 있으면 삭제 불가(409) |
| 마일스톤(milestone) | O (보드 하위) | O (보드 하위) | O | O | O | 삭제 시 카드의 마일스톤은 null |
| 카드(card) | O (보드 하위) | O (필터·페이지) | O | O | O | 이동은 별도 동작 `POST /cards/{id}/move` |
| 코멘트(comment) | O (카드 하위) | O (created_at 순) | O | 없음 | O | 코멘트 수정은 제공하지 않는다 |

### 5.2 자동 채움 규칙

스키마를 바꾸지 않는 대신 서비스 계층이 아래 값을 채운다.

| 대상 | 규칙 |
|---|---|
| `cards.issue_number` | 요청에 없으면 `max(issue_number)+1`(테이블 전체, 비어 있으면 1). 요청에 있는데 이미 있으면 409 |
| `cards.position` | 생성 시 항상 대상 단계의 `max(position)+1`(비어 있으면 1)이며 생성 요청에는 `position`이 없다. 이동(`move`) 시 `position` 없으면 대상 단계 맨 끝, `position`을 주면 그 자리 이상의 카드를 +1 밀고 삽입. 카드 수정(PATCH)으로 단계를 바꾸면 맨 끝 |
| `cards.created_at`, `comments.created_at` | 서버가 UTC 현재 시각으로 채움. 클라이언트가 보내도 무시됨(오류 아님) |
| `cards.closed_at` | 카드가 보드의 **마지막 단계(position 최대)** 에 생성·이동하면 현재 시각, 다른 단계로 이동하면 null. 단계 이름이 아니라 순서로 판단 |
| 기본 단계 | 보드 생성 시 `with_default_stages`(기본 true)면 `Todo(1)`, `In Progress(2)`, `Done(3)` 자동 생성 |
| `stages.position` | 생성 시 없으면 보드의 `max(position)+1` |
| 카드 생성 시 단계 | 단계를 안 주면 보드의 첫 단계(position 최소) |

### 5.3 이름·id 참조

Codex와 CLI가 사람 말 그대로 쓰게 하려고, 서버가 이름을 id로 풀어 준다.

| 참조 대상 | 이름으로 | id로 | 규칙 |
|---|---|---|---|
| 단계 | `stage` (단계 이름) | `stage_id` | 둘 다 non-null이면 422, 이름·id가 이 보드에 없으면 404 |
| 담당자 | `assignee` (github_login) | `assignee_id` | 위와 같음 |
| 마일스톤 | `milestone` (제목) | `milestone_id` | 위와 같음 |
| 코멘트 작성자 | `author` (github_login) | `author_id` | 위와 같음 |

담당자·마일스톤을 지우려면 카드 수정에서 `assignee_id: null` / `milestone_id: null`(또는 `assignee: null` / `milestone: null`)을 보낸다. 본문은 `body: null`로 비운다. 카드 목록 필터(`stage`, `assignee`, `milestone`)에 없는 이름을 주면 404가 아니라 빈 목록이다.

### 5.4 보드 뷰

`GET /boards/{board_id}/view`는 보드와 단계 목록을 position 순으로, 각 단계의 카드를 카드 position 순으로 돌려준다. 사람이 칸반 화면처럼 읽을 수 있는 한 번의 호출이다.

### 5.5 오류 응답

| 상태 코드 | 의미 |
|---|---|
| 404 | 대상 리소스 없음, 이름 참조 대상이 보드 안에 없음 |
| 409 | 유일성 충돌(issue_number, repo_url, github_login, 단계 이름·position, 마일스톤 제목), 삭제 불가(카드 있는 단계) |
| 422 | 입력 검증 실패(필수 누락, 형식 오류, 이름+id 동시 지정, 범위 밖 limit 등) |
| 503 | `/health`에서 DB 연결 실패 |

본문 형식은 `{"detail": "..."}`다. 입력 검증 422는 FastAPI 기본 형식으로 `detail`이 객체 배열이다. 503도 같은 `{"detail": "database unavailable"}`다.

요청 본문의 알 수 없는 필드는 오류 없이 무시한다.

## 6. 비기능 요구사항

| 항목 | 요구 |
|---|---|
| 데이터베이스 | PostgreSQL 전용. SQLite 미지원 |
| Supabase 호환 | Supabase 연결 문자열(`postgresql://...`)을 `DATABASE_URL`에 그대로 붙여 넣을 수 있고, 이미 같은 테이블이 있는 DB에서도 `alembic upgrade head`가 안전하다 |
| 접속 방식 | RLS가 켜져 있고 정책이 없으므로 PostgREST/anon 키가 아니라 DB 연결 문자열로 직접 접속 |
| 연결 풀 | 기본 `pool_size 5 / max_overflow 10 / timeout 30초`. Supabase 무료 플랜의 세션 풀러 한도를 넘지 않게 작게 둠. 환경 변수로 조정 |
| 재현성 | Python 3.11 고정, `uv.lock` 포함 |
| 품질 | `scripts/check.sh` 하나로 lint·포맷·테스트. pre-commit과 CI가 같은 스크립트를 실행 |
| 보안 전제 | 인증 없음. 로컬 또는 신뢰할 수 있는 네트워크에서만 실행. `.env`는 커밋하지 않음 |

## 7. 핵심 시나리오

1. 팀원이 보드를 만들면 `Todo / In Progress / Done`이 자동으로 생긴다.
2. 팀원을 등록하고(`codex` 포함) 마일스톤을 만든다.
3. 카드를 `Todo`에 만들고 담당자를 `github_login`으로 지정한다.
4. 카드를 `In Progress`로 옮기고 코멘트를 남긴다.
5. `Done`으로 옮기면 `closed_at`이 채워지고, 다시 옮기면 비워진다.
6. 보드 뷰로 단계별 현황을 확인한다.
7. Codex가 작업을 시작할 때 카드를 만들고, 끝나면 코멘트와 함께 `Done`으로 옮긴다.

## 8. 성공 기준

- `TEST_CASE.md`의 케이스가 통과하고(자동 테스트 83개 통과, 일부 케이스는 수동 확인) 자가 점검 표에서 모든 CRUD가 커버된다.
- `scripts/check.sh`가 로컬과 CI에서 통과한다.
- 빈 로컬 Postgres와 과제#5 테이블이 이미 있는 Supabase DB 양쪽에서 `alembic upgrade head`가 오류 없이 끝나고 두 번 실행해도 같은 결과다.
- 시드 데이터(47행)가 들어 있는 DB에서 `GET /boards/1/view`가 `Todo / In Progress / Done` 단계와 카드 27장을 올바른 순서로 돌려준다.
- Swagger UI(`/docs`)에서 모든 엔드포인트를 호출해 볼 수 있다.
- Codex가 `openapi.json`만 보고(또는 CLI로) 카드를 만들고 `Done`으로 옮길 수 있다.

## 9. 관련 문서

| 문서 | 내용 |
|---|---|
| `DESIGN.md` | 확정된 설계 결정(원천) |
| `TSD.md` | 기술 명세와 API 계약 |
| `DATABASE.md` | 스키마와 자동 채움 대상 컬럼 |
| `TEST_CASE.md` | 백엔드 테스트 케이스 |
| `PRD_CLI.md`, `TSD_CLI.md`, `TEST_CASE_CLI.md`, `CLI_GUIDE.md` | CLI 문서 |
| `CODEX.md` | Codex에서 쓰는 법과 실제 데모 결과 |
| `SECURITY_AUDIT.md`, `PERFORMANCE_AUDIT.md` | 보안·성능 점검 결과 |
