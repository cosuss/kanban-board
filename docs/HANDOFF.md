# 과제#8 — 프론트엔드 담당자와 AI를 위한 인수인계

이 저장소는 과제#7의 **팀 공유 간반 보드 백엔드**다. 과제#8에서는 이 API에
웹 프론트엔드를 연결하고 실제 팀 업무를 저장·공유한 뒤 라이브 또는 녹화로 시연한다.
강의의 team-todo 예시와 이 API는 다르다. 실제 구현은 `docs/openapi.json`을 따른다.

## 1. AI가 읽을 순서와 완료 기준

1. 이 문서 → `README.md` → `docs/openapi.json` 순서로 읽는다.
2. 실행 경로 하나를 골라 DB와 API를 준비한다. `/api/v1/health`가 200이고
   `{"status":"ok","database":"ok"}`일 때만 연결 준비 완료다.
3. 예제를 준비하고 출력된 **실제 보드 ID**를 기록한다. 1로 가정하지 않는다.
4. 프론트엔드는 별도의 형제 폴더/저장소에서 만든다. API를 먼저 확인한 다음 화면을 연결한다.
5. 아래 QA를 실제 API로 수행한다. 정적 명세만으로 구현한 상태와 실제 연결 검증을 구분해 보고한다.

인증은 없으며 로컬 개발용이다. 브라우저는 DB에 직접 접속하지 않는다.
공개 GitHub 저장소는 실행 중인 공용 API가 아니다.

## 2. 백엔드 실행 — 둘 중 하나

### A. Docker (Python·Postgres 직접 설치 없이)

Docker Desktop/Engine과 Compose가 실행 중이어야 한다.

```sh
git clone https://github.com/cosuss/kanban-board.git
cd kanban-board
docker compose up --build -d --wait
docker compose exec api uv run --locked --no-dev python -m app.demo
```

- API: `http://127.0.0.1:8000`, Swagger: `/docs`, 명세: `/openapi.json`
- DB는 별도 로컬 볼륨이며 Supabase와 연결되지 않는다. `.env`의 DATABASE_URL을 읽지 않는다.
- 로그: `docker compose logs --tail=100 api db`
- 종료: `docker compose down`. 다시 시작하면 기존 데이터를 재사용한다.
- `docker compose down -v`는 데이터를 지우므로 보존해야 하는 환경에서 실행하지 않는다.
- 포트 8000이 사용 중이면 `.env`에 `KANBAN_PORT=8001`을 설정한 뒤 다시 실행한다.
  이 경우 프론트 API 주소도 8001로 맞춘다. 컨테이너의 예제 출력은 내부 주소 8000이므로
  프론트 주소에는 호스트 포트를 사용한다.

### B. Python + 로컬 PostgreSQL 또는 팀 공유 Supabase

Python 3.11, uv, PostgreSQL 16 또는 접근 가능한 Supabase DB가 필요하다.
아래 명령은 macOS/Linux 기준이며 Windows에서는 `.env.example`을 `.env`로 복사할 때
PowerShell의 `Copy-Item .env.example .env`를 사용한다.

```sh
git clone https://github.com/cosuss/kanban-board.git
cd kanban-board
uv sync --locked --all-groups
cp .env.example .env
```

- 로컬 DB: PostgreSQL을 시작하고 `createdb kanban` 후 `.env`의 기본 주소를 사용한다.
  DB 사용자 인증이 필요한 환경이면 본인 계정에 맞게 DATABASE_URL을 설정한다.
- 팀 공유 DB: 작성자가 별도로 전달한 Supabase **Session pooler URI**를
  `.env`의 `DATABASE_URL`에 저장한다. 브라우저용 anon 키가 아니다.
  비밀번호의 특수문자는 URI 인코딩된 연결 문자열을 사용한다.
- 기존 `.env`가 있으면 덮어쓰지 않고 필요한 항목만 수정한다.

```sh
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

다른 터미널에서 같은 저장소 폴더로 이동해 실행한다:

```sh
uv run --locked kanban health
uv run --locked python -m app.demo
```

예제 준비는 별도 예제 보드를 사용하며 기존 데이터를 삭제하지 않는다. 재실행하면 같은
예제 보드를 재사용하고 누락된 예제 항목을 채운다. 수정·삭제한 예제는 재생성될 수 있으므로
실제 업무는 별도의 팀 보드에 기록한다. 원본 과제#5 SQL이나 로컬 폴더는 필요 없다.
동일 명령을 여러 터미널에서 동시에 실행하지 않는다.

## 3. 공유와 환경변수

예제 명령은 아래와 같은 값을 출력한다. 팀원이 만든 **프론트 저장소의 `.env.local`**에 저장한다.
프론트 구현이 이 변수 이름을 실제로 읽도록 해야 한다.

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_KANBAN_BOARD_ID=<출력된 숫자>
```

