# 성능 감사 (부하 테스트)

작성일 2026-10-19. 대상 커밋 `ffcb636` + 이 문서의 수정(아래 §6). 측정은 전부 이 맥에서 직접 돌린 값이다. 추정은 "추정"이라고 표시했다.

## 1. 환경과 방법

| 항목 | 값 |
|---|---|
| 기기 | MacBook Air M5, 16GB (팬 없음). 서버·클라이언트·DB가 같은 기기에서 CPU를 나눠 쓴다 |
| DB | PostgreSQL 16.14 (Homebrew, 로컬), 전용 DB `kanban_stress`(측정 후 삭제). `max_connections=100` |
| 서버 | `uvicorn app.main:app --port 8002 --workers 1`, FastAPI 0.146, SQLAlchemy 2.1.5, psycopg 3.3.6, Python 3.11 |
| 클라이언트 | `scripts/stress_test.py` (표준 라이브러리 raw asyncio, keep-alive 소켓 N개) |
| 초기 데이터 | 보드 1, 팀원 3, 카드 200장. 비교 실행마다 `TRUNCATE ... RESTART IDENTITY`로 되돌리고 다시 시드 |
| 기본 풀 | `pool_size=5`, `max_overflow=10`(최대 15), `pool_timeout=30s` |

재현:

```bash
createdb kanban_stress
export DATABASE_URL=postgresql+psycopg://localhost/kanban_stress
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8002 --workers 1 &     # DATABASE_POOL_SIZE 등은 환경 변수로
uv run python scripts/stress_test.py seed --url http://127.0.0.1:8002   # 보드 1 + 3명 + 200장
uv run python scripts/stress_test.py A --url http://127.0.0.1:8002
uv run python scripts/stress_test.py B --url http://127.0.0.1:8002
uv run python scripts/stress_test.py C --url http://127.0.0.1:8002
uv run python scripts/stress_test.py D --label 5/10 --url http://127.0.0.1:8002
```

측정 중 알게 된 도구 문제 하나: 처음에는 httpx로 부하를 줬는데, 동시 100 연결 이상에서 httpx 클라이언트 자체가 병목이었다
(같은 서버에 `ab -n 3000 -c 100 /health`는 2,129 req/s, p99 61ms인데 httpx 스크립트는 170 req/s에 p95 2초가 나왔다).
그래서 부하 생성기는 raw asyncio 소켓으로 바꿨고, 아래 표는 전부 그 클라이언트 값이다. 시드·카드 조회(동시 이동 대상 선택)에만 httpx를 쓴다.
같은 기기에서 돌리는 부하이므로 절대 수치보다 **수정 전후와 설정 간 상대 비교**로 읽는다. 같은 설정도 실행마다 ±15% 정도 흔들렸다.

## 2. 가장 큰 발견: 동시 요청이 풀 크기를 넘으면 앱이 멈춘다 (수정 전)

수정 전 코드(`ffcb636`)에서 `GET /boards/1/view` 동시 50은 정상(409 req/s)인데 **동시 100에서 거의 전부 실패**했다.

| 수정 전, 같은 시드(카드 200) | 동시 | RPS | 오류율 | 상태 코드 | p50 |
|---|---|---|---|---|---|
| GET view | 50 | 408.9 | 0% | 200×1000 | 116ms |
| GET view | 100 | 2.3 | 95.9% | 클라이언트 45초 타임아웃 847, 500 56, 200 41 | 45,005ms(=타임아웃) |
| GET cards?limit=50 | 100 | 2.4 | 95.2% | 타임아웃 830, 500 61, 200 48 | 45,006ms |
| POST cards (B) | 50 | 1.1 | 100% | 타임아웃 500 (실제로 만들어진 카드 58장) | 45,013ms |
| POST move (C) | 100 | 3.3 | 40% | 200 60, 500 40 | 30,125ms |

(첫 측정에서는 httpx로 120초 타임아웃을 줬는데 결과는 같은 모양이었다: B 500건 중 63% 오류, C 100건 전부 실패. 위 표는 raw 클라이언트·45초 타임아웃 값. 카드 조회 50 동시 행은 view 100 직후라 서버가 막힌 채로 시작해서 오염됐으므로 표에서 뺐다.)

