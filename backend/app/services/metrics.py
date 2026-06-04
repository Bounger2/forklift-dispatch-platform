from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select

from ..models import Alert, Driver, Forklift, TransportTask

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def local_day_bounds(now=None):
    current = now or datetime.utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_now = current.astimezone(LOCAL_TZ)
    start_local = datetime(
        local_now.year, local_now.month, local_now.day, tzinfo=LOCAL_TZ
    )
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
        start_local.date(),
    )


def local_period_bounds(period="week", now=None):
    current = now or datetime.utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_now = current.astimezone(LOCAL_TZ)

    if period == "day":
        start_local = datetime(local_now.year, local_now.month, local_now.day, tzinfo=LOCAL_TZ)
    elif period == "month":
        start_local = datetime(local_now.year, local_now.month, 1, tzinfo=LOCAL_TZ)
    elif period == "quarter":
        month = ((local_now.month - 1) // 3) * 3 + 1
        start_local = datetime(local_now.year, month, 1, tzinfo=LOCAL_TZ)
    elif period == "year":
        start_local = datetime(local_now.year, 1, 1, tzinfo=LOCAL_TZ)
    else:
        week_start = local_now - timedelta(days=local_now.weekday())
        start_local = datetime(week_start.year, week_start.month, week_start.day, tzinfo=LOCAL_TZ)
        period = "week"

    end_utc = local_now.astimezone(timezone.utc).replace(tzinfo=None)
    return start_local.astimezone(timezone.utc).replace(tzinfo=None), end_utc, period


def overview_metrics(session, now=None):
    today_start, tomorrow_start, _ = local_day_bounds(now)
    today_task_filter = (
        TransportTask.created_at >= today_start,
        TransportTask.created_at < tomorrow_start,
    )
    total_tasks = (
        session.scalar(select(func.count(TransportTask.id)).where(*today_task_filter))
        or 0
    )
    completed = session.scalar(
        select(func.count(TransportTask.id)).where(
            TransportTask.status == "completed", *today_task_filter
        )
    ) or 0
    pending = session.scalar(
        select(func.count(TransportTask.id)).where(
            TransportTask.status.in_(["pending_review", "pending_dispatch"])
        )
    ) or 0
    active = session.scalar(
        select(func.count(TransportTask.id)).where(
            TransportTask.status.in_(
                [
                    "assigned",
                    "accepted",
                    "to_origin",
                    "arrived_origin",
                    "loading",
                    "transporting",
                    "arrived_dest",
                    "unloading",
                    "exception",
                ]
            )
        )
    ) or 0
    vehicles = session.scalars(select(Forklift)).all()
    online = len([v for v in vehicles if v.online])
    usable = len(
        [
            v
            for v in vehicles
            if v.online and v.status in {"idle", "low_battery"} and v.battery_level > 15
        ]
    )
    open_alerts = session.scalar(select(func.count(Alert.id)).where(Alert.status == "open")) or 0
    avg_battery = round(sum(v.battery_level for v in vehicles) / max(len(vehicles), 1), 1)
    completion_rate = round(completed / max(total_tasks, 1) * 100, 1)
    return {
        "totalTasks": total_tasks,
        "completedTasks": completed,
        "pendingTasks": pending,
        "activeTasks": active,
        "onlineForklifts": online,
        "usableForklifts": usable,
        "openAlerts": open_alerts,
        "avgBattery": avg_battery,
        "completionRate": completion_rate,
    }


def daily_report(session, now=None):
    today_start, tomorrow_start, today = local_day_bounds(now)
    tasks = session.scalars(
        select(TransportTask).where(
            TransportTask.created_at >= today_start,
            TransportTask.created_at < tomorrow_start,
        )
    ).all()
    completed = [t for t in tasks if t.status == "completed"]
    abnormal = [t for t in tasks if t.status == "exception"]
    avg_eta = (
        round(sum(t.eta_minutes for t in completed) / len(completed), 1)
        if completed
        else 0
    )
    vehicles = session.scalars(select(Forklift)).all()
    drivers = session.scalars(select(Driver)).all()
    completed_by_driver = {}
    for task in completed:
        if not task.assigned_driver_id:
            continue
        minutes = 0
        if task.accepted_at and task.finished_at:
            minutes = max(1, int((task.finished_at - task.accepted_at).total_seconds() / 60))
        row = completed_by_driver.setdefault(
            task.assigned_driver_id, {"taskCount": 0, "workingMinutes": 0, "distance": 0.0}
        )
        row["taskCount"] += 1
        row["workingMinutes"] += minutes
        row["distance"] += task.distance or 0
    return {
        "date": today.isoformat(),
        "taskTotal": len(tasks),
        "completed": len(completed),
        "abnormal": len(abnormal),
        "avgResponseMinutes": avg_eta,
        "vehicleUtilization": [
            {
                "code": v.code,
                "status": v.status,
                "batteryLevel": v.battery_level,
                "area": v.current_area,
            }
            for v in vehicles
        ],
        "driverWorkload": [
            {
                "name": d.user.name,
                "team": d.user.team,
                "taskCount": completed_by_driver.get(d.id, {}).get("taskCount", 0),
                "workloadScore": min(
                    100,
                    round(
                        completed_by_driver.get(d.id, {}).get("workingMinutes", 0) / 4
                        + completed_by_driver.get(d.id, {}).get("taskCount", 0) * 8,
                        1,
                    ),
                ),
                "workingMinutes": completed_by_driver.get(d.id, {}).get("workingMinutes", 0),
                "distance": round(completed_by_driver.get(d.id, {}).get("distance", 0), 1),
            }
            for d in drivers
        ],
    }


def driver_day_gantt(session, now=None):
    today_start, tomorrow_start, today = local_day_bounds(now)
    current = now or datetime.utcnow()
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)

    drivers = session.scalars(select(Driver).order_by(Driver.employee_no)).all()
    tasks = session.scalars(
        select(TransportTask).where(
            TransportTask.assigned_driver_id.is_not(None),
            TransportTask.created_at < tomorrow_start,
            or_(TransportTask.finished_at.is_(None), TransportTask.finished_at >= today_start),
        )
    ).all()

    tasks_by_driver = {}
    for task in tasks:
        start = task.accepted_at or task.started_at or task.assigned_at or task.created_at
        end = task.finished_at or current
        if not start or not end:
            continue
        start = max(start, today_start)
        end = min(end, tomorrow_start)
        if end <= start:
            end = min(start + timedelta(minutes=5), tomorrow_start)
        if end <= today_start or start >= tomorrow_start:
            continue

        start_local = start.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        end_local = end.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        start_minutes = start_local.hour * 60 + start_local.minute
        end_minutes = end_local.hour * 60 + end_local.minute
        tasks_by_driver.setdefault(task.assigned_driver_id, []).append(
            {
                "taskId": task.id,
                "taskNo": task.task_no,
                "origin": task.origin_label,
                "destination": task.dest_label,
                "status": task.status,
                "priority": task.priority,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "startLabel": start_local.strftime("%H:%M"),
                "endLabel": end_local.strftime("%H:%M"),
                "startMinutes": max(0, min(1440, start_minutes)),
                "endMinutes": max(0, min(1440, end_minutes)),
            }
        )

    rows = []
    for driver in drivers:
        segments = sorted(
            tasks_by_driver.get(driver.id, []),
            key=lambda item: (item["startMinutes"], item["endMinutes"]),
        )
        rows.append(
            {
                "driverId": driver.id,
                "employeeNo": driver.employee_no,
                "name": driver.user.name if driver.user else "",
                "team": driver.user.team if driver.user else "",
                "segments": segments,
            }
        )

    return {"date": today.isoformat(), "rows": rows}


