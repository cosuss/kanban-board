# 간반 보드 CLI 기술 설계 (TSD_CLI)

> 문서 목적: `kanban` CLI의 기술 구성, 명령별 인자·옵션·예시·출력·종료 코드, 설정, 오류 처리, 모듈 구조, 테스트 전략을 정의한다.

## 1. 기술 구성

- Python 3.11. Typer가 명령 트리와 도움말을 만들고, httpx가 API를 호출하며, rich가 표 출력을 맡는다.
- 콘솔 명령 `kanban`은 `pyproject.toml`의 `[project.scripts] kanban = "app.cli:app"`로 등록한다.
- CLI는 `/api/v1/...`을 호출하는 API 클라이언트다. 실행 시 `openapi.json`을 읽지 않는다. DB에 직접 접근하지 않는다(`serve`, `db upgrade` 제외).
- 모듈 구조는 `app/cli/` 패키지다(`__init__.py`에서 `app` 노출). **명령 트리는 이 문서가 고정한다.** 실제 구성은 3절.

## 2. 설치와 실행

`uv`가 설치된 환경에서 저장소 루트를 `<repo>`라 한다.

| 방식 | 명령 |
|---|---|
| 설치 없이 실행 | `uvx --from <repo> kanban --help` (저장소 안이면 `uvx --from . kanban ...`) |
| 설치해서 실행 | `uv tool install --editable <repo>` → `kanban --help` |
| 개발 환경 | `uv run kanban --help` |

서버 준비는 CLI 안에서 끝낸다.

```sh
kanban db upgrade          # 데이터베이스 준비 (DATABASE_URL 필요)
kanban serve               # 서버 실행. 이 터미널은 열어 둔다
kanban health              # 다른 터미널에서 확인
```

셸에 종속된 설치 스크립트나 경로 처리를 두지 않는다. PowerShell, Command Prompt, POSIX 셸에서 같은 예시가 동작해야 한다(따옴표는 큰따옴표 사용).

## 3. 모듈 구조

| 파일 | 역할 |
|---|---|
| `app/cli/__init__.py` | `app/cli/main.py`의 `app`을 노출 |
| `app/cli/main.py` | 루트 `app = typer.Typer(...)`, 전역 옵션 콜백(`--api-url`, `--board`, `--json`), 하위 앱 등록 |
| `app/cli/client.py` | httpx 클라이언트 생성(`get_client`, 타임아웃 10초), `request()` 래퍼, 오류 변환, JSON 출력 |
| `app/cli/common.py` | 전역 옵션을 명령 뒤에서도 받게 하는 `GlobalOptionsCommand`, 표·시각·`-` 서식 도우미, 사용법 검사(`exclusive`, `need_change`) |
| `app/cli/system.py` | `health`, `serve`, `view`, `db upgrade` |
| `app/cli/resources.py` | `board`, `member`, `stage`, `milestone` 그룹 |
| `app/cli/cards.py` | `card`, `comment` 그룹 |

테스트에서 서버 없이 앱에 연결할 수 있도록 클라이언트 생성 함수를 한 곳(`app.cli.client.get_client`)에 모아 두고, 테스트가 이 함수를 FastAPI `TestClient`(동기 httpx 호환 객체)를 돌려주는 함수로 바꿔 끼운다(`monkeypatch`). 계약은 "CLI 코드가 요청을 보내는 지점이 한 곳이며 교체 가능하다"이다.

## 4. 설정

| 설정 | 설명 | 우선순위 |
|---|---|---|
| 기본값 | `http://127.0.0.1:8000`, 보드 `1` | 가장 낮음 |
| `KANBAN_API_URL`, `KANBAN_BOARD` | 환경 변수 | 기본값보다 높음 |
| `--api-url`, `--board` | 이번 실행에만 적용 | 가장 높음 |

주소 끝의 `/`는 허용하고 정규화한다. 주소는 `http://` 또는 `https://`로 시작하고 호스트가 있어야 하며 아니면 사용법 오류(종료 코드 2). 보드 번호는 양의 정수여야 하며 아니면 사용법 오류(종료 코드 2). 요청 제한 시간은 10초다.

`--api-url`, `--board`, `--json`은 명령 앞(`kanban --json card list`)에도, 명령 뒤(`kanban card list --json`)에도 쓸 수 있다. 명령 뒤에 쓴 값이 앞에 쓴 값보다 우선한다.

## 5. 도움말 작성 규칙

