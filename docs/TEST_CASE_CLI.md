# 간반 보드 CLI 테스트 케이스 (TEST_CASE_CLI)

> 문서 목적: `kanban` CLI의 모든 명령을 성공/실패 케이스로 정의하고, 서버 기동부터 삭제까지의 E2E 시나리오를 체크리스트로 추적한다.

## 공통 기준

- 실행 형태는 `kanban ...`이다(`uvx --from . kanban ...`, `uv run kanban ...`과 같다). API 주소는 기본값 `http://127.0.0.1:8000`이며 단위 테스트는 앱에 직접 연결한다(`TSD_CLI.md` 9절).
- 준비 `P` = 서버가 떠 있고 보드 1(`Team A`, 기본 단계 Todo/In Progress/Done)이 있으며 팀원 `codex`(name `Codex 에이전트`)와 `minji`, 마일스톤 `MVP`가 있는 상태. 케이스에 "준비"가 따로 적혀 있으면 그것을 추가로 만든다.
- 텍스트 출력은 **핵심 문구**의 포함 여부로 확인한다(공백·표 선은 비교하지 않음). `--json` 출력은 표준 출력이 JSON 한 덩어리로 파싱되고 지정한 키가 있는지 확인한다.
- 오류 문구는 표준 오류(stderr)로 나가며 `Error: <detail> (<status>)` 꼴이다(422는 첫 메시지만: `Error: github_login: String should have at least 1 character (422)`). traceback은 나오지 않는다. 사용법 오류(종료 코드 2)는 Typer/rich의 `Usage: ...` + 오류 상자 형식이다.
- 종료 코드: 0 성공 / 1 API·연결 오류 / 2 사용법 오류.
- 케이스 ID 접두사 `TC-C`는 CLI다.
- 체크 박스는 수동 추적용이다. 자동 테스트(`tests/test_cli.py` 31개, `tests/test_cli_e2e.py` 2개)가 대부분을 확인하지만 케이스별 1:1 매핑은 하지 않았다. 자동 테스트가 없는 케이스(`serve`·`db upgrade` 실패 경로 등)는 수동으로 확인한다.

## 1. 도움말·전역 옵션

- [ ] **TC-C-001 루트 도움말**
  - Command: `kanban --help`
  - Expected: 종료 코드 0; `Manage your team's kanban board`가 포함되고 명령 목록에 `health`, `serve`, `db`, `board`, `member`, `stage`, `milestone`, `card`, `comment`, `view`가 있으며 전역 옵션 `--api-url`, `--board`, `--json`이 보인다.

- [ ] **TC-C-002 모든 명령의 --help**
  - Command: 모든 명령 경로(`board list`, `card move`, `db upgrade` 등 모든 하위 명령)에 대해 `kanban <명령> --help`
  - Expected: 모두 종료 코드 0이고 설명이 비어 있지 않으며 `HTTP`, `endpoint`, `payload`, `enum`, `pagination` 단어가 없다.

- [ ] **TC-C-003 인자 없이 실행**
  - Command: `kanban`
  - Expected: 도움말(사용법)이 표시된다. 종료 코드는 설치된 Click 버전에 따라 0 또는 2이므로 테스트는 사용법 출력 여부만 확인한다.

- [ ] **TC-C-004 알 수 없는 명령 → 사용법 오류**
  - Command: `kanban boards`
  - Expected: 종료 코드 2; stderr에 사용법 안내(`--help`).

- [ ] **TC-C-005 --api-url 옵션**
  - Command: `kanban --api-url http://127.0.0.1:8000/ health` (끝의 `/` 포함)
  - Expected: 종료 코드 0; `Database: ok`.

- [ ] **TC-C-006 환경 변수 KANBAN_API_URL**
  - Command: `KANBAN_API_URL=http://127.0.0.1:8000 kanban health`
  - Expected: 종료 코드 0.

- [ ] **TC-C-007 우선순위: 옵션 > 환경 변수 > 기본값**
  - Command: `KANBAN_API_URL=http://127.0.0.1:1 kanban --api-url http://127.0.0.1:8000 health`
  - Expected: 종료 코드 0(옵션이 환경 변수를 이김). 환경 변수만 있고 옵션이 없으면 종료 코드 1(`Cannot reach`).

- [ ] **TC-C-008 --board와 KANBAN_BOARD**
  - Command: 준비 — 보드 2에 카드 `X`; `kanban --board 2 card list` 및 `KANBAN_BOARD=2 kanban card list`
  - Expected: 둘 다 종료 코드 0이고 카드 `X`만 보인다. 옵션이 있으면 환경 변수보다 우선한다. 둘 다 없으면 보드 1.

