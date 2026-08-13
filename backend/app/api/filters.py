"""筛选默认值 API"""
from fastapi import APIRouter, Depends
from typing import Dict, Any

from app.deps import get_current_user
from app.services.filter_service import FilterService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/defaults")
async def get_defaults() -> Dict[str, Any]:
    return FilterService.get()


@router.post("/defaults")
async def update_defaults(updates: Dict[str, Any]) -> Dict[str, Any]:
    return FilterService.update(updates)


@router.post("/reset")
async def reset_defaults() -> Dict[str, Any]:
    return FilterService.reset()