사용자에게 보이는 영어 문구이므로 plain English로 쓴다. 짧은 문장, 익숙한 단어를 쓰고 `endpoint`, `payload`, `HTTP`, `enum`, `pagination` 같은 용어를 설명에 쓰지 않는다. 옵션 이름과 입력값은 그대로 두고 옆에 뜻을 쉬운 영어로 적는다. 각 `--help`는 "하는 일, 필요한 값, 선택 값, 기본 동작, 예시"를 담아 도움말만 읽고 첫 작업을 할 수 있어야 한다.

| 위치 | 도움말 문구 (기준) |
|---|---|
| 루트 | `Manage your team's kanban board from the command line.` |
| `health` | `Check that the server and its database are working.` |
| `serve` | `Start the kanban server on this computer. Keep this window open while you work.` |
| `db upgrade` | `Set up or update the database tables. Safe to run more than once.` |
| `board add` | `Create a new board. It starts with three columns: Todo, In Progress, and Done.` |
| `member add` | `Add a person to the board. Use their GitHub login name.` |
| `stage add` | `Add a column to the board.` |
| `milestone add` | `Add a goal with an optional due date.` |
| `card list` | `Show cards. You can narrow the list by column, person, goal, or words in the title or text.` |
| `card add` | `Create a card. If you do not choose a column, it goes into the first column.` |
| `card update` | `Change only the details you provide. Anything you leave out stays as it is.` |
| `card move` | `Move a card to another column. Moving a card to the last column closes it.` |
| `card delete` | `Delete a card and its comments permanently. This cannot be undone.` |
| `comment add` | `Add a comment to a card.` |
| `view` | `Show the whole board, one column per stage.` |
| `--api-url` | `Use a different kanban server. Default: http://127.0.0.1:8000.` |
| `--board` | `The board number to work on. Default: 1.` |
| `--json` | `Print the result as JSON for use with other tools.` |
| `--stage` (card add/list) | `The name of the column, for example "In Progress".` |
| `--assignee` | `The GitHub login of the person responsible, for example codex.` |
| `--milestone` | `The title of the goal this card belongs to.` |
| `--query` | `Show cards whose title or text contains these words.` |
| `--limit` | `The most cards to show at once (1-200).` (기본값은 Typer가 `[default: 50]`로 덧붙임) |
| `--offset` | `How many cards to skip before showing results.` (기본값은 Typer가 `[default: 0]`로 덧붙임) |
| `--clear-...` | `Remove the <thing>.` |

## 6. 출력 규칙

- 기본(텍스트): 목록은 rich 표, 단건은 `필드: 값` 줄, 쓰기 명령은 한 문장 결과.
- `--json`: 표준 출력에 API 응답 JSON만 출력한다(들여쓰기 2칸, 한글은 이스케이프하지 않음). 카드 목록도 다른 목록처럼 **JSON 배열**을 그대로 출력한다(`[{...CardOut...}]`, 없으면 `[]`). 삭제(`204`)는 표준 출력이 비어 있고 종료 코드 0이다.
- 오류 문장(`Error: ...`)은 표준 오류(stderr)로 보낸다. 정상 결과 문장(`Created card ...`, `No cards found.`, `Showing 3 cards.` 등)은 표준 출력이다. `--json` 실행에서 stdout에는 JSON 외 텍스트가 없다.
- 시각은 텍스트 출력에서 `YYYY-MM-DD HH:MM`(UTC)로 줄여 보여 주고, JSON은 API 값 그대로.
- 값이 없으면 텍스트에서 `-`로 표시한다.

## 7. 종료 코드와 오류 처리

| 종료 코드 | 의미 | 예 |
|---|---|---|
| 0 | 성공 | 모든 정상 응답 |
| 1 | API 오류, 연결 오류, 로컬 명령 실패 | 404, 409, 422 응답; 서버 꺼짐; `serve`·`db upgrade` 실패 |
| 2 | 사용법 오류 | 필수 인자 누락, 알 수 없는 옵션, `--stage`와 `--stage-id` 동시 사용, 변경 옵션 없는 `update`, 잘못된 `--board` |

| 상황 | stderr 출력 (한 줄) |
|---|---|
| API 오류 | `Error: <detail> (<status>)` 예: `Error: card 99 not found (404)`. `detail`이 배열(422)이면 첫 항목만 `loc`(`body`는 뺌)과 `msg`를 `loc: msg`로 보여 준다. 예: `Error: github_login: String should have at least 1 character (422)` |
| 연결 실패 | `Error: Cannot reach the kanban server at http://127.0.0.1:8000. Start it with "kanban serve".` |
| 시간 초과 | `Error: The server did not answer in time. Check that it is running.` |
| 사용법 | Typer/rich 오류 상자(`Usage: ...`, `Try 'kanban <command> --help' for help.`, 상자 안에 `Invalid value: ...` 또는 `No such option: ...`) (종료 코드 2) |