- [ ] **TC-C-009 잘못된 --board → 사용법 오류**
  - Command: `kanban --board abc card list`, `kanban --board 0 card list`
  - Expected: 둘 다 종료 코드 2. 요청은 보내지 않는다.

- [ ] **TC-C-010 --json은 stdout에 JSON만 출력**
  - Command: `kanban --json board list`
  - Expected: 종료 코드 0; stdout 전체가 JSON 배열로 파싱된다. 안내 문장이 stdout에 섞이지 않는다.

- [ ] **TC-C-011 서버가 꺼져 있을 때**
  - Command: `kanban --api-url http://127.0.0.1:1 board list`
  - Expected: 종료 코드 1; stderr 한 줄에 `Error: Cannot reach the kanban server`와 `kanban serve`. traceback 없음.

## 2. 시스템 명령

- [ ] **TC-C-012 health 성공**
  - Command: `kanban health` 및 `kanban --json health`
  - Expected: 종료 코드 0; 텍스트 `Server is running` + `Database: ok`; JSON 키 `status`("ok"), `database`("ok").

- [ ] **TC-C-013 health — 서버 없음 / DB 장애**
  - Command: `kanban --api-url http://127.0.0.1:1 health`; DB 장애를 흉내 낸 서버에는 `kanban health`
  - Expected: 각각 종료 코드 1, stderr `Cannot reach the kanban server`; `Error: database unavailable (503)`.

- [ ] **TC-C-014 serve로 서버 기동**
  - Command: `kanban serve --port <빈 포트>` (서브프로세스)
  - Expected: stdout/stderr에 `Starting kanban server at http://127.0.0.1:<포트>`; 몇 초 안에 `kanban --api-url ... health`가 종료 코드 0. 프로세스에 종료 신호를 보내면 종료 코드 0.

- [ ] **TC-C-015 serve — 이미 사용 중인 포트**
  - Command: 같은 포트로 `kanban serve`를 두 번째 실행
  - Expected: 종료 코드 1; 오류 메시지가 나온다.

- [ ] **TC-C-016 serve — 잘못된 포트 값**
  - Command: `kanban serve --port abc`
  - Expected: 종료 코드 2.

- [ ] **TC-C-017 db upgrade 성공·반복 실행**
  - Command: `kanban db upgrade` (두 번 연속)
  - Expected: 둘 다 종료 코드 0; `Database is up to date.`.

- [ ] **TC-C-018 db upgrade — DB 연결 실패**
  - Command: 잘못된 `DATABASE_URL`로 `kanban db upgrade`
  - Expected: 종료 코드 1; `Error: Cannot connect to the database`.

## 3. board

- [ ] **TC-C-019 board list**
  - Command: `kanban board list` / `kanban --json board list`
  - Expected: 종료 코드 0; 텍스트에 보드 id·이름; JSON은 배열이고 각 항목에 `id`, `name`, `repo_url`.

- [ ] **TC-C-020 board add (기본 단계 포함)**
  - Command: `kanban board add "Team B" --repo-url https://github.com/acme/team-b`
  - Expected: 종료 코드 0; `Created board 2: Team B`. 이어서 `kanban --board 2 stage list`에 `Todo`, `In Progress`, `Done`. JSON은 `id`, `name`, `repo_url`.

- [ ] **TC-C-021 board add --no-default-stages**
  - Command: `kanban board add "Empty" --no-default-stages`
  - Expected: 종료 코드 0; 이어서 그 보드의 `stage list`가 비어 있다.

- [ ] **TC-C-022 board show**
  - Command: `kanban board show 1`, `kanban board show`(생략 시 `--board`)
  - Expected: 종료 코드 0; `Board 1: Team A`. JSON 키 `id`, `name`, `repo_url`.

- [ ] **TC-C-023 board update**
  - Command: `kanban board update 1 --name "Team A (2026)"`, `kanban board update 1 --clear-repo-url`
  - Expected: 종료 코드 0; `Updated board 1.`; 이어서 `show`에서 이름이 바뀌고 repo가 `-`.

- [ ] **TC-C-024 board delete**
  - Command: `kanban board delete 2` 후 `kanban board show 2`
  - Expected: 삭제는 종료 코드 0, `Deleted board 2`. `--json`이면 stdout이 비어 있다. 이어서 `show 2`는 종료 코드 1.

- [ ] **TC-C-025 board add — 이름 누락**
  - Command: `kanban board add`
  - Expected: 종료 코드 2.

- [ ] **TC-C-026 board add — repo_url 중복**
  - Command: 준비 — 보드 1의 repo_url 사용 중; 같은 URL로 `kanban board add "Dup" --repo-url <url>`
  - Expected: 종료 코드 1; `Error: ... (409)`.

