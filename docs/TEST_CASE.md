# 간반 보드 백엔드 테스트 케이스 (TEST_CASE)

> 문서 목적: 백엔드 API의 모든 엔드포인트와 자동 채움 규칙을 성공/실패 케이스로 정의하고, 체크리스트로 구현·검증 여부를 추적한다.

## 공통 기준

- 기본 URL `http://127.0.0.1:8000`, API prefix `/api/v1`. 헬스 체크는 `/api/v1/health`와 문서에 숨겨진 편의 경로 `/health` 둘 다 있다. 모든 요청·응답은 JSON이며 `DELETE` 성공은 `204`에 본문이 없다.
- 각 테스트는 독립적이다. 테스트 전에 6개 테이블을 `TRUNCATE ... RESTART IDENTITY CASCADE` 하므로 id는 1부터 시작한다.
- 표기: `B1` = 기본 단계(Todo 1, In Progress 2, Done 3; stage id 1·2·3)를 가진 보드(id 1, `name: "Team A"`). `codex`, `minji` = B1의 팀원(`github_login`). `MVP` = B1의 마일스톤. `card#N`은 케이스 안에서 준비한 카드.
- "준비"는 해당 케이스 전에 필요한 데이터이며, 요청 본문은 핵심 필드만 적는다.
- 오류 응답은 `{"detail": ...}`다. 상태 코드와 `detail` 존재를 확인하고 문구 자체는 비교하지 않는다. FastAPI/Pydantic 검증 오류(필수 누락, 이름+id 동시 지정 등)는 `detail`이 배열이다.
- 시각 필드는 ISO 8601이며(오프셋 표기는 DB 세션 시간대를 따를 수 있다), 값 비교 대신 null 여부·형식·변경 여부를 확인한다.
- 요청 본문의 알 수 없는 필드는 오류 없이 무시된다(`extra = forbid`가 아니다).
- 목록 응답은 모두 JSON 배열이다(카드 목록 포함).
- 케이스 ID 접두사 `TC-B`는 Backend다. 체크 박스는 수동 추적용이다. 자동 테스트(`uv run pytest`, 83개 통과)가 이 케이스 대부분을 포함하지만 케이스별 1:1 매핑은 하지 않았다. 마이그레이션(TC-B-147·148·150)과 RLS는 `tests/test_migrations.py`가 확인한다. 자동 테스트가 없는 케이스(TC-B-146·149·151~154)는 "수동"으로 표시했다.

## 1. Health

- [ ] **TC-B-001 헬스 체크 성공**
  - Endpoint: `GET /api/v1/health` 및 `GET /health`
  - Request: 없음
  - Expected: 둘 다 `200`; `{"status": "ok", "database": "ok"}`

- [ ] **TC-B-002 DB 연결 실패 시 503**
  - Endpoint: `GET /health`
  - Request: 세션 의존성이 SQLAlchemy 오류를 던지도록 오버라이드
  - Expected: `503`; 본문 `{"detail": "database unavailable"}`

## 2. 보드 (boards)

- [ ] **TC-B-003 보드 생성 — 기본 단계 3개 자동 생성**
  - Endpoint: `POST /api/v1/boards`
  - Request: `{"name": "Team A"}`
  - Expected: `201`; `id: 1`, `name: "Team A"`, `repo_url: null`. 이어서 `GET /boards/1/stages`가 `Todo(1) / In Progress(2) / Done(3)` 세 개를 position 순으로 돌려준다.

- [ ] **TC-B-004 저장소 URL을 포함해 생성**
  - Endpoint: `POST /api/v1/boards`
  - Request: `{"name": "Team A", "repo_url": "https://github.com/acme/team-a"}`
  - Expected: `201`; `repo_url`이 요청값과 같다.

- [ ] **TC-B-005 with_default_stages=false면 단계 없이 생성**
  - Endpoint: `POST /api/v1/boards`
  - Request: `{"name": "Empty", "with_default_stages": false}`
  - Expected: `201`; 이어서 `GET /boards/{id}/stages` → `200`, `[]`.

- [ ] **TC-B-006 보드 목록**
  - Endpoint: `GET /api/v1/boards`
  - Request: 준비 — 보드 2개 생성
  - Expected: `200`; 배열 길이 2, `id` 오름차순. 보드가 없으면 `[]`.

- [ ] **TC-B-007 보드 단건 조회**
  - Endpoint: `GET /api/v1/boards/1`
  - Request: 준비 — B1
  - Expected: `200`; `id`, `name`, `repo_url` 포함.

- [ ] **TC-B-008 이름 수정**
  - Endpoint: `PATCH /api/v1/boards/1`
  - Request: `{"name": "Team A (2026)"}`
  - Expected: `200`; `name`이 바뀌고 `repo_url`은 유지된다.

- [ ] **TC-B-009 저장소 URL 비우기**
  - Endpoint: `PATCH /api/v1/boards/1`
  - Request: 준비 — repo_url이 있는 보드; 본문 `{"repo_url": null}`
  - Expected: `200`; `repo_url: null`.

- [ ] **TC-B-010 빈 본문 수정은 변경 없음**
  - Endpoint: `PATCH /api/v1/boards/1`
  - Request: `{}`
  - Expected: `200`; 현재 값 그대로.

- [ ] **TC-B-011 보드 삭제 — 카드·코멘트까지 모두 삭제**
  - Endpoint: `DELETE /api/v1/boards/1`
  - Request: 준비 — B1에 팀원 2, 마일스톤 1, 카드 3(서로 다른 단계), 카드에 코멘트 2
  - Expected: `204`. 이어서 `GET /boards/1` → `404`; 같은 보드의 members·stages·milestones·cards·comments 행이 DB에 0건(다른 보드의 행은 남아 있음).

- [ ] **TC-B-012 이름 없이 생성 → 422**
  - Endpoint: `POST /api/v1/boards`
  - Request: `{}`
  - Expected: `422`.

- [ ] **TC-B-013 빈 이름 → 422**
  - Endpoint: `POST /api/v1/boards`
  - Request: `{"name": ""}`
  - Expected: `422`.

- [ ] **TC-B-014 repo_url 중복 → 409**
  - Endpoint: `POST /api/v1/boards`
  - Request: 준비 — `repo_url`이 `https://github.com/acme/team-a`인 보드; 같은 URL로 다시 생성
  - Expected: `409`; `detail` 존재. 보드 수는 늘지 않는다.