traceback은 출력하지 않는다. `kanban --board abc ...`처럼 CLI가 검증할 수 있는 입력은 요청을 보내기 전에 종료 코드 2로 막는다. 서버가 거절한 입력(중복, 없는 이름 등)은 종료 코드 1이다.

## 8. 명령 상세

공통: `ID`는 양의 정수 인자다. "보드 하위 명령"(`member list/add`, `stage list/add`, `milestone list/add`, `card list/add`, `view`)은 전역 `--board`를 사용한다. 예시 출력은 형태를 보이는 용도이며, 테스트는 핵심 문구와 JSON 키를 확인한다.

### 8.1 health

| 항목 | 내용 |
|---|---|
| 형식 | `kanban health` |
| 호출 | `GET /api/v1/health` |
| 텍스트 | `Server is running. Database: ok.` |
| JSON | `{"status": "ok", "database": "ok"}` |
| 종료 코드 | 0 정상 / 1 연결 실패 또는 `503`(`Error: database unavailable (503)`) |

### 8.2 serve

| 항목 | 내용 |
|---|---|
| 형식 | `kanban serve [--host TEXT] [--port INT] [--reload]` |
| 옵션 | `--host` 기본 `127.0.0.1`, `--port` 기본 `8000`, `--reload` 코드 변경 시 재시작(개발용) |
| 동작 | `uvicorn.run("app.main:app", host, port, reload)`를 실행하고 종료될 때까지 대기 |
| 텍스트 | 시작 시 `Starting kanban server at http://127.0.0.1:8000 (press Ctrl+C to stop)` 후 uvicorn 로그 |
| 종료 코드 | 0 정상 종료(Ctrl+C 포함) / 1 포트 사용 중 등 시작 실패 / 2 잘못된 `--port` |

### 8.3 db upgrade

| 항목 | 내용 |
|---|---|
| 형식 | `kanban db upgrade` |
| 동작 | `alembic upgrade head`와 같다(`DATABASE_URL` 사용). 반복 실행해도 안전 |
| 텍스트 | `Database is up to date.` |
| 종료 코드 | 0 / 1 DB 연결 실패 등(`Error: Cannot connect to the database. Check DATABASE_URL.`) |

### 8.4 board

| 명령 | 인자·옵션 | 호출 | 텍스트 출력 | JSON |
|---|---|---|---|---|
| `board list` | 없음 | GET /boards | 표: `ID  NAME  REPO` | BoardOut 배열 |
| `board add NAME` | `--repo-url TEXT`, `--no-default-stages` | POST /boards | `Created board 2: Team A` | BoardOut |
| `board show [BOARD_ID]` | BOARD_ID 생략 시 `--board` | GET /boards/{id} | `Board 1: Team A` 다음 줄 `Repo: https://...` | BoardOut |
| `board update BOARD_ID` | `--name`, `--repo-url`, `--clear-repo-url` | PATCH /boards/{id} | `Updated board 1.` | BoardOut |
| `board delete BOARD_ID` | | DELETE /boards/{id} | `Deleted board 1 and everything in it.` | (출력 없음) |

예시:

```sh
kanban board add "Team A" --repo-url https://github.com/acme/team-a
kanban board update 2 --name "Team A (2026)"
kanban board update 2 --clear-repo-url
kanban --json board list
```

`--repo-url`과 `--clear-repo-url`을 함께 쓰면 종료 코드 2. 옵션 없는 `update`도 2.

### 8.5 member

| 명령 | 인자·옵션 | 호출 | 텍스트 출력 | JSON |
|---|---|---|---|---|
| `member list` | | GET /boards/{board}/members | 표: `ID  LOGIN  NAME  ROLE` | MemberOut 배열 |
| `member add GITHUB_LOGIN` | `--name TEXT`(필수), `--role TEXT` | POST /boards/{board}/members | `Added member codex (id 5).` | MemberOut |
| `member show MEMBER_ID` | | GET /members/{id} | `Member 5: Codex 에이전트 (codex)` + `Role: AI 에이전트` | MemberOut |
| `member update MEMBER_ID` | `--github-login`, `--name`, `--role`, `--clear-role` | PATCH /members/{id} | `Updated member 5.` | MemberOut |
| `member delete MEMBER_ID` | | DELETE /members/{id} | `Deleted member 5.` | (출력 없음) |

