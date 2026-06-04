import random
from datetime import datetime, timedelta

from sqlalchemy import func, select

from ..models import Driver, Forklift, MapPoint, TaskEvent, TransportTask, User, VehicleBinding
from .dispatch_engine import assign_task
from .simulator import advance_simulation

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
PENDING_TASK_STATUSES = {"pending_review", "pending_dispatch"}
WORKDAY_TASK_STATUSES = ACTIVE_TASK_STATUSES | PENDING_TASK_STATUSES | {"completed", "exception"}

CARGO_TYPES = [
    "生产转运物料",
    "铜线盘",
    "成品托盘",
    "辅料周转箱",
    "线缆半成品",
    "空托盘回收",
]
PRIORITIES = ["B", "B", "A", "C", "S"]


def prepare_workday_resources(session, driver_limit=None):
    """Put available drivers online and keep/admin-create active vehicle bindings."""
    drivers = session.scalars(
        select(Driver)
        .join(User)
        .where(User.status == "active", User.role == "driver")
        .order_by(Driver.employee_no)
    ).all()
    if driver_limit:
        drivers = drivers[: max(1, int(driver_limit))]

    for driver in drivers:
        driver.shift_status = "on_shift"

    vehicles = session.scalars(
        select(Forklift).where(Forklift.online.is_(True)).order_by(Forklift.code)
    ).all()
    bindable_vehicles = [
        vehicle
        for vehicle in vehicles
        if vehicle.status not in {"maintenance", "fault", "disabled", "offline", "charging"}
    ]

    active_bindings = session.scalars(
        select(VehicleBinding).where(VehicleBinding.status == "active")
    ).all()
    bound_driver_ids = set()
    bound_vehicle_ids = set()
    for binding in active_bindings:
        if binding.driver in drivers and binding.forklift in bindable_vehicles:
            binding.driver.bind_status = "bound"
            binding.driver.shift_status = "on_shift"
            binding.forklift.driver_id = binding.driver_id
            bound_driver_ids.add(binding.driver_id)
            bound_vehicle_ids.add(binding.forklift_id)

    free_drivers = [driver for driver in drivers if driver.id not in bound_driver_ids]
    free_vehicles = [
        vehicle
        for vehicle in bindable_vehicles
        if vehicle.id not in bound_vehicle_ids and not vehicle.driver_id and vehicle.status in {"idle", "low_battery"}
    ]
    now = datetime.utcnow()
    for driver, vehicle in zip(free_drivers, free_vehicles):
        driver.bind_status = "bound"
        vehicle.driver = driver
        session.add(
            VehicleBinding(
                forklift=vehicle,
                driver=driver,
                shift_code="SIM-DAY",
                bound_at=now,
                status="active",
                bind_method="simulator",
            )
        )

    session.flush()
    return {
        "driversOnline": len(drivers),
        "activeBindings": session.scalar(select(func.count(VehicleBinding.id)).where(VehicleBinding.status == "active"))
        or 0,
    }


def pending_dispatch_count(session):
    return (
        session.scalar(
            select(func.count(TransportTask.id)).where(TransportTask.status.in_(PENDING_TASK_STATUSES))
        )
        or 0
    )


def active_task_count(session):
    return (
        session.scalar(
            select(func.count(TransportTask.id)).where(TransportTask.status.in_(ACTIVE_TASK_STATUSES))
        )
        or 0
    )


def completed_task_count(session, since):
    return (
        session.scalar(
            select(func.count(TransportTask.id)).where(
                TransportTask.status == "completed",
                TransportTask.created_at >= since,
            )
        )
        or 0
    )


def random_transport_points(session):
    points = session.scalars(
        select(MapPoint).where(
            MapPoint.enabled.is_(True),
            MapPoint.is_temporary.is_(False),
            MapPoint.point_type.notin_(["lora", "maintenance", "charging", "parking", "route"]),
        )
    ).all()
    origins = [point for point in points if point.point_type in {"pickup", "dock", "handover"}]
    destinations = [point for point in points if point.point_type in {"dropoff", "dock", "handover"}]
    if len(points) >= 2:
        if not origins:
            origins = points
        if not destinations:
            destinations = points
    if not origins or not destinations:
        raise ValueError("至少需要两个启用的取送货点才能运行全日模拟")

    origin = random.choice(origins)
    destination = random.choice([point for point in destinations if point.id != origin.id] or destinations)
    return origin, destination