- [ ] **TC-B-015 repo_url 수정 중 중복 → 409**
  - Endpoint: `PATCH /api/v1/boards/2`
  - Request: 준비 — 보드 1(`url-a`), 보드 2(`url-b`); 본문 `{"repo_url": "url-a"}`
  - Expected: `409`.

- [ ] **TC-B-016 없는 보드 조회 → 404**
  - Endpoint: `GET /api/v1/boards/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-017 없는 보드 수정 → 404**
  - Endpoint: `PATCH /api/v1/boards/999`
  - Request: `{"name": "x"}`
  - Expected: `404`.

- [ ] **TC-B-018 없는 보드 삭제 → 404**
  - Endpoint: `DELETE /api/v1/boards/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-019 id 형식 오류 → 422**
  - Endpoint: `GET /api/v1/boards/abc`
  - Request: 없음
  - Expected: `422`.

## 3. 보드 뷰 (view)

- [ ] **TC-B-020 단계·카드 순서대로 반환**
  - Endpoint: `GET /api/v1/boards/1/view`
  - Request: 준비 — B1에 카드 4장: Todo(position 2, 1), In Progress(1), Done(1)을 생성 순서를 섞어서 준비
  - Expected: `200`; `board.id: 1`, `stages`가 `Todo, In Progress, Done` 순서(position 오름차순). 각 단계의 `cards`가 카드 `position` 오름차순. 각 카드는 CardOut 필드(`stage`, `assignee`, `milestone`, `issue_number`, ...)를 가진다.

- [ ] **TC-B-021 카드 없는 단계도 포함**
  - Endpoint: `GET /api/v1/boards/1/view`
  - Request: 준비 — B1, 카드 없음
  - Expected: `200`; `stages` 길이 3, 모든 `cards`가 `[]`.

- [ ] **TC-B-022 다른 보드의 카드는 섞이지 않음**
  - Endpoint: `GET /api/v1/boards/1/view`
  - Request: 준비 — 보드 1과 2 각각에 카드 1장
  - Expected: `200`; 보드 1 뷰에는 보드 1의 카드 1장만 나온다.

- [ ] **TC-B-023 없는 보드의 뷰 → 404**
  - Endpoint: `GET /api/v1/boards/999/view`
  - Request: 없음
  - Expected: `404`.

## 4. 팀원 (members)

- [ ] **TC-B-024 팀원 생성**
  - Endpoint: `POST /api/v1/boards/1/members`
  - Request: `{"github_login": "codex", "name": "Codex 에이전트", "role": "AI 에이전트"}`
  - Expected: `201`; `id`, `board_id: 1`, `github_login: "codex"`, `name`, `role` 포함.

- [ ] **TC-B-025 role 없이 생성**
  - Endpoint: `POST /api/v1/boards/1/members`
  - Request: `{"github_login": "minji", "name": "민지"}`
  - Expected: `201`; `role: null`.

- [ ] **TC-B-026 팀원 목록**
  - Endpoint: `GET /api/v1/boards/1/members`
  - Request: 준비 — B1에 팀원 2명, 보드 2에 팀원 1명
  - Expected: `200`; B1의 팀원 2명만 `id` 오름차순.

- [ ] **TC-B-027 팀원 단건 조회**
  - Endpoint: `GET /api/v1/members/1`
  - Request: 준비 — 팀원 `codex`
  - Expected: `200`; `github_login: "codex"`.

- [ ] **TC-B-028 팀원 수정**
  - Endpoint: `PATCH /api/v1/members/1`
  - Request: `{"name": "Codex", "role": "AI"}`
  - Expected: `200`; 두 필드가 바뀌고 `github_login`은 유지.

- [ ] **TC-B-029 role 비우기**
  - Endpoint: `PATCH /api/v1/members/1`
  - Request: `{"role": null}`
  - Expected: `200`; `role: null`.

- [ ] **TC-B-030 팀원 삭제 — 카드 담당자·코멘트 작성자는 null**
  - Endpoint: `DELETE /api/v1/members/1`
  - Request: 준비 — `codex`가 담당자인 카드와 `codex`가 쓴 코멘트
  - Expected: `204`. 이어서 `GET /cards/{id}` → `200`, `assignee_id/assignee/assignee_name`이 `null`(카드는 남음). `GET /comments/{id}` → `200`, `author_id/author/author_name`이 `null`.

- [ ] **TC-B-031 github_login 중복 → 409**
  - Endpoint: `POST /api/v1/boards/1/members`
  - Request: 준비 — `codex` 존재; 같은 `github_login`으로 다시 생성
  - Expected: `409`.

- [ ] **TC-B-032 다른 보드에서도 같은 login 사용 불가 → 409**
  - Endpoint: `POST /api/v1/boards/2/members`
  - Request: 준비 — 보드 1에 `codex`; 보드 2에 `{"github_login": "codex", "name": "x"}`
  - Expected: `409` (스키마가 `github_login`을 테이블 전체에서 유일하게 정의함).

- [ ] **TC-B-033 필수 필드 누락 → 422**
  - Endpoint: `POST /api/v1/boards/1/members`
  - Request: `{"github_login": "x"}` (name 없음) 및 `{"name": "x"}` (github_login 없음)
  - Expected: 둘 다 `422`.

- [ ] **TC-B-034 없는 보드에 생성 → 404**
  - Endpoint: `POST /api/v1/boards/999/members`
  - Request: `{"github_login": "x", "name": "x"}`
  - Expected: `404`.

