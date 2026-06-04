from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import MapPoint, TaskEvent, TransportTask
from ..services.dispatch_engine import assign_task, recommend_for_task
from ..services.gps import sync_latest_positions
from ..services.map_points import retire_task_temporary_points
from ..services.simulator import calculate_task_distance
from ..services.wecom import WeComClient
from ..utils import auth_required, current_user, error, parse_dt, response, role_required

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@bp.get("")
@auth_required
def list_tasks():
    sync_latest_positions(g.db)
    g.db.commit()
    status = request.args.get("status")
    stmt = select(TransportTask).order_by(TransportTask.updated_at.desc())
    if current_user().role == "driver":
        driver = current_user().driver
        if not driver:
            return response([])
        stmt = stmt.where(TransportTask.assigned_driver_id == driver.id)
    if status:
        stmt = stmt.where(TransportTask.status == status)
    rows = g.db.scalars(stmt).all()
    return response([row.to_dict() for row in rows])


@bp.post("")
@role_required("admin")
def create_task():
    data = request.get_json(force=True)
    origin = g.db.get(MapPoint, int(data["originPointId"]))
    dest = g.db.get(MapPoint, int(data["destPointId"]))
    if not origin or not dest:
        return error("起点或终点不存在", 400)
    task_no = "TASK-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
    task = TransportTask(
        task_no=task_no,
        requester=current_user(),
        origin=origin,
        destination=dest,
        origin_label=origin.name,
        dest_label=dest.name,
        cargo_type=data.get("cargoType", ""),
        estimated_weight=float(data.get("estimatedWeight") or 0),
        pallet_count=int(data.get("palletCount") or 1),
        expected_finish_at=parse_dt(data.get("expectedFinishAt")),
        priority=data.get("priority", "B"),
        status="pending_dispatch",
        note=data.get("note", ""),
    )
    g.db.add(task)
    g.db.flush()
    g.db.add(
        TaskEvent(
            task=task,
            event_type="created",
            operator=current_user(),
            message="用车申请创建，进入任务池。",
        )
    )
    g.db.commit()
    return response(task.to_dict(), "created", 201)


@bp.get("/<int:task_id>")
@auth_required
def get_task(task_id):
    task = g.db.get(TransportTask, task_id)
    if not task:
        return error("task not found", 404)
    events = [event.to_dict() for event in task.events]
    payload = task.to_dict()
    payload["events"] = events
    return response(payload)


@bp.get("/<int:task_id>/recommendations")
@role_required("admin")
def recommendations(task_id):
    try:
        return response(recommend_for_task(g.db, task_id))
    except ValueError as exc:
        return error(str(exc), 400)


@bp.post("/<int:task_id>/assign")
@role_required("admin")
def assign(task_id):
    data = request.get_json(silent=True) or {}
    try:
        result = assign_task(
            g.db,
            task_id,
            operator=current_user(),
            forklift_id=data.get("forkliftId"),
        )
        g.db.commit()
        return response(result, "assigned")
    except ValueError as exc:
        g.db.rollback()
        return error(str(exc), 400)


@bp.post("/<int:task_id>/status")
@role_required("admin")
def update_status(task_id):
    task = g.db.get(TransportTask, task_id)
    if not task:
        return error("task not found", 404)
    data = request.get_json(force=True)
    next_status = data.get("status")
    if not next_status:
        return error("status required", 400)
    task.status = next_status
    if next_status == "completed":
        task.finished_at = datetime.utcnow()
        task.distance = calculate_task_distance(g.db, task)
        if task.assigned_forklift:
            task.assigned_forklift.status = "idle"
        retired_points = retire_task_temporary_points(task)
    else:
        retired_points = []
    if next_status == "exception":
        task.abnormal_reason = data.get("reason", "")
    g.db.add(
        TaskEvent(
            task=task,
            event_type=f"status_{next_status}",
            operator=current_user(),
            forklift=task.assigned_forklift,
            driver=task.assigned_driver,
            location_x=task.assigned_forklift.current_x if task.assigned_forklift else None,
            location_y=task.assigned_forklift.current_y if task.assigned_forklift else None,
            message=data.get("message", "状态更新"),
            payload={"retiredTemporaryPointIds": retired_points} if retired_points else {},
        )
    )
    g.db.commit()
    return response(task.to_dict())


def _driver_can_operate(task):
    driver = current_user().driver
    return driver and task.assigned_driver_id == driver.id


