import math
import random
from datetime import datetime

from flask import current_app
from sqlalchemy import select

from ..models import Alert, Forklift, ForkliftPosition, MapPoint, TaskEvent, TransportTask
from .dispatch_engine import create_alert, euclidean_distance
from .gps import clamp_xy_to_work_area, map_xy_to_latlng
from .map_points import retire_task_temporary_points


IDLE_PATROL = [
    (19, 80, "南侧主干道"),
    (25, 55, "西侧通道"),
    (48, 55, "中心通道"),
    (76, 51, "东侧装卸区"),
    (72, 28, "北侧仓储区"),
    (35, 30, "原料仓库区"),
]

DEFAULT_MAP_UNIT_TO_KM = 0.0065


def movement_step_units(speed_kmh, step_seconds):
    unit_to_km = current_app.config.get("MAP_UNIT_TO_KM", DEFAULT_MAP_UNIT_TO_KM)
    if unit_to_km <= 0:
        unit_to_km = DEFAULT_MAP_UNIT_TO_KM
    return max(0.3, (speed_kmh * max(step_seconds, 1) / 3600) / unit_to_km)


def move_towards(vehicle, target_x, target_y, step_seconds=5, speed_kmh=None):
    dx = target_x - vehicle.current_x
    dy = target_y - vehicle.current_y
    distance = math.sqrt(dx * dx + dy * dy)
    speed_kmh = speed_kmh or random.uniform(5.5, 9.0)
    step = movement_step_units(speed_kmh, step_seconds)
    if distance <= step:
        vehicle.current_x = target_x
        vehicle.current_y = target_y
        vehicle.speed = 0
        return True
    ratio = step / distance
    vehicle.current_x += dx * ratio
    vehicle.current_y += dy * ratio
    vehicle.heading = (math.degrees(math.atan2(dy, dx)) + 360) % 360
    vehicle.speed = round(speed_kmh, 1)
    return False


def nearest_area(session, x, y):
    points = session.scalars(select(MapPoint).where(MapPoint.enabled.is_(True))).all()
    if not points:
        return "未知区域"
    point = min(points, key=lambda p: euclidean_distance(x, y, p.x, p.y))
    return point.area or point.name


def calculate_task_distance(session, task):
    positions = session.scalars(
        select(ForkliftPosition)
        .where(ForkliftPosition.task_id == task.id)
        .order_by(ForkliftPosition.recorded_at, ForkliftPosition.id)
    ).all()
    units = 0
    for previous, current in zip(positions, positions[1:]):
        units += euclidean_distance(previous.x, previous.y, current.x, current.y)

    if units <= 0 and task.origin and task.destination:
        if task.assigned_forklift:
            units += euclidean_distance(
                task.assigned_forklift.current_x,
                task.assigned_forklift.current_y,
                task.origin.x,
                task.origin.y,
            )
        units += euclidean_distance(task.origin.x, task.origin.y, task.destination.x, task.destination.y)

    unit_to_km = current_app.config.get("MAP_UNIT_TO_KM", DEFAULT_MAP_UNIT_TO_KM)
    return round(max(units * unit_to_km, 0.1), 1)


def advance_simulation(session, step_seconds=5):
    now = datetime.utcnow()
    vehicles = session.scalars(select(Forklift).order_by(Forklift.id)).all()
    for vehicle in vehicles:
        if not vehicle.online:
            continue
        task = session.scalar(
            select(TransportTask)
            .where(
                TransportTask.assigned_forklift_id == vehicle.id,
                TransportTask.status.in_(
                    [
                        "accepted",
                        "to_origin",
                        "arrived_origin",
                        "loading",
                        "transporting",
                        "arrived_dest",
                        "unloading",
                    ]
                ),
            )
            .order_by(TransportTask.updated_at.asc())
        )

        if task and task.origin and task.destination:
            simulate_task_vehicle(session, vehicle, task, step_seconds=step_seconds)
        else:
            simulate_idle_vehicle(vehicle, step_seconds=step_seconds)

        vehicle.current_x, vehicle.current_y = clamp_xy_to_work_area(vehicle.current_x, vehicle.current_y, session)
        vehicle.current_area = nearest_area(session, vehicle.current_x, vehicle.current_y)
        vehicle.last_seen_at = now
        latlng = map_xy_to_latlng(vehicle.current_x, vehicle.current_y, session)
        lat, lng = latlng if latlng else (0, 0)
        if vehicle.status in {"idle", "assigned", "executing"}:
            if vehicle.power_type in {"diesel", "gasoline", "lpg"}:
                vehicle.fuel_level = max(1, vehicle.fuel_level - random.choice([0, 0, 1]))
            else:
                vehicle.battery_level = max(1, vehicle.battery_level - random.choice([0, 0, 1]))
        session.add(
            ForkliftPosition(
                forklift=vehicle,
                task_id=task.id if task else None,
                recorded_at=now,
                x=vehicle.current_x,
                y=vehicle.current_y,
                lat=lat,
                lng=lng,
                heading=vehicle.heading,
                speed=vehicle.speed,
                source="simulator",
                quality=round(random.uniform(0.86, 0.99), 2),
                area=vehicle.current_area,
            )
        )

    detect_simulated_alerts(session)
    session.flush()