```sh
kanban member add codex --name "Codex 에이전트" --role "AI 에이전트"
kanban member list
```

### 8.6 stage

| 명령 | 인자·옵션 | 호출 | 텍스트 출력 | JSON |
|---|---|---|---|---|
| `stage list` | | GET /boards/{board}/stages | 표: `ID  POSITION  NAME` | StageOut 배열 |
| `stage add NAME` | `--position INT` | POST /boards/{board}/stages | `Added stage "Review" (id 4, position 4).` | StageOut |
| `stage show STAGE_ID` | | GET /stages/{id} | `Stage 4: Review (position 4)` | StageOut |
| `stage update STAGE_ID` | `--name`, `--position` | PATCH /stages/{id} | `Updated stage 4.` | StageOut |
| `stage delete STAGE_ID` | | DELETE /stages/{id} | `Deleted stage 4.` | (출력 없음) |

카드가 남은 단계 삭제는 종료 코드 1, `Error: stage 1 still has 2 card(s); move or delete them first (409)`.

### 8.7 milestone

| 명령 | 인자·옵션 | 호출 | 텍스트 출력 | JSON |
|---|---|---|---|---|
| `milestone list` | | GET /boards/{board}/milestones | 표: `ID  TITLE  DUE` | MilestoneOut 배열 |
| `milestone add TITLE` | `--due-on YYYY-MM-DD` | POST /boards/{board}/milestones | `Added milestone "MVP" (id 1).` | MilestoneOut |
| `milestone show MILESTONE_ID` | | GET /milestones/{id} | `Milestone 1: MVP` + `Due: 2026-11-01` | MilestoneOut |
| `milestone update MILESTONE_ID` | `--title`, `--due-on`, `--clear-due-on` | PATCH /milestones/{id} | `Updated milestone 1.` | MilestoneOut |
| `milestone delete MILESTONE_ID` | | DELETE /milestones/{id} | `Deleted milestone 1.` | (출력 없음) |

### 8.8 card

| 명령 | 인자·옵션 | 호출 | 텍스트 출력 | JSON |
|---|---|---|---|---|
| `card list` | `--stage`, `--assignee`, `--milestone`, `--query`(별칭 `--search`, 짧은 이름 `-q`), `--limit`(1-200, 기본 50), `--offset`(기본 0) | GET /boards/{board}/cards | 표: `ID  ISSUE  STAGE  ASSIGNEE  TITLE`, 마지막 줄 `Showing 3 cards.`(1장이면 `Showing 1 card.`). 없으면 `No cards found.` | CardOut 배열 |
| `card add TITLE` | `--body`, `--stage` \| `--stage-id`, `--assignee` \| `--assignee-id`, `--milestone` \| `--milestone-id`, `--issue-number` | POST /boards/{board}/cards | `Created card 31 (issue #28) in In Progress: 로그인 API 구현` | CardOut |
| `card show CARD_ID` | | GET /cards/{id} | 여러 줄(아래 예) | CardOut |
| `card update CARD_ID` | `--title`, `--body`, `--clear-body`, `--stage` \| `--stage-id`, `--assignee` \| `--assignee-id`, `--clear-assignee`, `--milestone` \| `--milestone-id`, `--clear-milestone` | PATCH /cards/{id} | `Updated card 31.` | CardOut |
| `card move CARD_ID [STAGE]` | 위치 인자 `STAGE`(이름) 또는 `--stage-id`, `--position` | POST /cards/{id}/move | `Moved card 31 to Done.` | CardOut |
| `card delete CARD_ID` | | DELETE /cards/{id} | `Deleted card 31.` | (출력 없음) |

규칙:

- `--stage`/`--stage-id`, `--assignee`/`--assignee-id`, `--milestone`/`--milestone-id`는 각 쌍 중 하나만 쓴다. 함께 쓰면 요청 전에 종료 코드 2. 대응하는 `--clear-...`와 값 옵션을 함께 써도 2.
- `card move`는 `STAGE` 위치 인자와 `--stage-id` 중 **정확히 하나**가 필요하다. 없거나 둘 다면 종료 코드 2.
- `card add`에서 `--stage`를 생략하면 서버가 보드의 첫 단계를 쓴다.
- `card add`·`card update`에는 `--position`이 없다(API의 `CardCreate`·`CardUpdate`가 `position`을 받지 않는다). 순서는 `card move --position`으로만 바꾼다.
- `card update --body`와 `--clear-body`를 함께 쓰면 종료 코드 2.
- `card update`에 변경 옵션이 하나도 없으면 요청을 보내지 않고 종료 코드 2.
- `card update --stage`는 서버가 이동 규칙을 적용한다(`closed_at` 등).

