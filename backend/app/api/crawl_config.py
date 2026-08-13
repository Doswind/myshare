"""抓取策略配置 API"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any

from app.deps import get_current_user
from app.services.crawl_config_service import CrawlConfigService
from app.scheduler.scheduler import reload_job, reload_all

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("")
async def list_configs() -> List[Dict[str, Any]]:
    return CrawlConfigService.list_all()


@router.get("/{job_key}")
async def get_config(job_key: str) -> Dict[str, Any]:
    cfg = CrawlConfigService.get(job_key)
    if not cfg:
        raise HTTPException(404, f"未知任务: {job_key}")
    return cfg


@router.post("/{job_key}")
async def update_config(job_key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """单条更新并热重载调度器"""
    try:
        cfg = CrawlConfigService.update(job_key, updates)
    except ValueError as e:
        raise HTTPException(400, str(e))
    reload_job(job_key)
    return cfg


@router.post("/bulk/update")
async def bulk_update(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """批量更新整张表（Settings 页面保存）"""
    out = CrawlConfigService.bulk_update(items)
    reload_all()
    return out


@router.post("/reset")
async def reset_configs() -> List[Dict[str, Any]]:
    """重置为默认配置"""
    out = CrawlConfigService.reset_all()
    reload_all()
    return out
