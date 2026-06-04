import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.gettempdir()) / 'forklift_dispatch_pytest.db'}"
os.environ["SIMULATION_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.database import session_scope
from app.models import Alert, Driver, Forklift, ForkliftPosition, MapPoint, TransportTask
from app.seed import seed_all
from app.services.metrics import daily_report, overview_metrics
from app.services.workday_simulator import run_workday_simulation


def fresh_client():
    app = create_app()
    with session_scope() as session:
        seed_all(session, reset=True)
    return app.test_client()


def test_recommendation_and_assignment():
    client = fresh_client()
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login.status_code == 200
    token = login.json["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    rec = client.get("/api/tasks/1/recommendations", headers=headers)
    assert rec.status_code == 200
    assert rec.json["data"]["candidates"]
    assert rec.json["data"]["weights"]["distance_eta"] > 0

    assigned = client.post("/api/tasks/1/assign", json={}, headers=headers)
    assert assigned.status_code == 200
    assert assigned.json["data"]["task"]["status"] == "assigned"


def test_manual_assignment_is_visible_to_driver():
    client = fresh_client()
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    rec = client.get("/api/tasks/1/recommendations", headers=headers)
    candidate = rec.json["data"]["candidates"][0]
    forklift_id = candidate["vehicle"]["id"]
    driver_username = candidate["driver"]["employeeNo"].lower()

    assigned = client.post(
        "/api/tasks/1/assign",
        json={"forkliftId": forklift_id},
        headers=headers,
    )
    assert assigned.status_code == 200
    assert assigned.json["data"]["task"]["assignedDriver"]["employeeNo"].lower() == driver_username

    driver_login = client.post(
        "/api/auth/login",
        json={"username": driver_username, "password": "123456"},
    )
    driver_headers = {"Authorization": f"Bearer {driver_login.json['data']['token']}"}
    my_tasks = client.get("/api/tasks", headers=driver_headers)
    task_numbers = [task["taskNo"] for task in my_tasks.json["data"]]
    assert assigned.json["data"]["task"]["taskNo"] in task_numbers


def test_custom_rule_can_be_created():
    client = fresh_client()
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    token = login.json["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/rules",
        json={
            "name": "测试自定义加权",
            "category": "manual",
            "ruleType": "custom_boost",
            "conditionJson": {"match": {"vehicleCode": "FLC-001"}},
            "actionJson": {"scoreBoost": 10},
            "description": "测试用户可配置规则。",
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json["data"]["editable"] is True


def test_temporary_map_points_are_retired_after_task_completion():
    client = fresh_client()
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    token = login.json["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    origin = client.post(
        "/api/map-points",
        json={
            "name": "临时取货点-测试",
            "pointType": "pickup",
            "area": "任务临时点",
            "x": 22,
            "y": 33,
            "temporary": True,
        },
        headers=headers,
    )
    dest = client.post(
        "/api/map-points",
        json={
            "name": "临时送货点-测试",
            "pointType": "dropoff",
            "area": "任务临时点",
            "x": 66,
            "y": 77,
            "temporary": True,
        },
        headers=headers,
    )
    assert origin.status_code == 201
    assert dest.status_code == 201
    assert origin.json["data"]["temporary"] is True
    assert dest.json["data"]["temporary"] is True

    task = client.post(
        "/api/tasks",
        json={
            "originPointId": origin.json["data"]["id"],
            "destPointId": dest.json["data"]["id"],
            "cargoType": "地图标点测试货物",
            "estimatedWeight": 100,
            "palletCount": 1,
            "priority": "B",
        },
        headers=headers,
    )
    assert task.status_code == 201

    completed = client.post(
        f"/api/tasks/{task.json['data']['id']}/status",
        json={"status": "completed"},
        headers=headers,
    )
    assert completed.status_code == 200

    with session_scope() as session:
        rows = session.scalars(
            select(MapPoint).where(MapPoint.id.in_([origin.json["data"]["id"], dest.json["data"]["id"]]))
        ).all()
        assert {row.is_temporary for row in rows} == {True}
        assert {row.enabled for row in rows} == {False}

    visible_points = client.get("/api/map-points", headers=headers)
    visible_ids = {point["id"] for point in visible_points.json["data"]}
    assert origin.json["data"]["id"] not in visible_ids
    assert dest.json["data"]["id"] not in visible_ids


def test_vehicle_binding_can_be_changed_and_closed():
    client = fresh_client()
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    token = login.json["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with session_scope() as session:
        session.get(Driver, 9).shift_status = "on_shift"

    changed = client.post(
        "/api/bindings",
        json={
            "driverId": 9,
            "forkliftId": 1,
            "shiftCode": "DAY",
            "bindMethod": "manual",
        },
        headers=headers,
    )
    assert changed.status_code == 201
    assert changed.json["data"]["driver"]["id"] == 9
    assert changed.json["data"]["forklift"]["id"] == 1

    binding_id = changed.json["data"]["id"]
    closed = client.post(f"/api/bindings/{binding_id}/close", json={}, headers=headers)
    assert closed.status_code == 200
    assert closed.json["data"]["status"] == "closed"


def test_admin_can_manage_forklifts_and_schedules():
    client = fresh_client()
    login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    vehicle = client.post(
        "/api/vehicles",
        json={
            "code": "FLC-T99",
            "plateNo": "苏F-T99",
            "model": "4T 柴油叉车",
            "powerType": "diesel",
            "tonnage": 4,
            "status": "idle",
            "fuelLevel": 88,
            "batteryLevel": 0,
            "currentArea": "测试区域",
            "x": 52,
            "y": 48,
        },
        headers=headers,
    )
    assert vehicle.status_code == 201
    assert vehicle.json["data"]["powerType"] == "diesel"
    assert vehicle.json["data"]["energyLevel"] == 88

    patched_vehicle = client.patch(
        f"/api/vehicles/{vehicle.json['data']['id']}",
        json={"fuelLevel": 66, "note": "测试修改"},
        headers=headers,
    )
    assert patched_vehicle.status_code == 200
    assert patched_vehicle.json["data"]["fuelLevel"] == 66

    assignment = client.post(
        "/api/schedules/assignments",
        json={
            "shiftDate": "2026-06-02",
            "shiftCode": "DAY",
            "driverId": 9,
            "forkliftId": vehicle.json["data"]["id"],
            "area": "测试区域",
            "status": "scheduled",
        },
        headers=headers,
    )
    assert assignment.status_code == 201
    assert assignment.json["data"]["forklift"]["code"] == "FLC-T99"

    patched_assignment = client.patch(
        f"/api/schedules/assignments/{assignment.json['data']['id']}",
        json={"area": "测试区域B", "status": "signed_in"},
        headers=headers,
    )
    assert patched_assignment.status_code == 200
    assert patched_assignment.json["data"]["area"] == "测试区域B"

    deleted_assignment = client.delete(
        f"/api/schedules/assignments/{assignment.json['data']['id']}",
        headers=headers,
    )
    assert deleted_assignment.status_code == 200

    deleted_vehicle = client.delete(f"/api/vehicles/{vehicle.json['data']['id']}", headers=headers)
    assert deleted_vehicle.status_code == 200
    assert deleted_vehicle.json["data"]["status"] == "disabled"


def test_admin_can_read_basemap_and_sync_latest_gps():
    client = fresh_client()
    login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    basemap = client.get("/api/basemap")
    assert basemap.status_code == 200
    assert basemap.json["data"]["scaleMeters"] == 50

    with session_scope() as session:
        vehicle = session.scalar(select(Forklift).where(Forklift.code == "FLC-001"))
        session.add(
            ForkliftPosition(
                forklift_id=vehicle.id,
                recorded_at=datetime.utcnow() + timedelta(minutes=1),
                x=77.7,
                y=66.6,
                heading=90,
                speed=5.5,
                source="hardware",
                area="GPS测试区",
            )
        )

    overview = client.get("/api/overview", headers=headers)
    assert overview.status_code == 200
    vehicle = next(row for row in overview.json["data"]["vehicles"] if row["code"] == "FLC-001")
    assert vehicle["x"] == 77.7
    assert vehicle["y"] == 66.6
    assert vehicle["currentArea"] == "GPS测试区"
    gantt = overview.json["data"]["driverGantt"]
    assert gantt["date"]
    assert gantt["rows"]
    assert {"driverId", "employeeNo", "name", "segments"} <= set(gantt["rows"][0])


def test_overview_metrics_count_only_local_today_tasks():
    client = fresh_client()
    now = datetime(2026, 6, 4, 0, 30)
    with client.application.app_context(), session_scope() as session:
        tasks = session.scalars(select(TransportTask).order_by(TransportTask.id)).all()
        for task in tasks:
            task.created_at = datetime(2026, 6, 2, 8, 0)
            task.updated_at = task.created_at
            if task.finished_at:
                task.finished_at = datetime(2026, 6, 2, 9, 0)
        session.commit()

        metrics = overview_metrics(session, now=now)
        report = daily_report(session, now=now)
        assert metrics["totalTasks"] == 0
        assert metrics["completedTasks"] == 0
        assert metrics["completionRate"] == 0
        assert report["taskTotal"] == 0

        task = tasks[0]
        task.created_at = datetime(2026, 6, 3, 18, 0)
        task.updated_at = task.created_at
        task.status = "completed"
        session.commit()

        metrics = overview_metrics(session, now=now)
        report = daily_report(session, now=now)
        assert metrics["totalTasks"] == 1
        assert metrics["completedTasks"] == 1
        assert metrics["completionRate"] == 100
        assert report["taskTotal"] == 1


def test_admin_can_create_users_and_read_driver_report():
    client = fresh_client()
    login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    admin_user = client.post(
        "/api/users",
        json={
            "username": "admin2",
            "password": "123456",
            "name": "管理员测试",
            "role": "admin",
            "team": "平台组",
            "wecomUserId": "wecom_admin2",
        },
        headers=headers,
    )
    assert admin_user.status_code == 201
    assert admin_user.json["data"]["role"] == "admin"

    patched = client.patch(
        f"/api/users/{admin_user.json['data']['id']}",
        json={
            "name": "管理员测试修改",
            "team": "平台二组",
            "wecomUserId": "wecom_admin2_updated",
            "status": "active",
        },
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json["data"]["name"] == "管理员测试修改"
    assert patched.json["data"]["team"] == "平台二组"

    driver = client.post(
        "/api/users",
        json={
            "username": "d099",
            "password": "123456",
            "name": "司机测试",
            "role": "driver",
            "employeeNo": "D099",
            "team": "测试班组",
            "wecomUserId": "wecom_d099",
        },
        headers=headers,
    )
    assert driver.status_code == 201
    assert driver.json["data"]["role"] == "driver"

    deleted = client.delete(f"/api/users/{driver.json['data']['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json["data"]["status"] == "disabled"

    report = client.get("/api/reports/drivers?period=month", headers=headers)
    assert report.status_code == 200
    assert report.json["data"]["period"] == "month"
    assert report.json["data"]["rows"]

    day_report = client.get("/api/reports/drivers?period=day", headers=headers)
    assert day_report.status_code == 200
    assert day_report.json["data"]["period"] == "day"

    year_report = client.get("/api/reports/drivers?period=year", headers=headers)
    assert year_report.status_code == 200
    assert year_report.json["data"]["period"] == "year"

    fallback_report = client.get("/api/reports/drivers?period=bad", headers=headers)
    assert fallback_report.status_code == 200
    assert fallback_report.json["data"]["period"] == "week"


def test_driver_can_go_online_and_request_idle_forklift():
    client = fresh_client()
    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json['data']['token']}"}

    driver_user = client.post(
        "/api/users",
        json={
            "username": "d088",
            "password": "123456",
            "name": "司机申请测试",
            "role": "driver",
            "employeeNo": "D088",
            "team": "测试班",
            "shiftStatus": "off_shift",
        },
        headers=admin_headers,
    )
    assert driver_user.status_code == 201

    vehicle = client.post(
        "/api/vehicles",
        json={
            "code": "FLC-088",
            "plateNo": "TEST-088",
            "model": "3T 电动测试车",
            "powerType": "electric",
            "tonnage": 3,
            "status": "idle",
            "batteryLevel": 88,
            "online": True,
            "currentArea": "测试区",
            "x": 28,
            "y": 32,
        },
        headers=admin_headers,
    )
    assert vehicle.status_code == 201

    driver_login = client.post("/api/auth/login", json={"username": "d088", "password": "123456"})
    driver_headers = {"Authorization": f"Bearer {driver_login.json['data']['token']}"}

    rejected = client.post(
        "/api/driver/forklift-requests",
        json={"forkliftId": vehicle.json["data"]["id"]},
        headers=driver_headers,
    )
    assert rejected.status_code == 400

    online = client.patch("/api/driver/status", json={"shiftStatus": "on_shift"}, headers=driver_headers)
    assert online.status_code == 200
    assert online.json["data"]["shiftStatus"] == "on_shift"

    requested = client.post(
        "/api/driver/forklift-requests",
        json={"forkliftId": vehicle.json["data"]["id"]},
        headers=driver_headers,
    )
    assert requested.status_code == 201
    assert requested.json["data"]["alertType"] == "forklift_request"
    assert requested.json["data"]["forklift"]["code"] == "FLC-088"

    personal_report = client.get("/api/reports/me?period=week", headers=driver_headers)
    assert personal_report.status_code == 200
    assert personal_report.json["data"]["rows"][0]["employeeNo"] == "D088"

    offline = client.patch("/api/driver/status", json={"shiftStatus": "off_shift"}, headers=driver_headers)
    assert offline.status_code == 200
    assert offline.json["data"]["shiftStatus"] == "off_shift"


def test_workday_simulator_runs_full_dispatch_flow():
    client = fresh_client()
    with client.application.app_context(), session_scope() as session:
        stats = run_workday_simulation(
            session,
            ticks=45,
            step_seconds=90,
            max_created=12,
            driver_limit=6,
            verbose=False,
        )
        assert stats["created"] > 0
        assert stats["assigned"] > 0
        assert stats["accepted"] > 0
        assert stats["completed"] > 0
        assert stats["maxPending"] <= 1
        assert stats["extraPendingTrimmed"] == 0


def test_driver_can_accept_reject_and_complete_tasks():
    client = fresh_client()

    d001_login = client.post("/api/auth/login", json={"username": "d001", "password": "123456"})
    d001_headers = {"Authorization": f"Bearer {d001_login.json['data']['token']}"}
    my_tasks = client.get("/api/tasks", headers=d001_headers)
    assert my_tasks.status_code == 200
    assert len(my_tasks.json["data"]) == 1
    task_id = my_tasks.json["data"][0]["id"]

    accepted = client.post(f"/api/tasks/{task_id}/driver-accept", json={}, headers=d001_headers)
    assert accepted.status_code == 200
    assert accepted.json["data"]["acceptedAt"]

    completed = client.post(
        f"/api/tasks/{task_id}/driver-complete",
        json={},
        headers=d001_headers,
    )
    assert completed.status_code == 200
    assert completed.json["data"]["status"] == "completed"
    assert completed.json["data"]["distance"] > 0

    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json['data']['token']}"}
    create = client.post(
        "/api/tasks",
        json={
            "originPointId": 1,
            "destPointId": 2,
            "cargoType": "拒绝测试货物",
            "estimatedWeight": 100,
            "palletCount": 1,
            "priority": "B",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201
    assign = client.post(f"/api/tasks/{create.json['data']['id']}/assign", json={}, headers=admin_headers)
    assert assign.status_code == 200
    assigned_driver_username = assign.json["data"]["assigned"]["driver"]["employeeNo"].lower()

    driver_login = client.post(
        "/api/auth/login",
        json={"username": assigned_driver_username, "password": "123456"},
    )
    driver_headers = {"Authorization": f"Bearer {driver_login.json['data']['token']}"}
    rejected = client.post(
        f"/api/tasks/{create.json['data']['id']}/driver-reject",
        json={"reason": "现场通道受阻"},
        headers=driver_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json["data"]["status"] == "pending_dispatch"
    assert "现场通道受阻" in rejected.json["data"]["abnormalReason"]


def test_admin_can_batch_close_open_alerts():
    client = fresh_client()
    login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    with client.application.app_context(), session_scope() as session:
        alerts = [
            Alert(
                code="TEST_BATCH_OPEN_1",
                alert_type="dispatch_failure",
                severity="critical",
                status="open",
                title="测试异常 1",
                message="测试批量闭环",
                suggestion="待处理",
            ),
            Alert(
                code="TEST_BATCH_OPEN_2",
                alert_type="low_battery",
                severity="warning",
                status="open",
                title="测试异常 2",
                message="测试批量闭环",
                suggestion="待处理",
            ),
            Alert(
                code="TEST_BATCH_CLOSED",
                alert_type="offline",
                severity="critical",
                status="closed",
                title="已关闭异常",
                message="不应重复关闭",
                suggestion="已处理",
                closed_at=datetime.utcnow(),
            ),
        ]
        session.add_all(alerts)
        session.commit()
        ids = [alert.id for alert in alerts]

    closed = client.post(
        "/api/alerts/batch-close",
        json={"ids": ids, "message": "批量测试"},
        headers=headers,
    )
    assert closed.status_code == 200
    assert closed.json["data"]["closed"] == 2
    assert closed.json["data"]["requested"] == 3

    open_alerts = client.get("/api/alerts", headers=headers)
    open_codes = {alert["code"] for alert in open_alerts.json["data"]}
    assert "TEST_BATCH_OPEN_1" not in open_codes
    assert "TEST_BATCH_OPEN_2" not in open_codes

    closed_alerts = client.get("/api/alerts?status=closed", headers=headers)
    closed_codes = {alert["code"] for alert in closed_alerts.json["data"]}
    assert {"TEST_BATCH_OPEN_1", "TEST_BATCH_OPEN_2", "TEST_BATCH_CLOSED"} <= closed_codes
