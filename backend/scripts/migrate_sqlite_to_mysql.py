import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402
from app.database import Base  # noqa: E402
from app import models  # noqa: F401,E402


DEFAULT_SQLITE_URL = f"sqlite:///{(BACKEND_DIR / 'instance' / 'dispatch_dev.db').as_posix()}"


def mysql_database_name(url):
    parsed = make_url(url)
    if not parsed.drivername.startswith("mysql"):
        return None
    return parsed.database


def create_mysql_database_if_needed(target_url):
    parsed = make_url(target_url)
    database = mysql_database_name(target_url)
    if not database:
        return
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError(f"不安全的数据库名：{database}")

    server_url = parsed.set(database=None)
    engine = create_engine(server_url, future=True, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
            )
        )


def migrate(source_url, target_url, reset=False, create_database=True):
    if make_url(source_url) == make_url(target_url):
        raise ValueError("源数据库和目标数据库不能相同")

    if create_database:
        create_mysql_database_if_needed(target_url)

    source_engine = create_engine(source_url, future=True)
    target_engine = create_engine(target_url, future=True, pool_pre_ping=True)

    if reset:
        Base.metadata.drop_all(bind=target_engine)
    Base.metadata.create_all(bind=target_engine)

    counts = {}
    tables = list(Base.metadata.sorted_tables)
    source_inspector = inspect(source_engine)
    source_table_names = set(source_inspector.get_table_names())
    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        for table in tables:
            if table.name not in source_table_names:
                counts[table.name] = 0
                continue
            source_columns = {column["name"] for column in source_inspector.get_columns(table.name)}
            selected_columns = [table.c[name] for name in table.c.keys() if name in source_columns]
            rows = [dict(row) for row in source_conn.execute(select(*selected_columns)).mappings()]
            if rows:
                target_conn.execute(table.insert(), rows)
            counts[table.name] = len(rows)

    return counts


def main():
    parser = argparse.ArgumentParser(description="把本地 SQLite 演示数据迁移到当前 DATABASE_URL 指向的 MySQL。")
    parser.add_argument("--source-url", default=DEFAULT_SQLITE_URL, help="源 SQLite 连接串")
    parser.add_argument("--target-url", default=Config.DATABASE_URL, help="目标 MySQL 连接串，默认读取 backend/.env")
    parser.add_argument("--reset", action="store_true", help="先清空并重建目标库表，再复制数据")
    parser.add_argument("--skip-create-database", action="store_true", help="不自动创建 MySQL 数据库")
    args = parser.parse_args()

    counts = migrate(
        source_url=args.source_url,
        target_url=args.target_url,
        reset=args.reset,
        create_database=not args.skip_create_database,
    )
    print("SQLite -> MySQL 迁移完成")
    for table_name, count in counts.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
