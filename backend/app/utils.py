from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .database import SessionLocal
from .models import User


def response(data=None, message="ok", status=200):
    payload = {"message": message, "data": data}
    return jsonify(payload), status


def error(message, status=400, data=None):
    return jsonify({"message": message, "data": data}), status


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def make_token(user):
    exp = datetime.utcnow() + timedelta(seconds=current_app.config["JWT_EXP_SECONDS"])
    payload = {"sub": str(user.id), "role": user.role, "name": user.name, "exp": exp}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def current_user():
    return getattr(g, "current_user", None)


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.replace("Bearer ", "", 1).strip()
        if not token:
            return error("missing token", 401)
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.PyJWTError:
            return error("invalid token", 401)
        session = getattr(g, "db", None) or SessionLocal()
        user = session.get(User, int(payload["sub"]))
        if not user or user.status != "active":
            return error("user disabled", 401)
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @auth_required
        def wrapper(*args, **kwargs):
            user = current_user()
            if user.role not in roles and user.role != "admin":
                return error("permission denied", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