- [ ] **TC-C-027 board show — 없는 보드**
  - Command: `kanban board show 999`
  - Expected: 종료 코드 1; `Error: board 999 not found (404)`.

- [ ] **TC-C-028 board update — 변경 옵션 없음 / 상충 옵션**
  - Command: `kanban board update 1`; `kanban board update 1 --repo-url x --clear-repo-url`
  - Expected: 둘 다 종료 코드 2(요청을 보내지 않음).

- [ ] **TC-C-029 board update — 없는 보드**
  - Command: `kanban board update 999 --name x`
  - Expected: 종료 코드 1; `(404)`.

- [ ] **TC-C-030 board delete — 없는 보드**
  - Command: `kanban board delete 999`
  - Expected: 종료 코드 1; `(404)`.

## 4. member

- [ ] **TC-C-031 member add**
  - Command: `kanban member add codex --name "Codex 에이전트" --role "AI 에이전트"`
  - Expected: 종료 코드 0; `Added member codex`. JSON 키 `id`, `board_id`, `github_login`, `name`, `role`.

- [ ] **TC-C-032 member list**
  - Command: 준비 P; `kanban member list` / `kanban --json member list`
  - Expected: 종료 코드 0; `codex`, `minji` 포함. JSON은 배열.

- [ ] **TC-C-033 member show**
  - Command: `kanban member show 1`
  - Expected: 종료 코드 0; 로그인·이름·역할이 표시된다. JSON 키 `github_login`.

- [ ] **TC-C-034 member update**
  - Command: `kanban member update 1 --name "Codex"`, `kanban member update 1 --clear-role`
  - Expected: 종료 코드 0; `Updated member 1.`. 이어서 `show`에서 이름 변경, 역할 `-`.

- [ ] **TC-C-035 member delete**
  - Command: 준비 — `codex`가 담당자인 카드 1장; `kanban member delete 1` 후 `kanban card show <id>`
  - Expected: 삭제 종료 코드 0, `Deleted member 1.`. 카드는 남고 담당자가 `-`.

- [ ] **TC-C-036 member add — --name 누락**
  - Command: `kanban member add x`
  - Expected: 종료 코드 2.

- [ ] **TC-C-037 member add — 이미 있는 login**
  - Command: `kanban member add codex --name x`
  - Expected: 종료 코드 1; `(409)`.

- [ ] **TC-C-038 member show/update/delete — 없는 팀원**
  - Command: `kanban member show 999`, `kanban member update 999 --name x`, `kanban member delete 999`
  - Expected: 모두 종료 코드 1; `(404)`.

- [ ] **TC-C-039 member update — 변경 옵션 없음 / 상충**
  - Command: `kanban member update 1`; `kanban member update 1 --role x --clear-role`
  - Expected: 둘 다 종료 코드 2.

- [ ] **TC-C-040 member list/add — 없는 보드**
  - Command: `kanban --board 999 member list`, `kanban --board 999 member add z --name z`
  - Expected: 둘 다 종료 코드 1; `(404)`.

## 5. stage

- [ ] **TC-C-041 stage list**
  - Command: `kanban stage list` / `--json`
  - Expected: 종료 코드 0; `Todo`, `In Progress`, `Done`가 position 순서로 보인다. JSON은 `position` 오름차순 배열.

- [ ] **TC-C-042 stage add (자동 position)**
  - Command: `kanban stage add "Review"`
  - Expected: 종료 코드 0; `Added stage "Review" (id 4, position 4).`

- [ ] **TC-C-043 stage add --position**
  - Command: `kanban stage add "QA" --position 10`
  - Expected: 종료 코드 0; JSON `position: 10`.

- [ ] **TC-C-044 stage show**
  - Command: `kanban stage show 1`
  - Expected: 종료 코드 0; `Stage 1: Todo (position 1)`.

- [ ] **TC-C-045 stage update**
  - Command: `kanban stage update 4 --name "Code Review" --position 5`
  - Expected: 종료 코드 0; `Updated stage 4.`

- [ ] **TC-C-046 stage delete (빈 단계)**
  - Command: `kanban stage delete 4`
  - Expected: 종료 코드 0; `Deleted stage 4.`

- [ ] **TC-C-047 stage add — 이름 또는 position 중복**
  - Command: `kanban stage add "Todo"`, `kanban stage add X --position 1`
  - Expected: 둘 다 종료 코드 1; `(409)`.

- [ ] **TC-C-048 stage delete — 카드가 있는 단계**
  - Command: 준비 — Todo에 카드; `kanban stage delete 1`
  - Expected: 종료 코드 1; `Error: stage 1 still has 1 card(s); move or delete them first (409)`.

