from datetime import date

from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import Driver, Forklift, ScheduleAssignment, ShiftTemplate, VehicleBinding
from ..utils import auth_required, error, response, role_required

bp = Blueprint("schedules", __name__, url_prefix="/api/schedules")


@bp.get("")
@auth_required
def schedules():
    templates = g.db.scalars(select(ShiftTemplate).order_by(ShiftTemplate.code)).all()
    assignments = g.db.scalars(
        select(ScheduleAssignment).order_by(ScheduleAssignment.shift_date.desc())
    ).all()
    bindings = g.db.scalars(select(VehicleBinding).order_by(VehicleBinding.bound_at.desc())).all()
    return response(
        {
            "shiftTemplates": [row.to_dict() for row in templates],
            "assignments": [row.to_dict() for row in assignments],
            "bindings": [row.to_dict() for row in bindings],
        }
    )


def _parse_date(value):
    if not value:
        return date.today()
    return date.fromisoformat(value)


@bp.post("/assignments")
@role_required("admin")
def create_assignment():
    data = request.get_json(force=True)
    driver = g.db.get(Driver, int(data["driverId"]))
    forklift_id = data.get("forkliftId")
    forklift = g.db.get(Forklift, int(forklift_id)) if forklift_id else None
    if not driver:
        return error("driver not found", 404)
    if forklift_id and not forklift:
        return error("forklift not found", 404)
    assignment = ScheduleAssignment(
        shift_date=_parse_date(data.get("shiftDate")),
        shift_code=data.get("shiftCode", "DAY"),
        driver=driver,
        forklift=forklift,
        area=data.get("area", "全厂"),
        status=data.get("status", "scheduled"),
    )
    driver.shift_status = "on_shift" if assignment.status in {"scheduled", "signed_in"} else driver.shift_status
    g.db.add(assignment)
    g.db.commit()
    return response(assignment.to_dict(), "created", 201)


@bp.patch("/assignments/<int:assignment_id>")
@role_required("admin")
def update_assignment(assignment_id):
    assignment = g.db.get(ScheduleAssignment, assignment_id)
    if not assignment:
        return error("assignment not found", 404)
    data = request.get_json(force=True)
    if "shiftDate" in data:
        assignment.shift_date = _parse_date(data.get("shiftDate"))
    if "shiftCode" in data:
        assignment.shift_code = data["shiftCode"]
    if "driverId" in data and data["driverId"]:
        driver = g.db.get(Driver, int(data["driverId"]))
        if not driver:
            return error("driver not found", 404)
        assignment.driver = driver
    if "forkliftId" in data:
        forklift_id = data.get("forkliftId")
        assignment.forklift = g.db.get(Forklift, int(forklift_id)) if forklift_id else None
        if forklift_id and not assignment.forklift:
            return error("forklift not found", 404)
    if "area" in data:
        assignment.area = data["area"]
    if "status" in data:
        assignment.status = data["status"]
    g.db.commit()
    return response(assignment.to_dict())


@bp.delete("/assignments/<int:assignment_id>")
@role_required("admin")
def delete_assignment(assignment_id):
    assignment = g.db.get(ScheduleAssignment, assignment_id)
    if not assignment:
        return error("assignment not found", 404)
    g.db.delete(assignment)
    g.db.commit()
    return response({"id": assignment_id}, "deleted")