def driver_period_report(session, period="week", driver_id=None, now=None):
    start, end, period = local_period_bounds(period, now)

    driver_stmt = select(Driver).order_by(Driver.employee_no)
    if driver_id:
        driver_stmt = driver_stmt.where(Driver.id == driver_id)
    drivers = session.scalars(driver_stmt).all()

    task_stmt = select(TransportTask).where(
        TransportTask.status == "completed",
        TransportTask.finished_at >= start,
        TransportTask.finished_at <= end,
    )
    if driver_id:
        task_stmt = task_stmt.where(TransportTask.assigned_driver_id == driver_id)
    completed_tasks = session.scalars(task_stmt).all()

    tasks_by_driver = {}
    for task in completed_tasks:
        if task.assigned_driver_id:
            tasks_by_driver.setdefault(task.assigned_driver_id, []).append(task)

    rows = []
    for driver in drivers:
        tasks = tasks_by_driver.get(driver.id, [])
        total_distance = sum(task.distance or 0 for task in tasks)
        total_minutes = 0
        task_rows = []
        for task in tasks:
            minutes = 0
            if task.accepted_at and task.finished_at:
                minutes = max(1, int((task.finished_at - task.accepted_at).total_seconds() / 60))
                total_minutes += minutes
            task_rows.append(
                {
                    "taskNo": task.task_no,
                    "origin": task.origin_label,
                    "destination": task.dest_label,
                    "acceptedAt": task.accepted_at.isoformat() if task.accepted_at else None,
                    "finishedAt": task.finished_at.isoformat() if task.finished_at else None,
                    "distance": round(task.distance or 0, 1),
                    "minutes": minutes,
                }
            )
        rows.append(
            {
                "driverId": driver.id,
                "employeeNo": driver.employee_no,
                "name": driver.user.name if driver.user else "",
                "team": driver.user.team if driver.user else "",
                "taskCount": len(tasks),
                "totalDistance": round(total_distance, 1),
                "totalMinutes": total_minutes,
                "avgDistance": round(total_distance / max(len(tasks), 1), 1),
                "completedTasks": task_rows,
            }
        )
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": rows,
    }