- [ ] **TC-C-049 stage add — 이름 누락 / 잘못된 position**
  - Command: `kanban stage add`; `kanban stage add X --position abc`
  - Expected: 둘 다 종료 코드 2.

- [ ] **TC-C-050 stage update — 변경 옵션 없음**
  - Command: `kanban stage update 1`
  - Expected: 종료 코드 2.

- [ ] **TC-C-051 stage show/update/delete — 없는 단계**
  - Command: `kanban stage show 999`, `kanban stage update 999 --name x`, `kanban stage delete 999`
  - Expected: 모두 종료 코드 1; `(404)`.

- [ ] **TC-C-052 stage list/add — 없는 보드**
  - Command: `kanban --board 999 stage list`, `kanban --board 999 stage add X`
  - Expected: 둘 다 종료 코드 1; `(404)`.

## 6. milestone

- [ ] **TC-C-053 milestone add**
  - Command: `kanban milestone add MVP --due-on 2026-11-01`
  - Expected: 종료 코드 0; `Added milestone "MVP" (id 1).` JSON `due_on: "2026-11-01"`. `--due-on` 없이 추가하면 `due_on: null`.

- [ ] **TC-C-054 milestone list**
  - Command: `kanban milestone list` / `--json`
  - Expected: 종료 코드 0; 제목과 마감일(`-` 포함). JSON은 배열.

- [ ] **TC-C-055 milestone show**
  - Command: `kanban milestone show 1`
  - Expected: 종료 코드 0; `Milestone 1: MVP`, `Due: 2026-11-01`.

- [ ] **TC-C-056 milestone update**
  - Command: `kanban milestone update 1 --title "MVP v2" --due-on 2026-12-01`; `kanban milestone update 1 --clear-due-on`
  - Expected: 종료 코드 0; `Updated milestone 1.`; 이어서 `show`에서 `Due: -`.

- [ ] **TC-C-057 milestone delete**
  - Command: 준비 — `MVP`를 쓰는 카드; `kanban milestone delete 1`
  - Expected: 종료 코드 0; `Deleted milestone 1.`; 카드의 마일스톤은 `-`.

- [ ] **TC-C-058 milestone add — 제목 중복**
  - Command: `kanban milestone add MVP`
  - Expected: 종료 코드 1; `(409)`.

- [ ] **TC-C-059 milestone add — 제목 누락 / 날짜 형식 오류**
  - Command: `kanban milestone add`; `kanban milestone add X --due-on 11/01/2026`
  - Expected: 둘 다 종료 코드 2. 둘째는 CLI가 요청을 보내기 전에 막는다(`Invalid value: Use a day written as YYYY-MM-DD.`).

- [ ] **TC-C-060 milestone update — 변경 옵션 없음 / 상충**
  - Command: `kanban milestone update 1`; `kanban milestone update 1 --due-on 2026-12-01 --clear-due-on`
  - Expected: 둘 다 종료 코드 2.

- [ ] **TC-C-061 milestone show/update/delete — 없는 항목**
  - Command: `kanban milestone show 999`, `kanban milestone update 999 --title x`, `kanban milestone delete 999`
  - Expected: 모두 종료 코드 1; `(404)`.

- [ ] **TC-C-062 milestone list/add — 없는 보드**
  - Command: `kanban --board 999 milestone list`, `kanban --board 999 milestone add X`
  - Expected: 둘 다 종료 코드 1; `(404)`.

## 7. card

- [ ] **TC-C-063 card add — 제목만**
  - Command: `kanban card add "로그인 구현"`
  - Expected: 종료 코드 0; `Created card 1 (issue #1) in Todo`. JSON 키 `id`, `stage`("Todo"), `issue_number`(1), `position`(1), `closed_at`(null), `created_at`.

- [ ] **TC-C-064 card add — 이름으로 지정**
  - Command: `kanban card add "API 구현" --stage "In Progress" --assignee codex --milestone MVP --body "계획 요약"`
  - Expected: 종료 코드 0; `in In Progress`. JSON `stage: "In Progress"`, `assignee: "codex"`, `assignee_name: "Codex 에이전트"`, `milestone: "MVP"`, `body: "계획 요약"`.

- [ ] **TC-C-065 card add — id로 지정**
  - Command: `kanban card add "화면" --stage-id 2 --assignee-id 1 --milestone-id 1`
  - Expected: 종료 코드 0; JSON `stage: "In Progress"`, `assignee: "codex"`, `milestone: "MVP"`.