서버 로그에는 `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`이 수백 번 찍혔고
(동시 100 한 번에 822건), 부하를 멈춘 뒤에도 한동안 `pg_stat_activity`에 연결 15개가 `idle in transaction`으로 남고 CPU는 0%였다.

### 원인

직접 확인한 것: 멈춘 서버에서 연결 15개가 `idle in transaction`, CPU 0%, 그리고 아래 덤프. 2~4번의 메커니즘은 실험으로 좁힌 해석이다(스레드 수만 15로 줄인 1차 시도는 여전히 정체했고, 세션 입장 제한을 넣자 사라졌다).

`faulthandler`로 멈춘 서버의 스레드를 덤프하니 워커 스레드 15개가 전부 `sqlalchemy/pool/impl.py _do_get → queue.get`(풀 체크아웃 대기)에 있었다.
구조는 이렇다.

1. 동기 라우트(`def`)는 anyio 스레드풀(기본 40)에서 돈다. 풀 연결은 최대 15개다.
2. 라우트가 끝난 요청도 `get_db`의 세션이 닫힐 때까지 연결을 쥔다. 세션은 응답 직렬화·dependency 정리 뒤에 닫히는데, 그 단계가 **스레드풀의 스레드를 또 필요로 한다**(동기 제너레이터 의존성의 정리와 응답 검증이 `run_in_threadpool`).
3. 동시 요청이 많으면 스레드 40개 중 25개 이상이 "연결을 기다리는 새 라우트"로 막힌다. 연결을 쥔 요청은 마무리할 스레드를 못 얻는다. 연결은 풀로 안 돌아온다. 서로 기다린다(교착).
4. `pool_timeout`(30초)이 지나서 대기 스레드가 500으로 죽어야 풀린다. 그 사이 새 요청이 또 들어와서 반복된다.

즉 "풀을 5+10으로 작게 잡았다"가 문제가 아니라, **스레드 수(40) > 연결 수(15) 구조에서 연결 반환이 스레드를 필요로 해서** 생긴 교착성 정체다.
풀 크기를 10/20, 20/40으로 키우면 교착 문턱만 올라가고 Supabase 무료 플랜의 연결 한도에는 더 빨리 닿는다.

### 수정 (`app/db/session.py`, `app/core/config.py`)

1. **세션 동시 보유 수를 연결 수와 같게 제한한다.** `get_db`가 `async` 의존성이 되어 이벤트 루프에서 `CapacityLimiter(pool_size + max_overflow)`로 먼저 입장권을 받고, 세션을 닫은 뒤에 반납한다. 연결을 못 얻어서 스레드가 막히는 일이 구조적으로 없어진다. 대기는 스레드가 아니라 이벤트 루프(싸다)에서 한다.
2. 입장권을 `DATABASE_POOL_TIMEOUT`초 안에 못 받으면 **503 `{"detail":"database busy, try again"}`**. 전에는 스택트레이스가 찍히는 500이었다.
3. `DbSession`에 `scope="function"`을 붙여 라우트가 반환하는 즉시 세션을 닫는다(응답 직렬화·전송 동안 연결을 쥐지 않는다). 정리 단계는 async라서 스레드를 기다리지 않는다.
4. `DATABASE_POOL_PRE_PING`(기본 true)를 환경 변수로 노출했다. 값은 그대로(켜짐)다.
5. `app/main.py`: Postgres가 거부하는 값(int64 초과 id·`position`·`issue_number`, 문자열 안의 NUL 바이트)이 500이 되던 것을 422로 바꿨다(보안 감사 §2의 항목).

테스트: `tests/test_session.py`(실제 `get_db`가 슬롯을 반납하는지, 슬롯이 없으면 503인지, 범위 초과 값이 422인지). `./scripts/check.sh` 통과.

## 3. 수정 후 시나리오별 결과 (기본 풀 5/10, 워커 1, 같은 시드 200장에서 시작)

### A. 동시 읽기 (요청 1,000개씩)

