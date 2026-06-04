import math
from datetime import datetime

from sqlalchemy import func, select

from ..models import (
    Alert,
    DispatchRule,
    Driver,
    Forklift,
    TaskEvent,
    TransportTask,
    VehicleBinding,
)
from .wecom import WeComClient
from .gps import sync_latest_positions


PRIORITY_SCORE = {"S": 100, "A": 85, "B": 60, "C": 40}
ACTIVE_TASK_STATUSES = {
    "assigned",
    "accepted",
    "to_origin",
    "arrived_origin",
    "loading",
    "transporting",
    "arrived_dest",
    "unloading",
    "exception",
}
DISPATCHABLE_STATUSES = {"pending_review", "pending_dispatch"}


def euclidean_distance(x1, y1, x2, y2):
    return math.sqrt((float(x1) - float(x2)) ** 2 + (float(y1) - float(y2)) ** 2)


def estimate_eta_minutes(distance):
    return max(2, int(distance / 8 * 6) + 2)


def get_weight_map(session):
    defaults = {
        "distance_eta": 0.30,
        "priority_deadline": 0.20,
        "driver_load": 0.20,
        "vehicle_fit": 0.15,
        "area_congestion": 0.10,
        "manual_rule": 0.05,
    }
    rules = session.scalars(
        select(DispatchRule).where(
            DispatchRule.enabled.is_(True),
            DispatchRule.category == "score",
        )
    ).all()
    for rule in rules:
        factor = (rule.action_json or {}).get("factor")
        if factor in defaults:
            defaults[factor] = float(rule.weight or defaults[factor])
    total = sum(defaults.values()) or 1
    return {key: value / total for key, value in defaults.items()}


def active_bindings(session):
    rows = session.scalars(
        select(VehicleBinding).where(VehicleBinding.status == "active")
    ).all()
    return {row.forklift_id: row for row in rows}


def active_task_count_by_area(session):
    rows = session.execute(
        select(Forklift.current_area, func.count(Forklift.id))
        .where(Forklift.status.in_(["idle", "assigned", "executing", "waiting"]))
        .group_by(Forklift.current_area)
    ).all()
    return {area or "未知": count for area, count in rows}


def filter_reason(vehicle, binding):
    if not vehicle.online:
        return "车辆离线"
    if vehicle.status in {"charging", "maintenance", "fault", "disabled"}:
        return f"车辆状态不可派单：{vehicle.status}"
    energy_level = vehicle.fuel_level if vehicle.power_type in {"diesel", "gasoline", "lpg"} else vehicle.battery_level
    if energy_level <= 15:
        return "油量低于禁派阈值" if vehicle.power_type in {"diesel", "gasoline", "lpg"} else "电量低于禁派阈值"
    if not binding:
        return "未完成人车绑定"
    if not binding.driver or binding.driver.shift_status != "on_shift":
        return "司机未当班/未签到"
    if binding.driver.bind_status != "bound":
        return "司机未绑定车辆"
    if vehicle.status not in {"idle", "low_battery"}:
        return "车辆非空闲状态"
    return ""


def score_candidate(session, task, vehicle, binding, congestion_map, weights):
    origin = task.origin
    dest = task.destination
    distance = euclidean_distance(vehicle.current_x, vehicle.current_y, origin.x, origin.y)
    route_distance = distance + euclidean_distance(origin.x, origin.y, dest.x, dest.y)
    distance_score = max(0, min(100, 100 - distance * 1.25))

    priority_score = PRIORITY_SCORE.get(task.priority, 50)
    if task.expected_finish_at:
        minutes_left = (task.expected_finish_at - datetime.utcnow()).total_seconds() / 60
        if minutes_left < 30:
            priority_score = min(100, priority_score + 20)
        elif minutes_left > 240:
            priority_score = max(30, priority_score - 10)

    driver = binding.driver
    driver_load_score = max(0, 100 - float(driver.workload_score or 0))
    energy_level = vehicle.fuel_level if vehicle.power_type in {"diesel", "gasoline", "lpg"} else vehicle.battery_level
    vehicle_fit_score = min(100, energy_level + 15)
    if vehicle.tonnage < task.estimated_weight / 1000:
        vehicle_fit_score -= 45
    if vehicle.status == "low_battery":
        vehicle_fit_score -= 25

    vehicles_in_area = congestion_map.get(task.origin.area or task.origin_label, 0)
    congestion_score = max(10, 100 - vehicles_in_area * 15)
    manual_score = apply_manual_rules(session, task, vehicle, driver)

    total = (
        distance_score * weights["distance_eta"]
        + priority_score * weights["priority_deadline"]
        + driver_load_score * weights["driver_load"]
        + vehicle_fit_score * weights["vehicle_fit"]
        + congestion_score * weights["area_congestion"]
        + manual_score * weights["manual_rule"]
    )
    return {
        "score": round(total, 2),
        "distance": round(route_distance, 1),
        "etaMinutes": estimate_eta_minutes(distance),
        "breakdown": {
            "distanceEta": round(distance_score, 1),
            "priorityDeadline": round(priority_score, 1),
            "driverLoad": round(driver_load_score, 1),
            "vehicleFit": round(vehicle_fit_score, 1),
            "areaCongestion": round(congestion_score, 1),
            "manualRule": round(manual_score, 1),
        },
    }