- [ ] **TC-C-066 card add — issue 번호 지정, --position은 없음**
  - Command: `kanban card add "기존 이슈" --issue-number 100 --stage Todo`; `kanban card add x --position 1`
  - Expected: 첫째는 종료 코드 0, JSON `issue_number: 100`(position은 단계 맨 끝). 둘째는 종료 코드 2(`No such option: --position`). `card add`·`card update`에는 `--position`이 없고 `card move --position`만 있다.

- [ ] **TC-C-067 card add — 마지막 단계에 만들면 닫힘**
  - Command: `kanban card add "끝난 일" --stage Done`
  - Expected: 종료 코드 0; JSON `closed_at`이 null이 아니다.

- [ ] **TC-C-068 card list — 기본**
  - Command: 준비 — 카드 3장(Todo 2, In Progress 1); `kanban card list` / `--json`
  - Expected: 종료 코드 0; 텍스트 표에 3장과 `Showing 3 cards.`; JSON은 길이 3의 배열(감싸기 객체 없음).

- [ ] **TC-C-069 card list — 필터**
  - Command: `kanban card list --stage "In Progress"`; `--assignee codex`; `--milestone MVP`; `-q login`(`--query login`, `--search login`도 같다); `--stage Todo --assignee codex`
  - Expected: 각각 종료 코드 0이고 조건에 맞는 카드만. 마지막(조합)은 AND. 일치하는 카드가 없거나 없는 이름(`--stage Nope`)이면 종료 코드 0과 `No cards found.`(JSON은 `[]`). 없는 이름은 404가 아니다.

- [ ] **TC-C-070 card list — limit/offset**
  - Command: `kanban --json card list --limit 2 --offset 1`
  - Expected: 종료 코드 0; JSON 배열 길이 ≤ 2이고 첫 항목은 전체 목록의 둘째 카드.

- [ ] **TC-C-071 card list — 범위 밖 limit**
  - Command: `kanban card list --limit 0`, `kanban card list --limit 201`, `kanban card list --offset -1`
  - Expected: 값 범위(`--limit` 1-200, `--offset` 0 이상)는 CLI가 검사하므로 세 명령 모두 종료 코드 2(`Invalid value for '--limit': 0 is not in the range 1<=x<=200.`). 요청은 보내지 않는다.

- [ ] **TC-C-072 card show**
  - Command: `kanban card show 1` / `--json`
  - Expected: 종료 코드 0; `Card 1 (issue #1)`, `Stage:`, `Assignee:`, `Milestone:`, `Created:`, `Closed:`가 보인다. JSON은 CardOut의 모든 키.

- [ ] **TC-C-073 card update**
  - Command: `kanban card update 1 --title "새 제목" --assignee minji`
  - Expected: 종료 코드 0; `Updated card 1.`; JSON `title`, `assignee: "minji"`. 생략한 필드(`stage`, `milestone`)는 유지.

- [ ] **TC-C-074 card update — clear 옵션**
  - Command: `kanban card update 1 --clear-assignee --clear-milestone --clear-body`
  - Expected: 종료 코드 0; JSON `assignee: null`, `milestone: null`, `body: null`.

- [ ] **TC-C-075 card update — 단계 변경은 이동 규칙을 따름**
  - Command: `kanban card update 1 --stage Done`
  - Expected: 종료 코드 0; JSON `stage: "Done"`, `closed_at` 채움.

- [ ] **TC-C-076 card move — 이름**
  - Command: `kanban card move 1 "In Progress"`
  - Expected: 종료 코드 0; `Moved card 1 to In Progress.`; JSON `stage: "In Progress"`, `closed_at: null`.

- [ ] **TC-C-077 card move — 마지막 단계로 이동하면 닫힘, 나오면 열림**
  - Command: `kanban card move 1 Done` 후 `kanban card move 1 Todo`
  - Expected: 둘 다 종료 코드 0; 첫 번째 JSON `closed_at`이 null이 아니고 두 번째는 `null`.

- [ ] **TC-C-078 card move — --stage-id와 --position**
  - Command: `kanban card move 1 --stage-id 1 --position 1`
  - Expected: 종료 코드 0; JSON `stage_id: 1`, `position: 1`.

- [ ] **TC-C-079 card delete**
  - Command: 준비 — 코멘트가 달린 카드; `kanban card delete 1`, 이어서 `kanban card show 1`
  - Expected: 삭제 종료 코드 0, `Deleted card 1.`(`--json`은 stdout 비어 있음). `show`는 종료 코드 1 `(404)`.

- [ ] **TC-C-080 card add — 제목 누락**
  - Command: `kanban card add`
  - Expected: 종료 코드 2.

