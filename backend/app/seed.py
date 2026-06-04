from datetime import date, datetime, timedelta

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .database import Base, engine
from .models import (
    DispatchRule,
    Driver,
    Forklift,
    ForkliftPosition,
    MapPoint,
    ScheduleAssignment,
    ShiftTemplate,
    TaskEvent,
    TransportTask,
    User,
    VehicleBinding,
)


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_all(session, reset=False):
    if reset:
        reset_database()
    if session.scalar(select(User).limit(1)):
        return

    users = seed_users(session)
    points = seed_map_points(session)
    drivers = seed_drivers(session, users)
    forklifts = seed_forklifts(session, drivers)
    seed_shifts(session, drivers, forklifts)
    seed_rules(session)
    seed_tasks(session, users, points, forklifts, drivers)
    seed_alerts(session, forklifts)
    session.commit()


def seed_users(session):
    rows = [
        ("admin", "系统管理员", "admin", "信息化部", "平台组", "wecom_admin"),
    ]
    users = {}
    for username, name, role, dept, team, wecom in rows:
        user = User(
            username=username,
            password_hash=generate_password_hash("123456"),
            name=name,
            role=role,
            department=dept,
            team=team,
            phone="13800000000",
            wecom_user_id=wecom,
        )
        session.add(user)
        users[username] = user
    return users


