from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import Alert, Forklift, TransportTask, VehicleBinding
from ..services.wecom import WeComClient
from ..utils import current_user, error, response, role_required

bp = Blueprint("driver", __name__, url_prefix="/api/driver")

ACTIVE_TASK_STATUSES = {
    "assigned",
    "accepted",
    "to_origin",
    "arrived_origin",
    "loading",
    "transporting",
    "arrived_dest",
    "unloading",
}


def current_driver():
    driver = current_user().driver
    if not driver:
        return None
    return driver


def active_task_for_driver(driver):
    return g.db.scalar(
        select(TransportTask)
        .where(
            TransportTask.assigned_driver_id == driver.id,
            TransportTask.status.in_(ACTIVE_TASK_STATUSES),
        )
        .order_by(TransportTask.updated_at.desc())
        .limit(1)
    )


def close_driver_bindings(driver):
    now = datetime.utcnow()
    bindings = g.db.scalars(
        select(VehicleBinding).where(
            VehicleBinding.driver_id == driver.id,
            VehicleBinding.status == "active",
        )
    ).all()
    for binding in bindings:
        binding.status = "closed"
        binding.unbound_at = now
        if binding.forklift and binding.forklift.driver_id == driver.id:
            binding.forklift.driver_id = None
    driver.bind_status = "unbound"
    return bindings


@bp.patch("/status")
@role_required("driver")
def update_driver_status():
    driver = current_driver()
    if not driver:
        return error("driver profile not found", 404)
    data = request.get_json(force=True)
    status = data.get("shiftStatus")
    if status not in {"on_shift", "off_shift"}:
        return error("shiftStatus must be on_shift/off_shift", 400)

    if status == "off_shift":
        active_task = active_task_for_driver(driver)
        if active_task:
            return error(f"当前存在未完成任务 {active_task.task_no}，完成或拒绝后才能下线。", 400)
        close_driver_bindings(driver)

    driver.shift_status = status
    g.db.commit()
    return response(current_user().to_dict())


@bp.post("/forklift-requests")
@role_required("driver")
def request_forklift():
    driver = current_driver()
    if not driver:
        return error("driver profile not found", 404)
    if driver.shift_status != "on_shift":
        return error("请先上线后再申请叉车", 400)
    if driver.bind_status == "bound":
        return error("当前已经绑定叉车，无需重复申请", 400)

    data = request.get_json(force=True)
    vehicle = g.db.get(Forklift, int(data.get("forkliftId") or 0))
    if not vehicle:
        return error("forklift not found", 404)
    if not vehicle.online or vehicle.status != "idle" or vehicle.driver_id:
        return error("该叉车当前不是可申请的空闲状态", 400)

    duplicate = g.db.scalar(
        select(Alert)
        .where(
            Alert.alert_type == "forklift_request",
            Alert.status == "open",
            Alert.driver_id == driver.id,
            Alert.forklift_id == vehicle.id,
        )
        .limit(1)
    )
    if duplicate:
        return response(duplicate.to_dict(), "already_requested")

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    alert = Alert(
        code=f"FORKLIFT-REQ-{driver.id}-{vehicle.id}-{stamp}",
        alert_type="forklift_request",
        severity="info",
        status="open",
        title=f"{driver.user.name if driver.user else driver.employee_no} 申请绑定 {vehicle.code}",
        message=(
            f"司机 {driver.user.name if driver.user else driver.employee_no} 已上线，"
            f"申请空闲叉车 {vehicle.code}，当前位置 {vehicle.current_area}。"
        ),
        suggestion="管理员确认现场条件后，在排班绑定页面为司机绑定叉车。",
        forklift=vehicle,
        driver=driver,
        payload={"requestedBy": "driver", "forkliftId": vehicle.id, "driverId": driver.id},
    )
    g.db.add(alert)
    g.db.flush()
    WeComClient(g.db).send_text(
        "司机申请叉车",
        f"{driver.user.name if driver.user else driver.employee_no} 申请绑定 {vehicle.code}",
        target_role="admin",
        payload={"alertId": alert.id, "forkliftId": vehicle.id, "driverId": driver.id},
    )
    g.db.commit()
    return response(alert.to_dict(), "requested", 201)
