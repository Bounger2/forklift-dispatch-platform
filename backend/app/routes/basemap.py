from pathlib import Path
from mimetypes import guess_type

from flask import Blueprint, current_app, g, redirect, request, send_file
from sqlalchemy import select

from ..models import GpsCalibrationPoint
from ..services.gps import CALIBRATION_CORNERS, calibration_payload, latlng_to_map_xy
from ..utils import error, response, role_required

bp = Blueprint("basemap", __name__, url_prefix="/api/basemap")

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
BASENAME = "factory-satellite"


def basemap_path():
    base = Path(current_app.instance_path)
    for suffix in ALLOWED_SUFFIXES:
        path = base / f"{BASENAME}{suffix}"
        if path.exists():
            return path
    return base / f"{BASENAME}.png"


@bp.get("")
def info():
    path = basemap_path()
    return response(
        {
            "imageUrl": "/api/basemap/image" if path.exists() else "/factory-satellite.svg",
            "uploaded": path.exists(),
            "scaleMeters": current_app.config["MAP_SCALE_METERS"],
            "metersPerUnit": current_app.config["MAP_METERS_PER_UNIT"],
            "calibration": calibration_payload(g.db),
        }
    )


@bp.get("/calibration")
def get_calibration():
    return response(calibration_payload(g.db))


@bp.put("/calibration")
@role_required("admin")
def save_calibration():
    data = request.get_json(force=True)
    rows = data.get("points", [])
    if not isinstance(rows, list):
        return error("points must be array", 400)

    defaults = {key: {"label": label, "x": x, "y": y} for key, label, x, y in CALIBRATION_CORNERS}
    seen = set()
    for row in rows:
        key = row.get("cornerKey")
        if key not in defaults:
            return error(f"invalid cornerKey: {key}", 400)
        seen.add(key)
        point = g.db.scalar(select(GpsCalibrationPoint).where(GpsCalibrationPoint.corner_key == key))
        if not point:
            point = GpsCalibrationPoint(corner_key=key)
            g.db.add(point)
        point.label = row.get("label") or defaults[key]["label"]
        point.x = float(row.get("x", defaults[key]["x"]))
        point.y = float(row.get("y", defaults[key]["y"]))
        point.lat = optional_float(row.get("lat"))
        point.lng = optional_float(row.get("lng"))
        point.enabled = bool(row.get("enabled", True))

    for key, meta in defaults.items():
        if key in seen:
            continue
        point = GpsCalibrationPoint(
            corner_key=key,
            label=meta["label"],
            x=meta["x"],
            y=meta["y"],
            enabled=True,
        )
        g.db.add(point)

    g.db.commit()
    return response(calibration_payload(g.db), "saved")


@bp.post("/convert")
@role_required("admin")
def convert_gps():
    data = request.get_json(force=True)
    lat = optional_float(data.get("lat"))
    lng = optional_float(data.get("lng"))
    if lat is None or lng is None:
        return error("lat and lng are required", 400)
    mapped = latlng_to_map_xy(lat, lng, g.db)
    if not mapped:
        return error("请先完成四角 GPS 标定，或配置 MAP_GPS_NORTH/SOUTH/EAST/WEST", 400)
    x, y = mapped
    return response({"x": round(x, 2), "y": round(y, 2), "lat": lat, "lng": lng})


def optional_float(value):
    if value in {None, ""}:
        return None
    return float(value)


@bp.get("/image")
def image():
    path = basemap_path()
    if not path.exists():
        return redirect("/factory-satellite.svg", code=302)
    mimetype = guess_type(path.name)[0] or "image/png"
    return send_file(path, mimetype=mimetype)


@bp.post("/image")
@role_required("admin")
def upload_image():
    file = request.files.get("image")
    if not file:
        return error("image file required", 400)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return error("only png/jpg/jpeg/webp images are supported", 400)
    for old_suffix in ALLOWED_SUFFIXES:
        old_path = Path(current_app.instance_path) / f"{BASENAME}{old_suffix}"
        if old_path.exists():
            old_path.unlink()
    path = Path(current_app.instance_path) / f"{BASENAME}{suffix}"
    path.parent.mkdir(exist_ok=True)
    file.save(path)
    return response({"imageUrl": "/api/basemap/image", "uploaded": True}, "uploaded")
