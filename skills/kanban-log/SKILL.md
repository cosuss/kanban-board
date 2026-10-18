---
name: kanban-log
description: Use this skill whenever you (Codex) start, finish, or get blocked on a piece of work in a repository that has a team Kanban board available through the `kanban` CLI (or when the user says "보드에 등록", "간반에 기록", "log this to the board", "kanban"). It registers the work you are doing as a card on the shared Kanban board, moves the card through Todo → In Progress → Done, and leaves a comment with what changed and how it was verified, so teammates can see what the AI agent did without reading the chat.
---

# kanban-log — Codex 작업을 팀 간반 보드에 기록하기

팀 간반 보드(과제#5 DB, Supabase Postgres)에는 `codex`라는 팀원이 있다. 당신이 하는 작업은 이 팀원의 카드로 남긴다.
목적은 **채팅을 안 본 팀원도 보드만 보고 Codex가 무엇을 했는지 알 수 있게** 하는 것이다.

## 언제 쓰나

- 사용자가 코드 수정·문서 작성·조사 같은 **작업 단위**를 시켰을 때: 시작할 때 카드를 만들고, 끝나면 코멘트와 함께 Done으로 옮긴다.
- 사용자가 "보드에 올려/등록해/기록해"라고 하면 그 요청 자체를 카드로 만든다(할 일 등록).
- 단순 질문·답변(코드 변경 없음)은 카드로 남기지 않는다.

## 준비 확인 (매번 첫 명령)

```sh
kanban health
```

- 성공(`Server is running. Database: ok.`)이면 진행한다.
- 실패하면 작업은 계속하되 보드 기록은 건너뛰고, 마지막 보고에 "보드 서버가 꺼져 있어 기록하지 못했다. `kanban serve`로 켜 달라"고 한 줄 남긴다. 서버를 대신 띄우지 않는다(사용자 터미널 세션을 점유하게 되므로).
- `kanban` 명령이 없으면 `uv tool install --editable /Users/jinhwan/workspace/cocone-school/kanban-board`를 안내한다.
- 보드 번호는 기본 1이다. 다른 보드를 쓰라고 하면 모든 명령에 `--board <id>`를 붙인다.

## 작업 흐름

### 1. 시작: 카드를 "In Progress"에 만든다

```sh
kanban card add "<작업을 한 줄로: 동사로 시작>" \
  --stage "In Progress" --assignee codex \
  --body "요청: <사용자 요청 요약 1~2줄>
계획: <무엇을 어떻게 할지 1~3줄>" --json
```

- 출력 JSON의 `id`를 기억한다(이후 명령에 쓴다).
- 제목은 60자 이내, 한국어 사용자면 한국어로. 예: `README에 Supabase 연결 절차 추가`, `카드 이동 API의 closed_at 버그 수정`.
- 사용자가 "할 일로만 등록"하라고 하면 `--stage Todo`로 만들고 여기서 끝낸다.

### 2. 진행 중 메모(선택)

중간에 중요한 결정이나 막힌 점이 생기면 코멘트로 남긴다.

```sh
kanban comment add <id> "<결정 또는 막힌 점 1~3줄>" --author codex
```

### 3. 완료: 결과 코멘트를 남기고 Done으로 옮긴다

```sh
kanban comment add <id> "변경: <바꾼 파일·내용 요약>
검증: <실행한 테스트·명령과 결과>
남은 일: <없으면 '없음'>" --author codex
kanban card move <id> Done
```

### 4. 막혔거나 사용자가 중단시켰을 때

```sh
kanban comment add <id> "중단: <이유와 현재 상태, 다음에 할 일>" --author codex
kanban card move <id> Todo
```

## 규칙

- 카드 하나 = 작업 단위 하나. 사용자가 한 번에 여러 작업을 시키면 작업마다 카드를 만든다.
- 비밀값(토큰, 비밀번호, 연결 문자열)은 제목·본문·코멘트에 절대 적지 않는다.
- 보드 명령이 실패해도(네트워크 오류 등) 본 작업을 멈추지 않는다. 실패한 명령과 오류 한 줄을 마지막 보고에 적는다.
- 이미 같은 제목의 카드가 "In Progress"에 있으면(`kanban card list --stage "In Progress" --json`으로 확인) 새로 만들지 않고 그 카드를 이어 쓴다.
- 마지막 보고에는 카드 번호와 현재 단계를 한 줄로 적는다. 예: `보드: 카드 #31 "…" → Done`.

## 명령 요약

| 할 일 | 명령 |
|---|---|
| 서버 확인 | `kanban health` |
| 보드 보기 | `kanban view` |
| 카드 만들기 | `kanban card add "<제목>" --stage "In Progress" --assignee codex --body "<본문>" --json` |
| 카드 옮기기 | `kanban card move <id> "<Todo\|In Progress\|Done>"` |
| 코멘트 | `kanban comment add <id> "<내용>" --author codex` |
| 카드 찾기 | `kanban card list --stage "In Progress" --json`, `kanban card list -q "<검색어>"` |
| 도움말 | `kanban --help`, `kanban card add --help` |

자세한 사용법은 저장소의 `docs/CLI_GUIDE.md`, API 전체는 `http://127.0.0.1:8000/docs`.
