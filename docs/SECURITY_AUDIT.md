# 보안 감사

작성일 2026-10-19. 대상: 커밋 `ffcb636` 위에서 이 작업의 수정을 적용한 상태. 로컬 서버(포트 8002)와 전용 DB `kanban_stress`에 직접 요청을 보내 확인한 것, 코드 줄을 읽고 확인한 것만 적었다. 확인하지 못한 것은 "미확인"으로 표시했다.

전제(DESIGN.md §3): 인증 없음, 로컬 배포, 소규모 수업 팀. 서버는 `127.0.0.1`에 바인딩한다(`kanban serve`의 기본 `--host 127.0.0.1`, `app/cli/system.py:44-46`).

## 1. 요약

| 항목 | 상태 | 비고 |
|---|---|---|
| 인증·인가 | 없음 (수업 전제) | 같은 기기·같은 네트워크의 누구나 읽고 쓸 수 있다 |
| CORS | 미설정 = 교차 출처 브라우저 호출 차단 | 확인함(§3) |
| 브라우저 CSRF | 막힘 | JSON이 아닌 Content-Type은 422, 프리플라이트는 405(§3) |
| SQL 인젝션 | 발견 못 함 | 전부 ORM 바인딩, `q`는 `autoescape=True`(§5) |
| 입력 길이 한도 | **없음** (5MB 제목이 201) | 지금 고칠 것 |
| int64 초과·NUL 문자 | 500이었음 → **422로 고침** | `app/main.py` |
| 오류 메시지 노출 | 500은 일반 문구만, 스택은 서버 로그에만 | 422 응답이 입력을 되돌려 보냄(§6) |
| 의존성 취약점 | `pip-audit` 알려진 취약점 없음 | §7 |
| 비밀값 | 추적 파일에 비밀번호 URL 없음 | §8 |

## 2. 입력 검증 (직접 요청해서 확인)

| 요청 | 결과 |
|---|---|
| `GET /boards/1/cards?limit=201` | 422 `less_than_equal` (`app/api/routes/cards.py` `Query(ge=1, le=200)`) |
| `GET /boards/1/cards?limit=abc` | 422 `int_parsing` |
| 잘못된 JSON `{bad` | 422 `json_invalid` |
| 같은 `github_login` 두 번 | 409 (`a member with this github_login already exists`) |
| 같은 `repo_url` 두 번 | 409 |
| 5,000,000자 `title`로 POST | **201 (저장됨)** — 길이 한도가 없다 |
| `title`에 NUL(`\u0000`) | 수정 전 500, 수정 후 **422** |
| `issue_number=99999999999999999999` | 수정 전 500, 수정 후 **422** |
| `GET /cards/99999999999999999999` | 수정 전 500, 수정 후 **422** |
| `/move`의 `position=99999999999` | 수정 전 500, 수정 후 **422** |

코드로 본 스키마 한도(`app/schemas/*.py`): 모든 문자열은 `min_length=1`뿐이고 `max_length`가 없다. `body`·`title`·`name`·`github_login` 전부 마찬가지다. `position`/`issue_number`는 `ge=1`만 있고 상한이 없다.
500의 원인은 Postgres `DataError`(int64 초과, NUL 바이트)였고 `app/main.py`의 핸들러가 이를 422(`a value is out of range or contains invalid characters`)로 바꾼다. 테스트: `tests/test_session.py`.

그 외 전체 본문 크기 제한도 없다(uvicorn/FastAPI 기본은 무제한). 같은 기기의 로컬 도구이므로 위험은 낮지만, 5MB 제목을 `GET /view`가 전부 되돌려 주는 구조라서 한 건이 응답을 부풀릴 수 있다.

## 3. 인증 없음, CORS, CSRF

- **인증 없음**: 모든 엔드포인트가 열려 있다. `kanban serve`는 `127.0.0.1`로만 연다. `uvicorn app.main:app --host 0.0.0.0`으로 띄우면 같은 네트워크 누구나 보드를 지울 수 있다(`DELETE /boards/{id}`는 카드까지 지운다). 이건 코드가 아니라 실행 방법의 문제다.
- **CORS**: `grep -rn "CORS\|allow_origins" app` → 0건, 미들웨어 없음. 실제로 `OPTIONS /api/v1/boards`(Origin: `http://evil.example`)가 `405 Method Not Allowed`, `Access-Control-Allow-*` 헤더 없음. 브라우저의 다른 출처 페이지는 응답을 읽지 못하고 프리플라이트가 필요한 요청(`PATCH`/`DELETE`, JSON 본문)을 보내지 못한다. 지금 상태가 안전한 기본값이다. 프런트엔드를 붙일 때 `allow_origins=["*"]`로 열지 않는다.
- **CSRF**: 프리플라이트를 건너뛰는 "단순 요청"(`text/plain`, 폼 본문)으로 `POST /boards/1/cards`를 보내 봤다. 전부 422(`model_attributes_type`). FastAPI가 JSON Content-Type이 아니면 본문을 객체로 받지 않아서 다른 사이트의 `<form>`이 카드를 만들 수 없다. 본문이 없는 `DELETE` 등은 프리플라이트 대상이라 위 405로 막힌다.
- **DNS 리바인딩/로컬호스트 접근**: 브라우저가 `127.0.0.1:8000`을 다른 호스트 이름으로 열게 만드는 공격은 `Host` 헤더 검사가 없어서 막혀 있지 않다(`TrustedHostMiddleware` 없음). 읽기 응답을 가져가려면 CORS가 아니라 리바인딩이 필요한 공격이라 위험은 낮다. 미확인(재현은 안 했다).

