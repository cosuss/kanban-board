# Codex에서 간반 보드 쓰기 (CODEX)

> 문서 목적: Codex가 하는 작업을 CLI, API, `kanban-log` 스킬로 팀 간반 보드에 등록하고 공유하는 방법을 예시 프롬프트와 함께 안내한다.

## 1. 준비

Codex가 보드를 쓰려면 아래가 갖춰져 있어야 한다.

| 항목 | 확인 방법 |
|---|---|
| 서버가 떠 있다 | `kanban health` → `Server is running. Database: ok.` (안 되면 `kanban serve`) |
| `kanban` 명령을 쓸 수 있다 | `kanban --help` (설치 전이면 `uvx --from <repo> kanban --help`) |
| 보드에 팀원 `codex`가 있다 | `kanban member list`에 `codex`가 보임 |
| 쓸 보드 번호를 안다 | `kanban board list` (기본은 1번, 다르면 `KANBAN_BOARD=<번호>`) |

팀원 `codex`가 없다면 한 번만 등록한다.

```sh
kanban member add codex --name "Codex 에이전트" --role "AI 에이전트"
```

`github_login`은 전체 보드에서 유일하므로, 이미 다른 보드에 `codex`가 있으면 등록이 `409`로 거절된다. 그 경우 그 팀원을 그대로 쓰거나 팀과 상의한다.

서버 주소가 기본값이 아니면 환경 변수로 알려 준다: `export KANBAN_API_URL=http://192.168.0.10:8000`.

## 2. 방법 (a) — CLI로 팀 업무 등록하기

Codex는 터미널 명령을 실행할 수 있으므로 CLI가 가장 간단하다. `--json`을 쓰면 출력에서 카드 `id`를 읽을 수 있다.

### 예시 프롬프트 1 — 작업 카드 만들기

```text
간반 보드에 지금 할 일을 등록해 줘.
- kanban CLI를 써. 먼저 `kanban health`로 서버가 떠 있는지 확인해.
- 제목은 "로그인 API 구현", 단계는 "In Progress", 담당자는 codex, 본문에는 작업 계획을 세 줄로 요약해서 넣어.
- `--json` 출력의 id를 알려 줘.
```

Codex가 실행하는 명령 예:

```sh
kanban health
kanban --json card add "로그인 API 구현" --stage "In Progress" --assignee codex --body "1. 모델 추가 2. 엔드포인트 구현 3. 테스트 작성"
```

### 예시 프롬프트 2 — 끝난 작업 기록하고 닫기

```text
방금 끝낸 작업을 보드에 기록해 줘. 카드 31에 무엇을 바꿨고 어떻게 검증했는지 코멘트로 남기고(작성자 codex), Done으로 옮겨. 마지막에 `kanban view` 결과를 보여 줘.
```

```sh
kanban comment add 31 "로그인 API 구현. pytest 12개 통과, ruff 통과." --author codex
kanban card move 31 Done
kanban view
```

### 예시 프롬프트 3 — 여러 업무 한꺼번에 등록하고 정리하기

```text
다음 세 가지 업무를 보드에 등록해 줘. 담당자는 각각 minji, cosuss, codex이고 마일스톤은 MVP야. 모두 Todo에 만들어. 등록 후 `kanban card list --milestone MVP`로 확인해서 표를 보여 줘.
1. 회원가입 화면 시안
2. 결제 API 설계
3. CI 설정 점검
```

```sh
kanban card add "회원가입 화면 시안" --assignee minji --milestone MVP
kanban card add "결제 API 설계" --assignee cosuss --milestone MVP
kanban card add "CI 설정 점검" --assignee codex --milestone MVP
kanban card list --milestone MVP
```

## 3. 방법 (b) — `openapi.json`을 읽고 API로 직접 등록하기

CLI를 쓸 수 없는 환경(샌드박스에 `kanban`이 없는 경우 등)이나 더 세밀한 제어가 필요할 때는 API를 직접 호출한다. 서버는 `GET /openapi.json`으로 모든 엔드포인트와 요청 형식을 알려 준다. Swagger UI(`/docs`)로 사람이 확인할 수도 있다.

