"""Standalone simulator for forklift GPS movement and full workday workflow.

Run from the backend directory:
    python scripts/gps_simulator.py --interval 2 --ticks 300
    python scripts/gps_simulator.py --mode workday --ticks 160 --step-seconds 90

The simulator writes records into forklift_positions. Assigned tasks stay still
until the driver accepts them in the system. Accepted tasks are moved from the
current vehicle location to the pickup point, then to the dropoff point. When
the destination unloading step completes, the task is closed and distance is
calculated from the generated GPS track.

Workday mode additionally simulates admin task publishing, dispatch assignment,
driver acceptance, forklift travel and task completion. It keeps at most one
pending dispatch task in the pool.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.database import SessionLocal, session_scope  # noqa: E402
from app.models import Forklift, TransportTask  # noqa: E402
from app.services.simulator import advance_simulation  # noqa: E402
from app.services.workday_simulator import run_workday_simulation  # noqa: E402


def snapshot(session):
    active_tasks = session.query(TransportTask).filter(
        TransportTask.status.in_(
            ["accepted", "to_origin", "arrived_origin", "loading", "transporting", "arrived_dest", "unloading"]
        )
    ).count()
    vehicles = session.query(Forklift).count()
    return vehicles, active_tasks


def main():
    parser = argparse.ArgumentParser(description="Generate simulated forklift GPS data and workday workflow.")
    parser.add_argument("--mode", choices=["movement", "workday"], default="movement", help="movement only or full workday workflow.")
    parser.add_argument("--interval", type=float, default=2, help="Seconds between GPS ticks.")
    parser.add_argument("--ticks", type=int, default=0, help="Number of ticks, 0 means run forever.")
    parser.add_argument("--step-seconds", type=int, default=5, help="Virtual seconds advanced per tick.")
    parser.add_argument("--max-created", type=int, default=80, help="Maximum tasks generated in workday mode.")
    parser.add_argument("--driver-limit", type=int, default=0, help="Limit online drivers in workday mode, 0 means all active drivers.")
    parser.add_argument("--rollback", action="store_true", help="Run the workday simulation and roll back database changes.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.mode == "workday":
            ticks = args.ticks if args.ticks > 0 else 160
            session = SessionLocal()
            try:
                stats = run_workday_simulation(
                    session,
                    ticks=ticks,
                    step_seconds=args.step_seconds,
                    max_created=args.max_created,
                    driver_limit=args.driver_limit or None,
                    verbose=True,
                )
                if args.rollback:
                    session.rollback()
                    stats["database"] = "rolled_back"
                else:
                    session.commit()
                    stats["database"] = "committed"
                print(json.dumps(stats, ensure_ascii=False, indent=2))
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
            return

        tick = 0
        while args.ticks <= 0 or tick < args.ticks:
            tick += 1
            with session_scope() as session:
                advance_simulation(session, args.step_seconds)
                vehicles, active_tasks = snapshot(session)
                print(f"tick={tick} vehicles={vehicles} activeTasks={active_tasks}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
