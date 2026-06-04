from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import Driver, Forklift, VehicleBinding
from ..services.gps import sync_latest_positions
from ..utils import auth_required, error, response, role_required

bp = Blueprint("vehicles", __name__, url_prefix="/api")


@bp.get("/vehicles")
@auth_required
def vehicles():
    sync_latest_positions(g.db)
    g.db.commit()
    rows = g.db.scalars(select(Forklift).order_by(Forklift.code)).all()
    return response([row.to_dict() for row in rows])


@bp.post("/vehicles")
@role_required("admin")
def create_vehicle():
    data = request.get_json(force=True)
    code = (data.get("code") or "").strip()
    if not code:
        return error("vehicle code is required", 400)
    if g.db.scalar(select(Forklift).where(Forklift.code == code)):
        return error("vehicle code already exists", 409)
    vehicle = Forklift(
        code=code,
        plate_no=data.get("plateNo", ""),
        model=data.get("model", ""),
        power_type=data.get("powerType", "electric"),
        tonnage=float(data.get("tonnage") or 3),
        status=data.get("status", "idle"),
        battery_level=int(data.get("batteryLevel") or 0),
        fuel_level=int(data.get("fuelLevel") or 0),
        online=bool(data.get("online", True)),
        current_area=data.get("currentArea", "自定义区域"),
        current_x=float(data.get("x") or 50),
        current_y=float(data.get("y") or 50),
        note=data.get("note", ""),
    )
    g.db.add(vehicle)
    g.db.commit()
    return response(vehicle.to_dict(), "created", 201)


@bp.patch("/vehicles/<int:vehicle_id>")
@role_required("admin")
def update_vehicle(vehicle_id):
    vehicle = g.db.get(Forklift, vehicle_id)
    if not vehicle:
        return error("vehicle not found", 404)
    data = request.get_json(force=True)
    for field, attr in {
        "code": "code",
        "plateNo": "plate_no",
        "model": "model",
        "powerType": "power_type",
        "tonnage": "tonnage",
        "status": "status",
        "batteryLevel": "battery_level",
        "fuelLevel": "fuel_level",
        "online": "online",
        "currentArea": "current_area",
        "x": "current_x",
        "y": "current_y",
        "note": "note",
    }.items():
        if field in data:
            if field == "code":
                code = str(data[field]).strip()
                existing = g.db.scalar(select(Forklift).where(Forklift.code == code))
                if existing and existing.id != vehicle.id:
                    return error("vehicle code already exists", 409)
                setattr(vehicle, attr, code)
                continue
            setattr(vehicle, attr, data[field])
    g.db.commit()
    return response(vehicle.to_dict())


@bp.delete("/vehicles/<int:vehicle_id>")
@role_required("admin")
def delete_vehicle(vehicle_id):
    vehicle = g.db.get(Forklift, vehicle_id)
    if not vehicle:
        return error("vehicle not found", 404)
    vehicle.status = "disabled"
    vehicle.online = False
    if vehicle.driver:
        vehicle.driver.bind_status = "unbound"
    vehicle.driver_id = None
    now = datetime.utcnow()
    for binding in vehicle.bindings:
        if binding.status == "active":
            binding.status = "closed"
            binding.unbound_at = now
    g.db.commit()
    return response(vehicle.to_dict(), "disabled")


@bp.get("/drivers")
@auth_required
def drivers():
    rows = g.db.scalars(select(Driver).order_by(Driver.employee_no)).all()
    return response([row.to_dict() for row in rows])


@bp.post("/bindings")
@role_required("admin")
def bind_vehicle():
    data = request.get_json(force=True)
    vehicle = g.db.get(Forklift, int(data["forkliftId"]))
    driver = g.db.get(Driver, int(data["driverId"]))
    if not vehicle or not driver:
        return error("vehicle or driver not found", 404)
    if driver.shift_status != "on_shift":
        return error("司机未上线，不能绑定叉车", 400)
    now = datetime.utcnow()
    for old in g.db.scalars(
        select(VehicleBinding).where(
            VehicleBinding.status == "active",
            (VehicleBinding.forklift_id == vehicle.id) | (VehicleBinding.driver_id == driver.id),
        )
    ).all():
        old.status = "closed"
        old.unbound_at = now
        if old.forklift:
            old.forklift.driver_id = None
        if old.driver:
            old.driver.bind_status = "unbound"
    binding = VehicleBinding(
        forklift=vehicle,
        driver=driver,
        shift_code=data.get("shiftCode", "DAY"),
        status="active",
        bind_method=data.get("bindMethod", "manual"),
    )
    vehicle.driver = driver
    driver.bind_status = "bound"
    driver.shift_status = "on_shift"
    g.db.add(binding)
    g.db.commit()
    return response(binding.to_dict(), "bound", 201)


@bp.post("/bindings/<int:binding_id>/close")
@role_required("admin")
def close_binding(binding_id):
    binding = g.db.get(VehicleBinding, binding_id)
    if not binding:
        return error("binding not found", 404)
    binding.status = "closed"
    binding.unbound_at = datetime.utcnow()

    if binding.forklift and binding.forklift.driver_id == binding.driver_id:
        binding.forklift.driver_id = None
    if binding.driver:
        active_count = g.db.scalar(
            select(VehicleBinding)
            .where(
                VehicleBinding.driver_id == binding.driver_id,
                VehicleBinding.status == "active",
                VehicleBinding.id != binding.id,
            )
            .limit(1)
        )
        if not active_count:
            binding.driver.bind_status = "unbound"
    g.db.commit()
    return response(binding.to_dict(), "closed")