- [ ] **TC-C-081 이름과 id를 함께 지정 → 사용법 오류**
  - Command: `kanban card add x --stage Todo --stage-id 1`; `kanban card add x --assignee codex --assignee-id 1`; `kanban card add x --milestone MVP --milestone-id 1`
  - Expected: 모두 종료 코드 2; 요청은 보내지 않는다.

- [ ] **TC-C-082 없는 단계·담당자·마일스톤 이름**
  - Command: `kanban card add x --stage Review`; `kanban card add x --assignee nobody`; `kanban card add x --milestone Nope`
  - Expected: 모두 종료 코드 1; `(404)`.

- [ ] **TC-C-083 card add — issue 번호 중복**
  - Command: 준비 — issue 번호 5가 있음; `kanban card add x --issue-number 5`
  - Expected: 종료 코드 1; `(409)`.

- [ ] **TC-C-084 card update — 변경 옵션 없음 / 상충**
  - Command: `kanban card update 1`; `kanban card update 1 --assignee codex --clear-assignee`; `kanban card update 1 --body x --clear-body`; `kanban card update 1 --stage Todo --stage-id 1`
  - Expected: 모두 종료 코드 2.

- [ ] **TC-C-085 card move — 단계 지정 없음 / 둘 다 지정**
  - Command: `kanban card move 1`; `kanban card move 1 Done --stage-id 3`
  - Expected: 둘 다 종료 코드 2.

- [ ] **TC-C-086 card move — 없는 단계**
  - Command: `kanban card move 1 Review`; `kanban card move 1 --stage-id 999`
  - Expected: 둘 다 종료 코드 1; `(404)`.

- [ ] **TC-C-087 card show/update/move/delete — 없는 카드**
  - Command: `kanban card show 999`, `kanban card update 999 --title x`, `kanban card move 999 Done`, `kanban card delete 999`
  - Expected: 모두 종료 코드 1; `Error: card 999 not found (404)`.

- [ ] **TC-C-088 card list/add — 없는 보드**
  - Command: `kanban --board 999 card list`, `kanban --board 999 card add x`
  - Expected: 둘 다 종료 코드 1; `(404)`.

- [ ] **TC-C-089 숫자가 아닌 id**
  - Command: `kanban card show abc`
  - Expected: 종료 코드 2.

## 8. comment

- [ ] **TC-C-090 comment add — author**
  - Command: `kanban comment add 1 "구현 완료, 테스트 통과" --author codex`
  - Expected: 종료 코드 0; `Added comment 1 to card 1.`. JSON 키 `id`, `card_id`, `author`("codex"), `author_name`, `body`, `created_at`.

- [ ] **TC-C-091 comment add — author-id / 작성자 없음**
  - Command: `kanban comment add 1 "확인" --author-id 1`; `kanban comment add 1 "메모"`
  - Expected: 둘 다 종료 코드 0; 첫째 `author: "codex"`, 둘째 `author: null`.

- [ ] **TC-C-092 comment list**
  - Command: 준비 — 코멘트 2개; `kanban comment list 1` / `--json`
  - Expected: 종료 코드 0; 오래된 것부터 작성자와 본문이 보인다. JSON은 배열. 없으면 `No comments yet.`(JSON `[]`).

- [ ] **TC-C-093 comment show**
  - Command: `kanban comment show 1`
  - Expected: 종료 코드 0; `Comment 1 on card 1 by codex` + 본문.

- [ ] **TC-C-094 comment delete**
  - Command: `kanban comment delete 1`, 이어서 `kanban comment show 1`
  - Expected: 삭제 종료 코드 0, `Deleted comment 1.`; `show`는 종료 코드 1 `(404)`.

- [ ] **TC-C-095 comment add — 인자 누락**
  - Command: `kanban comment add 1`; `kanban comment add`
  - Expected: 둘 다 종료 코드 2.

- [ ] **TC-C-096 comment add — author와 author-id 동시**
  - Command: `kanban comment add 1 x --author codex --author-id 1`
  - Expected: 종료 코드 2.

- [ ] **TC-C-097 comment add — 없는 작성자**
  - Command: `kanban comment add 1 x --author nobody`
  - Expected: 종료 코드 1; `(404)`.

- [ ] **TC-C-098 comment add — 빈 본문**
  - Command: `kanban comment add 1 ""`
  - Expected: 서버가 거절하므로 종료 코드 1, `(422)`. 코멘트는 생기지 않는다.

- [ ] **TC-C-099 comment — 없는 카드·코멘트**
  - Command: `kanban comment list 999`, `kanban comment add 999 x`, `kanban comment show 999`, `kanban comment delete 999`
  - Expected: 모두 종료 코드 1; `(404)`.

