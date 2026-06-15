"""
额度与邀请码服务

职责：
- 检查/消费用户额度
- 邀请码兑换（校验 + 发放额度 + 记录使用）

所有业务错误通过 ValueError（中文消息）抛出，由路由层转为 HTTP 400。
"""

from typing import Dict, Optional

from app.db.sqlite_db import get_db


class QuotaService:
    """额度与邀请码业务逻辑"""

    def __init__(self):
        self.db = get_db()

    def check_quota(self, user_id: str) -> bool:
        """检查用户是否还有剩余额度（无限用户始终通过）"""
        user = self.db.get_user_by_id(user_id)
        if not user:
            return False
        if user.get("is_unlimited"):
            return True
        return user.get("remaining_quota", 0) > 0

    def consume(self, user_id: str) -> bool:
        """消费一次额度，成功返回 True；无限用户不扣减、始终成功"""
        user = self.db.get_user_by_id(user_id)
        if user and user.get("is_unlimited"):
            return True
        return self.db.consume_quota(user_id)

    def redeem_invite(self, user_id: str, code: str) -> Dict[str, int]:
        """兑换邀请码，成功返回发放数量与最新剩余额度"""
        code = (code or "").strip().upper()
        if not code:
            raise ValueError("请输入邀请码")

        info = self.db.get_invite_code(code)
        if not info or not info.get("active"):
            raise ValueError("邀请码无效")

        if info["used_count"] >= info["max_uses"]:
            raise ValueError("邀请码已被用完")

        if self.db.has_redeemed(user_id, code):
            raise ValueError("你已经使用过该邀请码")

        grant = info["grant_count"]
        remaining = self.db.update_quota(user_id, grant)
        self.db.record_redemption(user_id, code)
        self.db.increment_invite_used(code)

        return {"granted": grant, "remaining_quota": remaining}

    # 分享奖励用的伪邀请码（每个账号仅可领取一次）
    SHARE_CODE = "__SHARE__"

    def claim_share_reward(self, user_id: str, grant: int = 1) -> Dict[str, int]:
        """分享给微信好友奖励：每个账号仅可领取一次 +grant 次。"""
        if self.db.has_redeemed(user_id, self.SHARE_CODE):
            raise ValueError("分享奖励已领取过啦")
        remaining = self.db.update_quota(user_id, grant)
        self.db.record_redemption(user_id, self.SHARE_CODE)
        return {"granted": grant, "remaining_quota": remaining}


_quota_service: Optional[QuotaService] = None


def get_quota_service() -> QuotaService:
    """获取 QuotaService 单例"""
    global _quota_service
    if _quota_service is None:
        _quota_service = QuotaService()
    return _quota_service
