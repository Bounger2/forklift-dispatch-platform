import json
import urllib.parse
import urllib.request
from datetime import datetime

from flask import current_app

from ..models import WeComMessage


class WeComClient:
    def __init__(self, session):
        self.session = session

    def send_text(self, title, content, target_user_id="", target_role="", payload=None):
        msg = WeComMessage(
            target_user_id=target_user_id or "",
            target_role=target_role or "",
            title=title,
            content=content,
            payload=payload or {},
            status="pending",
        )
        self.session.add(msg)
        self.session.flush()

        if current_app.config["WECOM_DRY_RUN"]:
            msg.status = "dry_run"
            msg.sent_at = datetime.utcnow()
            return msg

        if not (
            current_app.config["WECOM_CORP_ID"]
            and current_app.config["WECOM_SECRET"]
            and current_app.config["WECOM_AGENT_ID"]
        ):
            msg.status = "failed"
            msg.error = "missing WECOM_CORP_ID/WECOM_SECRET/WECOM_AGENT_ID"
            return msg

        try:
            token = self._get_access_token()
            self._send(token, target_user_id or "@all", content)
            msg.status = "sent"
            msg.sent_at = datetime.utcnow()
        except Exception as exc:  # external network or enterprise wechat errors
            msg.status = "failed"
            msg.error = str(exc)
        return msg

    def _get_access_token(self):
        params = urllib.parse.urlencode(
            {
                "corpid": current_app.config["WECOM_CORP_ID"],
                "corpsecret": current_app.config["WECOM_SECRET"],
            }
        )
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?{params}"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("errcode") != 0:
            raise RuntimeError(data)
        return data["access_token"]

    def _send(self, token, touser, content):
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        payload = {
            "touser": touser,
            "msgtype": "text",
            "agentid": int(current_app.config["WECOM_AGENT_ID"]),
            "text": {"content": content},
            "safe": 0,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("errcode") != 0:
            raise RuntimeError(data)
        return data
