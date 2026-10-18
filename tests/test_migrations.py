from sqlalchemy import Engine, inspect, text

from alembic import command
from tests.conftest import alembic_config

EXPECTED = {"boards", "members", "stages", "milestones", "cards", "comments"}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) & EXPECTED


def test_upgrade_twice_is_idempotent_and_keeps_data(engine: Engine) -> None:
    command.upgrade(alembic_config(), "head")
    with engine.begin() as connection:
        connection.execute(text("insert into boards (name) values ('keep me')"))
    command.upgrade(alembic_config(), "head")
    assert _tables(engine) == EXPECTED
    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from boards")) == 1
        # the view exists and is queryable
        assert connection.execute(text("select * from v_board")).fetchall() == []


def test_rls_enabled_and_table_comments(engine: Engine) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "select c.relname, c.relrowsecurity, obj_description(c.oid) "
                "from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                "where n.nspname = 'public' and c.relname = any(:names)"
            ),
            {"names": sorted(EXPECTED)},
        ).fetchall()
    assert {row[0] for row in rows} == EXPECTED
    assert all(row[1] for row in rows)
    assert all(row[2] for row in rows)


def test_downgrade_then_upgrade_restores_schema(engine: Engine) -> None:
    command.downgrade(alembic_config(), "base")
    assert _tables(engine) == set()
    command.upgrade(alembic_config(), "head")
    assert _tables(engine) == EXPECTED
