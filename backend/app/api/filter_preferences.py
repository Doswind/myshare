"""用户筛选偏好 API"""
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.rbac import User
from app.models.user_filter_preference import UserFilterPreference

router = APIRouter(dependencies=[Depends(get_current_user)])
ALLOWED_SCOPES = {"holdings"}


def _check_scope(scope: str) -> None:
    if scope not in ALLOWED_SCOPES:
        raise HTTPException(status_code=400, detail="不支持的筛选偏好范围")


@router.get("/{scope}")
async def get_filter_preference(
    scope: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _check_scope(scope)
    row = db.query(UserFilterPreference).filter(
        UserFilterPreference.user_id == user.id,
        UserFilterPreference.scope == scope,
    ).first()
    if not row:
        return {"scope": scope, "filters": None}
    try:
        filters = json.loads(row.filters_json)
    except (TypeError, json.JSONDecodeError):
        filters = {}
    return {"scope": scope, "filters": filters, "updated_at": row.updated_at}


@router.put("/{scope}")
async def save_filter_preference(
    scope: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _check_scope(scope)
    try:
        filters_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="筛选条件不是有效 JSON") from exc

    row = db.query(UserFilterPreference).filter(
        UserFilterPreference.user_id == user.id,
        UserFilterPreference.scope == scope,
    ).first()
    if row:
        row.filters_json = filters_json
    else:
        row = UserFilterPreference(
            user_id=user.id,
            scope=scope,
            filters_json=filters_json,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"scope": scope, "filters": payload, "updated_at": row.updated_at}


@router.delete("/{scope}")
async def reset_filter_preference(
    scope: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    _check_scope(scope)
    db.query(UserFilterPreference).filter(
        UserFilterPreference.user_id == user.id,
        UserFilterPreference.scope == scope,
    ).delete(synchronize_session=False)
    db.commit()
    return {"scope": scope, "status": "reset"}
