import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=False, default="Guest User")
    avatar_url = Column(String(512), nullable=True)
    auth_provider = Column(String(50), default="email") # email, google, guest
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String(20), nullable=True)
    reset_token = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), default="New Chat")
    model_name = Column(String(100), default="llama-3.3-70b-versatile")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    chat_id = Column(String(64), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False) # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True) # JSON or markdown formatted source citations
    feedback = Column(String(20), nullable=True) # 'like', 'dislike', None
    created_at = Column(DateTime, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False) # .pdf, .docx, .txt, .csv, .json
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, default=0)
    num_chunks = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="documents")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    provider = Column(String(50), default="groq")
    api_key = Column(String(255), nullable=True)
    base_url = Column(String(255), nullable=True)
    model_name = Column(String(100), default="llama-3.3-70b-versatile")
    temperature = Column(Float, default=0.7)
    top_p = Column(Float, default=0.9)
    system_prompt = Column(Text, default="You are a helpful, brilliant, and friendly AI assistant.")
    theme = Column(String(20), default="dark")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")

