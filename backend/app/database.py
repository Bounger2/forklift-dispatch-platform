from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from .config import Config


Base = declarative_base()

engine = create_engine(
    Config.DATABASE_URL,
    echo=Config.SQL_ECHO,
    future=True,
    pool_pre_ping=True,
)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()


def ensure_schema_columns():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "forklifts" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("forklifts")}
    additions = []
    if "power_type" not in columns:
        additions.append("ADD COLUMN power_type VARCHAR(32) DEFAULT 'electric'")
    if "fuel_level" not in columns:
        additions.append("ADD COLUMN fuel_level INTEGER DEFAULT 0")
    with engine.begin() as conn:
        for clause in additions:
            conn.execute(text(f"ALTER TABLE forklifts {clause}"))
        conn.execute(
            text(
                "UPDATE forklifts "
                "SET power_type='diesel', fuel_level=CASE WHEN fuel_level=0 THEN battery_level ELSE fuel_level END, battery_level=0 "
                "WHERE model LIKE '%柴油%' AND power_type='electric'"
            )
        )

    if "map_points" in table_names:
        columns = {column["name"] for column in inspector.get_columns("map_points")}
        additions = []
        if "lat" not in columns:
            additions.append("ADD COLUMN lat DOUBLE NULL")
        if "lng" not in columns:
            additions.append("ADD COLUMN lng DOUBLE NULL")
        if "is_temporary" not in columns:
            additions.append("ADD COLUMN is_temporary BOOLEAN DEFAULT FALSE")
        with engine.begin() as conn:
            for clause in additions:
                conn.execute(text(f"ALTER TABLE map_points {clause}"))
            conn.execute(
                text(
                    "UPDATE map_points "
                    "SET is_temporary=1 "
                    "WHERE is_temporary=0 AND ("
                    "area='任务临时点' "
                    "OR description='发布搬运任务地图标点自动生成' "
                    "OR name LIKE '临时取货点-%' "
                    "OR name LIKE '临时送货点-%'"
                    ")"
                )
            )
            if "transport_tasks" in table_names:
                conn.execute(
                    text(
                        "UPDATE map_points "
                        "SET enabled=0 "
                        "WHERE is_temporary=1 AND enabled=1 AND id IN ("
                        "SELECT origin_point_id FROM transport_tasks WHERE status='completed' "
                        "UNION "
                        "SELECT dest_point_id FROM transport_tasks WHERE status='completed'"
                        ")"
                    )
                )


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