## 4. 오류 메시지와 문서 노출

- 404/409/422 도메인 오류는 `{"detail": "card 999999 not found"}`처럼 한 줄이다(`app/core/errors.py`). 스택·SQL·DB 이름이 나오지 않는다.
- 처리 못 한 예외는 본문 `Internal Server Error`(일반 문구)만 간다. 스택트레이스는 서버 로그(표준 오류)에만 남는다. DB 접속 정보가 로그에 들어가는지는 확인하지 못했다. `QueuePool limit` 예외 로그에는 연결 문자열이 없었다.
- **422 응답은 `input`에 요청 값을 그대로 돌려준다**(예: 5MB 제목이면 5MB를 되돌려 보낸다). 외부 노출 서비스라면 줄여야 하지만 요청한 본인에게 돌려주는 값이라 로컬 도구에서는 허용한다.
- `/docs`, `/redoc`, `/openapi.json`은 열려 있다(200 확인). 인증이 없으니 문서가 숨겨도 얻는 게 없다.
- 풀이 모자랄 때는 503 `{"detail":"database busy, try again"}`로 일반 문구만 낸다.

## 5. SQL 인젝션과 `q` 필터

- 쿼리는 전부 SQLAlchemy 표현식이다. `grep`으로 본 범위(`app/services/*.py`)에 문자열을 이어 붙인 SQL이 없다. `text(...)`는 `app/api/routes/health.py`의 상수 `select 1`뿐이다.
- `q` 필터: `Card.title.icontains(q, autoescape=True) | Card.body.icontains(q, autoescape=True)`(`app/services/cards.py`). `autoescape=True`라서 `%`·`_`·`\`가 리터럴로 처리된다. 실제 확인: 제목이 `100% done_ok`와 `100xx doneXok`인 두 카드를 만들고
  - `q=%` → 1건(`100% done_ok`만)
  - `q=_` → 1건(`100% done_ok`만. `doneXok`는 안 걸린다)
- 인젝션 시도: `q=' OR 1=1; DROP TABLE cards;--` → 200, 빈 배열, 이후 `select count(*) from cards`가 그대로(2,002행). `stage=Todo' OR '1'='1` → 200, 빈 배열.
- 다만 `q`로 패턴이 `%`로 시작하는 `ILIKE`라서 카드가 수만 장이면 순차 스캔이다(성능 이슈, `docs/PERFORMANCE_AUDIT.md`). 보안 문제는 아니다.

## 6. 서비스 거부(DoS) 관점

인증이 없으니 로컬 전제 밖에서는 쉽다. 직접 확인한 것:

- 수정 전에는 동시 요청 100개만으로 앱이 30~45초 단위로 정체했다(`PERFORMANCE_AUDIT.md` §2). 수정 후에는 동시 300에서도 오류 0이거나(풀 5/10) 깨끗한 503이다(풀 부족 시).
- 본문 크기, `GET /boards/{id}/view`의 카드 수(`limit=1_000_000`)가 무제한이다. 카드 2,000장이면 응답 약 570KB.
- 속도 제한 없음.

## 7. 의존성 취약점

```
uv export --frozen --no-hashes --no-emit-project > req.txt   # 123줄, dev 그룹 포함 전부
uvx pip-audit -r req.txt --no-deps --disable-pip
→ No known vulnerabilities found
```

pip-audit 2.10.1, 2026-10-19 기준 데이터베이스. 의존성 해시를 고정하지 않은 requirements라서 경고가 나왔다(`uv.lock` 자체가 고정). 주기적으로 다시 돌린다.

## 8. Supabase 접속과 비밀값

