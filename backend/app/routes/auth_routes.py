import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, UserSettings
from ..schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    GoogleAuthRequest,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
    TokenResponse,
    UserResponse
)
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters."
        )

    user = User(
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name or email.split("@")[0],
        auth_provider="email",
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize user settings
    settings_obj = UserSettings(user_id=user.id)
    db.add(settings_obj)
    db.commit()

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not verify_password(user.password_hash, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.post("/google", response_model=TokenResponse)
def google_auth(req: GoogleAuthRequest, db: Session = Depends(get_db)):
    # Extract identity from token or request body
    email = (req.email or f"google_{uuid.uuid4().hex[:8]}@gmail.com").strip().lower()
    display_name = req.name or email.split("@")[0]

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            display_name=display_name,
            avatar_url=req.avatar_url or "https://api.dicebear.com/7.x/bottts/svg?seed=user",
            auth_provider="google",
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        settings_obj = UserSettings(user_id=user.id)
        db.add(settings_obj)
        db.commit()
    else:
        if req.avatar_url:
            user.avatar_url = req.avatar_url
        if req.name and (not user.display_name or user.display_name == "Google User"):
            user.display_name = req.name
        user.auth_provider = "google"
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.post("/guest", response_model=TokenResponse)
def guest_login(db: Session = Depends(get_db)):
    """1-Click Guest Persona login matching screenshot UI."""
    guest_uid = uuid.uuid4().hex[:6]
    email = f"guest_{guest_uid}@chatgpt.platform"
    display_name = f"Guest User {guest_uid.upper()}"

    user = User(
        email=email,
        display_name=display_name,
        auth_provider="guest",
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    settings_obj = UserSettings(user_id=user.id)
    db.add(settings_obj)
    db.commit()

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse.from_orm(user)


@router.post("/reset-password")
def request_password_reset(req: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.strip().lower()).first()
    if user:
        user.reset_token = uuid.uuid4().hex[:8]
        db.commit()
        return {"status": "ok", "message": "Password reset token generated.", "demo_token": user.reset_token}
    return {"status": "ok", "message": "If this email is registered, reset instructions have been generated."}


@router.post("/reset-password/confirm")
def confirm_password_reset(req: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.strip().lower(), User.reset_token == req.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token or email.")
    
    user.password_hash = hash_password(req.new_password)
    user.reset_token = None
    db.commit()
    return {"status": "ok", "message": "Password has been reset successfully."}