API 경로에는 `/api/v1`을 한 번만 붙인다. 환경변수 변경 뒤 프론트 개발 서버를 재시작한다.
DB 연결 문자열은 `NEXT_PUBLIC_*`나 프론트 소스에 넣지 않는다.

각자 Docker DB나 로컬 DB를 만들면 데이터가 서로 공유되지 않는다. 최종 공유 데모는
각자의 로컬 백엔드가 **같은 팀 개발용 Supabase DB**에 연결되고 같은 보드 ID를 사용해야 한다.
실제 보드는 `GET /api/v1/boards`에서 조회한다. 새 팀 보드 생성 시 기본 단계는 자동 생성된다.
공유 DB에서는 기존 업무를 삭제하지 않고 시연용 카드를 따로 만든다.
DB 접속 정보는 작성자가 별도 비공개 채널로 전달한다.

## 4. 프론트가 연결할 API

| 화면·동작 | 요청 |
|---|---|
| 보드 선택 | `GET /api/v1/boards` |
| 보드 전체 표시 | `GET /api/v1/boards/{board_id}/view` |
| 카드 상세 | `GET /api/v1/cards/{card_id}` |
| 생성 | `POST /api/v1/boards/{board_id}/cards` |
| 수정 | `PATCH /api/v1/cards/{card_id}` |
| 단계·위치 이동 | `POST /api/v1/cards/{card_id}/move` |
| 삭제 | `DELETE /api/v1/cards/{card_id}` |
| 담당자·마일스톤 선택지 | `GET /api/v1/boards/{board_id}/members`, `/milestones` |
| 댓글 목록·작성 | `GET/POST /api/v1/cards/{card_id}/comments` |

요청 예시:

```json
POST /api/v1/boards/{board_id}/cards
{"title":"발표자료 만들기","body":"3분 데모 준비","stage":"Todo"}
```

생성 응답의 `id`를 이후 요청에 사용한다. 담당자는 조회한 실제 멤버의 `github_login`을
`assignee`에 넣거나 `assignee_id`를 사용한다. 이름과 ID를 동시에 지정하지 않는다.

```json
PATCH /api/v1/cards/{card_id}
{"title":"발표자료 수정","assignee_id":null}
```

```json
POST /api/v1/cards/{card_id}/move
{"stage":"In Progress","position":1}
```

- 보드 화면 응답은 `{board, stages:[{id,name,position,cards:[...]}]}`이다.
- 단계명은 보드에서 조회한다. 완료 상태는 이름이 아니라 **마지막 단계**로 판정한다.
- 카드 이동은 서버에 저장한 후 다시 조회한다. `position`을 PATCH에 넣어 순서를 바꾸지 않는다.
- PATCH에서 생략한 필드는 유지한다. 담당자·마일스톤 해제는 해당 ID에 `null`을 보낸다.
- 목록 필터 `assignee`는 표시 이름이 아니라 `github_login`이다.
- 카드 목록은 기본 50개/최대 200개이므로 `limit`, `offset`으로 페이지를 처리한다.
  보드 전체 표시는 `/view`를 사용한다.
- DELETE 성공은 **204/본문 없음**이다. 항상 `response.json()`을 호출하면 오류가 난다.
- 404는 없는 항목, 409는 충돌, 422는 잘못된 입력, 503은 DB 연결/부하 문제다.
  `detail`은 문자열 또는 검증 오류 배열일 수 있다. 화면에 읽을 수 있는 오류를 표시한다.
- 인증 헤더와 쿠키는 필요 없다. CORS는 인증 기능이 아니다.

## 5. 브라우저 연결 문제 해결

기본 허용 Origin은 `http://localhost:3000`, `http://127.0.0.1:3000`이다.
프론트 포트가 다르면 백엔드 `.env`에 JSON 배열로 추가하고 백엔드를 재시작한다.
Docker 사용 시 `compose.yaml`의 API 환경변수를 수정하고 컨테이너를 재생성한다.

