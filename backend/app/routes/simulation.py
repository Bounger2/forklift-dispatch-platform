from flask import Blueprint, current_app, g

from ..seed import seed_all
from ..services.simulator import advance_simulation
from ..utils import response, role_required

bp = Blueprint("simulation", __name__, url_prefix="/api/simulation")


@bp.post("/tick")
@role_required("admin")
def tick():
    advance_simulation(g.db, current_app.config["SIMULATION_STEP_SECONDS"])
    g.db.commit()
    return response({"advanced": True})


@bp.post("/reset")
@role_required("admin")
def reset():
    seed_all(g.db, reset=True)
    return response({"reset": True})
