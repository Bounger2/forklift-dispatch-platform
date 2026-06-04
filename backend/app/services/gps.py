from flask import current_app
from sqlalchemy import select

from ..models import Forklift, ForkliftPosition, GpsCalibrationPoint


CALIBRATION_CORNERS = [
    ("nw", "西北角", 0, 0),
    ("ne", "东北角", 100, 0),
    ("se", "东南角", 100, 100),
    ("sw", "西南角", 0, 100),
]


def gps_bounds():
    bounds = {
        "north": current_app.config.get("MAP_GPS_NORTH"),
        "south": current_app.config.get("MAP_GPS_SOUTH"),
        "east": current_app.config.get("MAP_GPS_EAST"),
        "west": current_app.config.get("MAP_GPS_WEST"),
    }
    if any(value is None for value in bounds.values()):
        return None
    if bounds["north"] == bounds["south"] or bounds["east"] == bounds["west"]:
        return None
    return bounds


def default_calibration_points():
    return [
        {"cornerKey": key, "label": label, "x": x, "y": y, "lat": None, "lng": None, "enabled": True}
        for key, label, x, y in CALIBRATION_CORNERS
    ]


def calibration_payload(session):
    defaults = {item["cornerKey"]: item for item in default_calibration_points()}
    if session:
        rows = session.scalars(select(GpsCalibrationPoint).order_by(GpsCalibrationPoint.id)).all()
        for row in rows:
            if row.corner_key in defaults:
                defaults[row.corner_key] = row.to_dict()
    points = [defaults[key] for key, *_ in CALIBRATION_CORNERS]
    ready = all(point.get("lat") is not None and point.get("lng") is not None for point in points)
    return {"ready": ready, "points": points}


def calibration_lookup(session):
    payload = calibration_payload(session)
    if not payload["ready"]:
        return None
    return {point["cornerKey"]: point for point in payload["points"]}


def work_area_lookup(session):
    payload = calibration_payload(session)
    return {point["cornerKey"]: point for point in payload["points"]}


def bilinear_value(corners, field, u, v):
    nw = corners["nw"][field]
    ne = corners["ne"][field]
    se = corners["se"][field]
    sw = corners["sw"][field]
    return (1 - u) * (1 - v) * nw + u * (1 - v) * ne + u * v * se + (1 - u) * v * sw


def solve_uv_from_fields(corners, value_a, value_b, field_a, field_b):
    values_a = [point[field_a] for point in corners.values()]
    values_b = [point[field_b] for point in corners.values()]
    min_a, max_a = min(values_a), max(values_a)
    min_b, max_b = min(values_b), max(values_b)
    u = 0.5 if max_b == min_b else (value_b - min_b) / (max_b - min_b)
    v = 0.5 if max_a == min_a else (max_a - value_a) / (max_a - min_a)

    for _ in range(12):
        current_a = bilinear_value(corners, field_a, u, v)
        current_b = bilinear_value(corners, field_b, u, v)
        err_a = current_a - value_a
        err_b = current_b - value_b
        if abs(err_a) + abs(err_b) < 1e-10:
            break

        nw, ne, se, sw = corners["nw"], corners["ne"], corners["se"], corners["sw"]
        da_du = -(1 - v) * nw[field_a] + (1 - v) * ne[field_a] + v * se[field_a] - v * sw[field_a]
        da_dv = -(1 - u) * nw[field_a] - u * ne[field_a] + u * se[field_a] + (1 - u) * sw[field_a]
        db_du = -(1 - v) * nw[field_b] + (1 - v) * ne[field_b] + v * se[field_b] - v * sw[field_b]
        db_dv = -(1 - u) * nw[field_b] - u * ne[field_b] + u * se[field_b] + (1 - u) * sw[field_b]
        det = da_du * db_dv - da_dv * db_du
        if abs(det) < 1e-14:
            break

        u += (-err_a * db_dv + da_dv * err_b) / det
        v += (err_a * db_du - da_du * err_b) / det

    return max(0, min(1, u)), max(0, min(1, v))


def solve_uv_from_latlng(corners, lat, lng):
    return solve_uv_from_fields(corners, lat, lng, "lat", "lng")


def solve_uv_from_xy(corners, x, y):
    return solve_uv_from_fields(corners, y, x, "y", "x")


def latlng_to_calibrated_xy(lat, lng, session):
    corners = calibration_lookup(session)
    if not corners:
        return None
    u, v = solve_uv_from_latlng(corners, float(lat), float(lng))
    x = bilinear_value(corners, "x", u, v)
    y = bilinear_value(corners, "y", u, v)
    return max(0, min(100, x)), max(0, min(100, y))


def latlng_to_map_xy(lat, lng, session=None):
    if lat is None or lng is None:
        return None
    if session:
        calibrated = latlng_to_calibrated_xy(lat, lng, session)
        if calibrated:
            return calibrated
    bounds = gps_bounds()
    if not bounds:
        return None
    x = (float(lng) - bounds["west"]) / (bounds["east"] - bounds["west"]) * 100
    y = (bounds["north"] - float(lat)) / (bounds["north"] - bounds["south"]) * 100
    return max(0, min(100, x)), max(0, min(100, y))


def map_xy_to_latlng(x, y, session=None):
    if x is None or y is None:
        return None
    if session:
        corners = calibration_lookup(session)
        if corners:
            u, v = solve_uv_from_xy(corners, float(x), float(y))
            lat = bilinear_value(corners, "lat", u, v)
            lng = bilinear_value(corners, "lng", u, v)
            return lat, lng
    bounds = gps_bounds()
    if not bounds:
        return None
    lng = bounds["west"] + float(x) / 100 * (bounds["east"] - bounds["west"])
    lat = bounds["north"] - float(y) / 100 * (bounds["north"] - bounds["south"])
    return lat, lng


def clamp_xy_to_work_area(x, y, session=None):
    x = max(0, min(100, float(x)))
    y = max(0, min(100, float(y)))
    if not session:
        return x, y
    corners = work_area_lookup(session)
    if not corners:
        return x, y
    u, v = solve_uv_from_xy(corners, x, y)
    clamped_x = bilinear_value(corners, "x", u, v)
    clamped_y = bilinear_value(corners, "y", u, v)
    return max(0, min(100, clamped_x)), max(0, min(100, clamped_y))


def position_xy(position, session=None):
    mapped = latlng_to_map_xy(position.lat, position.lng, session)
    if mapped:
        return mapped
    return position.x, position.y


def latest_position_for_vehicle(session, forklift_id):
    return session.scalar(
        select(ForkliftPosition)
        .where(ForkliftPosition.forklift_id == forklift_id)
        .order_by(ForkliftPosition.recorded_at.desc(), ForkliftPosition.id.desc())
        .limit(1)
    )


def sync_latest_positions(session):
    vehicles = session.scalars(select(Forklift).order_by(Forklift.id)).all()
    for vehicle in vehicles:
        position = latest_position_for_vehicle(session, vehicle.id)
        if not position:
            continue
        if vehicle.last_seen_at and position.recorded_at and position.recorded_at < vehicle.last_seen_at:
            continue
        x, y = position_xy(position, session)
        vehicle.current_x = x
        vehicle.current_y = y
        vehicle.heading = position.heading
        vehicle.speed = position.speed
        vehicle.current_area = position.area or vehicle.current_area
        vehicle.last_seen_at = position.recorded_at
        vehicle.online = True
    session.flush()