| 엔드포인트 | 동시 | RPS | p50 | p95 | p99 | 오류율 |
|---|---|---|---|---|---|---|
| GET /boards/1/view | 50 | 412.6 | 120ms | 137ms | 142ms | 0% |
| GET /boards/1/view | 100 | 409.6 | 243ms | 257ms | 262ms | 0% |
| GET /boards/1/view | 200 | 402.1 | 491ms | 513ms | 522ms | 0% |
| GET /boards/1/cards?limit=50 | 50 | 938.7 | 52ms | 64ms | 69ms | 0% |
| GET /boards/1/cards?limit=50 | 100 | 905.0 | 106ms | 120ms | 126ms | 0% |
| GET /boards/1/cards?limit=50 | 200 | 904.7 | 216ms | 229ms | 262ms | 0% |

처리량은 동시 수와 무관하게 일정하고(view ≈ 400, cards ≈ 900 req/s), 동시 수가 늘면 지연이 비례해서 늘어난다(대기열). 수정 전 같은 조건의 동시 50은 408.9 req/s로 **정상 경로 성능은 같다**(회귀 없음).

### B. 동시 쓰기: POST /boards/1/cards, 동시 50, 500건

| RPS | p50 | p95 | p99 | 오류율 | 만들어진 카드 | issue_number 중복 | position 중복 |
|---|---|---|---|---|---|---|---|
| 725.4 | 67ms | 73ms | 87ms | 0% (201×500) | 500 | 0 | 0 |

검증 SQL(스크립트가 실행): `select issue_number, count(*) from cards group by 1 having count(*)>1` → 0행,
`select stage_id, position, count(*) from cards group by 1,2 having count(*)>1` → 0행.

### C. 동시 이동: Todo 카드 100장을 동시에 Done으로 (동시 100)

| RPS | p50 | p95 | p99 | 오류율 | Done에 도착 | position 중복 | Done인데 closed_at 없음 | Done 아닌데 closed_at 있음 |
|---|---|---|---|---|---|---|---|---|
| 685.7 | 88ms | 140ms | 143ms | 0% (200×100) | 100 | 0 | 0 | 0 |

데이터 무결성은 수정 전(부하 중 일부만 성공한 상태)과 후 모두 깨지지 않았다. 어드바이저리 락(`pg_advisory_xact_lock(7001)`)이 제 역할을 한다.

### D. 커넥션 풀 스트레스 (수정 후, 동시 100/300, 요청 1,000개, 카드 700장)

풀 설정별 비교. `view`는 700장 응답(약 200KB), `health`는 `select 1` 한 번.

| 풀 (size/overflow) | 엔드포인트 | 동시 | RPS | 평균 | p95 | 오류 |
|---|---|---|---|---|---|---|
| 2/0 | view | 100 | 108.0 | 879ms | 937ms | 0 |
| 2/0 | view | 300 | 106.5 | 2,404ms | 2,833ms | 0 |
| 2/0 | cards?limit=50 | 100 | 280.2 | 340ms | 405ms | 0 |
| 2/0 | cards?limit=50 | 300 | 275.4 | 941ms | 1,128ms | 0 |
| 2/0 | health | 100 / 300 | 2,255 / 2,341 | 42 / 112ms | 49 / 136ms | 0 |
| 5/10 | view | 100 | 156.8 | 609ms | 671ms | 0 |
| 5/10 | view | 300 | 150.6 | 1,713ms | 2,031ms | 0 |
| 5/10 | cards?limit=50 | 100 | 879.6 | 109ms | 123ms | 0 |
| 5/10 | cards?limit=50 | 300 | 874.9 | 298ms | 347ms | 0 |
| 5/10 | health | 100 / 300 | 2,255 / 2,282 | 43 / 115ms | 55 / 132ms | 0 |
| 10/20 | view | 100 | 155.1 | 619ms | 710ms | 0 |
| 10/20 | view | 300 | 148.8 | 1,743ms | 2,094ms | 0 |
| 10/20 | cards?limit=50 | 100 | 880.3 | 110ms | 129ms | 0 |
| 10/20 | cards?limit=50 | 300 | 864.6 | 305ms | 372ms | 0 |
| 10/20 | health | 100 / 300 | 2,264 / 2,238 | 43 / 119ms | 50 / 151ms | 0 |

읽는 법:

- 5xx, `pool_timeout`, `TimeoutError`는 어느 설정에서도 0건. 수정 전에는 5/10에서 동시 100이면 거의 전부 실패했다(§2).
- 풀 5/10과 10/20은 차이가 없다(노이즈 범위). 풀을 키워도 처리량이 안 는다. 2/0은 카드 조회가 3배 느리다(280 vs 880 req/s). 이 부하에서는 **5/10이면 충분하고 2/0은 너무 작다**.
- 평균 지연은 동시 수에 비례(view: 100→300에서 0.6초→1.7초). 처리량이 일정할 때 줄 서는 시간이라는 뜻이고, 서버가 죽는 모양이 아니다.
- 대기 시간이 `pool_timeout`을 넘을 때의 동작: 풀 2/0 + `DATABASE_POOL_TIMEOUT=0.5` + 동시 300에서 view 1,000건 중 913건, cards 590건이 **503**, health 0건, 서버 로그의 `Traceback` 0건. 연결이 모자라면 느려지는 게 아니라 깨끗하게 거절된다.

### 워커 수와 `pool_pre_ping` (카드 2,003장 상태, 동시 100, 같은 기기에서 2회씩)

| 설정 | view RPS | cards RPS | health RPS |
|---|---|---|---|
| 워커 1, pre_ping 켬 | 47.7 / 39.2 | 766.7 / 665.2 | 1,824 / 1,797 |
| 워커 1, pre_ping 끔 | 33.6 / 34.4 | 624.2 / 768.2 | 1,832 / 2,114 |
| 워커 2, pre_ping 켬 | 77.0 / 75.3 | 1,211.9 / 1,252.6 | 3,012 / 3,107 |

- 워커 2개는 처리량이 약 1.6~1.9배다(파이썬 GIL 한계가 CPU 병목이라 워커를 늘리면 선형에 가깝게 는다). 단 풀이 워커마다 따로이므로 최대 연결 수는 2×15=30이다. Supabase에서는 한도를 먼저 확인한다.
- pre_ping 켬/끔은 로컬에서 구분되지 않는다(실행 간 노이즈가 더 크다). 로컬 왕복이 ~0.1ms라서 그렇고, 원격 DB에서는 §7.

## 4. 병목 분석

### 4.1 view가 카드 수에 비례해서 느려진다 (CPU 병목, 가장 큰 남은 항목)

같은 코드, 동시 50~100, 카드 수만 다르게:

| 카드 수 | view RPS (동시 100 전후) | 응답 크기 |
|---|---|---|
| 200 | 409.6 | 약 65KB |
| 700 | 156.8 (풀 5/10) | 약 200KB |
| 2,003 | 39~48 | 약 570KB |

`app/services/view.py`가 `limit=1_000_000`으로 **보드의 모든 카드를 한 번에** 읽고 카드마다 `CardOut`을 만든 뒤 FastAPI가 응답 모델로 한 번 더 검증·직렬화한다. 풀을 늘려도 안 빨라지는 이유가 이것이다(CPU, GIL).
참고로 2,000장 기준 `board_view()`(쿼리+`to_out`)가 23~51ms, `model_dump_json`이 1.4ms로 측정됐다. 나머지는 FastAPI 응답 검증과 소켓 전송이라고 **추정**한다(별도 프로파일은 안 했다).
수업 규모(카드 수십~수백 장)에서는 문제가 아니다. 카드가 수천 장이 되면 권고 §8을 적용한다.

### 4.2 N+1은 없다

SQLAlchemy `before_cursor_execute` 훅으로 센 실제 쿼리 수(카드 200장):

| 요청 | 쿼리 수 | 내용 |
|---|---|---|
| GET /boards/1/view | 3 | boards, stages, cards(+`joinedload` stage/assignee/milestone 한 쿼리) |
| GET /boards/1/cards?limit=50 | 2 | boards, cards(joinedload) |
| GET /cards/{id} | 1 | joinedload 한 쿼리 |
| GET /health | 1 | `select 1` |
| POST /boards/1/cards | 8 | board, stage, advisory lock, max(issue_number), max(position), max(stage.position), INSERT, 재조회 |

카드 수가 늘어도 쿼리 수는 그대로다. 단 `max(issue_number)`는 `cards` 전체에서 집계한다. `issue_number`에 UNIQUE 인덱스가 있어서 인덱스 스캔이지만(추정, EXPLAIN은 안 봄), 카드가 수십만이 되기 전에는 영향이 없다.