- [ ] **TC-B-035 없는 보드의 팀원 목록 → 404**
  - Endpoint: `GET /api/v1/boards/999/members`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-036 없는 팀원 조회 → 404**
  - Endpoint: `GET /api/v1/members/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-037 없는 팀원 수정 → 404**
  - Endpoint: `PATCH /api/v1/members/999`
  - Request: `{"name": "x"}`
  - Expected: `404`.

- [ ] **TC-B-038 수정 중 github_login 중복 → 409**
  - Endpoint: `PATCH /api/v1/members/2`
  - Request: 준비 — `codex`(1), `minji`(2); 본문 `{"github_login": "codex"}`
  - Expected: `409`.

- [ ] **TC-B-039 없는 팀원 삭제 → 404**
  - Endpoint: `DELETE /api/v1/members/999`
  - Request: 없음
  - Expected: `404`.

## 5. 단계 (stages)

- [ ] **TC-B-040 position 자동 부여**
  - Endpoint: `POST /api/v1/boards/1/stages`
  - Request: 준비 — B1(기본 3단계); 본문 `{"name": "Review"}`
  - Expected: `201`; `position: 4`, `board_id: 1`.

- [ ] **TC-B-041 단계가 없는 보드의 첫 단계는 position 1**
  - Endpoint: `POST /api/v1/boards/2/stages`
  - Request: 준비 — `with_default_stages=false` 보드; 본문 `{"name": "Backlog"}`
  - Expected: `201`; `position: 1`.

- [ ] **TC-B-042 position 직접 지정**
  - Endpoint: `POST /api/v1/boards/1/stages`
  - Request: `{"name": "QA", "position": 10}`
  - Expected: `201`; `position: 10`.

- [ ] **TC-B-043 단계 목록은 position 순**
  - Endpoint: `GET /api/v1/boards/1/stages`
  - Request: 준비 — B1, 이어서 `position: 10`인 단계와 `position: 5`인 단계를 순서를 바꿔 생성
  - Expected: `200`; position 1, 2, 3, 5, 10 순서.

- [ ] **TC-B-044 단계 단건 조회**
  - Endpoint: `GET /api/v1/stages/1`
  - Request: 없음
  - Expected: `200`; `name: "Todo"`, `position: 1`.

- [ ] **TC-B-045 단계 이름 수정**
  - Endpoint: `PATCH /api/v1/stages/2`
  - Request: `{"name": "Doing"}`
  - Expected: `200`; `name: "Doing"`. 이 단계의 카드 응답의 `stage`도 `"Doing"`.

- [ ] **TC-B-046 단계 position 수정**
  - Endpoint: `PATCH /api/v1/stages/2`
  - Request: `{"position": 20}`
  - Expected: `200`; `position: 20`.

- [ ] **TC-B-047 빈 단계 삭제**
  - Endpoint: `DELETE /api/v1/stages/2`
  - Request: 준비 — 카드가 없는 단계
  - Expected: `204`. 이어서 `GET /stages/2` → `404`.

- [ ] **TC-B-048 카드가 있는 단계 삭제 → 409**
  - Endpoint: `DELETE /api/v1/stages/1`
  - Request: 준비 — `Todo`에 카드 1장
  - Expected: `409`. 단계와 카드는 그대로 남는다(`GET /stages/1` → `200`).

- [ ] **TC-B-049 이름 중복 → 409**
  - Endpoint: `POST /api/v1/boards/1/stages`
  - Request: `{"name": "Todo"}`
  - Expected: `409`.

- [ ] **TC-B-050 다른 보드에서는 같은 이름 허용**
  - Endpoint: `POST /api/v1/boards/2/stages`
  - Request: 준비 — 단계 없는 보드 2; 본문 `{"name": "Todo"}`
  - Expected: `201`.

- [ ] **TC-B-051 position 중복 → 409**
  - Endpoint: `POST /api/v1/boards/1/stages`
  - Request: `{"name": "X", "position": 2}`
  - Expected: `409`.

- [ ] **TC-B-052 이름 없음·position 0 → 422**
  - Endpoint: `POST /api/v1/boards/1/stages`
  - Request: `{}` 및 `{"name": "X", "position": 0}`
  - Expected: 둘 다 `422`.

- [ ] **TC-B-053 없는 보드에 생성 → 404**
  - Endpoint: `POST /api/v1/boards/999/stages`
  - Request: `{"name": "X"}`
  - Expected: `404`.

- [ ] **TC-B-054 없는 보드의 단계 목록 → 404**
  - Endpoint: `GET /api/v1/boards/999/stages`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-055 없는 단계 조회 → 404**
  - Endpoint: `GET /api/v1/stages/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-056 없는 단계 수정 → 404**
  - Endpoint: `PATCH /api/v1/stages/999`
  - Request: `{"name": "x"}`
  - Expected: `404`.

- [ ] **TC-B-057 수정 중 이름/position 중복 → 409**
  - Endpoint: `PATCH /api/v1/stages/2`
  - Request: `{"name": "Todo"}` 및 `{"position": 1}`
  - Expected: 둘 다 `409`.

- [ ] **TC-B-058 없는 단계 삭제 → 404**
  - Endpoint: `DELETE /api/v1/stages/999`
  - Request: 없음
  - Expected: `404`.

## 6. 마일스톤 (milestones)

- [ ] **TC-B-059 마감일 포함 생성**
  - Endpoint: `POST /api/v1/boards/1/milestones`
  - Request: `{"title": "MVP", "due_on": "2026-11-01"}`
  - Expected: `201`; `title: "MVP"`, `due_on: "2026-11-01"`, `board_id: 1`.

- [ ] **TC-B-060 마감일 없이 생성**
  - Endpoint: `POST /api/v1/boards/1/milestones`
  - Request: `{"title": "Backlog"}`
  - Expected: `201`; `due_on: null`.

- [ ] **TC-B-061 마일스톤 목록**
  - Endpoint: `GET /api/v1/boards/1/milestones`
  - Request: 준비 — B1에 2개, 보드 2에 1개
  - Expected: `200`; B1의 2개만 `id` 순.

- [ ] **TC-B-062 마일스톤 단건 조회**
  - Endpoint: `GET /api/v1/milestones/1`
  - Request: 준비 — `MVP`
  - Expected: `200`; `title: "MVP"`.

- [ ] **TC-B-063 마일스톤 수정**
  - Endpoint: `PATCH /api/v1/milestones/1`
  - Request: `{"title": "MVP v2", "due_on": "2026-12-01"}`
  - Expected: `200`; 두 필드가 바뀐다. 이 마일스톤을 쓰는 카드 응답의 `milestone`도 `"MVP v2"`.

- [ ] **TC-B-064 마감일 비우기**
  - Endpoint: `PATCH /api/v1/milestones/1`
  - Request: `{"due_on": null}`
  - Expected: `200`; `due_on: null`, `title` 유지.

- [ ] **TC-B-065 마일스톤 삭제 — 카드의 마일스톤은 null**
  - Endpoint: `DELETE /api/v1/milestones/1`
  - Request: 준비 — `MVP`를 쓰는 카드 1장
  - Expected: `204`. 이어서 `GET /cards/{id}` → `200`, `milestone_id: null`, `milestone: null`.

