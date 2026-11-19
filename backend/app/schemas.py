from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr
from datetime import datetime


# Auth Schemas
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    username: Optional[str] = None
    plan: Optional[str] = "Free"
    age_range: Optional[str] = "18 or older"
    gpt_builder_profile: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: str
    is_verified: bool

    class Config:
        from_attributes = True


class UserProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    gpt_builder_profile: Optional[str] = None
    age_range: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str


class ActiveSessionResponse(BaseModel):
    id: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    last_active: datetime
    is_current: bool = False

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Chat & Message Schemas
class MessageResponse(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    sources: Optional[str] = None
    feedback: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatCreateRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    title: Optional[str] = "New Chat"
    model_name: Optional[str] = "llama-3.3-70b-versatile"


class ChatUpdateRequest(BaseModel):
    title: str


class ChatResponse(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}
    id: str
    title: str
    model_name: str
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0


class ChatDetailResponse(ChatResponse):
    model_config = {"from_attributes": True, "protected_namespaces": ()}
    messages: List[MessageResponse] = []


class ChatStreamRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    chat_id: Optional[str] = None
    message: str
    image_url: Optional[str] = None
    document_name: Optional[str] = None
    model_name: Optional[str] = None
    use_rag: bool = True
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    system_prompt: Optional[str] = None


class ImageUploadResponse(BaseModel):
    url: str
    filename: str
    width: int
    height: int
    format: str
    size: int


class ImageEditRequest(BaseModel):
    image_url: str
    instruction: str
    mask_data: Optional[str] = None # Base64 painted mask
    chat_id: Optional[str] = None
    operation: Optional[str] = None # Optional override


class ImageEditResponse(BaseModel):
    status: str
    image_url: str
    original_url: Optional[str] = None
    operation: str
    instruction: str
    version: Optional[int] = 1
    filename: str
    dimensions: Optional[Dict[str, int]] = None
    pixel_preservation: Optional[str] = None


class MessageFeedbackRequest(BaseModel):
    message_id: str
    feedback: Optional[str] # 'like', 'dislike', or None


# Document Schemas
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    num_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True


# User Settings Schemas
class SettingsUpdateRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    theme: Optional[str] = None
    memory_enabled: Optional[bool] = None
    memory_summary: Optional[str] = None
    reference_photo_url: Optional[str] = None
    full_body_photo_url: Optional[str] = None
    tone_warmth: Optional[str] = None


class SettingsResponse(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}
    provider: str
    api_key_set: bool
    base_url: Optional[str] = None
    model_name: str
    temperature: float
    top_p: float
    max_tokens: int = 1050
    system_prompt: str
    theme: str
    memory_enabled: bool = True
    memory_summary: str = "VYNEXA adapts to your technical expertise, programming languages, and workflow preferences."
    reference_photo_url: Optional[str] = None
    full_body_photo_url: Optional[str] = None
    tone_warmth: str = "Warm"


class MemoryCategory(BaseModel):
    id: str
    title: str
    icon: str
    badge: str
    content: str


class MemoryDetailResponse(BaseModel):
    enabled: bool
    summary: str
    categories: List[MemoryCategory]
    total_chats_analyzed: int
    last_updated: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    category_id: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None



class UsageResponse(BaseModel):
    plan_name: str = "VYNEXA AI Free"
    plan_price: str = "₹0 / month"
    member_since: str = "November 2026"
    status: str = "Active"
    monthly_prompts_used: int = 7
    monthly_prompts_limit: int = 1000
    total_chats: int = 0
    prompts_sent: int = 0
    ai_responses: int = 0
    documents_count: int = 0
    pages_indexed: int = 0
