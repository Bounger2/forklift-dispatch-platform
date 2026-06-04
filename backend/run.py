import argparse

from app import create_app
from app.database import session_scope
from app.seed import seed_all

app = create_app()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="run", choices=["run", "seed", "reset"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5000, type=int)
    args = parser.parse_args()

    if args.command in {"seed", "reset"}:
        with session_scope() as session:
            seed_all(session, reset=args.command == "reset")
        print(f"database {args.command} completed")
        return

    with session_scope() as session:
        seed_all(session)
    app.run(host=args.host, port=args.port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