def simulate_task_vehicle(session, vehicle, task, step_seconds=5):
    if task.status in {"accepted", "to_origin"}:
        task.status = "to_origin"
        target_x, target_y = clamp_xy_to_work_area(task.origin.x, task.origin.y, session)
        arrived = move_towards(vehicle, target_x, target_y, step_seconds=step_seconds)
        arrived = arrived and euclidean_distance(vehicle.current_x, vehicle.current_y, target_x, target_y) < 1.2
        if arrived:
            task.status = "arrived_origin"
            session.add(
                TaskEvent(
                    task=task,
                    event_type="arrived_origin",
                    forklift=vehicle,
                    driver=vehicle.driver,
                    location_x=vehicle.current_x,
                    location_y=vehicle.current_y,
                    message="进入起点围栏，自动记录到达",
                )
            )
    elif task.status == "arrived_origin":
        task.status = "loading"
        vehicle.status = "waiting"
        vehicle.speed = 0
    elif task.status == "loading":
        task.status = "transporting"
        vehicle.status = "executing"
    elif task.status == "transporting":
        target_x, target_y = clamp_xy_to_work_area(task.destination.x, task.destination.y, session)
        arrived = move_towards(vehicle, target_x, target_y, step_seconds=step_seconds)
        arrived = arrived and euclidean_distance(vehicle.current_x, vehicle.current_y, target_x, target_y) < 1.2
        if arrived:
            task.status = "arrived_dest"
            session.add(
                TaskEvent(
                    task=task,
                    event_type="arrived_dest",
                    forklift=vehicle,
                    driver=vehicle.driver,
                    location_x=vehicle.current_x,
                    location_y=vehicle.current_y,
                    message="进入终点围栏，自动记录到达",
                )
            )
    elif task.status == "arrived_dest":
        task.status = "unloading"
        vehicle.status = "waiting"
        vehicle.speed = 0
    elif task.status == "unloading":
        task.status = "completed"
        task.finished_at = datetime.utcnow()
        task.distance = calculate_task_distance(session, task)
        retired_points = retire_task_temporary_points(task)
        vehicle.status = "idle"
        vehicle.speed = 0
        if vehicle.driver:
            vehicle.driver.task_count_today += 1
            if task.accepted_at:
                minutes = max(1, int((task.finished_at - task.accepted_at).total_seconds() / 60))
            else:
                minutes = max(task.eta_minutes, 8)
            vehicle.driver.working_minutes_today += minutes
            vehicle.driver.distance_today += task.distance
            vehicle.driver.workload_score = min(100, vehicle.driver.workload_score + 5)
        session.add(
            TaskEvent(
                task=task,
                event_type="completed",
                forklift=vehicle,
                driver=vehicle.driver,
                location_x=vehicle.current_x,
                location_y=vehicle.current_y,
                message=f"卸货完成，按GPS轨迹计算距离 {task.distance} km",
                payload={"distance": task.distance, "retiredTemporaryPointIds": retired_points},
            )
        )


def simulate_idle_vehicle(vehicle, step_seconds=5):
    if vehicle.status not in {"idle", "low_battery"}:
        return
    target = IDLE_PATROL[vehicle.id % len(IDLE_PATROL)]
    if euclidean_distance(vehicle.current_x, vehicle.current_y, target[0], target[1]) < 2:
        target = random.choice(IDLE_PATROL)
    move_towards(vehicle, target[0], target[1], step_seconds=step_seconds, speed_kmh=random.uniform(1.5, 3.0))
    vehicle.speed = round(random.uniform(0, 3.5), 1)


def detect_simulated_alerts(session):
    vehicles = session.scalars(select(Forklift)).all()
    open_alerts = {
        row.alert_type + ":" + str(row.forklift_id or "")
        for row in session.scalars(select(Alert).where(Alert.status == "open")).all()
    }
    for vehicle in vehicles:
        energy_level = vehicle.fuel_level if vehicle.power_type in {"diesel", "gasoline", "lpg"} else vehicle.battery_level
        if energy_level <= 20 and f"low_battery:{vehicle.id}" not in open_alerts:
            create_alert(
                session,
                "low_battery",
                "warning",
                f"{vehicle.code} 能源余量偏低",
                f"当前余量 {energy_level}%，建议完成短任务后安排补能。",
                "低能源车辆降低派单权重，低于禁派阈值后禁止新任务。",
                forklift=vehicle,
            )
            vehicle.status = "low_battery"
        if vehicle.online is False and f"offline:{vehicle.id}" not in open_alerts:
            create_alert(
                session,
                "offline",
                "critical",
                f"{vehicle.code} 设备离线",
                "车载终端未上报定位数据，系统保留最后有效位置。",
                "通知运维检查 4G/MQTT 链路，必要时转人工调度。",
                forklift=vehicle,
            )

    area_counter = {}
    for vehicle in vehicles:
        if vehicle.current_area:
            area_counter[vehicle.current_area] = area_counter.get(vehicle.current_area, 0) + 1
    open_area_alerts = {
        (row.payload or {}).get("area")
        for row in session.scalars(
            select(Alert).where(Alert.status == "open", Alert.alert_type == "area_congestion")
        ).all()
    }
    for area, count in area_counter.items():
        if count >= 4 and area not in open_area_alerts:
            create_alert(
                session,
                "area_congestion",
                "warning",
                f"{area} 车辆扎堆",
                f"当前区域聚集 {count} 台叉车，可能影响装卸秩序。",
                "暂停继续派入该区域，调整任务顺序或分流到其他装卸点。",
                payload={"area": area, "count": count},
            )
