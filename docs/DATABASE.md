# 간반 보드 데이터베이스 (DATABASE)

> 문서 목적: 백엔드가 쓰는 과제#5 v3 스키마(테이블 6개, 관계 8개, 뷰 1개)를 백엔드 관점의 설명과 함께 정리한다. 스키마의 원본은 `side-projects/kanban-db/sql/001_schema.sql`이며 과제#7은 이를 바꾸지 않는다.

## 1. 개요

- DB: PostgreSQL (Supabase 호환). 백엔드는 `DATABASE_URL`로 **직접 접속**한다.
- 모든 PK는 `bigint generated always as identity`. 타임스탬프는 `timestamptz`, 마감일은 `date`.
- 6개 테이블 모두 RLS가 켜져 있고 정책이 없다. 따라서 PostgREST/anon 키로는 읽고 쓸 수 없고 DB 연결 문자열(서버 역할)로만 접근한다.
- 스키마를 바꾸지 않는다(컬럼 추가 없음). 스키마가 비워 둔 값(`issue_number`, `position`, `created_at`, `closed_at`)은 서비스 계층이 채운다.

## 2. ER 구조

```text
boards 1 ─┬─< members       (board_id, cascade)
          ├─< stages        (board_id, cascade)
          └─< milestones    (board_id, cascade)

stages     1 ─< cards       (stage_id, restrict)
members    1 ─< cards       (assignee_id, set null)
milestones 1 ─< cards       (milestone_id, set null)

cards      1 ─< comments    (card_id, cascade)
members    1 ─< comments    (author_id, set null)
```

## 3. 테이블

### 3.1 boards

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | bigint | PK, identity | 보드 id |
| name | text | NOT NULL | 보드 이름 |
| repo_url | text | UNIQUE, null 가능 | GitHub 저장소 URL. 보드–저장소는 1:1이라 같은 표에 둔다 |

### 3.2 members

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | bigint | PK, identity | 팀원 id |
| board_id | bigint | NOT NULL, FK → boards(id) ON DELETE CASCADE | 소속 보드 |
| github_login | text | NOT NULL, UNIQUE | GitHub 로그인. **테이블 전체에서** 유일 (보드별이 아님) |
| name | text | NOT NULL | 표시 이름 |
| role | text | null 가능 | 역할(예: 백엔드, PM, AI 에이전트) |

### 3.3 stages

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | bigint | PK, identity | 단계 id |
| board_id | bigint | NOT NULL, FK → boards(id) ON DELETE CASCADE | 소속 보드 |
| name | text | NOT NULL | 단계 이름(Todo, In Progress, Done 등) |
| position | int | NOT NULL | 단계 순서(왼쪽부터 1) |
| (복합) | | UNIQUE (board_id, name) | 보드 안에서 이름 유일 |
| (복합) | | UNIQUE (board_id, position) | 보드 안에서 순서 유일 |

### 3.4 milestones

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | bigint | PK, identity | 마일스톤 id |
| board_id | bigint | NOT NULL, FK → boards(id) ON DELETE CASCADE | 소속 보드 |
| title | text | NOT NULL | 마일스톤 제목 |
| due_on | date | null 가능 | 마감일 |
| (복합) | | UNIQUE (board_id, title) | 보드 안에서 제목 유일 |

### 3.5 cards

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | bigint | PK, identity | 카드 id |
| stage_id | bigint | NOT NULL, FK → stages(id) ON DELETE RESTRICT | 현재 단계. 카드의 상태를 나타냄 |
| assignee_id | bigint | FK → members(id) ON DELETE SET NULL | 담당자(없을 수 있음) |
| milestone_id | bigint | FK → milestones(id) ON DELETE SET NULL | 마일스톤(없을 수 있음) |
| issue_number | int | NOT NULL, UNIQUE | GitHub 이슈 번호. 테이블 전체에서 유일 |
| title | text | NOT NULL | 제목 |
| body | text | null 가능 | 본문 |
| position | int | NOT NULL | 단계 안에서의 순서 (UNIQUE 아님) |
| created_at | timestamptz | NOT NULL | 생성 시각 (DB 기본값 없음) |
| closed_at | timestamptz | null 가능 | 닫힌 시각 (null이면 열린 카드) |

카드에는 `board_id` 컬럼이 없다. 소속 보드는 `stage_id → stages.board_id`로 구한다.

### 3.6 comments

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | bigint | PK, identity | 코멘트 id |
| card_id | bigint | NOT NULL, FK → cards(id) ON DELETE CASCADE | 대상 카드 |
| author_id | bigint | FK → members(id) ON DELETE SET NULL | 작성자(없거나 팀원 삭제 시 null) |
| body | text | NOT NULL | 내용 |
| created_at | timestamptz | NOT NULL | 작성 시각 (DB 기본값 없음) |

## 4. 관계 8개

| # | 자식.컬럼 | 부모 | 삭제 동작 | 백엔드에서의 의미 |
|---|---|---|---|---|
| 1 | members.board_id | boards | CASCADE | 보드를 지우면 팀원도 삭제 |
| 2 | stages.board_id | boards | CASCADE | 보드를 지우면 단계도 삭제 |
| 3 | milestones.board_id | boards | CASCADE | 보드를 지우면 마일스톤도 삭제 |
| 4 | cards.stage_id | stages | RESTRICT | 카드가 있는 단계는 DB가 삭제를 막음. API는 409로 답함 |
| 5 | cards.assignee_id | members | SET NULL | 팀원을 지우면 카드는 남고 담당자만 비워짐 |
| 6 | cards.milestone_id | milestones | SET NULL | 마일스톤을 지우면 카드는 남고 마일스톤만 비워짐 |
| 7 | comments.card_id | cards | CASCADE | 카드를 지우면 코멘트도 삭제 |
| 8 | comments.author_id | members | SET NULL | 팀원을 지우면 코멘트는 남고 작성자만 비워짐 |

