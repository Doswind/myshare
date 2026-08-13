"""筛选条件持久化服务（简单 JSON 文件）"""
import json
import logging
from typing import Dict, Any

from app.config import settings, DATA_DIR

logger = logging.getLogger(__name__)

FILTERS_FILE = DATA_DIR / "filters.json"

DEFAULTS = {
    "min_scale": settings.default_min_scale,
    "min_ret_1y": settings.default_min_ret_1y,
    "price_min": None,
    "price_max": None,
    "industry": None,
}


class FilterService:
    """筛选默认值持久化"""

    @staticmethod
    def _ensure_file():
        if not FILTERS_FILE.exists():
            FILTERS_FILE.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2))

    @staticmethod
    def get() -> Dict[str, Any]:
        FilterService._ensure_file()
        try:
            return json.loads(FILTERS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULTS)

    @staticmethod
    def update(updates: Dict[str, Any]) -> Dict[str, Any]:
        cur = FilterService.get()
        for k, v in updates.items():
            if k in DEFAULTS:
                cur[k] = v
        FILTERS_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2))
        return cur

    @staticmethod
    def reset() -> Dict[str, Any]:
        FILTERS_FILE.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2))
        return dict(DEFAULTS)