def seed_drivers(session, users):
    names = [
        ("D001", "司机赵强", "A组", 18),
        ("D002", "司机孙浩", "A组", 34),
        ("D003", "司机周亮", "B组", 44),
        ("D004", "司机吴杰", "B组", 12),
        ("D005", "司机郑峰", "C组", 28),
        ("D006", "司机钱磊", "C组", 58),
        ("D007", "司机冯涛", "机动组", 6),
        ("D008", "司机陈凯", "机动组", 72),
        ("D009", "司机蒋明", "夜班组", 0),
        ("D010", "司机韩旭", "夜班组", 0),
    ]
    drivers = []
    for employee_no, name, team, workload in names:
        user = User(
            username=employee_no.lower(),
            password_hash=generate_password_hash("123456"),
            name=name,
            role="driver",
            department="物流部",
            team=team,
            phone=f"139{employee_no[-3:]}0000",
            wecom_user_id=f"wecom_{employee_no.lower()}",
        )
        driver = Driver(
            user=user,
            employee_no=employee_no,
            shift_status="on_shift" if employee_no not in {"D009", "D010"} else "off_shift",
            bind_status="bound" if employee_no <= "D008" else "unbound",
            workload_score=workload,
            task_count_today=max(0, workload // 12),
            working_minutes_today=workload * 3,
            distance_today=workload * 0.8,
            emergency_count_today=1 if workload > 50 else 0,
        )
        session.add_all([user, driver])
        drivers.append(driver)
    return drivers


def seed_map_points(session):
    rows = [
        ("南门待命区", "parking", "南侧主干道", 18, 82, "门卫"),
        ("北侧原料仓库A", "pickup", "北侧仓储区", 31, 24, "仓库A"),
        ("北侧原料仓库B", "pickup", "北侧仓储区", 56, 29, "仓库B"),
        ("中心线缆车间", "dropoff", "中心生产区", 49, 51, "车间一"),
        ("东侧成品暂存区", "pickup", "东侧装卸区", 74, 52, "成品库"),
        ("东门装卸口1", "dock", "东侧装卸区", 84, 36, "装卸班"),
        ("东门装卸口2", "dock", "东侧装卸区", 83, 65, "装卸班"),
        ("南侧辅料仓库", "pickup", "南侧仓储区", 42, 78, "辅料库"),
        ("西侧维修点", "maintenance", "西侧通道", 17, 57, "维保"),
        ("充电区", "charging", "南侧主干道", 66, 79, "设备组"),
        ("车间入口LoRa点", "lora", "中心生产区", 40, 49, "定位"),
        ("仓库门洞LoRa点", "lora", "北侧仓储区", 45, 32, "定位"),
        ("临时交接点", "handover", "中心通道", 57, 57, "调度"),
        ("西北通行点", "route", "西侧通道", 20, 29, "调度"),
        ("东北通行点", "route", "北侧通道", 78, 25, "调度"),
    ]
    points = {}
    for name, point_type, area, x, y, contact in rows:
        point = MapPoint(
            name=name,
            point_type=point_type,
            area=area,
            x=x,
            y=y,
            geofence_radius=6 if point_type in {"pickup", "dropoff", "dock"} else 4,
            contact=contact,
            description="系统默认厂区作业点，可在地图中继续新增/调整。",
        )
        session.add(point)
        points[name] = point
    return points



def seed_forklifts(session, drivers):
    rows = [
        ("FLC-001", "苏F-001", "3T 电动平衡重", "electric", 3.0, "idle", 88, 0, True, 20, 80),
        ("FLC-002", "苏F-002", "3T 电动平衡重", "electric", 3.0, "idle", 74, 0, True, 34, 25),
        ("FLC-003", "苏F-003", "5T 柴油叉车", "diesel", 5.0, "assigned", 0, 67, True, 49, 51),
        ("FLC-004", "苏F-004", "2T 电动叉车", "electric", 2.0, "idle", 45, 0, True, 82, 37),
        ("FLC-005", "苏F-005", "3T 电动平衡重", "electric", 3.0, "low_battery", 19, 0, True, 66, 78),
        ("FLC-006", "苏F-006", "5T 柴油叉车", "diesel", 5.0, "maintenance", 0, 82, True, 17, 57),
        ("FLC-007", "苏F-007", "3T 电动平衡重", "electric", 3.0, "idle", 93, 0, True, 74, 54),
        ("FLC-008", "苏F-008", "3T 电动平衡重", "electric", 3.0, "idle", 61, 0, True, 43, 79),
        ("FLC-009", "苏F-009", "2T 电动叉车", "electric", 2.0, "offline", 52, 0, False, 56, 29),
    ]
    forklifts = []
    for index, row in enumerate(rows):
        code, plate, model, power_type, tonnage, status, battery, fuel, online, x, y = row
        driver = drivers[index] if index < len(drivers) and index < 8 else None
        forklift = Forklift(
            code=code,
            plate_no=plate,
            model=model,
            power_type=power_type,
            tonnage=tonnage,
            status=status,
            battery_level=battery,
            fuel_level=fuel,
            online=online,
            current_x=x,
            current_y=y,
            current_area="初始区域",
            driver=driver,
        )
        session.add(forklift)
        forklifts.append(forklift)
        if driver:
            session.add(
                VehicleBinding(
                    forklift=forklift,
                    driver=driver,
                    shift_code="DAY",
                    status="active",
                    bind_method="rfid",
                )
            )
    return forklifts


def seed_shifts(session, drivers, forklifts):
    templates = [
        ("DAY", "早班", "08:00", "16:00", "全厂"),
        ("MID", "中班", "16:00", "00:00", "全厂"),
        ("NIGHT", "夜班", "00:00", "08:00", "全厂"),
        ("TEMP", "临时班", "10:00", "18:00", "高峰支援"),
    ]
    for code, name, start, end, area in templates:
        session.add(
            ShiftTemplate(
                code=code,
                name=name,
                start_time=start,
                end_time=end,
                area=area,
            )
        )
    today = date.today()
    for idx, driver in enumerate(drivers[:8]):
        session.add(
            ScheduleAssignment(
                shift_date=today,
                shift_code="DAY",
                driver=driver,
                forklift=forklifts[idx],
                area="全厂" if idx < 4 else "东侧装卸区",
                status="signed_in",
            )
        )


def seed_rules(session):
    rules = [
        (
            "FILTER_SHIFT_ON",
            "未当班/未签到禁止派单",
            "filter",
            "availability",
            10,
            0,
            {"field": "driver.shiftStatus", "operator": "eq", "value": "on_shift"},
            {"rejectMessage": "司机未当班或未签到"},
            "强制读取排班状态，未排班人员不可接单。",
        ),
        (
            "FILTER_BINDING_ACTIVE",
            "未人车绑定禁止派单",
            "filter",
            "binding",
            11,
            0,
            {"field": "binding.status", "operator": "eq", "value": "active"},
            {"rejectMessage": "车辆未完成 RFID 人车绑定"},
            "避免责任不清和冒名作业。",
        ),
        (
            "FILTER_VEHICLE_ONLINE",
            "车辆离线禁止派单",
            "filter",
            "vehicle_state",
            12,
            0,
            {"field": "vehicle.online", "operator": "eq", "value": True},
            {"rejectMessage": "车载终端离线"},
            "设备离线时保留最后有效位置并转人工处理。",
        ),
        (
            "FILTER_VEHICLE_IDLE",
            "仅空闲可用车辆进入候选池",
            "filter",
            "vehicle_state",
            13,
            0,
            {"field": "vehicle.status", "operator": "in", "value": ["idle", "low_battery"]},
            {"rejectMessage": "车辆正在执行/充电/维保/故障/停用"},
            "调度引擎只从空闲且可用车辆池中选择。",
        ),
        (
            "FILTER_BATTERY_FORBID",
            "低于禁派电量禁止新任务",
            "filter",
            "energy",
            14,
            0,
            {"field": "vehicle.batteryLevel", "operator": "gt", "value": 15},
            {"rejectMessage": "电量低于禁派阈值"},
            "达到禁派阈值时不再接收新任务。",
        ),
        (
            "SCORE_DISTANCE_ETA",
            "距离与预计到达时间",
            "score",
            "weight",
            30,
            0.30,
            {},
            {"factor": "distance_eta"},
            "优先选择距离起点更近、空驶距离更短、预计到达更快的车辆。",
        ),
        (
            "SCORE_PRIORITY_DEADLINE",
            "任务优先级与时限",
            "score",
            "weight",
            31,
            0.20,
            {},
            {"factor": "priority_deadline"},
            "紧急任务、临近超时任务优先。",
        ),
        (
            "SCORE_DRIVER_LOAD",
            "司机当前负荷均衡",
            "score",
            "weight",
            32,
            0.20,
            {},
            {"factor": "driver_load"},
            "优先派给负荷较低人员，降低连续高负荷司机权重。",
        ),
        (
            "SCORE_VEHICLE_FIT",
            "车辆状态与适配性",
            "score",
            "weight",
            33,
            0.15,
            {},
            {"factor": "vehicle_fit"},
            "按吨位、车型、能量状态、故障/维保状态进行筛选加权。",
        ),
        (
            "SCORE_CONGESTION",
            "区域拥堵与扎堆抑制",
            "score",
            "weight",
            34,
            0.10,
            {},
            {"factor": "area_congestion"},
            "同一区域车辆过多或任务积压时降低继续派入权重。",
        ),
        (
            "SCORE_MANUAL_RULE",
            "管理员人工规则",
            "score",
            "weight",
            35,
            0.05,
            {},
            {"factor": "manual_rule"},
            "保留人工置顶、指定司机、指定车辆、禁派区域、临时锁定等规则。",
        ),
        (
            "INSERT_S_PRIORITY",
            "S级任务立即插队",
            "priority",
            "urgent_insert",
            40,
            0,
            {"priority": "S"},
            {"popup": True, "wecomNotify": ["admin"], "canPreempt": True},
            "S级任务可抢占未接单或未出发普通任务，运输中不强制打断。",
        ),
        (
            "REASSIGN_BEFORE_ACCEPT",
            "已派未接可自动撤回重派",
            "reassign",
            "task_stage",
            50,
            0,
            {"taskStatus": "assigned"},
            {"action": "auto_recall_and_reassign"},
            "司机未接单阶段可以自动撤回并重新派单。",
        ),
        (
            "REASSIGN_BEFORE_ORIGIN",
            "接单未到起点需管理员确认改派",
            "reassign",
            "task_stage",
            51,
            0,
            {"taskStatus": "to_origin"},
            {"action": "confirm_reassign", "notifyOriginalDriver": True},
            "原司机收到撤单说明，所有操作记录原因。",
        ),
        (
            "REASSIGN_AFTER_LOADING",
            "已装货或运输中转人工处置",
            "reassign",
            "task_stage",
            52,
            0,
            {"taskStatus": ["loading", "transporting"]},
            {"action": "manual_handover", "options": ["临时交接点", "补派车辆", "变更终点"]},
            "运输中不建议强制打断，避免现场安全和责任风险。",
        ),
        (
            "EXCEPTION_WAITING_TIMEOUT",
            "车到人未到/等待超时",
            "exception",
            "timeout",
            60,
            0,
            {"geofence": "origin_or_dest", "waitingMinutesGt": 10},
            {"notify": ["requester", "driver", "admin"], "escalateMinutes": 20},
            "车辆进入围栏后等待超过阈值，用车人未确认装卸条件。",
        ),
        (
            "EXCEPTION_SITE_NOT_READY",
            "现场不具备作业条件",
            "exception",
            "site",
            61,
            0,
            {"driverReasonIn": ["货未备好", "通道受阻", "无人交接", "装卸点占用"]},
            {"actions": ["催办", "改派", "挂起", "取消"]},
            "司机上报现场条件问题后生成异常工单并闭环。",
        ),
        (
            "EXCEPTION_ROUTE_DEVIATION",
            "未按任务执行/路线偏离",
            "exception",
            "route",
            62,
            0,
            {"routeDeviationMinutesGt": 5},
            {"notify": ["admin", "team_leader"], "actions": ["允许绕行", "纠偏提醒", "标记违规"]},
            "车辆偏离推荐路线或未进入任务区域持续超过阈值。",
        ),
        (
            "EXCEPTION_LONG_STATIC",
            "中途脱岗或长期静止",
            "exception",
            "idle",
            63,
            0,
            {"nonWorkAreaStaticMinutesGt": 15},
            {"notify": ["admin"], "requireDriverReason": True},
            "非作业区域静止超过阈值且未上报等待/充电/维保。",
        ),
        (
            "EXCEPTION_PEAK_BACKLOG",
            "高峰期任务堆积",
            "exception",
            "peak",
            64,
            0,
            {"pendingTasksGt": 8, "avgWaitMinutesGt": 15},
            {"suggestions": ["启用备用司机", "暂停低优先级", "调整驻车点"]},
            "滚动预测未来一段时间是否无法按时完成任务。",
        ),
        (
            "EXCEPTION_LONG_IDLE",
            "叉车长期闲置",
            "exception",
            "resource",
            65,
            0,
            {"onlineIdleMinutesGt": 30, "sameTeamHasPendingTask": True},
            {"suggestion": "后续任务优先派给该车辆/司机或调整驻车区域"},
            "避免部分司机一直忙、部分司机一直闲。",
        ),
        (
            "EXCEPTION_AREA_CONGESTION",
            "扎堆作业/区域拥堵",
            "exception",
            "congestion",
            66,
            0,
            {"vehiclesInAreaGt": 3},
            {"mapHighlight": True, "action": "stop_dispatch_into_area"},
            "地图区域变色提醒，管理员分流至其他装卸点。",
        ),
        (
            "EXCEPTION_POSITION_QUALITY",
            "设备离线/定位异常",
            "exception",
            "position",
            67,
            0,
            {"qualityLt": 0.65},
            {"notify": ["admin", "maintenance"], "fallback": "last_valid_position"},
            "定位漂移、无数据上报或定位质量低于阈值。",
        ),
        (
            "REPORT_DAILY_PUSH",
            "每日运营日报企业微信推送",
            "report",
            "wecom",
            80,
            0,
            {"time": "17:10"},
            {"targets": ["admin"], "reports": ["异常汇总", "运营日报"]},
            "每日班后生成任务、准时率、车辆利用率、司机负荷等报表。",
        ),
    ]
    for code, name, category, rule_type, priority, weight, condition, action, desc in rules:
        session.add(
            DispatchRule(
                code=code,
                name=name,
                category=category,
                rule_type=rule_type,
                priority=priority,
                weight=weight,
                condition_json=condition,
                action_json=action,
                description=desc,
                editable=category not in {"filter"},
            )
        )


def seed_tasks(session, users, points, forklifts, drivers):
    admin = users["admin"]
    now = datetime.utcnow()
    data = [
        ("TASK-20260601-001", "北侧原料仓库A", "中心线缆车间", "铜线盘", 1800, 3, "A", "pending_dispatch", 90, None),
        ("TASK-20260601-002", "东侧成品暂存区", "东门装卸口1", "成品托盘", 2200, 4, "B", "assigned", 120, 0),
        ("TASK-20260601-003", "南侧辅料仓库", "中心线缆车间", "辅料箱", 900, 2, "C", "completed", 180, 1),
    ]
    for idx, row in enumerate(data):
        task_no, origin_name, dest_name, cargo, weight, pallets, priority, status, deadline, driver_index = row
        task = TransportTask(
            task_no=task_no,
            requester=admin,
            origin=points[origin_name],
            destination=points[dest_name],
            origin_label=origin_name,
            dest_label=dest_name,
            cargo_type=cargo,
            estimated_weight=weight,
            pallet_count=pallets,
            expected_finish_at=now + timedelta(minutes=deadline),
            priority=priority,
            status=status,
            note="核心流程样例工单：管理员创建、派给司机、司机接受/拒绝/完成。",
        )
        if driver_index is not None:
            forklift = forklifts[driver_index]
            driver = drivers[driver_index]
            task.assigned_forklift = forklift
            task.assigned_driver = driver
            task.assigned_at = now - timedelta(minutes=20)
            task.eta_minutes = 12 + idx
            task.distance = 20 + idx * 5
            forklift.status = "assigned" if status == "assigned" else "idle"
            if status == "completed":
                task.accepted_at = now - timedelta(minutes=75)
                task.started_at = task.accepted_at
                task.finished_at = now - timedelta(minutes=15)
                task.distance = 8.6
                driver.task_count_today += 1
                driver.working_minutes_today += 60
                driver.distance_today += task.distance
            session.add(
                TaskEvent(
                    task=task,
                    event_type="seed_task",
                    operator=admin,
                    forklift=forklift,
                    driver=driver,
                    location_x=forklift.current_x,
                    location_y=forklift.current_y,
                    message=f"初始化状态：{status}",
                )
            )
        session.add(task)
    for forklift in forklifts:
        session.add(
            ForkliftPosition(
                forklift=forklift,
                recorded_at=now,
                x=forklift.current_x,
                y=forklift.current_y,
                heading=forklift.heading,
                speed=forklift.speed,
                area=forklift.current_area,
                source="seed",
                quality=0.96,
            )
        )


def seed_alerts(session, forklifts):
    return