- [ ] **TC-B-066 제목 중복 → 409**
  - Endpoint: `POST /api/v1/boards/1/milestones`
  - Request: 준비 — `MVP` 존재; 다시 `{"title": "MVP"}`
  - Expected: `409`.

- [ ] **TC-B-067 제목 없음·날짜 형식 오류 → 422**
  - Endpoint: `POST /api/v1/boards/1/milestones`
  - Request: `{}` 및 `{"title": "X", "due_on": "11/01/2026"}`
  - Expected: 둘 다 `422`.

- [ ] **TC-B-068 없는 보드에 생성 → 404**
  - Endpoint: `POST /api/v1/boards/999/milestones`
  - Request: `{"title": "X"}`
  - Expected: `404`.

- [ ] **TC-B-069 없는 보드의 목록 → 404**
  - Endpoint: `GET /api/v1/boards/999/milestones`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-070 없는 마일스톤 조회 → 404**
  - Endpoint: `GET /api/v1/milestones/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-071 없는 마일스톤 수정 → 404**
  - Endpoint: `PATCH /api/v1/milestones/999`
  - Request: `{"title": "x"}`
  - Expected: `404`.

- [ ] **TC-B-072 수정 중 제목 중복 → 409**
  - Endpoint: `PATCH /api/v1/milestones/2`
  - Request: 준비 — `MVP`(1), `Beta`(2); 본문 `{"title": "MVP"}`
  - Expected: `409`.

- [ ] **TC-B-073 없는 마일스톤 삭제 → 404**
  - Endpoint: `DELETE /api/v1/milestones/999`
  - Request: 없음
  - Expected: `404`.

## 7. 카드 (cards) — 생성과 자동 채움

- [ ] **TC-B-074 제목만으로 생성 — 첫 단계, 자동 번호·순서**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "로그인 구현"}`
  - Expected: `201`; `stage: "Todo"`, `stage_id: 1`, `issue_number: 1`, `position: 1`, `assignee: null`, `milestone: null`, `body: null`, `closed_at: null`, `created_at`은 현재 시각 부근의 UTC 값, `board_id: 1`.

- [ ] **TC-B-075 이름으로 단계·담당자·마일스톤 지정**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: 준비 — B1, `codex`(name `Codex 에이전트`), `MVP`; 본문 `{"title": "API 구현", "body": "계획", "stage": "In Progress", "assignee": "codex", "milestone": "MVP"}`
  - Expected: `201`; `stage: "In Progress"`, `stage_id: 2`, `assignee: "codex"`, `assignee_name: "Codex 에이전트"`, `assignee_id`·`milestone_id`는 해당 id, `milestone: "MVP"`, `body: "계획"`.

- [ ] **TC-B-076 id로 단계·담당자·마일스톤 지정**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "화면", "stage_id": 2, "assignee_id": 1, "milestone_id": 1}`
  - Expected: `201`; 위 이름 지정 케이스와 같은 응답 필드(`stage`, `assignee`, `milestone` 이름이 채워짐).

- [ ] **TC-B-077 issue_number 자동 — max+1**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: 준비 — `issue_number: 41`인 카드 존재; 본문 `{"title": "다음 카드"}`
  - Expected: `201`; `issue_number: 42`.

- [ ] **TC-B-078 issue_number는 보드 전체가 아니라 테이블 전체 기준**
  - Endpoint: `POST /api/v1/boards/2/cards`
  - Request: 준비 — 보드 1에 카드 3장(번호 1~3), 보드 2(기본 단계); 본문 `{"title": "B2 카드"}`
  - Expected: `201`; `issue_number: 4`.

- [ ] **TC-B-079 issue_number 직접 지정**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "기존 이슈", "issue_number": 100}`
  - Expected: `201`; `issue_number: 100`. 이어서 자동 번호 카드는 `101`.

- [ ] **TC-B-080 issue_number 중복 → 409**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: 준비 — `issue_number: 5` 카드 존재; 본문 `{"title": "중복", "issue_number": 5}`
  - Expected: `409`. 카드 수는 늘지 않는다.

- [ ] **TC-B-081 position 자동 — 단계 안 max+1**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: 준비 — Todo에 카드 2장(position 1, 2), In Progress에 1장; 본문 `{"title": "세 번째", "stage": "Todo"}`
  - Expected: `201`; `position: 3`. In Progress에 만들면 `position: 2`(단계별 독립).

- [ ] **TC-B-082 카드 생성에는 position이 없다 — 보내도 무시**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: 준비 — Todo에 position 1, 2, 3 카드(A, B, C); 본문 `{"title": "끼워넣기", "stage": "Todo", "position": 2}`
  - Expected: `201`; `position: 4`(맨 끝, 요청의 `position`은 무시). 끼워 넣으려면 생성 뒤 `POST /cards/{id}/move`에 `position`을 쓴다(TC-B-125).

- [ ] **TC-B-083 마지막 단계에 생성하면 closed_at 채움**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "이미 끝남", "stage": "Done"}`
  - Expected: `201`; `closed_at`이 null이 아니다.

- [ ] **TC-B-084 마지막 단계 판정은 이름이 아니라 순서**
  - Endpoint: `POST /api/v1/boards/2/cards`
  - Request: 준비 — `with_default_stages=false` 보드 2에 단계 `Open`(1), `Shipped`(2); 본문 `{"title": "x", "stage": "Shipped"}`
  - Expected: `201`; `closed_at` 채움. `Open`에 만든 카드는 `closed_at: null`.

- [ ] **TC-B-085 클라이언트가 보낸 시각은 무시된다**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "created_at": "2020-01-01T00:00:00Z"}` 및 `{"title": "x", "closed_at": "2020-01-01T00:00:00Z"}`
  - Expected: 둘 다 `201`; `created_at`은 서버 시각(2020년이 아님), `closed_at: null`(Todo에 생성). 오류가 아니다.

- [ ] **TC-B-086 제목 없음·빈 제목 → 422**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{}` 및 `{"title": ""}`
  - Expected: 둘 다 `422`.

- [ ] **TC-B-087 stage + stage_id 동시 → 422**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "stage": "Todo", "stage_id": 1}`
  - Expected: `422`. (둘 다 non-null일 때만이다. `{"stage": "Todo", "stage_id": null}`은 `stage_id`를 안 준 것으로 보아 `201`.)