def apply_manual_rules(session, task, vehicle, driver):
    score = 80
    rules = session.scalars(
        select(DispatchRule).where(
            DispatchRule.enabled.is_(True),
            DispatchRule.category == "manual",
        )
    ).all()
    for rule in rules:
        condition = rule.condition_json or {}
        action = rule.action_json or {}
        match = condition.get("match", {})
        matched = True
        if "vehicleCode" in match and match["vehicleCode"] != vehicle.code:
            matched = False
        if "driverEmployeeNo" in match and match["driverEmployeeNo"] != driver.employee_no:
            matched = False
        if "originArea" in match and match["originArea"] != task.origin.area:
            matched = False
        if "priority" in match and match["priority"] != task.priority:
            matched = False
        if matched:
            score += float(action.get("scoreBoost", 0))
            if action.get("deny"):
                score -= 100
    return max(0, min(100, score))


def recommend_for_task(session, task_id):
    sync_latest_positions(session)
    task = session.get(TransportTask, task_id)
    if not task:
        raise ValueError("task not found")
    if not task.origin or not task.destination:
        raise ValueError("task origin/destination point is required")

    weights = get_weight_map(session)
    bindings = active_bindings(session)
    congestion = active_task_count_by_area(session)
    vehicles = session.scalars(select(Forklift).order_by(Forklift.code)).all()
    rejected = []
    candidates = []

    for vehicle in vehicles:
        binding = bindings.get(vehicle.id)
        reason = filter_reason(vehicle, binding)
        if reason:
            rejected.append({"vehicle": vehicle.to_dict(), "reason": reason})
            continue
        scored = score_candidate(session, task, vehicle, binding, congestion, weights)
        candidates.append(
            {
                "vehicle": vehicle.to_dict(),
                "driver": binding.driver.to_dict(),
                **scored,
            }
        )

    candidates.sort(key=lambda row: row["score"], reverse=True)
    return {
        "task": task.to_dict(),
        "weights": weights,
        "candidates": candidates,
        "rejected": rejected,
    }


def assign_task(session, task_id, operator=None, forklift_id=None):
    task = session.get(TransportTask, task_id)
    if not task:
        raise ValueError("task not found")
    if task.status not in DISPATCHABLE_STATUSES:
        raise ValueError("only pending tasks can be assigned")

    recommendation = recommend_for_task(session, task_id)
    candidate = None
    if forklift_id:
        for row in recommendation["candidates"]:
            if row["vehicle"]["id"] == int(forklift_id):
                candidate = row
                break
    else:
        candidate = recommendation["candidates"][0] if recommendation["candidates"] else None
    if not candidate:
        create_alert(
            session,
            "no_dispatch_candidate",
            "critical",
            "无可用叉车",
            f"工单 {task.task_no} 无符合条件的人车资源，请管理员人工处理。",
            "检查排班、人车绑定、电量、设备状态或启用备用车辆。",
            task=task,
        )
        raise ValueError("no dispatch candidate")

    vehicle = session.get(Forklift, candidate["vehicle"]["id"])
    driver = session.get(Driver, candidate["driver"]["id"])
    task.assigned_forklift_id = vehicle.id
    task.assigned_driver_id = driver.id
    task.assigned_forklift = vehicle
    task.assigned_driver = driver
    task.status = "assigned"
    task.assigned_at = datetime.utcnow()
    task.eta_minutes = candidate["etaMinutes"]
    task.distance = candidate["distance"]
    vehicle.status = "assigned"
    vehicle.driver_id = driver.id
    driver.workload_score = min(100, driver.workload_score + 8)

    session.add(
        TaskEvent(
            task=task,
            event_type="assigned",
            operator=operator,
            forklift=vehicle,
            driver=driver,
            location_x=vehicle.current_x,
            location_y=vehicle.current_y,
            message=f"系统推荐 {vehicle.code} / {driver.user.name}，评分 {candidate['score']}",
            payload={"recommendation": candidate},
        )
    )
    WeComClient(session).send_text(
        "叉车任务已派单",
        f"{task.task_no}：{task.origin_label} -> {task.dest_label}，预计 {task.eta_minutes} 分钟到达。",
        target_user_id=driver.user.wecom_user_id,
        target_role="driver",
        payload={"taskId": task.id, "forkliftId": vehicle.id},
    )
    return {"task": task.to_dict(), "assigned": candidate}


def create_alert(
    session,
    alert_type,
    severity,
    title,
    message,
    suggestion,
    task=None,
    forklift=None,
    driver=None,
    map_point=None,
    payload=None,
):
    base = f"{alert_type}-{task.id if task else 'x'}-{forklift.id if forklift else 'x'}"
    code = f"{base}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    existing = session.scalar(select(Alert).where(Alert.code == code))
    if existing:
        return existing
    alert = Alert(
        code=code,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        suggestion=suggestion,
        task=task,
        forklift=forklift,
        driver=driver,
        map_point=map_point,
        payload=payload or {},
    )
    session.add(alert)
    return alert
