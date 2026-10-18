# 간반 보드 CLI 제품 요구사항 (PRD_CLI)

> 문서 목적: 간반 보드 API를 터미널에서 쓰게 해 주는 `kanban` CLI가 무엇을 해야 하는지 정의한다. 명령별 상세는 `TSD_CLI.md`, 검증은 `TEST_CASE_CLI.md`, 사용 안내는 `CLI_GUIDE.md`를 본다.

## 1. 개요

`kanban`은 로컬 간반 보드 API(`PRD.md`)를 터미널에서 사용할 수 있게 하는 크로스플랫폼 CLI다. 터미널 명령에 익숙하지 않은 팀원도 보드, 팀원, 단계, 마일스톤, 카드, 코멘트를 만들고 조회하고 고치고 지울 수 있어야 한다. 대화형 입력 없이 명령과 옵션만으로 작업이 끝난다. Codex 에이전트도 같은 명령을 그대로 쓴다.

## 2. 목표

- macOS, Linux, Windows에서 같은 명령을 사용한다.
- `uvx`로 별도 설치 없이 실행할 수 있고, `uv tool install`로 설치해 `kanban`만 입력해도 된다.
- 백엔드 API의 **모든 엔드포인트(32개)** 를 명령으로 제공한다.
- 기본 출력은 읽기 쉬운 텍스트, 자동화용으로 `--json`을 제공한다.
- 도움말은 비개발자가 이해하는 plain English로 쓴다.
- 서버 실행(`serve`)과 마이그레이션(`db upgrade`)까지 명령으로 제공해 "서버 켜기"도 CLI 안에서 끝낸다.

## 3. 사용자와 사용 환경

- 사용자는 개발자가 아닐 수 있다. Python 코드나 HTTP를 직접 다루지 않는다.
- Codex 에이전트가 `--json` 출력을 읽어 다음 명령에 쓴다(`CODEX.md`).
- 기본 API 주소는 `http://127.0.0.1:8000`이다. CLI는 DB에 직접 접속하지 않고 API 클라이언트로만 동작한다. 예외는 `serve`와 `db upgrade`뿐이다.
- `uv`가 설치되어 있으면 `uvx --from <repo경로> kanban --help`로 시작한다. 설치형은 `uv tool install --editable <repo경로>` 후 `kanban --help`.
- API에 인증이 없으므로 접근 범위와 보안 전제는 `PRD.md`를 따른다.

## 4. 범위

### 포함

- 보드, 팀원, 단계, 마일스톤, 카드, 코멘트의 생성·목록·단건·수정·삭제 명령(코멘트 수정 제외)
- 카드 이동(`card move`), 보드 뷰(`view`), 헬스 체크(`health`)
- 카드 목록 필터(`--stage`, `--assignee`, `--milestone`, `--query`/`--search`/`-q`)와 `--limit`, `--offset`. 카드 순서는 `card move --position`으로만 바꾼다(`card add`·`card update`에는 없음).
- 이름 또는 id로 단계·담당자·마일스톤·작성자 지정
- 사람이 읽기 쉬운 텍스트 출력과 `--json` 출력
- 전역 옵션 `--api-url`, `--board`, `--json`
- 서버 실행 `serve`, 마이그레이션 `db upgrade`
- macOS, Linux, Windows 실행과 사용 문서

### 제외

- 로그인, 인증, 권한
- 대화형 프롬프트, 메뉴, 확인 질문, 터미널 UI
- 실행 시 `openapi.json`을 읽어 명령을 동적으로 만드는 기능
- 로컬 캐시, 오프라인 동기화
- 코멘트 수정(백엔드 API에 없음)
- 백엔드에 정의되지 않은 추가 기능

## 5. 명령 목록

CLI 이름은 `kanban`이며 명령은 API 리소스를 기준으로 구성한다.

