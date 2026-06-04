from flask import Blueprint, g, request

from ..services.metrics import daily_report, driver_period_report, overview_metrics
from ..utils import auth_required, current_user, error, response, role_required

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/daily")
@auth_required
def daily():
    return response(daily_report(g.db))


@bp.get("/overview")
@auth_required
def report_overview():
    return response(overview_metrics(g.db))


@bp.get("/drivers")
@role_required("admin")
def driver_report():
    period = request.args.get("period", "week")
    return response(driver_period_report(g.db, period))


@bp.get("/me")
@role_required("driver")
def my_driver_report():
    driver = current_user().driver
    if not driver:
        return error("driver profile not found", 404)
    period = request.args.get("period", "week")
    return response(driver_period_report(g.db, period, driver_id=driver.id))
