from flask import Blueprint, g, request
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from datetime import datetime

from ..models import Driver, User, VehicleBinding
from ..utils import error, response, role_required

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@role_required("admin")
def list_users():
    rows = g.db.scalars(
        select(User).where(User.role.in_(["admin", "driver"])).order_by(User.role, User.username)
    ).all()
    return response([row.to_dict() for row in rows])


@bp.post("")
@role_required("admin")
def create_user():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or "123456"
    role = data.get("role")
    name = (data.get("name") or "").strip()
    if role not in {"admin", "driver"}:
        return error("role must be admin/driver", 400)
    if not username or not name:
        return error("username and name are required", 400)
    if g.db.scalar(select(User).where(User.username == username)):
        return error("username already exists", 409)

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        name=name,
        role=role,
        phone=data.get("phone", ""),
        wecom_user_id=data.get("wecomUserId", ""),
        department=data.get("department", "物流部"),
        team=data.get("team", ""),
        status=data.get("status", "active"),
    )
    g.db.add(user)
    g.db.flush()

    if role == "driver":
        employee_no = (data.get("employeeNo") or username.upper()).strip()
        if g.db.scalar(select(Driver).where(Driver.employee_no == employee_no)):
            return error("employeeNo already exists", 409)
        driver = Driver(
            user=user,
            employee_no=employee_no,
            license_level=data.get("licenseLevel", "N2"),
            qualification_tags=data.get("qualificationTags", "standard"),
            shift_status=data.get("shiftStatus", "on_shift"),
            bind_status="unbound",
        )
        g.db.add(driver)

    g.db.commit()
    return response(user.to_dict(), "created", 201)


@bp.patch("/<int:user_id>")
@role_required("admin")
def update_user(user_id):
    user = g.db.get(User, user_id)
    if not user:
        return error("user not found", 404)
    data = request.get_json(force=True)
    for field, attr in {
        "name": "name",
        "phone": "phone",
        "wecomUserId": "wecom_user_id",
        "department": "department",
        "team": "team",
        "status": "status",
    }.items():
        if field in data:
            setattr(user, attr, data[field])
    if data.get("password"):
        user.password_hash = generate_password_hash(data["password"])
    if user.role == "driver" and user.driver:
        if "employeeNo" in data and data["employeeNo"]:
            employee_no = data["employeeNo"].strip()
            existing = g.db.scalar(select(Driver).where(Driver.employee_no == employee_no))
            if existing and existing.id != user.driver.id:
                return error("employeeNo already exists", 409)
            user.driver.employee_no = employee_no
        if "licenseLevel" in data:
            user.driver.license_level = data["licenseLevel"]
        if "shiftStatus" in data:
            user.driver.shift_status = data["shiftStatus"]
    g.db.commit()
    return response(user.to_dict())


@bp.delete("/<int:user_id>")
@role_required("admin")
def delete_user(user_id):
    user = g.db.get(User, user_id)
    if not user:
        return error("user not found", 404)
    if user.username == "admin":
        return error("default admin cannot be deleted", 400)
    user.status = "disabled"
    if user.driver:
        user.driver.shift_status = "off_shift"
        user.driver.bind_status = "unbound"
        now = datetime.utcnow()
        for binding in g.db.scalars(
            select(VehicleBinding).where(
                VehicleBinding.driver_id == user.driver.id,
                VehicleBinding.status == "active",
            )
        ).all():
            binding.status = "closed"
            binding.unbound_at = now
            if binding.forklift:
                binding.forklift.driver_id = None
    g.db.commit()
    return response(user.to_dict(), "disabled")
