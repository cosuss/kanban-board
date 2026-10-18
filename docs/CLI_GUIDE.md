# 간반 보드 CLI 사용 설명서 (CLI_GUIDE)

> 문서 목적: 터미널이 낯선 팀원이 `kanban` 명령으로 팀 간반 보드를 설치하고 쓰는 방법을 처음부터 끝까지 안내한다.

`kanban` 명령으로 팀 보드의 카드를 만들고, 옮기고, 코멘트를 남길 수 있습니다. 이 안내서는 `uv`가 설치되어 있고 저장소를 내려받았다고 가정합니다. 아래 `<repo>`는 `kanban-board` 저장소 폴더입니다.

## 1. 설치

`uv`가 없다면 먼저 설치합니다(공식 안내: https://docs.astral.sh/uv/). 그다음 둘 중 하나를 고릅니다.

**방법 A. 설치 없이 매번 실행** — 저장소 폴더에서:

```sh
uvx --from . kanban --help
```

이 방법을 쓰면 아래 예시의 `kanban` 앞에 `uvx --from . `를 붙여 입력하세요.

**방법 B. 한 번 설치하고 `kanban`만 입력** (권장):

```sh
uv tool install --editable <repo>
kanban --help
```

화면에 영어 도움말이 나오면 준비가 끝났습니다. 모든 명령은 `--help`를 붙이면 설명을 볼 수 있습니다(예: `kanban card add --help`).

## 2. 서버 켜기

보드 데이터는 데이터베이스에 저장되고, `kanban` 명령은 **서버**를 통해 그 데이터에 접근합니다. 그래서 서버가 켜져 있어야 합니다. 서버는 팀에서 한 사람만 켜면 됩니다(같은 컴퓨터에서 쓰는 경우).

1. 저장소 폴더에 `.env` 파일을 만들고 데이터베이스 주소를 적습니다(`.env.example`을 복사해서 고치세요). 이 파일은 남에게 보여 주거나 올리지 마세요.

   ```text
   DATABASE_URL=postgresql://사용자:비밀번호@호스트:5432/데이터베이스
   ```

2. 데이터베이스를 준비합니다(처음 한 번. 여러 번 해도 안전합니다).

   ```sh
   kanban db upgrade
   ```

3. 서버를 켭니다. **이 창은 작업하는 동안 닫지 마세요.**

   ```sh
   kanban serve
   ```

4. **새 터미널 창**을 열어 확인합니다.

   ```sh
   kanban health
   ```

   `Server is running. Database: ok.`가 보이면 성공입니다.

다른 컴퓨터의 서버를 쓰려면 주소를 알려 주세요: `kanban --api-url http://192.168.0.10:8000 health`. 매번 쓰기 번거로우면 환경 변수 `KANBAN_API_URL`에 주소를 넣어 두세요.

## 3. 기본 개념

| 용어 | 뜻 |
|---|---|
| 보드(board) | 팀의 칸반 판. 번호가 있고 기본은 `1`번 |
| 단계(stage) | 보드의 세로 칸. 기본은 `Todo`, `In Progress`, `Done` |
| 카드(card) | 해야 할 일 하나. GitHub 이슈 번호가 붙음 |
| 팀원(member) | 보드에 등록된 사람. GitHub 로그인 이름으로 부름 |
| 마일스톤(milestone) | 여러 카드를 묶는 목표(마감일 선택) |
| 코멘트(comment) | 카드에 남기는 메모 |

여러 보드가 있다면 `--board 2`처럼 번호를 정해서 실행합니다(생략하면 1번 보드). `KANBAN_BOARD=2`로 기본 보드를 바꿀 수도 있습니다.

## 4. 흔한 작업 10가지

### 1) 보드 만들기

```sh
kanban board add "우리 팀" --repo-url https://github.com/acme/our-team
```

`Todo`, `In Progress`, `Done` 세 단계가 함께 만들어집니다. 만들어진 보드 번호를 기억해 두세요.

### 2) 팀원 등록하기

```sh
kanban member add minji --name "민지" --role "PM"
kanban member list
```

GitHub 로그인 이름(`minji`)이 담당자를 부르는 이름이 됩니다. Codex도 `codex`라는 팀원으로 등록해 두세요(`CODEX.md`).

### 3) 마일스톤 만들기

```sh
kanban milestone add MVP --due-on 2026-11-01
```

### 4) 카드 만들기

```sh
kanban card add "로그인 화면 만들기"
```

단계를 정하지 않으면 첫 번째 칸(`Todo`)에 들어갑니다. 이슈 번호와 순서는 자동으로 붙습니다.

### 5) 담당자·단계·마일스톤을 정해서 카드 만들기

```sh
kanban card add "로그인 API" --stage "In Progress" --assignee minji --milestone MVP --body "이메일 로그인부터"
```

이름 사이에 띄어쓰기가 있으면 큰따옴표로 감싸세요.

### 6) 카드 목록 보고 좁혀 보기

```sh
kanban card list
kanban card list --stage "In Progress"
kanban card list --assignee minji --milestone MVP
kanban card list -q 로그인
```

조건을 여러 개 쓰면 모두 맞는 카드만 나옵니다. `-q` 대신 `--query` 또는 `--search`를 써도 됩니다. 이름이 맞는 카드가 없으면 오류 없이 `No cards found.`가 나옵니다. 많을 때는 `--limit 20 --offset 20`으로 나눠 봅니다(`--limit`은 1~200, 기본 50). 카드 순서를 바꾸는 `--position`은 `card move`에만 있고(`kanban card move 5 Todo --position 1`), `card add`·`card update`에는 없습니다.

### 7) 카드 옮기기

```sh
kanban card move 5 "In Progress"
kanban card move 5 Done
```

`5`는 카드 번호(목록의 `ID` 열)입니다. **마지막 단계(Done)로 옮기면 카드가 닫히고, 다른 단계로 되돌리면 다시 열립니다.**

### 8) 카드 고치기

```sh
kanban card update 5 --title "로그인 화면 다듬기" --assignee codex
kanban card update 5 --clear-milestone
```

적은 항목만 바뀝니다. `--clear-...`는 값을 지웁니다.

### 9) 코멘트 남기고 읽기

```sh
kanban comment add 5 "시안 확인했습니다" --author minji
kanban comment list 5
```

### 10) 보드 전체 한눈에 보기

```sh
kanban view
```

단계마다 한 열로 카드가 나옵니다. 지우고 싶은 것이 있다면 `kanban card delete 5`, `kanban comment delete 3`처럼 하세요. **지운 것은 되돌릴 수 없습니다.** 카드가 남아 있는 단계는 지울 수 없고, 보드를 지우면 그 안의 모든 카드와 코멘트도 함께 사라집니다.

## 5. 결과를 프로그램에게 넘기고 싶을 때

`--json`을 붙이면 사람이 읽는 표 대신 JSON이 나옵니다. 명령 앞(`kanban --json card list`)이나 뒤(`kanban card list --json`) 어디에 써도 됩니다.

```sh
kanban --json card list --stage Todo
```

Codex 같은 도구가 읽을 때 쓰는 형식입니다. 카드 목록은 카드 객체의 JSON 배열(`[{...}, {...}]`)이고, 없으면 `[]`입니다. 삭제 명령은 `--json`이면 아무것도 출력하지 않고 종료 코드 0으로 끝납니다.

## 6. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `Error: Cannot reach the kanban server ...` | 서버가 꺼져 있거나 주소가 다름 | 서버 담당자 컴퓨터에서 `kanban serve` 실행. 다른 컴퓨터라면 `--api-url` 확인 |
| `Error: Cannot connect to the database` (`db upgrade`) | `.env`의 `DATABASE_URL`이 없거나 틀림 | 주소·비밀번호 확인. 비밀번호의 특수문자는 URL 인코딩 필요 |
| `Error: stage 'review' not found on board (404)` | 단계 이름이 보드에 없거나 철자가 다름 | `kanban stage list`로 정확한 이름 확인(대소문자 구분) |
| `Error: board 9 not found (404)` | `--board` 번호가 없음 | `kanban board list`로 번호 확인 |
| `Error: stage 1 still has 2 card(s); move or delete them first (409)` | 카드가 있는 단계는 못 지움 | 카드를 다른 단계로 옮긴 뒤 다시 시도 |
| `Error: a card with this issue_number already exists (409)` 등 `... already exists (409)` | 이슈 번호, 로그인 이름(보드가 달라도 겹치면 안 됨), 단계 이름·위치, 마일스톤 제목 중복 | 다른 값을 쓰거나 `--issue-number` 생략 |
| `Error: name: String should have at least 1 character (422)` | 빈 값을 보냄(서버가 거절하면 첫 번째 문제만 보여 줌) | 값을 채워서 다시 실행 |
| `Invalid value: Use only one of these: --stage and --stage-id.` (종료 코드 2) | 같은 항목을 이름과 번호로 둘 다 적음 | 하나만 사용(`--stage` 또는 `--stage-id`) |
| 사용법 안내가 나오고 종료 코드 2 | 필요한 값이 빠졌거나 옵션이 잘못됨 | 그 명령에 `--help`를 붙여 확인 |
| `kanban: command not found` | 설치 안 함 또는 PATH 문제 | 방법 A(`uvx --from . kanban`)로 실행하거나 `uv tool install` 다시 실행 |
| `kanban serve`: 포트 사용 중 | 이미 서버가 켜져 있거나 다른 프로그램이 8000번 사용 | `kanban serve --port 8001` 후 `--api-url http://127.0.0.1:8001` 사용 |

그래도 안 되면 오류 메시지 한 줄(`Error: ...`)을 그대로 복사해 팀에 물어보세요. 서버 창에는 더 자세한 기록이 남습니다.