`card show` 텍스트 예:

```text
Card 31 (issue #28): 로그인 API 구현
Stage:     In Progress
Assignee:  codex (Codex 에이전트)
Milestone: MVP
Created:   2026-10-19 09:00
Closed:    -
Body:
계획 요약
```

예시:

```sh
kanban card add "로그인 API 구현" --stage "In Progress" --assignee codex --milestone MVP --body "계획 요약"
kanban card list --stage "In Progress" --assignee codex
kanban card list -q login --limit 20 --offset 20
kanban card update 31 --assignee minji --clear-milestone
kanban card move 31 Done
kanban card move 31 --stage-id 1 --position 1
kanban --json card add "x" --stage Todo
```

### 8.9 comment

| 명령 | 인자·옵션 | 호출 | 텍스트 출력 | JSON |
|---|---|---|---|---|
| `comment list CARD_ID` | | GET /cards/{id}/comments | 줄마다 `[id 11] 2026-10-19 10:30 codex: 구현 완료` | CommentOut 배열 |
| `comment add CARD_ID BODY` | `--author TEXT`(github_login) \| `--author-id INT` | POST /cards/{id}/comments | `Added comment 11 to card 31.` | CommentOut |
| `comment show COMMENT_ID` | | GET /comments/{id} | `Comment 11 on card 31 by codex (2026-10-19 10:30)` + 본문 | CommentOut |
| `comment delete COMMENT_ID` | | DELETE /comments/{id} | `Deleted comment 11.` | (출력 없음) |

`--author`와 `--author-id` 동시 사용은 종료 코드 2. 코멘트 수정 명령은 없다.

### 8.10 view

| 항목 | 내용 |
|---|---|
| 형식 | `kanban view` |
| 호출 | `GET /boards/{board}/view` |
| 텍스트 | 보드 이름 줄 아래, 단계마다 한 열. 열 제목은 `Todo (2)`처럼 단계 이름과 카드 수. 각 카드는 `#7 회원가입 화면 (JooJeongwon)`. 카드가 없는 열은 `(empty)` |
| JSON | 보드 뷰 응답 그대로 `{"board", "stages"}` |
| 종료 코드 | 0 / 1 보드 없음(404) |

```text
Board 1: ASPS TEAM 01
 Todo (2)                    In Progress (1)         Done (3)
 #7 회원가입 화면 (JooJeong…)  #9 배포 스크립트 (-)     #1 DB 스키마 (cosuss)
 #8 로그인 API (cosuss)                               ...
```

터미널 폭이 좁으면 rich가 줄바꿈한다. 파이프나 파일로 출력할 때(tty 아님)에도 열 제목과 카드 줄은 모두 출력한다.

## 9. 테스트 전략

| 층 | 방법 |
|---|---|
| 단위 (`tests/test_cli.py`) | 서버 프로세스 없이 `get_client`를 FastAPI `TestClient`로 바꿔 앱에 직접 연결. Typer `CliRunner`로 명령을 실행해 요청 내용(메서드·경로·쿼리·본문), 텍스트 출력, `--json`, 종료 코드를 확인. 데이터는 `TEST_DATABASE_URL` Postgres에 만들고 테스트마다 TRUNCATE |
| 오류 경로 | 연결 실패(`--api-url http://127.0.0.1:1`), 사용법 오류, API 오류(404/409/422)를 종료 코드와 stderr로 확인 |
| 도움말 | 모든 명령의 `--help`가 종료 코드 0이고 plain English 규칙(금지 용어 목록 `HTTP, endpoint, payload, enum, pagination`) 위반이 없음 (`test_every_command_has_help`) |
| E2E (`tests/test_cli_e2e.py`) | `TEST_DATABASE_URL`로 `kanban db upgrade` → 빈 포트에 실제 `uvicorn` 서브프로세스 기동(헬스 폴링으로 대기) → `kanban` 서브프로세스를 순서대로 실행(`KANBAN_API_URL` 지정) → 종료 시 서버 종료. `TEST_CASE_CLI.md`의 E2E 시나리오를 그대로 재현 |
| 패키징 | `uvx --from . kanban --help`가 종료 코드 0 (자동 테스트는 없고 수동 확인. 대신 E2E의 `test_help_runs_without_a_server`가 `kanban --help`를 서버 없이 실행) |

실행: `uv run --locked pytest tests/test_cli.py`, `uv run --locked pytest tests/test_cli_e2e.py`. 전체 품질 게이트는 `./scripts/check.sh`.
