from flask import Blueprint, g, request
from sqlalchemy import select

from ..models import DispatchRule
from ..utils import auth_required, error, response, role_required

bp = Blueprint("rules", __name__, url_prefix="/api/rules")


@bp.get("")
@auth_required
def list_rules():
    category = request.args.get("category")
    stmt = select(DispatchRule).order_by(DispatchRule.category, DispatchRule.priority)
    if category:
        stmt = stmt.where(DispatchRule.category == category)
    rows = g.db.scalars(stmt).all()
    return response([row.to_dict() for row in rows])


@bp.post("")
@role_required("admin")
def create_rule():
    data = request.get_json(force=True)
    code = data.get("code") or "CUSTOM-" + data.get("name", "RULE").upper().replace(" ", "-")
    if g.db.scalar(select(DispatchRule).where(DispatchRule.code == code)):
        return error("rule code already exists", 409)
    rule = DispatchRule(
        code=code,
        name=data.get("name", "自定义规则"),
        category=data.get("category", "manual"),
        rule_type=data.get("ruleType", "custom"),
        priority=int(data.get("priority", 200)),
        weight=float(data.get("weight", 0)),
        enabled=bool(data.get("enabled", True)),
        editable=True,
        condition_json=data.get("conditionJson") or {},
        action_json=data.get("actionJson") or {},
        description=data.get("description", "用户自定义调度规则"),
    )
    g.db.add(rule)
    g.db.commit()
    return response(rule.to_dict(), "created", 201)


@bp.patch("/<int:rule_id>")
@role_required("admin")
def update_rule(rule_id):
    rule = g.db.get(DispatchRule, rule_id)
    if not rule:
        return error("rule not found", 404)
    if not rule.editable:
        protected_fields = {"conditionJson", "actionJson", "category", "ruleType"}
        if protected_fields.intersection(request.get_json(force=True).keys()):
            return error("系统过滤规则只允许启停和调整优先级", 403)
    data = request.get_json(force=True)
    mapping = {
        "name": "name",
        "category": "category",
        "ruleType": "rule_type",
        "priority": "priority",
        "weight": "weight",
        "enabled": "enabled",
        "conditionJson": "condition_json",
        "actionJson": "action_json",
        "description": "description",
    }
    for key, attr in mapping.items():
        if key in data:
            setattr(rule, attr, data[key])
    g.db.commit()
    return response(rule.to_dict())


@bp.delete("/<int:rule_id>")
@role_required("admin")
def delete_rule(rule_id):
    rule = g.db.get(DispatchRule, rule_id)
    if not rule:
        return error("rule not found", 404)
    if not rule.editable:
        return error("系统规则不可删除，可停用", 403)
    g.db.delete(rule)
    g.db.commit()
    return response({"id": rule_id}, "deleted")
