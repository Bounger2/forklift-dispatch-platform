from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import Alert
from ..utils import auth_required, current_user, error, response, role_required

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.get("")
@auth_required
def list_alerts():
    status = request.args.get("status", "open")
    severity = request.args.get("severity", "")
    alert_type = request.args.get("alertType", "")
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if status:
        stmt = stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    rows = g.db.scalars(stmt).all()
    return response([row.to_dict() for row in rows])


@bp.post("/<int:alert_id>/close")
@role_required("admin")
def close_alert(alert_id):
    alert = g.db.get(Alert, alert_id)
    if not alert:
        return error("alert not found", 404)
    data = request.get_json(silent=True) or {}
    alert.status = "closed"
    alert.closed_at = datetime.utcnow()
    alert.closed_by = current_user()
    if data.get("message"):
        alert.suggestion = f"{alert.suggestion}\n处理结果：{data['message']}"
    g.db.commit()
    return response(alert.to_dict(), "closed")


@bp.post("/batch-close")
@role_required("admin")
def batch_close_alerts():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return error("ids required", 400)

    clean_ids = sorted({int(alert_id) for alert_id in ids if str(alert_id).isdigit()})
    if not clean_ids:
        return error("ids required", 400)

    rows = g.db.scalars(
        select(Alert).where(Alert.id.in_(clean_ids), Alert.status == "open")
    ).all()
    closed_at = datetime.utcnow()
    closer = current_user()
    message = (data.get("message") or "").strip()

    for alert in rows:
        alert.status = "closed"
        alert.closed_at = closed_at
        alert.closed_by = closer
        if message:
            alert.suggestion = f"{alert.suggestion}\n处理结果：{message}"

    g.db.commit()
    return response(
        {"closed": len(rows), "requested": len(clean_ids), "ids": [alert.id for alert in rows]},
        "closed",
    )