**보드 삭제와 RESTRICT:** 관계 4가 RESTRICT라서 보드를 지우는 DB cascade는 `boards → stages → cards`에서 막힌다. 그래서 서비스가 보드의 카드를 먼저 지운 뒤(코멘트는 cascade) 보드를 지운다(`TSD.md` 7.5절).

## 5. 인덱스

| 이름 | 대상 | 용도 |
|---|---|---|
| idx_cards_stage_id | cards(stage_id) | 단계별 카드 조회, 보드 뷰 |
| idx_cards_assignee_id | cards(assignee_id) | 담당자 필터 |
| idx_cards_milestone_id | cards(milestone_id) | 마일스톤 필터 |
| idx_comments_card_id | comments(card_id) | 카드의 코멘트 목록 |
| idx_comments_author_id | comments(author_id) | 작성자 조회, set null 처리 |

PK와 UNIQUE 제약(`boards.repo_url`, `members.github_login`, `stages(board_id,name)`, `stages(board_id,position)`, `milestones(board_id,title)`, `cards.issue_number`)이 만드는 암묵 인덱스는 별도로 있다.

## 6. 뷰 v_board

```sql
create view v_board with (security_invoker = true) as
select s.name as stage, k.issue_number, k.title, m.name as assignee, ms.title as milestone
from cards k
join stages s on s.id = k.stage_id
left join members m on m.id = k.assignee_id
left join milestones ms on ms.id = k.milestone_id
order by s.position, k.position;
```

- 단계 순서 → 카드 순서로 정렬된 읽기 전용 화면용 뷰다. `security_invoker = true`이므로 호출자의 권한(RLS)이 그대로 적용된다.
- 이 뷰에는 `board_id`가 없어 여러 보드가 섞인다. 그래서 API의 보드 뷰(`GET /boards/{id}/view`)는 `v_board`를 쓰지 않고 테이블을 직접 조인해 보드별로 만든다. `v_board`는 SQL 콘솔 확인용이다.
- 마이그레이션에서는 `create or replace view`로 멱등하게 만든다.

## 7. RLS와 접속 방식

| 항목 | 내용 |
|---|---|
| RLS | 6개 테이블 모두 `enable row level security`, 정책 없음 |
| 효과 | anon/authenticated 키(PostgREST, Supabase JS)로는 아무 행도 못 읽고 못 쓴다 |
| 백엔드 접속 | `DATABASE_URL`(Supabase 대시보드의 Database 연결 문자열)로 직접 접속. 접속 역할은 RLS를 우회하는 서버 역할(예: `postgres`)이다 |
| 연결 문자열 | `postgresql://...`를 그대로 붙이면 `postgresql+psycopg://`로 바꿔 쓴다 |
| 풀 | 기본 5 + overflow 10. Supabase 무료 플랜의 세션 풀러 한도를 넘지 않게 작게 둔다 |
| 풀 초과 | 풀 연결 수(`pool_size`+`max_overflow`)만큼만 동시에 세션을 받고, 초과분은 `DATABASE_POOL_TIMEOUT`초 기다린 뒤 503 `database busy, try again`을 돌려준다. |
| 비밀 | 연결 문자열은 `.env`에만 두고 커밋하지 않는다 |

## 8. 자동 채움이 적용되는 컬럼

스키마에는 기본값이 없으므로 서비스가 값을 정한다.

| 컬럼 | 채우는 시점 | 규칙 |
|---|---|---|
| cards.issue_number | 카드 생성 | 요청 없으면 `max+1`(전체, 비면 1; advisory lock으로 동시 요청 직렬화). 요청 값이 중복이면 409 |
| cards.position | 카드 생성·이동·단계 변경 | 생성과 PATCH 단계 변경은 대상 단계 `max+1`(생성 요청에 `position` 없음). `move`에서만 지정 위치에 삽입하고 같은 단계의 뒤를 +1 |
| cards.created_at | 카드 생성 | 서버 UTC now. 클라이언트가 보내도 무시 |
| cards.closed_at | 카드 생성·이동 | 보드의 마지막 단계(position 최대)면 now, 아니면 null |
| comments.created_at | 코멘트 생성 | 서버 UTC now. 클라이언트가 보내도 무시 |
| stages.position | 단계 생성 | 요청 없으면 보드 안 `max+1` |
| stages (3행) | 보드 생성 | `with_default_stages`가 true면 `Todo(1) / In Progress(2) / Done(3)` |

## 9. 시드 데이터

- 파일: `side-projects/kanban-db/sql/002_seed.sql` (과제#5에서 만든 실제 GitHub 데이터). 이 저장소에는 복사하지 않고 `README.md`에서 경로만 안내한다.
- 규모: 47행.

| 테이블 | 행 수 |
|---|---|
| boards | 1 |
| members | 4 |
| stages | 3 |
| milestones | 2 |
| cards | 27 |
| comments | 10 |
| 합계 | 47 |

- 로컬에서 시드를 넣으려면 마이그레이션 후 `psql "<postgresql:// 연결 문자열>" -f <경로>/002_seed.sql`을 실행한다.
- 자동 테스트는 시드에 의존하지 않고 fixture로 데이터를 만든다.

## 10. 마이그레이션과의 관계

`alembic/versions/0001_kanban_v3.py`가 이 문서의 모든 객체를 `if not exists` / `create or replace`로 만든다. 상세는 `TSD.md` 8절.
