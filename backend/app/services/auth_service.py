"""
鉴权服务

提供：
- 手机号 + 验证码登录（无真实短信，使用固定通用验证码）
- 站长本人手机号无限次
- JWT 签发与解析
- FastAPI 依赖 get_current_user

作者：Offer 捕手
"""

import os
import re
import jwt  # PyJWT
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import HTTPException, Header

from app.db.sqlite_db import get_db


# JWT 过期时长（天）
TOKEN_EXPIRE_DAYS = 30
JWT_ALGORITHM = "HS256"

# 站长本人手机号（无限次使用），支持逗号分隔多个
OWNER_PHONE = os.getenv("OWNER_PHONE", "18303891187,18077782359")
# 通用验证码：任何人凭它登录即可使用一次完整流程
VERIFY_CODE = os.getenv("VERIFY_CODE", "WASD")
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class AuthService:
    """鉴权服务（手机号 + 验证码）"""

    def __init__(self):
        self.jwt_secret = os.getenv("JWT_SECRET", "dev-secret-change-me")
        # 普通用户首次登录赠送的可用次数
        self.free_quota = int(os.getenv("FREE_QUOTA_ON_SIGNUP", "3"))
        self.owner_phone = OWNER_PHONE
        # 解析为集合，支持逗号分隔的多个站长号
        self.owner_phones = {p.strip() for p in OWNER_PHONE.split(",") if p.strip()}
        self.verify_code = VERIFY_CODE

    # ========== 手机号 + 验证码登录 ==========

    def login_with_phone(self, phone: str, code: str) -> Dict[str, Any]:
        """手机号 + 验证码登录/注册，返回 {token, user}。

        - 验证码必须等于通用验证码（不区分大小写）。
        - 站长本人手机号 → 无限次。
        - 其他手机号 → 首次登录赠送 free_quota 次（默认 3 次完整流程）。
        """
        phone = (phone or "").strip()
        code = (code or "").strip()
        if not _PHONE_RE.match(phone):
            raise ValueError("请输入有效的手机号")
        if not code:
            raise ValueError("请输入验证码")
        if code.upper() != self.verify_code.upper():
            raise ValueError("验证码错误")

        is_owner = (phone in self.owner_phones)
        user = get_db().get_or_create_user_by_phone(
            phone, signup_quota=self.free_quota, is_unlimited=is_owner
        )

        token = self._issue_token(user["id"])
        return {
            "token": token,
            "user": {
                "id": user["id"],
                "phone": user["phone"],
                "remaining_quota": user["remaining_quota"],
                "seen_onboarding": user["seen_onboarding"],
                "is_unlimited": user["is_unlimited"],
            },
        }

    # ========== JWT ==========

    def _issue_token(self, user_id: str) -> str:
        """签发 JWT"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "exp": now + timedelta(days=TOKEN_EXPIRE_DAYS),
            "iat": now,
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

    def decode_token(self, token: str) -> str:
        """解析 JWT，返回 user_id；无效或过期抛 ValueError"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise ValueError("登录已过期")
        except jwt.InvalidTokenError:
            raise ValueError("无效的登录凭证")
        return payload["sub"]


# 模块级单例
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """获取鉴权服务实例（单例模式）"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """FastAPI 依赖：从 Authorization 头解析当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.split(" ", 1)[1]
    try:
        user_id = get_auth_service().decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    user = get_db().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

