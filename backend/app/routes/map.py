from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import MapPoint
from ..utils import auth_required, error, response, role_required

bp = Blueprint("map", __name__, url_prefix="/api/map-points")


def optional_float(value):
    if value in {None, ""}:
        return None
    return float(value)


@bp.get("")
@auth_required
def list_points():
    include_temporary = request.args.get("includeTemporary") in {"1", "true", "yes"}
    stmt = select(MapPoint).order_by(MapPoint.id)
    if not include_temporary:
        stmt = stmt.where(MapPoint.is_temporary.is_(False))
    rows = g.db.scalars(stmt).all()
    return response([row.to_dict() for row in rows])


@bp.post("")
@role_required("admin")
def create_point():
    data = request.get_json(force=True)
    point = MapPoint(
        name=data.get("name", "新点位"),
        point_type=data.get("pointType", "pickup"),
        area=data.get("area", ""),
        x=float(data.get("x", 50)),
        y=float(data.get("y", 50)),
        lat=optional_float(data.get("lat")),
        lng=optional_float(data.get("lng")),
        geofence_radius=float(data.get("geofenceRadius", 5)),
        contact=data.get("contact", ""),
        is_temporary=bool(data.get("temporary", False)),
        description=data.get("description", ""),
    )
    g.db.add(point)
    g.db.commit()
    return response(point.to_dict(), "created", 201)


@bp.patch("/<int:point_id>")
@role_required("admin")
def update_point(point_id):
    point = g.db.get(MapPoint, point_id)
    if not point:
        return error("point not found", 404)
    data = request.get_json(force=True)
    mapping = {
        "name": "name",
        "pointType": "point_type",
        "area": "area",
        "x": "x",
        "y": "y",
        "lat": "lat",
        "lng": "lng",
        "geofenceRadius": "geofence_radius",
        "contact": "contact",
        "enabled": "enabled",
        "temporary": "is_temporary",
        "description": "description",
    }
    for key, attr in mapping.items():
        if key in data:
            value = optional_float(data[key]) if key in {"lat", "lng"} else data[key]
            setattr(point, attr, value)
    g.db.commit()
    return response(point.to_dict())


@bp.delete("/<int:point_id>")
@role_required("admin")
def delete_point(point_id):
    point = g.db.get(MapPoint, point_id)
    if not point:
        return error("point not found", 404)
    point.enabled = False
    g.db.commit()
    return response(point.to_dict(), "disabled")
