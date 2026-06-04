from flask import Blueprint, current_app, g
from sqlalchemy import select

from ..models import Alert, Forklift, MapPoint, TransportTask
from ..services.gps import sync_latest_positions
from ..services.metrics import driver_day_gantt, overview_metrics
from ..services.simulator import advance_simulation
from ..utils import auth_required, response

bp = Blueprint("overview", __name__, url_prefix="/api")


@bp.get("/overview")
@auth_required
def overview():
    if current_app.config["SIMULATION_ENABLED"]:
        advance_simulation(g.db, current_app.config["SIMULATION_STEP_SECONDS"])
        g.db.commit()
    else:
        sync_latest_positions(g.db)
        g.db.commit()
    tasks = g.db.scalars(
        select(TransportTask).order_by(TransportTask.updated_at.desc()).limit(12)
    ).all()
    alerts = g.db.scalars(
        select(Alert).where(Alert.status == "open").order_by(Alert.created_at.desc()).limit(10)
    ).all()
    vehicles = g.db.scalars(select(Forklift).order_by(Forklift.code)).all()
    points = g.db.scalars(select(MapPoint).where(MapPoint.enabled.is_(True))).all()
    return response(
        {
            "metrics": overview_metrics(g.db),
            "vehicles": [v.to_dict() for v in vehicles],
            "tasks": [t.to_dict() for t in tasks],
            "alerts": [a.to_dict() for a in alerts],
            "mapPoints": [p.to_dict() for p in points],
            "driverGantt": driver_day_gantt(g.db),
        }
    )