### 예시 프롬프트 4 — 스키마를 읽고 카드 등록하기

```text
간반 보드 API 서버는 http://127.0.0.1:8000 에 떠 있어. 먼저 `curl http://127.0.0.1:8000/openapi.json`으로 API 명세를 읽어서 카드를 만드는 엔드포인트와 필드를 확인해.
그다음 보드 1에 카드를 만들어 줘: 제목 "DB 인덱스 점검", 단계 "In Progress", 담당자 codex(github_login), 본문 "느린 쿼리 확인". 응답의 id와 issue_number를 알려 줘.
카드를 만든 뒤에는 같은 카드에 코멘트("점검 시작", 작성자 codex)를 달고, Done으로 옮겨.
```

Codex가 만드는 호출 예:

```sh
curl -s -X POST http://127.0.0.1:8000/api/v1/boards/1/cards \
  -H "Content-Type: application/json" \
  -d '{"title": "DB 인덱스 점검", "stage": "In Progress", "assignee": "codex", "body": "느린 쿼리 확인"}'

curl -s -X POST http://127.0.0.1:8000/api/v1/cards/31/comments \
  -H "Content-Type: application/json" \
  -d '{"body": "점검 시작", "author": "codex"}'

curl -s -X POST http://127.0.0.1:8000/api/v1/cards/31/move \
  -H "Content-Type: application/json" \
  -d '{"stage": "Done"}'
