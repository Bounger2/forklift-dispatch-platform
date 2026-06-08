from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


def now_utc():
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, onupdate=now_utc
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(32), default="")
    wecom_user_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    department: Mapped[str] = mapped_column(String(128), default="")
    team: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")

    driver = relationship("Driver", back_populates="user", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "phone": self.phone,
            "wecomUserId": self.wecom_user_id,
            "department": self.department,
            "team": self.team,
            "role": self.role,
            "status": self.status,
            "driverId": self.driver.id if self.driver else None,
            "employeeNo": self.driver.employee_no if self.driver else "",
            "licenseLevel": self.driver.license_level if self.driver else "",
            "shiftStatus": self.driver.shift_status if self.driver else "",
            "bindStatus": self.driver.bind_status if self.driver else "",
        }


class Driver(Base, TimestampMixin):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    employee_no: Mapped[str] = mapped_column(String(64), unique=True)
    license_level: Mapped[str] = mapped_column(String(64), default="N2")
    qualification_tags: Mapped[str] = mapped_column(String(255), default="standard")
    shift_status: Mapped[str] = mapped_column(String(32), default="off_shift")
    bind_status: Mapped[str] = mapped_column(String(32), default="unbound")
    workload_score: Mapped[float] = mapped_column(Float, default=0)
    task_count_today: Mapped[int] = mapped_column(Integer, default=0)
    working_minutes_today: Mapped[int] = mapped_column(Integer, default=0)
    distance_today: Mapped[float] = mapped_column(Float, default=0)
    emergency_count_today: Mapped[int] = mapped_column(Integer, default=0)

    user = relationship("User", back_populates="driver")
    bindings = relationship("VehicleBinding", back_populates="driver")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.user.name if self.user else "",
            "employeeNo": self.employee_no,
            "licenseLevel": self.license_level,
            "qualificationTags": self.qualification_tags.split(",")
            if self.qualification_tags
            else [],
            "shiftStatus": self.shift_status,
            "bindStatus": self.bind_status,
            "workloadScore": round(self.workload_score, 2),
            "taskCountToday": self.task_count_today,
            "workingMinutesToday": self.working_minutes_today,
            "distanceToday": round(self.distance_today, 1),
            "emergencyCountToday": self.emergency_count_today,
            "team": self.user.team if self.user else "",
        }


class Forklift(Base, TimestampMixin):
    __tablename__ = "forklifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plate_no: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(64), default="")
    power_type: Mapped[str] = mapped_column(String(32), default="electric")
    tonnage: Mapped[float] = mapped_column(Float, default=3.0)
    status: Mapped[str] = mapped_column(String(32), default="idle", index=True)
    battery_level: Mapped[int] = mapped_column(Integer, default=90)
    fuel_level: Mapped[int] = mapped_column(Integer, default=0)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    current_area: Mapped[str] = mapped_column(String(128), default="")
    current_x: Mapped[float] = mapped_column(Float, default=50)
    current_y: Mapped[float] = mapped_column(Float, default=50)
    heading: Mapped[float] = mapped_column(Float, default=0)
    speed: Mapped[float] = mapped_column(Float, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")

    driver = relationship("Driver")
    positions = relationship("ForkliftPosition", back_populates="forklift")
    bindings = relationship("VehicleBinding", back_populates="forklift")

    def to_dict(self):
        energy_level = self.fuel_level if self.power_type in {"diesel", "gasoline", "lpg"} else self.battery_level
        latest_position = max(
            self.positions,
            key=lambda row: (row.recorded_at or datetime.min, row.id or 0),
            default=None,
        )
        current_lat = latest_position.lat if latest_position else None
        current_lng = latest_position.lng if latest_position else None
        return {
            "id": self.id,
            "code": self.code,
            "plateNo": self.plate_no,
            "model": self.model,
            "powerType": self.power_type,
            "tonnage": self.tonnage,
            "status": self.status,
            "batteryLevel": self.battery_level,
            "fuelLevel": self.fuel_level,
            "energyLevel": energy_level,
            "online": self.online,
            "currentArea": self.current_area,
            "x": round(self.current_x, 2),
            "y": round(self.current_y, 2),
            "lat": current_lat,
            "lng": current_lng,
            "currentLat": current_lat,
            "currentLng": current_lng,
            "heading": round(self.heading, 1),
            "speed": round(self.speed, 1),
            "lastSeenAt": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "driver": self.driver.to_dict() if self.driver else None,
            "note": self.note,
        }


class MapPoint(Base, TimestampMixin):
    __tablename__ = "map_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    point_type: Mapped[str] = mapped_column(String(32), default="pickup", index=True)
    area: Mapped[str] = mapped_column(String(128), default="")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    geofence_radius: Mapped[float] = mapped_column(Float, default=5)
    contact: Mapped[str] = mapped_column(String(128), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(String(255), default="")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "pointType": self.point_type,
            "area": self.area,
            "x": self.x,
            "y": self.y,
            "lat": self.lat,
            "lng": self.lng,
            "geofenceRadius": self.geofence_radius,
            "contact": self.contact,
            "enabled": self.enabled,
            "temporary": self.is_temporary,
            "description": self.description,
        }


class GpsCalibrationPoint(Base, TimestampMixin):
    __tablename__ = "gps_calibration_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corner_key: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(64))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "cornerKey": self.corner_key,
            "label": self.label,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "lat": self.lat,
            "lng": self.lng,
            "enabled": self.enabled,
        }