- [ ] **TC-B-088 assignee + assignee_id 동시 → 422**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "assignee": "codex", "assignee_id": 1}`
  - Expected: `422`.

- [ ] **TC-B-089 milestone + milestone_id 동시 → 422**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "milestone": "MVP", "milestone_id": 1}`
  - Expected: `422`.

- [ ] **TC-B-090 없는 단계 이름 → 404**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "stage": "Review"}`
  - Expected: `404`.

- [ ] **TC-B-091 없는 담당자 이름 → 404**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "assignee": "nobody"}`
  - Expected: `404`.

- [ ] **TC-B-092 없는 마일스톤 이름 → 404**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "milestone": "Nope"}`
  - Expected: `404`.

- [ ] **TC-B-093 없는 id 또는 다른 보드의 id → 404**
  - Endpoint: `POST /api/v1/boards/1/cards`
  - Request: `{"title": "x", "stage_id": 999}`; 보드 2의 단계/팀원/마일스톤 id를 `stage_id`/`assignee_id`/`milestone_id`로 지정
  - Expected: 모두 `404`.

- [ ] **TC-B-094 단계가 없는 보드에서 단계 생략 → 422**
  - Endpoint: `POST /api/v1/boards/2/cards`
  - Request: 준비 — 단계 없는 보드 2; 본문 `{"title": "x"}`
  - Expected: `422`.

- [ ] **TC-B-095 없는 보드에 생성 → 404**
  - Endpoint: `POST /api/v1/boards/999/cards`
  - Request: `{"title": "x"}`
  - Expected: `404`.

## 8. 카드 — 조회·필터·페이지네이션

공통 준비(F): B1에 팀원 `codex`, `minji`, 마일스톤 `MVP`, `Beta`, 카드 6장 —
`c1`(Todo, minji, MVP, "로그인 화면", body "디자인 시안"), `c2`(Todo, codex, MVP, "로그인 API"), `c3`(In Progress, codex, Beta, "회원가입 API"), `c4`(In Progress, 담당자 없음, 마일스톤 없음, "배포 스크립트"), `c5`(Done, minji, MVP, "DB 스키마"), `c6`(Done, codex, Beta, "README").

- [ ] **TC-B-096 카드 목록 — 기본 형식과 정렬**
  - Endpoint: `GET /api/v1/boards/1/cards`
  - Request: 준비 F
  - Expected: `200`; JSON 배열(감싸기 객체 없음). 6건이 단계 position → 카드 position → id 순서(c1, c2, c3, c4, c5, c6).

- [ ] **TC-B-097 단계 이름 필터**
  - Endpoint: `GET /api/v1/boards/1/cards?stage=In%20Progress`
  - Request: 준비 F
  - Expected: `200`; c3, c4만.

- [ ] **TC-B-098 담당자 필터**
  - Endpoint: `GET /api/v1/boards/1/cards?assignee=codex`
  - Request: 준비 F
  - Expected: `200`; c2, c3, c6만. 담당자 없는 카드는 포함되지 않는다.

- [ ] **TC-B-099 마일스톤 필터**
  - Endpoint: `GET /api/v1/boards/1/cards?milestone=MVP`
  - Request: 준비 F
  - Expected: `200`; c1, c2, c5만.

- [ ] **TC-B-100 텍스트 검색 — 제목·본문, 대소문자 무시**
  - Endpoint: `GET /api/v1/boards/1/cards?q=api` 및 `?q=%EC%8B%9C%EC%95%88`(시안)
  - Request: 준비 F
  - Expected: `200`; `q=api`는 c2, c3(제목의 `API`가 대소문자 무시로 일치). `q=시안`은 c1(본문 일치).

- [ ] **TC-B-101 필터 조합은 AND**
  - Endpoint: `GET /api/v1/boards/1/cards?stage=Todo&assignee=codex&milestone=MVP`
  - Request: 준비 F
  - Expected: `200`; c2만.

- [ ] **TC-B-102 일치하는 카드가 없으면 빈 목록**
  - Endpoint: `GET /api/v1/boards/1/cards?stage=Nope`
  - Request: 준비 F
  - Expected: `200`; `[]`. (필터에 없는 이름은 404가 아니라 빈 배열이다. `assignee=nobody`, `milestone=Nope`도 같다.)

- [ ] **TC-B-103 limit/offset 페이지네이션**
  - Endpoint: `GET /api/v1/boards/1/cards?limit=2&offset=2`
  - Request: 준비 F
  - Expected: `200`; 배열이 c3, c4. `offset=6`이면 `[]`.

- [ ] **TC-B-104 limit 최대 200 허용**
  - Endpoint: `GET /api/v1/boards/1/cards?limit=200`
  - Request: 준비 F
  - Expected: `200`; 6건 모두(c1~c6).

- [ ] **TC-B-105 limit 범위 밖·offset 음수 → 422**
  - Endpoint: `GET /api/v1/boards/1/cards?limit=0`, `?limit=201`, `?offset=-1`
  - Request: 없음
  - Expected: 모두 `422`.

- [ ] **TC-B-106 없는 보드의 카드 목록 → 404**
  - Endpoint: `GET /api/v1/boards/999/cards`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-107 카드 단건 조회**
  - Endpoint: `GET /api/v1/cards/1`
  - Request: 준비 F
  - Expected: `200`; CardOut의 모든 키(`id, board_id, stage_id, stage, assignee_id, assignee, assignee_name, milestone_id, milestone, issue_number, title, body, position, created_at, closed_at`)가 존재.

- [ ] **TC-B-108 없는 카드 조회 → 404**
  - Endpoint: `GET /api/v1/cards/999`
  - Request: 없음
  - Expected: `404`.

## 9. 카드 — 수정·삭제

- [ ] **TC-B-109 제목·본문 수정**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: `{"title": "새 제목", "body": "새 본문"}`
  - Expected: `200`; 두 필드가 바뀌고 `stage`, `position`, `issue_number`, `created_at`은 유지.

- [ ] **TC-B-110 본문 비우기**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: `{"body": null}`
  - Expected: `200`; `body: null`, `title` 유지.

- [ ] **TC-B-111 이름으로 담당자 변경**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: `{"assignee": "codex"}`
  - Expected: `200`; `assignee: "codex"`, `assignee_id` 일치.

- [ ] **TC-B-112 담당자 지우기**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: `{"assignee_id": null}`
  - Expected: `200`; `assignee_id/assignee/assignee_name`이 `null`.

- [ ] **TC-B-113 마일스톤 변경·지우기**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: `{"milestone": "Beta"}` 후 `{"milestone_id": null}`
  - Expected: 각각 `200`; 먼저 `milestone: "Beta"`, 다음에 `milestone_id/milestone`이 `null`.

- [ ] **TC-B-114 생략한 필드는 유지**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: 준비 — 담당자·마일스톤이 있는 카드; 본문 `{"title": "x"}`
  - Expected: `200`; 담당자·마일스톤이 그대로다(null로 바뀌지 않음).

- [ ] **TC-B-115 단계 변경 — 이동 규칙 적용**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: 준비 — Todo의 카드; 본문 `{"stage": "Done"}`, 이어서 `{"stage": "Todo"}`
  - Expected: 각각 `200`; 첫 응답 `stage: "Done"`, `closed_at` 채움, `position`은 Done의 맨 끝. 두 번째 응답 `closed_at: null`.

- [ ] **TC-B-116 이름+id 동시 · 없는 이름 · stage null · 수정 불가 필드**
  - Endpoint: `PATCH /api/v1/cards/1`
  - Request: `{"stage": "Todo", "stage_id": 1}`; `{"assignee": "nobody"}`; `{"milestone": "Nope"}`; `{"stage": null}`; `{"issue_number": 99, "position": 7}`
  - Expected: 순서대로 `422`, `404`, `404`, `422`(`stage cannot be null`), `200`. 앞의 네 요청은 카드를 바꾸지 않고, 마지막 요청은 `issue_number`·`position`을 바꾸지 않는다(무시).

- [ ] **TC-B-117 없는 카드 수정 → 404**
  - Endpoint: `PATCH /api/v1/cards/999`
  - Request: `{"title": "x"}`
  - Expected: `404`.

- [ ] **TC-B-118 카드 삭제 — 코멘트도 삭제**
  - Endpoint: `DELETE /api/v1/cards/1`
  - Request: 준비 — 코멘트 2개가 달린 카드
  - Expected: `204`. 이어서 `GET /cards/1` → `404`, `GET /comments/{id}` → `404`(2개 모두).

- [ ] **TC-B-119 없는 카드 삭제 → 404**
  - Endpoint: `DELETE /api/v1/cards/999`
  - Request: 없음
  - Expected: `404`.

## 10. 카드 이동 (move)

- [ ] **TC-B-120 단계 이름으로 이동 — 대상 단계 맨 끝**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: 준비 — Todo의 카드 1, In Progress에 position 1, 2 카드; 본문 `{"stage": "In Progress"}`
  - Expected: `200`; `stage: "In Progress"`, `stage_id: 2`, `position: 3`, `closed_at: null`.

- [ ] **TC-B-121 단계 id로 이동**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: `{"stage_id": 2}`
  - Expected: `200`; `stage: "In Progress"`.

- [ ] **TC-B-122 마지막 단계로 이동하면 closed_at 채움**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: `{"stage": "Done"}`
  - Expected: `200`; `closed_at`이 null이 아니다(UTC ISO).

- [ ] **TC-B-123 마지막 단계에서 다른 단계로 이동하면 closed_at 해제**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: 준비 — Done에 있는 카드(closed_at 있음); 본문 `{"stage": "In Progress"}`
  - Expected: `200`; `closed_at: null`.

- [ ] **TC-B-124 마지막 단계 안에서 순서만 바꾸면 closed_at 유지**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: 준비 — Done의 카드; 본문 `{"stage": "Done", "position": 1}`
  - Expected: `200`; `closed_at`이 이동 전 값과 같다.

- [ ] **TC-B-125 position 지정 — 그 자리 이상을 밀고 삽입**
  - Endpoint: `POST /api/v1/cards/4/move`
  - Request: 준비 — Todo에 position 1, 2, 3 카드(A, B, C), In Progress에 카드 D; 본문 `{"stage": "Todo", "position": 2}` (D를 이동)
  - Expected: `200`; D `position: 2`. 이어서 Todo 순서 A(1), D(2), B(3), C(4).

- [ ] **TC-B-126 같은 단계에서 순서 변경**
  - Endpoint: `POST /api/v1/cards/3/move`
  - Request: 준비 — Todo의 A(1), B(2), C(3); 본문 `{"stage": "Todo", "position": 1}` (C를 이동)
  - Expected: `200`; C `position: 1`. 순서 C, A, B(C 자신은 밀리지 않는다).

- [ ] **TC-B-127 stage·stage_id 모두 없음 → 422**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: `{}` 및 `{"position": 1}`
  - Expected: 둘 다 `422`.

- [ ] **TC-B-128 stage와 stage_id 동시 → 422**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: `{"stage": "Done", "stage_id": 3}`
  - Expected: `422`.

- [ ] **TC-B-129 없는 단계 이름 → 404**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: `{"stage": "Review"}`
  - Expected: `404`. 카드는 그대로.

- [ ] **TC-B-130 없는 단계 id·다른 보드의 단계 id → 404**
  - Endpoint: `POST /api/v1/cards/1/move`
  - Request: `{"stage_id": 999}`; 보드 2의 단계 id
  - Expected: 둘 다 `404`.

- [ ] **TC-B-131 없는 카드 이동 → 404**
  - Endpoint: `POST /api/v1/cards/999/move`
  - Request: `{"stage": "Done"}`
  - Expected: `404`.

## 11. 코멘트 (comments)

- [ ] **TC-B-132 작성자 github_login으로 생성**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{"body": "구현 완료", "author": "codex"}`
  - Expected: `201`; `card_id: 1`, `author: "codex"`, `author_name`, `author_id`, `body`, `created_at`(서버 시각).