```

### 알아 두면 좋은 API 규칙

| 규칙 | 설명 |
|---|---|
| 이름으로 지정 | 단계는 `stage`, 담당자는 `assignee`(github_login), 마일스톤은 `milestone`(제목), 코멘트 작성자는 `author`. id를 쓰려면 `stage_id` 등을 쓰고 **둘을 함께 보내면 422** |
| 없는 이름 | `404`. 이름이 맞는지 `GET /api/v1/boards/1/stages` 등으로 먼저 확인 |
| 자동 값 | `issue_number`(생략하면 `max+1`), `position`, `created_at`, `closed_at`은 서버가 채우므로 보내지 않는다. 보내도 `created_at`·`closed_at`·`position`(카드 생성 시)은 무시된다. `issue_number`는 직접 지정할 수 있지만 중복이면 `409` |
| 목록 응답 | 카드 목록(`GET /api/v1/boards/1/cards`)을 포함한 모든 목록은 JSON 배열이다(`items` 감싸기 없음) |
| 순서 바꾸기 | 카드의 `position`은 `POST /api/v1/cards/{id}/move`에서만 정한다. 카드 생성·수정(PATCH)에는 `position`이 없다 |
| 닫힘 | 마지막 단계로 옮기면 `closed_at`이 채워지고, 다른 단계로 옮기면 비워진다 |
| 오류 형식 | `{"detail": "..."}` (검증 오류 422는 `detail`이 배열) |

## 4. 방법 (c) — `kanban-log` 스킬로 자동 기록하기

`kanban-log` 스킬을 설치하면 Codex가 작업을 시작하고 끝낼 때마다 보드에 스스로 기록한다. 사용자가 매번 "보드에 등록해 줘"라고 말하지 않아도 된다.

### 설치

스킬 원본은 저장소의 `skills/kanban-log/`에 있고, Codex 스킬 폴더에 심볼릭 링크로 연결한다. 저장소 폴더에서:

```sh
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skills/kanban-log" ~/.codex/skills/kanban-log
ls -l ~/.codex/skills/kanban-log/SKILL.md     # 링크가 잘 걸렸는지 확인
```

원본을 고치면 링크로 바로 반영된다. 이미 링크가 있으면 `ln -sfn "$(pwd)/skills/kanban-log" ~/.codex/skills/kanban-log`로 바꾼다. Windows에서는 PowerShell에서 `New-Item -ItemType SymbolicLink`로 같은 경로를 연결하거나 폴더를 복사한다(복사하면 원본 수정이 자동 반영되지 않는다). 설치 후 Codex를 새로 시작하면 스킬 목록에 `kanban-log`가 보인다.

### 동작 흐름

| 순서 | 때 | 스킬이 하는 일 | 명령 |
|---|---|---|---|
| 0 | 시작 전 | 서버 확인. 실패하면 사용자에게 `kanban serve`를 안내하고 기록을 건너뜀 | `kanban health` |
| 1 | 작업 시작 | 카드 생성, 출력의 `id`를 기억 | `kanban card add "<작업 제목>" --stage "In Progress" --assignee codex --body "<계획 요약>" --json` |
| 2 | 작업 끝 | 무엇을 바꿨고 어떻게 검증했는지 코멘트 | `kanban comment add <id> "<무엇을 바꿨고 어떻게 검증했는지>" --author codex` |
| 3 | 작업 끝 | 카드를 완료로 이동(닫힘) | `kanban card move <id> Done` |
| 막힘 | 진행 불가 | 이유를 코멘트로 남기고 Todo로 되돌림 | `kanban comment add <id> "<막힌 이유>" --author codex` 후 `kanban card move <id> Todo` |

기록되는 카드는 항상 담당자 `codex`로 만들어진다. 팀원은 `kanban view`나 `kanban card list --assignee codex`로 Codex가 하고 있는 일과 끝낸 일을 본다.

### 예시 프롬프트 5 — 스킬을 쓰는 평소 작업

```text
$kanban-log 를 사용해서 이 저장소의 로그인 API 버그를 고쳐 줘. 시작할 때 카드를 만들고, 끝나면 변경 내용과 테스트 결과를 코멘트로 남기고 Done으로 옮겨.
```

### 예시 프롬프트 6 — 보드 현황 요약

```text
kanban-log 스킬 규칙대로 `kanban view`와 `kanban card list --assignee codex --stage "In Progress"`를 실행해서, 지금 진행 중인 일과 최근에 끝난 일을 세 줄로 요약해 줘.
```

## 5. 주의사항

- **샌드박스에서는 네트워크를 열어 줘야 한다.** `codex exec`의 기본 샌드박스(`workspace-write`)는 네트워크를 막기 때문에 `localhost`의 간반 서버(`curl`, `kanban`)에 닿지 못한다. 아래 6절처럼 `-c sandbox_workspace_write.network_access=true`를 함께 줘야 한다.
- **서버가 떠 있어야 한다.** `kanban health`가 실패하면 기록할 수 없다. 이때 Codex는 사용자에게 `kanban serve`(또는 서버 담당자에게 요청)를 안내해야 하며, 기록 실패를 성공처럼 보고하면 안 된다.
- **담당자 `codex` 팀원이 있어야 한다.** 없으면 카드 생성이 `404`(`member 'codex' not found on board`)로 실패한다. 1절의 `member add`로 먼저 등록한다. 보드마다 팀원이 따로 있지만 `github_login`은 전체에서 유일하므로 `codex`는 한 보드에만 등록할 수 있다.
- **보드 번호를 맞춘다.** 다른 보드에 기록하려면 `--board <번호>` 또는 `KANBAN_BOARD`를 지정한다. 기본은 1번이다.
- **단계 이름은 그 보드에 실제로 있는 이름이어야 한다.** 기본 단계가 아닌 이름을 쓰는 보드는 `kanban stage list`로 먼저 확인한다. "닫힘"은 이름이 아니라 **마지막 단계**로 판단한다.
- **인증이 없다.** 서버 주소에 닿는 누구나 보드를 읽고 쓸 수 있으므로 신뢰할 수 있는 네트워크에서만 연다. 코멘트와 카드 본문에 비밀번호, 토큰, `.env` 값을 적지 않는다.
- **삭제는 되돌릴 수 없다.** Codex가 `delete` 명령을 쓰게 하려면 사용자가 명시적으로 요청해야 한다. 스킬은 기본적으로 삭제하지 않는다.
- **카드 하나에 작업 하나.** 작업이 끝날 때까지 같은 카드 `id`를 이어서 쓰고, 세션이 바뀌었다면 `kanban card list --assignee codex --stage "In Progress"`로 이어서 할 카드를 찾는다.

## 6. 실제로 돌려 본 데모 결과

2026-10-19에 실제 Codex(`codex exec`)로 세 가지 방법을 모두 한 번씩 실행했다. 대상은 Supabase에 시드(47행)가 들어 있는 보드 1(`ASPS TEAM 01 — 두근두근 코코네`)이며, 서버는 이 저장소의 FastAPI 앱이다. 아래 숫자와 문구는 실행 로그(Codex 출력, `hook:` 줄 제외)에서 그대로 옮겼다.

### Codex 실행 명령

```sh
codex exec -s workspace-write -c sandbox_workspace_write.network_access=true "<프롬프트>"
```

`codex exec`의 기본 샌드박스는 네트워크를 막는다. `localhost` API나 `kanban` CLI가 서버에 닿으려면 `-s workspace-write`와 함께 `-c sandbox_workspace_write.network_access=true`를 반드시 붙여야 한다(로그 머리글에 `sandbox: workspace-write [...] (network access enabled)`로 표시된다). 프롬프트는 작은따옴표나 큰따옴표로 한 덩어리로 감싼다.

### (a) `openapi.json`을 읽고 API로 카드 2개 등록

서버를 `http://127.0.0.1:8001`에 띄운 상태에서 보낸 프롬프트 요지: "`/openapi.json`을 curl로 읽고 그 명세를 참조해서 보드 1번에 업무 2개를 카드로 등록하고, `GET /api/v1/boards/1/view`로 단계별 카드 수를 확인해 표로 보고해. 다른 카드는 건드리지 마."