class TransportTask(Base, TimestampMixin):
    __tablename__ = "transport_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    origin_point_id: Mapped[int | None] = mapped_column(ForeignKey("map_points.id"))
    dest_point_id: Mapped[int | None] = mapped_column(ForeignKey("map_points.id"))
    origin_label: Mapped[str] = mapped_column(String(128))
    dest_label: Mapped[str] = mapped_column(String(128))
    cargo_type: Mapped[str] = mapped_column(String(128), default="")
    estimated_weight: Mapped[float] = mapped_column(Float, default=0)
    pallet_count: Mapped[int] = mapped_column(Integer, default=1)
    expected_finish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(8), default="B", index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", index=True)
    assigned_forklift_id: Mapped[int | None] = mapped_column(
        ForeignKey("forklifts.id"), nullable=True
    )
    assigned_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id"), nullable=True
    )
    eta_minutes: Mapped[int] = mapped_column(Integer, default=0)
    distance: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    abnormal_reason: Mapped[str] = mapped_column(String(255), default="")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    requester = relationship("User")
    origin = relationship("MapPoint", foreign_keys=[origin_point_id])
    destination = relationship("MapPoint", foreign_keys=[dest_point_id])
    assigned_forklift = relationship("Forklift")
    assigned_driver = relationship("Driver")
    events = relationship("TaskEvent", back_populates="task")

    def to_dict(self):
        return {
            "id": self.id,
            "taskNo": self.task_no,
            "requester": self.requester.to_dict() if self.requester else None,
            "originPointId": self.origin_point_id,
            "destPointId": self.dest_point_id,
            "originLabel": self.origin_label,
            "destLabel": self.dest_label,
            "cargoType": self.cargo_type,
            "estimatedWeight": self.estimated_weight,
            "palletCount": self.pallet_count,
            "expectedFinishAt": self.expected_finish_at.isoformat()
            if self.expected_finish_at
            else None,
            "priority": self.priority,
            "status": self.status,
            "assignedForklift": self.assigned_forklift.to_dict()
            if self.assigned_forklift
            else None,
            "assignedDriver": self.assigned_driver.to_dict()
            if self.assigned_driver
            else None,
            "etaMinutes": self.eta_minutes,
            "distance": round(self.distance, 1),
            "note": self.note,
            "abnormalReason": self.abnormal_reason,
            "assignedAt": self.assigned_at.isoformat() if self.assigned_at else None,
            "acceptedAt": self.accepted_at.isoformat() if self.accepted_at else None,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class TaskEvent(Base, TimestampMixin):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("transport_tasks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    forklift_id: Mapped[int | None] = mapped_column(ForeignKey("forklifts.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    location_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(String(255), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    task = relationship("TransportTask", back_populates="events")
    operator = relationship("User")
    forklift = relationship("Forklift")
    driver = relationship("Driver")

    def to_dict(self):
        return {
            "id": self.id,
            "taskId": self.task_id,
            "eventType": self.event_type,
            "operator": self.operator.to_dict() if self.operator else None,
            "forklift": self.forklift.code if self.forklift else None,
            "driver": self.driver.user.name if self.driver and self.driver.user else None,
            "x": self.location_x,
            "y": self.location_y,
            "message": self.message,
            "payload": self.payload or {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class ForkliftPosition(Base):
    __tablename__ = "forklift_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forklift_id: Mapped[int] = mapped_column(ForeignKey("forklifts.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("transport_tasks.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    heading: Mapped[float] = mapped_column(Float, default=0)
    speed: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(32), default="simulator")
    quality: Mapped[float] = mapped_column(Float, default=0.95)
    area: Mapped[str] = mapped_column(String(128), default="")

    forklift = relationship("Forklift", back_populates="positions")
    task = relationship("TransportTask")

    def to_dict(self):
        return {
            "id": self.id,
            "forkliftId": self.forklift_id,
            "taskId": self.task_id,
            "recordedAt": self.recorded_at.isoformat() if self.recorded_at else None,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "lat": self.lat,
            "lng": self.lng,
            "heading": round(self.heading, 1),
            "speed": round(self.speed, 1),
            "source": self.source,
            "quality": self.quality,
            "area": self.area,
        }


class ShiftTemplate(Base, TimestampMixin):
    __tablename__ = "shift_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[str] = mapped_column(String(8))
    end_time: Mapped[str] = mapped_column(String(8))
    rest_minutes: Mapped[int] = mapped_column(Integer, default=60)
    area: Mapped[str] = mapped_column(String(128), default="全厂")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "restMinutes": self.rest_minutes,
            "area": self.area,
            "enabled": self.enabled,
        }


class ScheduleAssignment(Base, TimestampMixin):
    __tablename__ = "schedule_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_date: Mapped[date] = mapped_column(Date, index=True)
    shift_code: Mapped[str] = mapped_column(String(64))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    forklift_id: Mapped[int | None] = mapped_column(ForeignKey("forklifts.id"), nullable=True)
    area: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="scheduled")

    driver = relationship("Driver")
    forklift = relationship("Forklift")

    def to_dict(self):
        return {
            "id": self.id,
            "shiftDate": self.shift_date.isoformat() if self.shift_date else None,
            "shiftCode": self.shift_code,
            "driver": self.driver.to_dict() if self.driver else None,
            "forklift": self.forklift.to_dict() if self.forklift else None,
            "area": self.area,
            "status": self.status,
        }


class VehicleBinding(Base, TimestampMixin):
    __tablename__ = "vehicle_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forklift_id: Mapped[int] = mapped_column(ForeignKey("forklifts.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    shift_code: Mapped[str] = mapped_column(String(64), default="")
    bound_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    bind_method: Mapped[str] = mapped_column(String(32), default="rfid")

    forklift = relationship("Forklift", back_populates="bindings")
    driver = relationship("Driver", back_populates="bindings")

    def to_dict(self):
        return {
            "id": self.id,
            "forklift": self.forklift.to_dict() if self.forklift else None,
            "driver": self.driver.to_dict() if self.driver else None,
            "shiftCode": self.shift_code,
            "boundAt": self.bound_at.isoformat() if self.bound_at else None,
            "unboundAt": self.unbound_at.isoformat() if self.unbound_at else None,
            "status": self.status,
            "bindMethod": self.bind_method,
        }


class DispatchRule(Base, TimestampMixin):
    __tablename__ = "dispatch_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), index=True)
    rule_type: Mapped[str] = mapped_column(String(64), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    weight: Mapped[float] = mapped_column(Float, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    editable: Mapped[bool] = mapped_column(Boolean, default=True)
    condition_json: Mapped[dict] = mapped_column(JSON, default=dict)
    action_json: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str] = mapped_column(Text, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "ruleType": self.rule_type,
            "priority": self.priority,
            "weight": self.weight,
            "enabled": self.enabled,
            "editable": self.editable,
            "conditionJson": self.condition_json or {},
            "actionJson": self.action_json or {},
            "description": self.description,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info", index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    title: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text, default="")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("transport_tasks.id"), nullable=True)
    forklift_id: Mapped[int | None] = mapped_column(ForeignKey("forklifts.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    map_point_id: Mapped[int | None] = mapped_column(ForeignKey("map_points.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    task = relationship("TransportTask")
    forklift = relationship("Forklift")
    driver = relationship("Driver")
    map_point = relationship("MapPoint")
    closed_by = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "alertType": self.alert_type,
            "severity": self.severity,
            "status": self.status,
            "title": self.title,
            "message": self.message,
            "suggestion": self.suggestion,
            "task": self.task.to_dict() if self.task else None,
            "forklift": self.forklift.to_dict() if self.forklift else None,
            "driver": self.driver.to_dict() if self.driver else None,
            "mapPoint": self.map_point.to_dict() if self.map_point else None,
            "closedAt": self.closed_at.isoformat() if self.closed_at else None,
            "payload": self.payload or {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class WeComMessage(Base, TimestampMixin):
    __tablename__ = "wecom_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_user_id: Mapped[str] = mapped_column(String(128), default="")
    target_role: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, default="")
    msg_type: Mapped[str] = mapped_column(String(32), default="text")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "targetUserId": self.target_user_id,
            "targetRole": self.target_role,
            "title": self.title,
            "content": self.content,
            "msgType": self.msg_type,
            "status": self.status,
            "error": self.error,
            "payload": self.payload or {},
            "sentAt": self.sent_at.isoformat() if self.sent_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