### 4.3 쓰기는 어드바이저리 락 하나가 직렬화한다

`create_card`·`move_card`는 전역 키 7001의 `pg_advisory_xact_lock`을 잡고 `issue_number`·`position`을 계산한 뒤 커밋까지 쥔다. 보드가 달라도 같은 락이다.

| 카드 생성 | RPS | 평균 지연 |
|---|---|---|
| 동시 1 | 214.7 | 4.7ms |
| 동시 10 | 707.0 | 14.1ms |
| 동시 50 | 747.2 | 64.2ms |

동시 10에서 이미 천장(약 750 req/s)이다. 천장 = 1/(락 구간 시간)이고 이 맥에서 락 구간은 약 1.3ms다(계산값). 정확성(중복 0)을 대가로 쓰기 처리량이 락으로 정해진다. 로컬에서는 수업에 충분하지만 DB 왕복이 느린 환경에서는 §7처럼 훨씬 낮아진다.

### 4.4 /health

`select 1` 한 번이고 풀 슬롯을 하나 쓴다. 로컬 2,255 req/s(동시 100). 비용 문제는 없다. 다만 풀이 꽉 찼을 때 헬스체크도 슬롯을 기다리므로 503이 될 수 있다. 이건 "DB가 바쁘다"는 정확한 신호이기도 하다.

### 4.5 스레드풀 40 vs 풀 15

수정 전 교착의 원인(§2). 수정으로 라우트 스레드가 연결을 기다리며 막히는 일이 없어졌다. 동시 DB 요청은 프로세스당 `pool_size + max_overflow`개로 상한이 생겼고, 그 위는 이벤트 루프 대기열에 쌓인다(동시 300에서도 오류 0, 지연만 증가).

## 5. 수정 전후 비교 요약

| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| view 동시 50 | 408.9 req/s, 오류 0 | 412.6 req/s, 오류 0 |
| view 동시 100 | 2.3 req/s, 오류 95.9%, p50 45초(타임아웃) | 409.6 req/s, 오류 0, p50 243ms |
| view 동시 200 | (측정 불가: 정체) | 402.1 req/s, 오류 0, p50 491ms |
| cards 동시 100 | 2.4 req/s, 오류 95.2% | 905.0 req/s, 오류 0 |
| POST 카드 동시 50 | 오류 100%(타임아웃 500건) | 725.4 req/s, 오류 0, 중복 0 |
| 동시 이동 100 | 오류 40%(500 40건), p50 30초 | 오류 0, 685.7 req/s |
| 풀이 모자랄 때 | 500 + 스택트레이스 | 503 `database busy` |
| 범위 초과 값(id·position·NUL) | 500 | 422 |

## 6. 변경한 파일

- `app/db/session.py`: async `get_db` + 슬롯 제한 + 503, `DbSession`에 `scope="function"`, pre_ping 설정 연결.
- `app/core/config.py`: `database_pool_pre_ping`(환경 변수 `DATABASE_POOL_PRE_PING`, 기본 true).
- `app/main.py`: `sqlalchemy.exc.DataError` → 422.
- `tests/test_session.py`(새 파일), `scripts/stress_test.py`(새 파일), `docs/DESIGN.md`(환경 변수 표 한 줄과 풀 대기 동작 한 줄).

풀 기본값(5/10/30초)은 **바꾸지 않았다**. 측정에서 10/20이 5/10보다 낫지 않았고, 줄이면(2/0) 카드 조회가 3배 느려졌기 때문이다.

## 7. Supabase 무료 플랜에서의 예상과 권고

아래는 이번에 Supabase에 접속하지 않았으므로 **전부 코드에서 계산한 추정이거나 일반 지식**이다. 한도 숫자는 사용 시점의 공식 문서로 확인한다.