| 명령 | 동작 |
|---|---|
| `kanban health` | 서버와 DB 상태를 확인한다 |
| `kanban serve [--host --port --reload]` | API 서버를 실행한다(uvicorn) |
| `kanban db upgrade` | 데이터베이스를 최신 구조로 만든다(`alembic upgrade head`) |
| `kanban board list\|add\|show\|update\|delete` | 보드 관리 |
| `kanban member list\|add\|show\|update\|delete` | 팀원 관리 |
| `kanban stage list\|add\|show\|update\|delete` | 단계 관리 |
| `kanban milestone list\|add\|show\|update\|delete` | 마일스톤 관리 |
| `kanban card list\|add\|show\|update\|move\|delete` | 카드 관리와 이동 |
| `kanban comment list\|add\|show\|delete` | 코멘트 관리 |
| `kanban view` | 보드를 단계별 열로 보여 준다 |

### 전역 옵션

| 옵션 | 환경 변수 | 기본값 | 설명 |
|---|---|---|---|
| `--api-url` | `KANBAN_API_URL` | `http://127.0.0.1:8000` | 사용할 서버 주소 |
| `--board` | `KANBAN_BOARD` | `1` | 보드 하위 명령이 쓸 보드 번호 |
| `--json` | | 꺼짐 | API 응답 JSON을 그대로 출력 |

전역 옵션은 명령 앞(`kanban --json card list`)에도 뒤(`kanban card list --json`)에도 쓸 수 있다.

## 6. API 엔드포인트와 CLI 명령 대응

백엔드 API의 모든 동작(32개)이 명령 하나에 1:1로 대응한다. `/docs`, `/redoc`, `/openapi.json`은 문서 경로이므로 명령으로 만들지 않는다. 카드 목록은 `{"items": ...}`가 아니라 JSON 배열이다.

| # | HTTP 요청 | CLI 명령 |
|---|---|---|
| 1 | `GET /api/v1/health` (별칭 `GET /health`) | `kanban health` |
| 2 | `GET /api/v1/boards` | `kanban board list` |
| 3 | `POST /api/v1/boards` | `kanban board add NAME [--repo-url] [--no-default-stages]` |
| 4 | `GET /api/v1/boards/{board_id}` | `kanban board show [BOARD_ID]` |
| 5 | `PATCH /api/v1/boards/{board_id}` | `kanban board update BOARD_ID [--name] [--repo-url] [--clear-repo-url]` |
| 6 | `DELETE /api/v1/boards/{board_id}` | `kanban board delete BOARD_ID` |
| 7 | `GET /api/v1/boards/{board_id}/view` | `kanban view` |
| 8 | `GET /api/v1/boards/{board_id}/members` | `kanban member list` |
| 9 | `POST /api/v1/boards/{board_id}/members` | `kanban member add GITHUB_LOGIN --name [--role]` |
| 10 | `GET /api/v1/members/{member_id}` | `kanban member show MEMBER_ID` |
| 11 | `PATCH /api/v1/members/{member_id}` | `kanban member update MEMBER_ID [--github-login] [--name] [--role] [--clear-role]` |
| 12 | `DELETE /api/v1/members/{member_id}` | `kanban member delete MEMBER_ID` |
| 13 | `GET /api/v1/boards/{board_id}/stages` | `kanban stage list` |
| 14 | `POST /api/v1/boards/{board_id}/stages` | `kanban stage add NAME [--position]` |
| 15 | `GET /api/v1/stages/{stage_id}` | `kanban stage show STAGE_ID` |
| 16 | `PATCH /api/v1/stages/{stage_id}` | `kanban stage update STAGE_ID [--name] [--position]` |
| 17 | `DELETE /api/v1/stages/{stage_id}` | `kanban stage delete STAGE_ID` |
| 18 | `GET /api/v1/boards/{board_id}/milestones` | `kanban milestone list` |
| 19 | `POST /api/v1/boards/{board_id}/milestones` | `kanban milestone add TITLE [--due-on]` |
| 20 | `GET /api/v1/milestones/{milestone_id}` | `kanban milestone show MILESTONE_ID` |
| 21 | `PATCH /api/v1/milestones/{milestone_id}` | `kanban milestone update MILESTONE_ID [--title] [--due-on] [--clear-due-on]` |
| 22 | `DELETE /api/v1/milestones/{milestone_id}` | `kanban milestone delete MILESTONE_ID` |
| 23 | `GET /api/v1/boards/{board_id}/cards` | `kanban card list [--stage] [--assignee] [--milestone] [--query\|--search\|-q] [--limit] [--offset]` |
| 24 | `POST /api/v1/boards/{board_id}/cards` | `kanban card add TITLE [--body] [--stage\|--stage-id] [--assignee\|--assignee-id] [--milestone\|--milestone-id] [--issue-number]` (`--position` 없음) |
| 25 | `GET /api/v1/cards/{card_id}` | `kanban card show CARD_ID` |
| 26 | `PATCH /api/v1/cards/{card_id}` | `kanban card update CARD_ID [--title] [--body\|--clear-body] [--stage\|--stage-id] [--assignee\|--assignee-id\|--clear-assignee] [--milestone\|--milestone-id\|--clear-milestone]` (`--position` 없음) |
| 27 | `DELETE /api/v1/cards/{card_id}` | `kanban card delete CARD_ID` |
| 28 | `POST /api/v1/cards/{card_id}/move` | `kanban card move CARD_ID [STAGE] [--stage-id] [--position]` |
| 29 | `GET /api/v1/cards/{card_id}/comments` | `kanban comment list CARD_ID` |
| 30 | `POST /api/v1/cards/{card_id}/comments` | `kanban comment add CARD_ID BODY [--author\|--author-id]` |
| 31 | `GET /api/v1/comments/{comment_id}` | `kanban comment show COMMENT_ID` |
| 32 | `DELETE /api/v1/comments/{comment_id}` | `kanban comment delete COMMENT_ID` |

