"""任务去重 + 冷却工具：保证同 job_id 同时只允许一个在跑 + 完成后 N 分钟内不许再触发"""
import time
import logging
from typing import Set, Dict, List

logger = logging.getLogger(__name__)


class JobGuard:
    """进程内任务去重（同一 job_id 重复触发时第二次直接返回 409）
    进程内冷却（同一 job_id 完成后 N 分钟内再触发返回 429）

    - acquire_sync / release：在同步上下文（endpoint 内）使用
    - is_running / list_running / force_release：管理 / 调试
    - get_cooldown / record_completion：冷却管理

    逻辑任务组（JOB_GROUPS）：同一业务任务的定时（sched_*）与手动（manual_*）形态
    共享互斥锁 —— 组内任一 key 在跑，其余 key 都不允许触发，
    避免「定时任务在跑时手动触发同一任务」的并行冲突。

    set.add() / dict 赋值 在 CPython 下原子（受 GIL 保护），无需额外锁
    """
    _running: Set[str] = set()
    # job_id -> 下次允许触发的 Unix 时间戳（含 cooldown）
    _cooldown_until: Dict[str, float] = {}

    # 逻辑任务组：组内任一 key 在跑 → 其余 key 都拒绝触发
    # manual_holdings 无定时形态，单独成组
    JOB_GROUPS: Dict[str, List[str]] = {
        "funds_full": ["sched_funds_full", "manual_funds"],
        "fund_nav": ["sched_fund_nav", "manual_fund_nav"],
        "quotes": ["sched_quotes", "manual_quotes"],
        "sectors": ["sched_sectors", "manual_sectors"],
        "stock_details": ["sched_stock_details", "manual_stock_details"],
    }

    # 各手动抓取任务的冷却时间（秒）
    # 手动任务完成后冷却时间
    COOLDOWN_SECONDS = {
        "manual_funds": 30 * 60,  # 基金列表 + 全量持仓
        "manual_fund_nav": 30 * 60,  # 基金净值 + 详情
        "manual_holdings": 30 * 60,  # 全量持仓
        "manual_quotes": 60,
        "manual_sectors": 15 * 60,
        "manual_stock_details": 30,
    }

    @classmethod
    def group_keys(cls, job_id: str) -> List[str]:
        """返回 job_id 所属逻辑组的全部 key（未入组的单任务自成一组）"""
        for keys in cls.JOB_GROUPS.values():
            if job_id in keys:
                return keys
        return [job_id]

    @classmethod
    def acquire_sync(cls, job_id: str) -> bool:
        """同步获取任务锁（按逻辑组互斥）。
        返回 True=成功可执行，False=同组已有任务在跑或冷却中"""
        group = cls.group_keys(job_id)
        if any(k in cls._running for k in group):
            return False
        # 冷却期检查
        if cls._cooldown_until.get(job_id, 0) > time.time():
            return False
        cls._running.add(job_id)
        return True

    @classmethod
    def release(cls, job_id: str) -> None:
        """释放任务锁并开始冷却（必须与 acquire_sync 配对）"""
        cls._running.discard(job_id)
        cd = cls.COOLDOWN_SECONDS.get(job_id, 0)
        if cd > 0:
            cls._cooldown_until[job_id] = time.time() + cd
            logger.info("[JobGuard] %s 冷却 %ds (到 %s)", job_id, cd,
                        time.strftime("%H:%M:%S", time.localtime(cls._cooldown_until[job_id])))

    @classmethod
    def is_running(cls, job_id: str) -> bool:
        """同组内任一 key 在跑即视为在跑"""
        return any(k in cls._running for k in cls.group_keys(job_id))

    @classmethod
    def cooldown_remaining(cls, job_id: str) -> int:
        """返回剩余冷却秒数（0 = 不在冷却期）"""
        return max(0, int(cls._cooldown_until.get(job_id, 0) - time.time()))

    @classmethod
    def list_running(cls) -> list:
        return sorted(cls._running)

    @classmethod
    def list_cooldowns(cls) -> Dict[str, int]:
        """返回所有 job_id 的剩余冷却秒数（仅包含仍在冷却期的）"""
        now = time.time()
        return {k: int(v - now) for k, v in cls._cooldown_until.items() if v > now}

    @classmethod
    def force_release(cls, job_id: str) -> bool:
        """强制释放（仅用于清理卡死任务，正常流程不要用）"""
        released = False
        if job_id in cls._running:
            cls._running.discard(job_id)
            released = True
        if job_id in cls._cooldown_until:
            del cls._cooldown_until[job_id]
            released = True
        return released