1. **왕복 수가 곧 지연이다.** 로컬에서는 왕복이 ~0.1ms라서 안 보이지만 원격 DB는 왕복마다 RTT가 붙는다. 코드에서 센 왕복: view ≈ 3 쿼리 + pre_ping 1 + 반환 시 롤백 1 ≈ 5회, 카드 생성 ≈ 8 쿼리 + 커밋 + pre_ping + 롤백 ≈ 11회. RTT가 30ms이면 view ≈ 150ms, 카드 생성 ≈ 330ms, RTT가 100ms이면 각각 ≈ 0.5초, ≈ 1.1초다(추정).
2. **쓰기 직렬화가 훨씬 아프다.** 어드바이저리 락은 락 획득부터 커밋까지(약 6왕복) 쥔다. RTT 30ms이면 전역 쓰기 처리량 ≈ 5건/초, 100ms이면 ≈ 1.7건/초가 천장이다(추정). 팀 5~6명이 가끔 쓰는 규모는 문제없다. Codex·CLI가 한꺼번에 수십 장을 쓰면 줄 서고, 줄이 `pool_timeout`(30초)을 넘으면 이제는 503이다.
3. **연결 한도.** 세션 풀러는 클라이언트 연결 수에 한도가 있다(무료 플랜의 정확한 숫자는 확인 필요). 앱은 프로세스당 최대 15개를 쓴다. 한도를 다른 도구(대시보드, 마이그레이션)와 나눠 쓰면 `DATABASE_POOL_SIZE=3 DATABASE_MAX_OVERFLOW=2` 정도로 줄인다. 슬롯 제한 덕분에 풀을 줄여도 터지지 않고 줄만 길어진다(로컬 2/0 측정: 오류 0).
4. **pre_ping.** 풀러가 유휴 연결을 끊는 경우가 있어 켜 둔 채가 안전하다. 왕복 한 번이 더 붙는다. 원격 RTT가 클 때 줄이고 싶으면 `DATABASE_POOL_PRE_PING=false`와 `pool_recycle`(예: 300초) 조합을 쓰되 끊긴 연결에서 첫 요청이 한 번 실패할 수 있다. 이번 측정으로 효과를 확인하진 않았다.
5. **워커 1개가 권장.** 연결 한도가 작은 환경에서 워커를 늘리면 연결이 배로 든다.
6. 서버는 로컬 노트북, DB는 원격이면 노트북 ↔ Supabase 왕복이 매 요청에 들어간다. 지연이 거슬리면 서버를 DB와 같은 리전에 두는 것이 가장 크게 먹힌다(추정).

## 8. 권고 (이번 범위 밖 파일)

지금 하면 좋은 것:

1. `app/services/cards.py` `create_card`/`move_card`: 락 구간 안의 왕복을 줄인다. 보드·단계·담당자·마일스톤 해석을 락 **앞**에 이미 하고 있으니, 락 안에서는 `INSERT ... SELECT coalesce(max(...),0)+1` 한 문장으로 `issue_number`·`position`을 계산해 왕복을 6회에서 2회 정도로 줄이는 방안을 검토한다. 락 키를 보드별로 나누면(`pg_advisory_xact_lock(7001, board_id)`) `position`은 보드별로 병렬화되지만 `issue_number`가 전역 UNIQUE라서 그 계산은 여전히 전역 락이 필요하다. 설계 결정(DESIGN.md §2)을 바꾸는 일이므로 문서 먼저.
2. `app/services/view.py`: 카드가 수백 장을 넘기 시작하면 단계별 `limit` 또는 `closed_at` 오래된 Done 카드 접기를 넣는다. 현재는 `limit=1_000_000`이다.
3. `.env.example`과 `docs/DATABASE.md`/`TSD.md`에 `DATABASE_POOL_PRE_PING`과 "풀 대기 후 503"을 반영한다(문서 담당 작업자).
4. `scripts/check.sh`/CI에 부하 테스트는 넣지 않는다(오래 걸리고 기기 의존적). 필요하면 `scripts/stress_test.py D --conc 100`만 수동으로.

팀 규모가 커지면:

5. 카드 목록 `offset` 기반 페이지네이션을 `(stage position, card position, id)` 키셋으로 바꾼다.
6. `cards (stage_id, position)` 복합 인덱스 여부를 `EXPLAIN`으로 확인한다(이번엔 확인 안 했다. 스키마를 바꾸지 않는다는 DESIGN.md §2와 충돌하므로 결정 먼저).
7. 멀티 인스턴스로 가면 어드바이저리 락 대신 DB 시퀀스·`UNIQUE` 충돌 재시도로 `issue_number`를 발급한다.