- [ ] **TC-C-100 comment update 명령은 없음**
  - Command: `kanban comment update 1 x`
  - Expected: 종료 코드 2.

## 9. view

- [ ] **TC-C-101 view — 단계별 열**
  - Command: 준비 — Todo 2장, In Progress 1장, Done 0장; `kanban view`
  - Expected: 종료 코드 0; `Board 1: Team A`, 열 제목 `Todo (2)`, `In Progress (1)`, `Done (0)`; 카드는 `#<issue> <title>` 형태로 단계·position 순; 카드 없는 열은 `(empty)`.

- [ ] **TC-C-102 view --json**
  - Command: `kanban --json view`
  - Expected: 종료 코드 0; JSON 키 `board`, `stages`; 각 stage에 `id`, `name`, `position`, `cards`.

- [ ] **TC-C-103 view — 다른 보드·없는 보드**
  - Command: `kanban --board 2 view`; `kanban --board 999 view`
  - Expected: 첫째 종료 코드 0(보드 2의 카드만); 둘째 종료 코드 1 `(404)`.

- [ ] **TC-C-104 view — 파이프 출력**
  - Command: `kanban view | cat` (tty 아님)
  - Expected: 종료 코드 0; 열 제목과 카드 줄이 모두 출력된다(색 코드 없음).

## 10. E2E 시나리오

`tests/test_cli_e2e.py`가 임시 데이터베이스(`kanban_e2e_<pid>`, 끝나면 삭제)를 만들고, `kanban db upgrade` 서브프로세스로 스키마를 준비한 뒤, 실제 `uvicorn` 서브프로세스와 `kanban` 서브프로세스로 아래 시나리오의 핵심 흐름을 실행한다. 자동 테스트는 `serve` 명령 대신 `python -m uvicorn`으로 서버를 띄우고, 보드 추가 → 팀원·마일스톤 → 카드 생성 → 이동 → 코멘트 → 뷰 → 카드 삭제(404 확인) → 보드 삭제까지 확인한다. 아래 표의 나머지 단계(`serve` 기동, 두 번째 팀원, 단계 삭제 409 등)는 수동 확인용이다. 두 번째 자동 테스트 `test_help_runs_without_a_server`는 서버 없이 `kanban --help`가 0, `health`가 1로 끝나는지 확인한다.

- [ ] **TC-C-105 서버 기동부터 삭제까지**

  | 단계 | Command | 확인 |
  |---|---|---|
  | 1 | `kanban db upgrade` | 종료 코드 0, `Database is up to date.` |
  | 2 | `kanban serve --port <빈 포트>` (백그라운드) | `health`가 성공할 때까지 대기 |
  | 3 | `kanban health` | `Database: ok` |
  | 4 | `kanban --json board add "E2E Team" --repo-url https://github.com/acme/e2e` | `id` 기억 → `KANBAN_BOARD` 설정 |
  | 5 | `kanban stage list` | `Todo`, `In Progress`, `Done` |
  | 6 | `kanban member add codex --name "Codex 에이전트" --role "AI 에이전트"` | `Added member codex` |
  | 7 | `kanban member add minji --name "민지" --role PM` | 종료 코드 0 |
  | 8 | `kanban milestone add MVP --due-on 2026-11-01` | `Added milestone "MVP"` |
  | 9 | `kanban --json card add "로그인 API" --stage "In Progress" --assignee codex --milestone MVP --body "계획"` | `issue_number: 1`, `stage: "In Progress"`; 카드 `id` 기억 |
  | 10 | `kanban card add "화면 시안" --assignee minji` | `in Todo`, `issue_number: 2` |
  | 11 | `kanban comment add <id> "구현 완료, 테스트 통과" --author codex` | `Added comment` |
  | 12 | `kanban comment list <id>` | 코멘트 본문 포함 |
  | 13 | `kanban view` | `Todo (1)`, `In Progress (1)`, `Done (0)` |
  | 14 | `kanban --json card move <id> Done` | `stage: "Done"`, `closed_at` 비어 있지 않음 |
  | 15 | `kanban view` | `Done (1)` |
  | 16 | `kanban card list --assignee codex --stage Done` | 1장 |
  | 17 | `kanban card move <id> "In Progress"` | `closed_at: null` (JSON으로 확인) |
  | 18 | `kanban card delete <id>` | 종료 코드 0; 이어서 `card show <id>` 종료 코드 1 |
  | 19 | `kanban stage delete 1` (Todo에 카드가 남아 있음) | 종료 코드 1, `still has ... card(s)` (409) |
  | 20 | `kanban board delete <보드 id>` | 종료 코드 0; 이어서 `board show` 종료 코드 1 |
  | 21 | 서버 프로세스 종료 | 종료 코드 0 또는 신호 종료, 포트 해제 |

