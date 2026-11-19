from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, UserSettings
from ..schemas import SettingsUpdateRequest, SettingsResponse
from ..auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=user.id)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)

    return SettingsResponse(
        provider=settings_obj.provider or "groq",
        api_key_set=bool(settings_obj.api_key),
        base_url=settings_obj.base_url,
        model_name=settings_obj.model_name or "llama-3.3-70b-versatile",
        temperature=settings_obj.temperature or 0.7,
        top_p=settings_obj.top_p or 0.9,
        system_prompt=settings_obj.system_prompt or "You are a helpful, brilliant, and friendly AI assistant.",
        theme=settings_obj.theme or "dark"
    )


@router.patch("", response_model=SettingsResponse)
def update_settings(
    req: SettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=user.id)
        db.add(settings_obj)

    if req.provider is not None:
        settings_obj.provider = req.provider
    if req.api_key is not None:
        settings_obj.api_key = req.api_key.strip() if req.api_key.strip() else None
    if req.base_url is not None:
        settings_obj.base_url = req.base_url.strip() if req.base_url.strip() else None
    if req.model_name is not None:
        settings_obj.model_name = req.model_name
    if req.temperature is not None:
        settings_obj.temperature = max(0.0, min(2.0, req.temperature))
    if req.top_p is not None:
        settings_obj.top_p = max(0.01, min(1.0, req.top_p))
    if req.system_prompt is not None:
        settings_obj.system_prompt = req.system_prompt
    if req.theme is not None:
        settings_obj.theme = req.theme

    db.commit()
    db.refresh(settings_obj)

    return SettingsResponse(
        provider=settings_obj.provider or "groq",
        api_key_set=bool(settings_obj.api_key),
        base_url=settings_obj.base_url,
        model_name=settings_obj.model_name or "llama-3.3-70b-versatile",
        temperature=settings_obj.temperature or 0.7,
        top_p=settings_obj.top_p or 0.9,
        system_prompt=settings_obj.system_prompt or "You are a helpful, brilliant, and friendly AI assistant.",
        theme=settings_obj.theme or "dark"
    )

