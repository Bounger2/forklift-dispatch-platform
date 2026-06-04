from flask import Blueprint, g, request
from sqlalchemy import select
from werkzeug.security import check_password_hash

from ..models import User
from ..utils import auth_required, error, make_token, response

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(force=True)
    username = data.get("username", "")
    password = data.get("password", "")
    user = g.db.scalar(select(User).where(User.username == username))
    if not user or not check_password_hash(user.password_hash, password):
        return response(None, "用户名或密码错误", 401)
    if user.role not in {"admin", "driver"}:
        return error("调度员权限已合并到管理员，请使用管理员或司机账号登录", 403)
    token = make_token(user)
    return response({"token": token, "user": user.to_dict()})


@bp.get("/me")
@auth_required
def me():
    return response(g.current_user.to_dict())


@bp.post("/wecom/mock-login")
def mock_wecom_login():
    data = request.get_json(force=True)
    user = g.db.scalar(select(User).where(User.wecom_user_id == data.get("wecomUserId")))
    if not user:
        return response(None, "企业微信用户未绑定系统账号", 404)
    if user.role not in {"admin", "driver"}:
        return error("调度员权限已合并到管理员，请使用管理员或司机账号登录", 403)
    return response({"token": make_token(user), "user": user.to_dict()})