Codex가 한 일: `kanban-log` 스킬 파일을 읽음 → `curl /openapi.json`으로 명세 확인 → `GET /boards/1/view`와 `/boards/1/members`로 현재 상태·`github_login` 확인 → `POST /api/v1/boards/1/cards` 두 번 → 뷰로 재확인. 이름 참조(`stage`, `assignee`)를 그대로 써서 id 조회 없이 한 번에 만들었다.

| 카드 id | issue_number | 제목 | 담당자 | 단계 |
|---:|---:|---|---|---|
| 31 | 35 | 과제#7 발표자료 3분 버전 만들기 | cosuss | In Progress |
| 32 | 36 | 간반 CLI E2E 테스트 돌려보기 | codex | Todo |

등록 직후 뷰의 단계별 카드 수: Todo 2, In Progress 1, Done 26(합계 29). 사용한 호출 예:

```sh
curl -fsS -X POST http://127.0.0.1:8001/api/v1/boards/1/cards -H 'Content-Type: application/json' \
  --data-binary '{"title":"간반 CLI E2E 테스트 돌려보기","assignee":"codex","stage":"Todo"}'
```

응답은 `{"id":32,"stage":"Todo","assignee":"codex","assignee_name":"Codex 에이전트","issue_number":36,...}` 형태였다.

### (b) `kanban` CLI로 마일스톤·카드 만들고 이동·코멘트

서버 `http://127.0.0.1:8000`, 프롬프트 요지: "`kanban --help`와 필요한 하위 명령의 `--help`를 읽고 CLI만 써서 (1) 마일스톤 '과제#7 제출'(마감 2026-10-20) 추가 (2) 카드 '발표 대본 3분 버전 작성'(담당 cosuss, Todo, 그 마일스톤) 생성 (3) 카드 32를 In Progress로 옮기고 코멘트 추가 (4) `kanban view` 출력과 요약 표."

Codex는 `--help`를 여러 개 읽은 뒤(`kanban --help`, `milestone`, `card`, `comment`, `view`, `comment add`, `card move`, `card show`, `milestone add`, `card add`) 아래 명령을 실행했다. 모두 `--json`을 붙여 id를 읽었다.

```sh
kanban health
kanban card show 32 --json
kanban milestone add '과제#7 제출' --due-on 2026-10-20 --json
kanban card add '발표 대본 3분 버전 작성' --assignee cosuss --stage Todo --milestone '과제#7 제출' --json
kanban card move 32 'In Progress' --json
kanban comment add 32 '83개 테스트 통과(단위 81 + E2E 2)' --author codex --json
kanban view
```