- [ ] **TC-B-133 작성자 id로 생성**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{"body": "확인", "author_id": 1}`
  - Expected: `201`; `author: "codex"`.

- [ ] **TC-B-134 작성자 없이 생성**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{"body": "익명 메모"}`
  - Expected: `201`; `author_id/author/author_name`이 `null`.

- [ ] **TC-B-135 코멘트 목록 — created_at 순**
  - Endpoint: `GET /api/v1/cards/1/comments`
  - Request: 준비 — 코멘트 3개를 차례로 생성, 다른 카드에도 1개
  - Expected: `200`; 이 카드의 3개만 생성 순서(오래된 것부터). 코멘트가 없으면 `[]`.

- [ ] **TC-B-136 코멘트 단건 조회**
  - Endpoint: `GET /api/v1/comments/1`
  - Request: 준비 — 코멘트 1개
  - Expected: `200`; `id: 1`, `body` 일치.

- [ ] **TC-B-137 코멘트 삭제**
  - Endpoint: `DELETE /api/v1/comments/1`
  - Request: 준비 — 코멘트 1개
  - Expected: `204`. 이어서 `GET /comments/1` → `404`. 카드는 그대로 남는다.

- [ ] **TC-B-138 body 없음·빈 body → 422**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{}` 및 `{"body": ""}`
  - Expected: 둘 다 `422`.

- [ ] **TC-B-139 author와 author_id 동시 → 422**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{"body": "x", "author": "codex", "author_id": 1}`
  - Expected: `422`.