추가로 API가 아닌 로컬 명령 `serve`, `db upgrade`가 있다. 백엔드에 엔드포인트나 매개변수가 추가되면 대응 명령과 테스트 케이스도 함께 추가한다.

## 7. 기능 요구사항

- CLI는 백엔드의 검증 규칙, 기본값, 상태 코드를 따른다. 이름 지정 규칙(`--stage` 또는 `--stage-id`, 둘 다 주면 오류)도 같다.
- 생성·수정에 대화형 입력을 요구하지 않는다. 필요한 값이 없으면 사용법 오류를 쉬운 문장으로 보여 준다.
- 수정 시 생략한 옵션은 기존 값을 유지한다. 값 비우기는 `--clear-...` 옵션으로 명시한다.
- 삭제는 확인 질문 없이 실행한다.
- 기본 출력은 사람이 읽을 수 있어야 하고, `--json`이면 표준 출력에 API 응답 JSON만 출력한다.
- 요청이 실패하면 원인과 다음 행동을 한 줄로 표준 오류에 보여 주고, 성공처럼 보이는 출력을 하지 않는다. 서버가 꺼져 있으면 `kanban serve`를 안내한다.
- 종료 코드는 성공 `0`, API·연결 오류 `1`, 사용법 오류 `2`.
- `kanban --help`와 모든 명령의 `--help`는 plain English(짧은 문장, 일상 단어)로 쓰고 `HTTP`, `endpoint`, `payload`, `enum`, `pagination` 같은 개발자 용어를 설명에 쓰지 않는다. 옵션 이름과 실제 입력값은 그대로 표기한다.
- Python traceback을 사용자에게 보여 주지 않는다.

## 8. 완료 기준

- 위 6절의 32개 대응이 모두 구현되고 각각 테스트로 검증된다.
- 카드 목록의 모든 필터·페이지 옵션이 동작한다.
- 텍스트와 `--json` 출력이 각각 동작하고 `--json`은 표준 출력에 JSON 외 텍스트가 없다.
- 서버 주소를 기본값, 환경 변수, 옵션으로 지정할 수 있고 우선순위가 옵션 > 환경 변수 > 기본값이다.
- macOS, Linux, Windows에서 `uvx --from . kanban --help`와 API 명령이 실행된다. (현재 macOS에서만 확인했고 Linux·Windows는 미검증이다. CI는 Ubuntu에서 pytest까지만 돈다.)
- 루트 도움말과 모든 명령 도움말이 plain English로 첫 작업을 실행할 수 있을 만큼 설명한다.
- `TEST_CASE_CLI.md`의 케이스와 E2E 시나리오가 통과한다. (자동 테스트 33개가 통과하고, `serve` 기동 등 일부는 수동 확인 항목이다.)
- Codex 스킬(`CODEX.md`)이 이 CLI만으로 카드 생성 → 코멘트 → 이동 흐름을 수행한다.