| 대상 | 결과 |
|---|---|
| 마일스톤 id 3 | `과제#7 제출`, 마감 2026-10-20 |
| 카드 id 33 (issue #37) | `발표 대본 3분 버전 작성`, 담당 cosuss, Todo, 마일스톤 `과제#7 제출` |
| 카드 id 32 (issue #36) | `간반 CLI E2E 테스트 돌려보기` → In Progress |
| 코멘트 id 11 | 카드 32, 작성자 codex, `83개 테스트 통과(단위 81 + E2E 2)` |

마지막 `kanban view` 열 제목은 `Todo (2)`, `In Progress (2)`, `Done (26)`이었다. Todo에는 `#22 발표 스토리라인 기획`과 새 `#37 발표 대본 3분 버전 작성 (cosuss)`, In Progress에는 `#35`·`#36`이 보였다. 다른 카드에는 변경 명령을 실행하지 않았다. 참고: 코멘트 문구의 "단위 81"은 프롬프트에서 준 숫자다. 이 저장소의 실제 구성은 API 47 + CLI 단위 31 + 마이그레이션 3 + CLI E2E 2 = 83개다.

### (c) `kanban-log` 스킬로 별도 저장소 작업을 카드로 기록

임시 저장소(`hello.py`만 있는 git 저장소)에서 프롬프트: "`kanban-log` 스킬을 사용해서 이 작업을 보드에 기록하면서 진행해줘: `hello.py`의 `greet`에 타입 힌트와 docstring을 추가하고 `tests/test_hello.py`에 pytest 테스트를 만든 뒤 `python3 -m pytest -q`로 통과를 확인해. 보고 마지막 줄에 카드 번호와 단계를 적어."

스킬 규칙대로 Codex가 한 순서:

1. `kanban health` → `Server is running. Database: ok.`
2. `kanban card list --stage "In Progress" --json`으로 같은 제목의 진행 중 카드가 없는지 확인(없음, 배열로 응답)
3. `kanban card add 'greet에 타입 힌트·docstring과 pytest 테스트 추가' --stage 'In Progress' --assignee codex --body '요청: ... 계획: ...' --json` → 카드 id 34, issue #38, In Progress
4. 코드와 테스트 작성. 기본 Python에 pytest가 없어 임시 가상환경을 만들어 설치한 뒤 `python3 -m pytest -q` 실행 → `3 passed`
5. `kanban comment add 34 '변경: ... 검증: ... 3 passed ...' --author codex` → `Added comment 12 to card 34.`
6. `kanban card move 34 Done` → `Moved card 34 to Done.`

마지막 줄 보고: `보드: 카드 #34 → Done`. 스킬이 요구한 "시작 시 In Progress 생성 → 완료 코멘트(변경·검증) → Done 이동" 흐름이 그대로 지켜졌다. 보고에서 말하는 `#34`는 이슈 번호가 아니라 카드 id(`kanban card move 34`에 쓰는 번호)다.

### 데모에서 확인한 점

- `codex` 팀원, `cosuss` 팀원 이름 참조가 모두 `404` 없이 동작했다. 스킬 설치 경로는 `~/.codex/skills/kanban-log/SKILL.md`였다.
- `kanban card list --json`은 `{"items": ...}`가 아니라 카드 객체의 JSON 배열을 출력한다. 스킬의 "이미 같은 제목의 카드가 있으면 이어 쓴다" 규칙이 이 배열을 그대로 읽어 동작했다.
- 시각은 데모 서버에서 `2026-10-18T18:19:38.439366Z`(UTC)로 나왔다. 서버 DB 세션 시간대에 따라 `+09:00` 같은 오프셋 표기가 될 수 있다.
- 보드 뷰의 `#`번호는 카드 id가 아니라 issue_number다. 카드 id는 `kanban card list`의 `ID` 열이나 JSON의 `id`에서 읽는다.
