"""轻量用户系统：注册/登录/令牌，零外部依赖。

产品策略：分析内容公开可看（获客），个人功能（持仓/提醒/交易）需登录。
- 密码：PBKDF2-SHA256（60万轮）加盐哈希，永不存明文；
- 令牌：HMAC 签名的 uid.过期时间.签名，无状态校验；
- 用户数据：data/users.json；个人持仓/提醒按 uid 分文件存放；
- 本地开发未设 AUTH_SECRET 时自动放行为 local 用户（零摩擦）。
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

from fastapi import Header, HTTPException

USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"
_lock = threading.Lock()

TOKEN_TTL = 30 * 86400  # 30 天
PBKDF2_ITERS = 600_000


def _secret() -> str | None:
    return os.environ.get("AUTH_SECRET")


def auth_enabled() -> bool:
    return bool(_secret())


def _load() -> dict:
    try:
        return json.loads(USERS_FILE.read_text()) if USERS_FILE.exists() else {}
    except Exception:
        return {}


def _save(users: dict):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False))


def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                               PBKDF2_ITERS).hex()


def register(email: str, password: str) -> dict:
    email = email.strip().lower()
    if "@" not in email or len(email) > 120:
        raise HTTPException(422, "邮箱格式不对")
    if len(password) < 8:
        raise HTTPException(422, "密码至少 8 位")
    with _lock:
        users = _load()
        if email in users:
            raise HTTPException(409, "这个邮箱已经注册过了——直接登录即可")
        salt = secrets.token_hex(16)
        users[email] = {
            "uid": secrets.token_hex(8),
            "salt": salt,
            "pw": _hash_pw(password, salt),
            "created": int(time.time()),
        }
        _save(users)
    return {"token": make_token(users[email]["uid"]), "email": email}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    users = _load()
    u = users.get(email)
    if not u or not hmac.compare_digest(u["pw"], _hash_pw(password, u["salt"])):
        raise HTTPException(401, "邮箱或密码不对")
    return {"token": make_token(u["uid"]), "email": email}


def delete_account(email: str, password: str) -> dict:
    """注销账号：验证密码后删除账号与该用户的全部数据（应用商店合规要求）。"""
    email = email.strip().lower()
    with _lock:
        users = _load()
        u = users.get(email)
        if not u or not hmac.compare_digest(u["pw"], _hash_pw(password, u["salt"])):
            raise HTTPException(401, "邮箱或密码不对")
        uid = u["uid"]
        users.pop(email)
        _save(users)
    # 连同个人数据一起删（持仓/提醒/交易设置）
    data_dir = USERS_FILE.parent
    for f in data_dir.glob(f"*_{uid}.json"):
        try:
            f.unlink()
        except Exception:
            pass
    return {"deleted": True}


def make_token(uid: str) -> str:
    exp = int(time.time()) + TOKEN_TTL
    payload = f"{uid}.{exp}"
    sig = hmac.new(_secret().encode() if _secret() else b"local-dev",
                   payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def verify_token(token: str) -> str | None:
    """合法返回 uid，否则 None。"""
    try:
        uid, exp, sig = token.split(".")
        payload = f"{uid}.{exp}"
        expect = hmac.new(_secret().encode() if _secret() else b"local-dev",
                          payload.encode(), hashlib.sha256).hexdigest()[:32]
        if hmac.compare_digest(sig, expect) and int(exp) > time.time():
            return uid
    except Exception:
        pass
    return None


def current_uid(authorization: str | None = Header(None)) -> str:
    """FastAPI 依赖：取当前用户。未启用 auth 时回退 local 用户（本地开发零摩擦）。"""
    if not auth_enabled():
        return "local"
    if authorization and authorization.startswith("Bearer "):
        uid = verify_token(authorization[7:])
        if uid:
            return uid
    raise HTTPException(401, "请先登录（个人功能需要账号，分析内容无需登录）")


def require_admin(x_admin_token: str | None = Header(None), key: str | None = None) -> bool:
    """FastAPI 依赖：owner 专用端点（如流量报告）。校验 X-Admin-Token 头或 ?key= 查询参数
    是否等于环境变量 ADMIN_TOKEN。未设 ADMIN_TOKEN 时一律拒绝（fail-closed，宁可锁死不公开）。"""
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(403, "管理端点未启用：请先设置 ADMIN_TOKEN（fly secrets set ADMIN_TOKEN=…）")
    provided = x_admin_token or key
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "需要有效的管理令牌（X-Admin-Token 头或 ?key=）")
    return True