@bp.post("/<int:task_id>/driver-accept")
@role_required("driver")
def driver_accept(task_id):
    task = g.db.get(TransportTask, task_id)
    if not task:
        return error("task not found", 404)
    if not _driver_can_operate(task):
        return error("只能处理派给自己的任务", 403)
    if task.status != "assigned":
        return error("只有待接收任务可以接受", 400)
    now = datetime.utcnow()
    task.status = "accepted"
    task.accepted_at = now
    task.started_at = now
    if task.assigned_forklift:
        task.assigned_forklift.status = "executing"
    g.db.add(
        TaskEvent(
            task=task,
            event_type="driver_accepted",
            operator=current_user(),
            forklift=task.assigned_forklift,
            driver=task.assigned_driver,
            location_x=task.assigned_forklift.current_x if task.assigned_forklift else None,
            location_y=task.assigned_forklift.current_y if task.assigned_forklift else None,
            message="司机登录系统确认接受任务",
        )
    )
    g.db.commit()
    return response(task.to_dict(), "accepted")


@bp.post("/<int:task_id>/driver-reject")
@role_required("driver")
def driver_reject(task_id):
    task = g.db.get(TransportTask, task_id)
    if not task:
        return error("task not found", 404)
    if not _driver_can_operate(task):
        return error("只能处理派给自己的任务", 403)
    if task.status != "assigned":
        return error("只有待接收任务可以拒绝", 400)
    data = request.get_json(force=True)
    reason = (data.get("reason") or "").strip()
    if not reason:
        return error("拒绝任务必须填写原因", 400)

    original_driver = task.assigned_driver
    original_forklift = task.assigned_forklift
    task.status = "pending_dispatch"
    task.abnormal_reason = f"司机拒绝：{reason}"
    task.assigned_driver_id = None
    task.assigned_forklift_id = None
    task.assigned_at = None
    task.accepted_at = None
    task.started_at = None
    if original_forklift:
        original_forklift.status = "idle"
    g.db.add(
        TaskEvent(
            task=task,
            event_type="driver_rejected",
            operator=current_user(),
            forklift=original_forklift,
            driver=original_driver,
            location_x=original_forklift.current_x if original_forklift else None,
            location_y=original_forklift.current_y if original_forklift else None,
            message=reason,
        )
    )
    WeComClient(g.db).send_text(
        "司机拒绝任务",
        f"{task.task_no} 被 {current_user().name} 拒绝，原因：{reason}",
        target_role="admin",
        payload={"taskId": task.id, "reason": reason},
    )
    g.db.commit()
    return response(task.to_dict(), "rejected")


@bp.post("/<int:task_id>/driver-complete")
@role_required("driver")
def driver_complete(task_id):
    task = g.db.get(TransportTask, task_id)
    if not task:
        return error("task not found", 404)
    if not _driver_can_operate(task):
        return error("只能处理派给自己的任务", 403)
    if task.status not in {"accepted", "to_origin", "arrived_origin", "loading", "transporting", "arrived_dest", "unloading"}:
        return error("任务未接受，不能完成", 400)
    task.status = "completed"
    task.finished_at = datetime.utcnow()
    distance = calculate_task_distance(g.db, task)
    task.distance = distance
    if task.assigned_forklift:
        task.assigned_forklift.status = "idle"
    if task.assigned_driver:
        minutes = 0
        if task.accepted_at:
            minutes = max(1, int((task.finished_at - task.accepted_at).total_seconds() / 60))
        task.assigned_driver.task_count_today += 1
        task.assigned_driver.working_minutes_today += minutes
        task.assigned_driver.distance_today += distance
        task.assigned_driver.workload_score = min(100, task.assigned_driver.workload_score + 5)
    retired_points = retire_task_temporary_points(task)
    g.db.add(
        TaskEvent(
            task=task,
            event_type="driver_completed",
            operator=current_user(),
            forklift=task.assigned_forklift,
            driver=task.assigned_driver,
            location_x=task.assigned_forklift.current_x if task.assigned_forklift else None,
            location_y=task.assigned_forklift.current_y if task.assigned_forklift else None,
            message=f"司机完成任务，系统按GPS轨迹自动计算公里数 {distance}",
            payload={"distance": distance, "retiredTemporaryPointIds": retired_points},
        )
    )
    g.db.commit()
    return response(task.to_dict(), "completed")
