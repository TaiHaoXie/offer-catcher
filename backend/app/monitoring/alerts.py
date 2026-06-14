"""
告警规则定义

定义告警条件和通知方式

作者：Claude
创建日期：2026-06-01
"""

import logging
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    description: str
    severity: AlertSeverity
    check_fn: Callable[[], bool]
    action_fn: Optional[Callable[[], None]] = None


class AlertManager:
    """告警管理器"""

    def __init__(self):
        self.rules: list[AlertRule] = []
        self.enabled = True

    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules.append(rule)

    def check_all(self):
        """检查所有告警规则"""
        if not self.enabled:
            return

        for rule in self.rules:
            try:
                if rule.check_fn():
                    self._trigger_alert(rule)
            except Exception as e:
                logger.error(f"告警检查失败 {rule.name}: {e}")

    def _trigger_alert(self, rule: AlertRule):
        """触发告警"""
        logger.warning(
            f"[{rule.severity.value.upper()}] {rule.name}: {rule.description}"
        )

        # 执行告警动作
        if rule.action_fn:
            try:
                rule.action_fn()
            except Exception as e:
                logger.error(f"告警动作执行失败: {e}")

    def enable(self):
        """启用告警"""
        self.enabled = True

    def disable(self):
        """禁用告警"""
        self.enabled = False


# 全局告警管理器
alert_manager = AlertManager()


def setup_default_alerts():
    """设置默认告警规则"""

    # 1. 高错误率告警
    async def check_high_error_rate():
        # TODO: 从 metrics 获取错误率
        # 这里简化为示例
        return False  # 实际应该从 Prometheus 查询

    alert_manager.add_rule(AlertRule(
        name="high_error_rate",
        description="错误率超过 5%",
        severity=AlertSeverity.CRITICAL,
        check_fn=check_high_error_rate
    ))

    # 2. 慢查询告警
    def check_slow_queries():
        # TODO: 检查数据库慢查询
        return False

    alert_manager.add_rule(AlertRule(
        name="slow_queries",
        description="存在超过 1 秒的数据库查询",
        severity=AlertSeverity.WARNING,
        check_fn=check_slow_queries
    ))

    # 3. LLM 调用失败率告警
    def check_llm_failure_rate():
        # TODO: 检查 LLM 调用失败率
        return False

    alert_manager.add_rule(AlertRule(
        name="llm_high_failure_rate",
        description="LLM 调用失败率超过 10%",
        severity=AlertSeverity.CRITICAL,
        check_fn=check_llm_failure_rate
    ))

    # 4. 缓存命中率低告警
    def check_low_cache_hit_rate():
        # TODO: 检查缓存命中率
        return False

    alert_manager.add_rule(AlertRule(
        name="low_cache_hit_rate",
        description="缓存命中率低于 50%",
        severity=AlertSeverity.WARNING,
        check_fn=check_low_cache_hit_rate
    ))

    # 5. Celery 任务积压告警
    def check_celery_backlog():
        # TODO: 检查 Celery 队列积压
        return False

    alert_manager.add_rule(AlertRule(
        name="celery_high_backlog",
        description="Celery 任务积压超过 100",
        severity=AlertSeverity.WARNING,
        check_fn=check_celery_backlog
    ))


# 简单的日志告警器
def log_alert(message: str, severity: AlertSeverity = AlertSeverity.INFO):
    """记录告警到日志"""
    if severity == AlertSeverity.CRITICAL:
        logger.critical(message)
    elif severity == AlertSeverity.WARNING:
        logger.warning(message)
    else:
        logger.info(message)