- `.env`는 `.gitignore`에 있다(`.env`, `.venv/`). `git ls-files | grep -i env` → `.env.example`만. `git grep -E "postgres(ql)?(\+psycopg)?://[^ /]*:[^ @]*@"` → 비밀번호 있는 URL 3건이 나왔지만 전부 예시다: CI의 테스트 DB(`.github/workflows/quality.yml:33`, `postgres:postgres@localhost`), 문서 안내문(`사용자:비밀번호@호스트`), 테스트 설명. 실제 Supabase 비밀번호는 추적 파일에 없다.
- 접속 방식은 DESIGN.md §2 그대로: 6개 테이블 RLS 켜짐(정책 없음) → 공개 키(anon)로는 PostgREST를 통해 접근할 수 없고, 백엔드가 `DATABASE_URL`(DB 비밀번호가 든 연결 문자열)로 직접 접속한다. **DB 비밀번호가 곧 전권**이다: 백엔드 DB 역할은 RLS를 우회하는 역할(`postgres`)로 접속하는 것이 일반적이므로(미확인, 이번에 Supabase에 접속하지 않았다) RLS는 "외부 키 노출 차단용"일 뿐 서버 프로세스를 보호하지 않는다.
- 서비스 키·anon 키를 클라이언트(CLI)에 주지 않는다: CLI는 `KANBAN_API_URL`의 HTTP API만 호출하고 DB에 직접 접근하지 않는다(DESIGN.md §4, `app/cli/client.py`는 httpx로 `api_url + /api/v1`만 호출).
- 연결 문자열은 서버와 Alembic 실행 환경에만 둔다. 팀원이 각자 서버를 띄우면 각자 DB 비밀번호가 필요하다는 뜻이므로, 하나의 서버를 공유하고 팀원은 CLI의 `--api-url`만 쓰게 하는 편이 비밀번호 확산이 적다.

## 9. CLI가 API URL을 임의로 받는 문제

`--api-url`/`KANBAN_API_URL`은 어떤 URL이든 받는다(`app/cli/common.py` `normalize_api_url`, `app/cli/client.py:14-23`에서 `httpx.Client(base_url=api_url + API_PREFIX)`). 이것은 SSRF가 아니다. CLI는 사용자가 자기 기기에서 직접 실행하는 도구이고, 공격자가 값을 넣을 경로가 없다(환경 변수와 인자는 실행하는 사람이 정한다).
남는 위험은 두 가지다. (1) `KANBAN_API_URL`이 신뢰할 수 없는 서버를 가리키면 요청으로 보내는 내용(카드 제목·본문)이 그 서버로 간다. 인증 헤더를 보내지 않으므로 토큰 유출은 없다. (2) 에이전트(Codex)가 `--api-url`을 임의 값으로 호출하도록 프롬프트 인젝션을 당하면 보드 내용을 외부 서버로 내보낼 수 있다. 스킬(`skills/kanban-log`)에서 `--api-url`을 쓰지 않도록 두면 충분하다. 코드는 건드리지 않았다.

## 10. 허용 가능한 타협점 (로컬 배포 전제)

- 인증 없음, 사용자 구분 없음. `comments.author`는 요청이 말하는 대로 믿는다.
- CORS 미설정, 로컬호스트 바인딩.
- 본문·문자열 길이 무제한(로컬 도구, 사용자가 곧 운영자).
- 스택트레이스는 서버 로그에만. 감사 로그 없음.
- 모든 사람이 모든 보드를 지울 수 있다.

## 11. 권고

### 지금 당장 고칠 것

1. 문자열 길이 한도를 스키마에 넣는다(`app/schemas/*.py`, 이번 범위 밖): 예) `title` 255자, `body`·comment `body` 10,000자, `name`/`github_login` 100자. 5MB 제목이 201인 것이 현재 가장 큰 구멍이다.
2. 정수 필드에 상한을 둔다(`position`, `issue_number`, 경로의 id `le=2**63-1`). 이번에 422로 막았지만 스키마에서 거르는 것이 정확한 메시지를 준다.
3. `uvicorn`을 `--host 0.0.0.0`으로 띄우지 않는다고 `README`/`CODEX.md`에 한 줄 명시한다(문서 담당 작업자). `kanban serve`의 기본값은 이미 안전하다.
4. 새 환경 변수 `DATABASE_POOL_PRE_PING`을 `.env.example`에 추가한다(범위 밖).
5. 이번에 추가한 슬롯 제한 덕분에 앱 정체는 풀렸다. 공유 서버라면 `DATABASE_POOL_SIZE`/`DATABASE_MAX_OVERFLOW`를 Supabase 한도에 맞춘다(`PERFORMANCE_AUDIT.md` §7).

### 팀 규모가 커지면 할 것

6. 인증: 최소한 정적 API 키 헤더(`X-API-Key`)를 서버에 두고 CLI 환경 변수로 준다. 사용자별 구분이 필요하면 GitHub OAuth 후 `members.github_login`과 연결.
7. `TrustedHostMiddleware`(허용 호스트 고정), 요청 본문 크기 제한(프록시 또는 미들웨어), 요청 속도 제한.
8. 프런트엔드를 붙이면 CORS 허용 출처를 명시 목록으로.
9. 422의 `input` 에코를 줄이고(외부 노출 시), 로그에서 연결 문자열 마스킹을 확인한다.
10. 의존성 감사를 CI에 넣는다(`uvx pip-audit`). 현재 CI(`quality.yml`)에는 없다.
11. 서버를 외부에 열기 전: HTTPS 종단 프록시, Supabase 쪽 DB 역할을 최소 권한 역할로 분리(백엔드가 쓰는 테이블 6개만).
