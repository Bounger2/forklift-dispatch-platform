import argparse

import pymysql


def main():
    parser = argparse.ArgumentParser(description="创建调度系统 MySQL 数据库和业务账号。")
    parser.add_argument("--root-user", default="root")
    parser.add_argument("--root-password", default="root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=3306, type=int)
    parser.add_argument("--database", default="forklift_dispatch")
    parser.add_argument("--app-user", default="dispatch_user")
    parser.add_argument("--app-password", default="dispatch_password")
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.root_user,
        password=args.root_password,
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{args.database}` "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                f"CREATE USER IF NOT EXISTS {args.app_user!r}@'localhost' "
                f"IDENTIFIED BY {args.app_password!r}"
            )
            cursor.execute(
                f"ALTER USER {args.app_user!r}@'localhost' "
                f"IDENTIFIED BY {args.app_password!r}"
            )
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON `{args.database}`.* TO {args.app_user!r}@'localhost'"
            )
            cursor.execute("FLUSH PRIVILEGES")
    finally:
        conn.close()

    print(f"MySQL 数据库 `{args.database}` 和用户 `{args.app_user}` 已准备完成")


if __name__ == "__main__":
    main()