def create_random_task(session, admin, sequence, now=None):
    now = now or datetime.utcnow()
    origin, destination = random_transport_points(session)
    task_no = f"TASK-SIM-{now.strftime('%Y%m%d%H%M%S')}-{sequence:04d}"
    task = TransportTask(
        task_no=task_no,
        requester=admin,
        origin=origin,
        destination=destination,
        origin_label=origin.name,
        dest_label=destination.name,
        cargo_type=random.choice(CARGO_TYPES),
        estimated_weight=random.choice([600, 900, 1200, 1500, 1800, 2200, 2600]),
        pallet_count=random.randint(1, 4),
        expected_finish_at=now + timedelta(minutes=random.randint(25, 90)),
        priority=random.choice(PRIORITIES),
        status="pending_dispatch",
        note="全日业务流模拟自动生成",
    )
    session.add(task)
    session.flush()
    session.add(
        TaskEvent(
            task=task,
            event_type="sim_created",
            operator=admin,
            message="全日模拟发布搬运任务，进入任务池。",
        )
    )
    return task


def accept_assigned_tasks(session):
    tasks = session.scalars(select(TransportTask).where(TransportTask.status == "assigned")).all()
    accepted = 0
    now = datetime.utcnow()
    for task in tasks:
        if not task.assigned_driver or not task.assigned_forklift:
            continue
        task.status = "accepted"
        task.accepted_at = now
        task.started_at = now
        task.assigned_forklift.status = "executing"
        session.add(
            TaskEvent(
                task=task,
                event_type="sim_driver_accepted",
                driver=task.assigned_driver,
                forklift=task.assigned_forklift,
                location_x=task.assigned_forklift.current_x,
                location_y=task.assigned_forklift.current_y,
                message="全日模拟：司机自动接收任务。",
            )
        )
        accepted += 1
    return accepted


def assign_one_pending_task(session, admin):
    task = session.scalar(
        select(TransportTask)
        .where(TransportTask.status.in_(PENDING_TASK_STATUSES))
        .order_by(TransportTask.created_at.asc(), TransportTask.id.asc())
        .limit(1)
    )
    if not task:
        return None, ""
    try:
        result = assign_task(session, task.id, operator=admin)
        return result["task"], ""
    except ValueError as exc:
        return None, str(exc)


def trim_extra_pending_tasks(session):
    rows = session.scalars(
        select(TransportTask)
        .where(TransportTask.status.in_(PENDING_TASK_STATUSES))
        .order_by(TransportTask.created_at.asc(), TransportTask.id.asc())
    ).all()
    for task in rows[1:]:
        task.status = "exception"
        task.abnormal_reason = "全日模拟限制任务池仅保留一个待分配任务，自动转异常待人工处理。"
    return max(0, len(rows) - 1)


def workday_snapshot(session, since):
    return {
        "pending": pending_dispatch_count(session),
        "active": active_task_count(session),
        "completed": completed_task_count(session, since),
    }


def run_workday_simulation(session, ticks=160, step_seconds=90, max_created=80, driver_limit=None, verbose=False):
    admin = session.scalar(select(User).where(User.role == "admin").order_by(User.id).limit(1))
    if not admin:
        raise ValueError("需要至少一个管理员账号才能运行全日模拟")

    started_at = datetime.utcnow()
    resources = prepare_workday_resources(session, driver_limit=driver_limit)
    session.flush()

    stats = {
        "startedAt": started_at.isoformat(),
        "ticks": 0,
        "created": 0,
        "assigned": 0,
        "accepted": 0,
        "completed": 0,
        "maxPending": 0,
        "maxActive": 0,
        "extraPendingTrimmed": 0,
        "assignmentFailures": 0,
        "lastAssignmentError": "",
        **resources,
    }

    for tick in range(1, int(ticks) + 1):
        stats["ticks"] = tick
        stats["extraPendingTrimmed"] += trim_extra_pending_tasks(session)

        task, assign_error = assign_one_pending_task(session, admin)
        if task:
            stats["assigned"] += 1
        elif assign_error:
            stats["assignmentFailures"] += 1
            stats["lastAssignmentError"] = assign_error

        accepted = accept_assigned_tasks(session)
        stats["accepted"] += accepted

        if pending_dispatch_count(session) == 0 and stats["created"] < int(max_created):
            create_random_task(session, admin, stats["created"] + 1)
            stats["created"] += 1

        advance_simulation(session, step_seconds=step_seconds)
        snapshot = workday_snapshot(session, started_at)
        stats["completed"] = snapshot["completed"]
        stats["maxPending"] = max(stats["maxPending"], snapshot["pending"])
        stats["maxActive"] = max(stats["maxActive"], snapshot["active"])

        if verbose and (tick == 1 or tick % 10 == 0 or tick == int(ticks)):
            print(
                f"tick={tick} created={stats['created']} assigned={stats['assigned']} "
                f"accepted={stats['accepted']} completed={stats['completed']} "
                f"pending={snapshot['pending']} active={snapshot['active']}"
            )

    final_snapshot = workday_snapshot(session, started_at)
    stats.update({f"final{k.title()}": value for k, value in final_snapshot.items()})
    stats["finishedAt"] = datetime.utcnow().isoformat()
    return stats