- [ ] **TC-B-140 없는 작성자 → 404**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{"body": "x", "author": "nobody"}`; 다른 보드 팀원의 login/id
  - Expected: 모두 `404`.

- [ ] **TC-B-141 클라이언트가 보낸 created_at은 무시된다**
  - Endpoint: `POST /api/v1/cards/1/comments`
  - Request: `{"body": "x", "created_at": "2020-01-01T00:00:00Z"}`
  - Expected: `201`; `created_at`은 서버 시각(2020년이 아님).

- [ ] **TC-B-142 없는 카드에 생성 → 404**
  - Endpoint: `POST /api/v1/cards/999/comments`
  - Request: `{"body": "x"}`
  - Expected: `404`.

- [ ] **TC-B-143 없는 카드의 목록 → 404**
  - Endpoint: `GET /api/v1/cards/999/comments`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-144 없는 코멘트 조회 → 404**
  - Endpoint: `GET /api/v1/comments/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-145 없는 코멘트 삭제 → 404**
  - Endpoint: `DELETE /api/v1/comments/999`
  - Request: 없음
  - Expected: `404`.

- [ ] **TC-B-146 코멘트 수정은 제공하지 않음**
  - Endpoint: `PATCH /api/v1/comments/1`
  - Request: `{"body": "x"}`
  - Expected: `405 Method Not Allowed`. (수동 확인)

## 12. 마이그레이션·설정

- [ ] **TC-B-147 빈 DB에서 upgrade head**
  - Endpoint: (명령) `alembic upgrade head` — 비어 있는 Postgres
  - Request: 없음
  - Expected: 종료 코드 0. 테이블 6개(`boards, members, stages, milestones, cards, comments`), 인덱스 5개, 뷰 `v_board`가 생기고 6개 테이블의 `relrowsecurity`가 true.

- [ ] **TC-B-148 두 번 실행해도 안전**
  - Endpoint: (명령) `alembic upgrade head`를 두 번 연속 실행하고, `alembic_version`을 지운 뒤 다시 실행
  - Request: 없음
  - Expected: 모두 종료 코드 0, 오류 없음. 테이블·인덱스 개수 변화 없음.

- [ ] **TC-B-149 이미 테이블과 데이터가 있는 DB(Supabase 상태)에서 안전 (수동)**
  - Endpoint: (명령) `alembic upgrade head`
  - Request: 준비 — `001_schema.sql`과 `002_seed.sql`을 먼저 적용한 DB(47행)
  - Expected: 종료 코드 0. 행 수가 그대로 47(boards 1, members 4, stages 3, milestones 2, cards 27, comments 10). 이어서 `GET /boards/1/view`가 `200`.

- [ ] **TC-B-150 downgrade는 뷰 → 자식 → 부모 순으로 제거**
  - Endpoint: (명령) `alembic downgrade base` — 테스트 전용 빈 DB에서 upgrade 후
  - Request: 없음
  - Expected: 종료 코드 0. 6개 테이블과 뷰가 모두 없다. (공존 중인 Supabase에서는 실행하지 않는다.)

- [ ] **TC-B-151 DATABASE_URL 정규화 (수동·단위)**
  - Endpoint: (단위) `normalize("postgresql://u:p@h/db")`
  - Request: `postgresql://...`, `postgres://...`, `postgresql+psycopg://...`
  - Expected: 앞의 둘은 `postgresql+psycopg://...`로 바뀌고, 이미 `+psycopg`인 값은 그대로.

- [ ] **TC-B-152 풀 설정 (수동·단위)**
  - Endpoint: (단위) 엔진 생성
  - Request: 기본값, 그리고 `DATABASE_POOL_SIZE=2 DATABASE_MAX_OVERFLOW=1 DATABASE_POOL_TIMEOUT=7`
  - Expected: 기본은 pool_size 5, max_overflow 10, timeout 30. 환경 변수를 주면 2 / 1 / 7.

- [ ] **TC-B-153 테스트는 DATABASE_URL을 건드리지 않는다**
  - Endpoint: (단위) pytest 세션 시작
  - Request: `TEST_DATABASE_URL` 미설정이고 `DATABASE_URL`만 설정
  - Expected: 테스트는 `DATABASE_URL`을 쓰지 않고 기본 `postgresql+psycopg://localhost/kanban_test`만 사용한다. 개발 DB는 TRUNCATE되지 않는다. ("시작 거부"는 구현하지 않았다 — 다음 단계. 수동 확인)

## 13. 문서 경로

- [ ] **TC-B-154 Swagger, ReDoc, openapi.json 제공 (수동)**
  - Endpoint: `GET /docs`, `GET /redoc`, `GET /openapi.json`
  - Request: 없음
  - Expected: 모두 `200`. `openapi.json`의 `paths`에 이 문서의 32개 동작(HTTP 메서드+경로, health 포함)이 모두 있다.

## 14. 자가 점검 — 모든 CRUD 커버 여부

### 14.1 엔드포인트별