## 11. 자가 점검 — API 엔드포인트 ↔ CLI 명령

| # | 엔드포인트 | CLI 명령 | 성공 케이스 | 실패 케이스 |
|---|---|---|---|---|
| 1 | GET /api/v1/health | `health` | TC-C-012 | TC-C-013, TC-C-011 |
| 2 | GET /boards | `board list` | TC-C-019 | TC-C-011 |
| 3 | POST /boards | `board add` | TC-C-020, TC-C-021 | TC-C-025, TC-C-026 |
| 4 | GET /boards/{id} | `board show` | TC-C-022 | TC-C-027 |
| 5 | PATCH /boards/{id} | `board update` | TC-C-023 | TC-C-028, TC-C-029 |
| 6 | DELETE /boards/{id} | `board delete` | TC-C-024 | TC-C-030 |
| 7 | GET /boards/{id}/view | `view` | TC-C-101, TC-C-102, TC-C-104 | TC-C-103 |
| 8 | GET /boards/{id}/members | `member list` | TC-C-032 | TC-C-040 |
| 9 | POST /boards/{id}/members | `member add` | TC-C-031 | TC-C-036, TC-C-037, TC-C-040 |
| 10 | GET /members/{id} | `member show` | TC-C-033 | TC-C-038 |
| 11 | PATCH /members/{id} | `member update` | TC-C-034 | TC-C-039, TC-C-038 |
| 12 | DELETE /members/{id} | `member delete` | TC-C-035 | TC-C-038 |
| 13 | GET /boards/{id}/stages | `stage list` | TC-C-041 | TC-C-052 |
| 14 | POST /boards/{id}/stages | `stage add` | TC-C-042, TC-C-043 | TC-C-047, TC-C-049, TC-C-052 |
| 15 | GET /stages/{id} | `stage show` | TC-C-044 | TC-C-051 |
| 16 | PATCH /stages/{id} | `stage update` | TC-C-045 | TC-C-050, TC-C-051 |
| 17 | DELETE /stages/{id} | `stage delete` | TC-C-046 | TC-C-048, TC-C-051 |
| 18 | GET /boards/{id}/milestones | `milestone list` | TC-C-054 | TC-C-062 |
| 19 | POST /boards/{id}/milestones | `milestone add` | TC-C-053 | TC-C-058, TC-C-059, TC-C-062 |
| 20 | GET /milestones/{id} | `milestone show` | TC-C-055 | TC-C-061 |
| 21 | PATCH /milestones/{id} | `milestone update` | TC-C-056 | TC-C-060, TC-C-061 |
| 22 | DELETE /milestones/{id} | `milestone delete` | TC-C-057 | TC-C-061 |
| 23 | GET /boards/{id}/cards | `card list` | TC-C-068, TC-C-069, TC-C-070 | TC-C-071, TC-C-088 |
| 24 | POST /boards/{id}/cards | `card add` | TC-C-063, TC-C-064, TC-C-065, TC-C-066, TC-C-067 | TC-C-080, TC-C-081, TC-C-082, TC-C-083, TC-C-088 |
| 25 | GET /cards/{id} | `card show` | TC-C-072 | TC-C-087, TC-C-089 |
| 26 | PATCH /cards/{id} | `card update` | TC-C-073, TC-C-074, TC-C-075 | TC-C-084, TC-C-087 |
| 27 | DELETE /cards/{id} | `card delete` | TC-C-079 | TC-C-087 |
| 28 | POST /cards/{id}/move | `card move` | TC-C-076, TC-C-077, TC-C-078 | TC-C-085, TC-C-086, TC-C-087 |
| 29 | GET /cards/{id}/comments | `comment list` | TC-C-092 | TC-C-099 |
| 30 | POST /cards/{id}/comments | `comment add` | TC-C-090, TC-C-091 | TC-C-095, TC-C-096, TC-C-097, TC-C-098, TC-C-099 |
| 31 | GET /comments/{id} | `comment show` | TC-C-093 | TC-C-099 |
| 32 | DELETE /comments/{id} | `comment delete` | TC-C-094 | TC-C-099 |
| - | (로컬) | `serve` | TC-C-014 | TC-C-015, TC-C-016 |
| - | (로컬) | `db upgrade` | TC-C-017 | TC-C-018 |

기타 공통 점검: 도움말 TC-C-001, TC-C-002, TC-C-003, TC-C-004; 전역 옵션 TC-C-005, TC-C-006, TC-C-007, TC-C-008, TC-C-009, TC-C-010; 코멘트 수정 명령 부재 TC-C-100; 전체 흐름 TC-C-105.
