# Kanban Board

팀이 함께 쓰는 간반 보드의 백엔드 API입니다. FastAPI + SQLAlchemy + PostgreSQL로 만들었고, 과제#5에서 설계한 보드 DB(테이블 6개)를 그대로 사용합니다. Python 3.11과 `uv`로 실행합니다. 설계 결정은 [docs/DESIGN.md](docs/DESIGN.md)에 있습니다.

## 시작하기

### 준비

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 (로컬) 또는 Supabase

```sh
uv sync --all-groups
cp .env.example .env   # 필요하면 DATABASE_URL을 고칩니다
```

### 데이터베이스 준비

로컬 Postgres에 빈 DB를 만들고 마이그레이션을 적용합니다.

```sh
createdb kanban
uv run alembic upgrade head
```

마이그레이션(`alembic/versions/0001_kanban_v3.py`)은 `create table if not exists`, `create index if not exists`, `create or replace view`로 되어 있어서 **여러 번 실행해도 안전하고, 이미 테이블이 있는 DB에서는 건너뜁니다.**

실제 GitHub 데이터 시드(보드 1개, 팀원 4명, 카드 27장 등 47행)는 이 저장소에 복사하지 않았습니다. 필요하면 과제#5 폴더의 SQL을 적용합니다.

```sh
psql -d kanban -f ../../side-projects/kanban-db/sql/002_seed.sql
```

시드는 `alembic upgrade head` 뒤에 한 번만 넣으세요. 이미 데이터가 있는 DB(Supabase 포함)에 다시 넣으면 중복으로 실패합니다. (`001_schema.sql`은 테이블을 DROP 하므로 실행하지 마세요.)

### API 서버 실행

```sh
uv run uvicorn app.main:app --reload --host 127.0.0.1
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- 상태 확인: <http://127.0.0.1:8000/api/v1/health> (`/health`도 같은 응답)
- 보드 화면: <http://127.0.0.1:8000/api/v1/boards/1/view>

서버는 기본적으로 이 컴퓨터에서만 접근할 수 있는 `127.0.0.1`에 바인딩합니다. 인증 기능이 없으므로 신뢰할 수 없는 네트워크에 공개하지 마세요.

### API 사용 예

```sh
curl -X POST http://127.0.0.1:8000/api/v1/boards/1/cards \
  -H 'Content-Type: application/json' \
  -d '{"title": "로그인 화면 만들기", "stage": "In Progress", "assignee": "cosuss"}'

curl -X POST http://127.0.0.1:8000/api/v1/cards/1/move \
  -H 'Content-Type: application/json' -d '{"stage": "Done"}'
```

카드의 단계·담당자·마일스톤은 이름(`stage`, `assignee`, `milestone`)이나 id(`stage_id` 등) 중 하나로 지정합니다. `issue_number`, `position`, `created_at`, `closed_at`은 서버가 채웁니다. 자세한 규칙은 [docs/DESIGN.md](docs/DESIGN.md) 2~3절을 보세요.

## Supabase에 연결하기

1. Supabase 대시보드의 Connect에서 **Session pooler** 연결 문자열(URI)을 복사합니다.
2. `.env`의 `DATABASE_URL`에 그대로 붙여 넣습니다. `postgresql://`로 시작해도 앱이 `postgresql+psycopg://`로 바꿔 씁니다.
3. 마이그레이션을 적용합니다.

   ```sh
   uv run alembic upgrade head
   ```

   과제#5에서 이미 만든 6개 테이블과 `v_board` 뷰가 있으면 건너뛰고, 없는 것만 만듭니다. 기존 데이터는 건드리지 않습니다.
4. 서버를 실행합니다. 연결 풀 크기는 `DATABASE_POOL_SIZE`(기본 5)와 `DATABASE_MAX_OVERFLOW`(기본 10)로 조절합니다. 무료 플랜의 세션 풀러 한도를 넘지 않게 작게 두었습니다.

6개 테이블은 RLS가 켜져 있고 정책이 없으므로 anon 키로는 접근할 수 없습니다. 이 백엔드가 DB 연결 문자열로 직접 접속합니다. `.env`와 연결 문자열(비밀번호 포함)은 커밋하지 마세요.

## 테스트와 품질 검사

테스트는 실제 Postgres의 **별도 DB**(`kanban_test`)를 사용합니다. 테스트마다 6개 테이블을 `TRUNCATE ... RESTART IDENTITY CASCADE`로 비우므로 운영 DB를 지정하면 안 됩니다.

```sh
createdb kanban_test
export TEST_DATABASE_URL=postgresql+psycopg://localhost/kanban_test   # 기본값과 같음
./scripts/check.sh      # ruff check + ruff format --check + pytest
./scripts/fix.sh        # 안전한 lint/format 자동 수정
./scripts/install-git-hooks.sh   # pre-commit에서 check.sh 실행
```

GitHub Actions(`.github/workflows/quality.yml`)는 `postgres:16` 컨테이너를 띄우고 같은 `check.sh`를 실행합니다.

## 구조

```text
app/
  main.py            FastAPI 앱, /api/v1 라우터, /health
  core/              설정(환경 변수), 도메인 오류
  db/                엔진·세션·Base
  models/            SQLAlchemy 매핑 (과제#5 v3 스키마와 동일)
  schemas/           Pydantic 입출력
  services/          비즈니스 규칙 (issue_number, position, closed_at, 삭제 규칙)
  api/routes/        boards, members, stages, milestones, cards, comments, health
alembic/             마이그레이션 0001_kanban_v3 (raw SQL, IF NOT EXISTS)
tests/               pytest (실제 Postgres)
```