| # | 엔드포인트 | 성공 케이스 | 실패 케이스 |
|---|---|---|---|
| 1 | GET /api/v1/health (및 /health) | TC-B-001 | TC-B-002 |
| 2 | GET /boards | TC-B-006 | (실패 없음: 빈 목록은 TC-B-006) |
| 3 | POST /boards | TC-B-003, TC-B-004, TC-B-005 | TC-B-012, TC-B-013, TC-B-014 |
| 4 | GET /boards/{id} | TC-B-007 | TC-B-016, TC-B-019 |
| 5 | PATCH /boards/{id} | TC-B-008, TC-B-009, TC-B-010 | TC-B-017, TC-B-015 |
| 6 | DELETE /boards/{id} | TC-B-011 | TC-B-018 |
| 7 | GET /boards/{id}/view | TC-B-020, TC-B-021, TC-B-022 | TC-B-023 |
| 8 | GET /boards/{id}/members | TC-B-026 | TC-B-035 |
| 9 | POST /boards/{id}/members | TC-B-024, TC-B-025 | TC-B-031, TC-B-032, TC-B-033, TC-B-034 |
| 10 | GET /members/{id} | TC-B-027 | TC-B-036 |
| 11 | PATCH /members/{id} | TC-B-028, TC-B-029 | TC-B-037, TC-B-038 |
| 12 | DELETE /members/{id} | TC-B-030 | TC-B-039 |
| 13 | GET /boards/{id}/stages | TC-B-043 | TC-B-054 |
| 14 | POST /boards/{id}/stages | TC-B-040, TC-B-041, TC-B-042, TC-B-050 | TC-B-049, TC-B-051, TC-B-052, TC-B-053 |
| 15 | GET /stages/{id} | TC-B-044 | TC-B-055 |
| 16 | PATCH /stages/{id} | TC-B-045, TC-B-046 | TC-B-056, TC-B-057 |
| 17 | DELETE /stages/{id} | TC-B-047 | TC-B-048, TC-B-058 |
| 18 | GET /boards/{id}/milestones | TC-B-061 | TC-B-069 |
| 19 | POST /boards/{id}/milestones | TC-B-059, TC-B-060 | TC-B-066, TC-B-067, TC-B-068 |
| 20 | GET /milestones/{id} | TC-B-062 | TC-B-070 |
| 21 | PATCH /milestones/{id} | TC-B-063, TC-B-064 | TC-B-071, TC-B-072 |
| 22 | DELETE /milestones/{id} | TC-B-065 | TC-B-073 |
| 23 | GET /boards/{id}/cards | TC-B-096, TC-B-097, TC-B-098, TC-B-099, TC-B-100, TC-B-101, TC-B-102, TC-B-103, TC-B-104 | TC-B-105, TC-B-106 |
| 24 | POST /boards/{id}/cards | TC-B-074, TC-B-075, TC-B-076, TC-B-077, TC-B-078, TC-B-079, TC-B-081, TC-B-082, TC-B-083, TC-B-084, TC-B-085 | TC-B-080, TC-B-086, TC-B-087, TC-B-088, TC-B-089, TC-B-090, TC-B-091, TC-B-092, TC-B-093, TC-B-094, TC-B-095 |
| 25 | GET /cards/{id} | TC-B-107 | TC-B-108 |
| 26 | PATCH /cards/{id} | TC-B-109, TC-B-110, TC-B-111, TC-B-112, TC-B-113, TC-B-114, TC-B-115 | TC-B-116, TC-B-117 |
| 27 | DELETE /cards/{id} | TC-B-118 | TC-B-119 |
| 28 | POST /cards/{id}/move | TC-B-120, TC-B-121, TC-B-122, TC-B-123, TC-B-124, TC-B-125, TC-B-126 | TC-B-127, TC-B-128, TC-B-129, TC-B-130, TC-B-131 |
| 29 | GET /cards/{id}/comments | TC-B-135 | TC-B-143 |
| 30 | POST /cards/{id}/comments | TC-B-132, TC-B-133, TC-B-134 | TC-B-138, TC-B-139, TC-B-140, TC-B-141, TC-B-142 |
| 31 | GET /comments/{id} | TC-B-136 | TC-B-144 |
| 32 | DELETE /comments/{id} | TC-B-137 | TC-B-145 |

### 14.2 자동 채움·규칙별

| 규칙 | 케이스 |
|---|---|
| issue_number 자동 / 중복 409 | TC-B-077, TC-B-078, TC-B-079, TC-B-080 |
| position 자동 / 삽입 밀기(이동에서만) | TC-B-081, TC-B-082, TC-B-120, TC-B-125, TC-B-126, TC-B-040 |
| created_at 서버 채움 / 클라이언트 값 무시 | TC-B-074, TC-B-085, TC-B-132, TC-B-141 |
| closed_at 설정 / 해제 / 유지 | TC-B-083, TC-B-084, TC-B-122, TC-B-123, TC-B-124, TC-B-115 |
| 기본 단계 3개 | TC-B-003, TC-B-005 |
| 보드 삭제 cascade | TC-B-011 |
| 카드 있는 단계 삭제 409 | TC-B-048 |
| 이름+id 동시 422 | TC-B-087, TC-B-088, TC-B-089, TC-B-128, TC-B-139, TC-B-116 |
| 없는 이름 404 | TC-B-090, TC-B-091, TC-B-092, TC-B-129, TC-B-140 |
| 팀원·마일스톤 삭제 시 set null | TC-B-030, TC-B-065 |
| 필터·페이지네이션 | TC-B-097, TC-B-098, TC-B-099, TC-B-100, TC-B-101, TC-B-103, TC-B-105 |
| view 정렬 | TC-B-020, TC-B-021, TC-B-022 |
| health | TC-B-001, TC-B-002 |
| 마이그레이션 멱등 | TC-B-147, TC-B-148, TC-B-149, TC-B-150 |
| 문서 경로 | TC-B-154 |
| 설정 | TC-B-151, TC-B-152, TC-B-153 |

### 14.3 리소스 × 동작 매트릭스

| 리소스 | Create | List | Get | Update | Delete |
|---|---|---|---|---|---|
| board | O | O | O | O | O |
| member | O | O | O | O | O |
| stage | O | O | O | O | O |
| milestone | O | O | O | O | O |
| card | O | O | O | O | O (+ move) |
| comment | O | O | O | 제공 안 함(TC-B-146) | O |

모든 행이 비어 있는 칸 없이 위 14.1의 케이스로 연결된다.