```dotenv
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001"]
```

- 연결 거부: API 프로세스·포트 확인. 다른 사람 PC의 localhost는 내 API가 아니다.
- `/health` 503: DB 실행·URI·비밀번호·네트워크 확인. 비밀번호를 오류 보고에 복사하지 않는다.
- 테이블 없음: 올바른 DATABASE_URL로 `alembic upgrade head` 실행.
- 보드 404: 실제 보드 ID와 연결된 DB 확인. 기본값 1을 추측하지 않는다.
- 브라우저 CORS 오류: Origin의 프로토콜·호스트·포트를 정확히 맞춘다.
- Docker 연결 실패: Docker 엔진 실행 확인. 실패 시 `logs`를 읽고 B 경로로 진행할 수 있다.
- 공개 웹 배포: 로컬 API를 가리키는 배포 프론트는 팀 전체가 쓰는 공용 서버가 아니다.
  공개 API 운영은 인증·접근 제어와 배포 설계가 추가로 필요하다.

## 6. 과제 QA와 인수 완료

과제#8 공식 요구: 연동 웹 프론트, 실제 팀 업무 저장·공유, 동작 화면의 라이브/녹화 데모.
수업 실습을 따를 경우 Next.js, 두 디자인 가이드의 테마 전환, 목록·상세·별도 설정 화면,
생성·수정·삭제를 포함한다. 두 DESIGN 파일은 프론트 담당자가 준비한다.
발표자료는 2026-10-27 09:00까지 과제#8 스레드 제출, 팀당 3분 발표다.

수동으로 확인하고 결과를 프론트의 테스트 문서에 기록한다:

- 목록·상세·빈 보드·로딩·API 연결 오류를 표시한다.
- 카드 생성 → 본문/담당자 수정 → 단계 이동 → 새로고침 후 값 유지.
- 두 브라우저 또는 같은 DB에 연결된 두 컴퓨터에서 새로고침 후 같은 카드가 보임.
  실시간 푸시는 API에 없으므로 필요하면 재조회나 폴링으로 구현한다.
- 카드 삭제 후 목록에서 사라지고 204 응답 처리에 오류가 없음.
- 설정에서 두 테마 전환, 재접속 후 선택 유지.
- 모바일 화면과 키보드 조작을 확인하고 실제 화면으로 데모.

백엔드 검사: 별도 로컬 테스트 DB `kanban_test`를 만든 뒤 `./scripts/check.sh`.
테스트 DB의 데이터는 초기화되므로 팀 공유 DB를 TEST_DATABASE_URL로 지정하지 않는다.

## 7. 팀원이 AI에게 줄 프롬프트

```text
과제#7 간반 보드 백엔드에 연결하는 과제#8 웹 프론트엔드를 만들어줘.
백엔드 저장소: https://github.com/cosuss/kanban-board
먼저 docs/HANDOFF.md, README.md, docs/openapi.json을 읽어.
웹 링크를 못 읽으면 저장소를 clone해서 로컬 파일로 읽어.
강의 예시 team-todo의 엔드포인트 대신 이 저장소의 API 계약을 사용해.
백엔드와 별도의 형제 폴더에 Next.js 프론트 프로젝트를 만들어.
우선 실행 중인 API health, 보드 목록과 실제 보드 ID를 확인해.
API가 실행되지 않았으면 HANDOFF의 실행 경로를 준비하고 연결 확인 후 진행해.
프론트에서 DB 비밀번호를 사용하지 말고 환경변수의 API 주소로 HTTP 요청해.
내가 제공할 두 DESIGN 가이드를 읽고 목록·상세·설정 화면과 테마 전환을 계획해.
카드 생성·수정·삭제·단계 이동과 에러·로딩·빈 상태를 구현해.
계획과 수동 테스트 시나리오를 docs에 남기고 구현 후 실제 API로 검증해.
부족한 디자인 가이드·공유 DB 접속 정보만 나에게 질문해.
```

서버 없이 명세만 전달할 때:
- `https://raw.githubusercontent.com/cosuss/kanban-board/main/docs/HANDOFF.md`
- `https://raw.githubusercontent.com/cosuss/kanban-board/main/docs/openapi.json`

## 8. 검증 기록

이 문서의 마지막 검증 결과는 `docs/HANDOFF_VALIDATION.md`를 참조한다.
