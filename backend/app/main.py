import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import init_db
from .routes import auth_routes, chat_routes, doc_routes, settings_routes, xray_routes, export_routes

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ChatGPT-Style AI Platform API — Hosted LLM Endpoints, Multi-User Auth, and Document RAG"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join("backend_uploads", "generated_images"), exist_ok=True)
    init_db()


# Mount Static Files for Generated Images and Uploads
generated_images_dir = os.path.join("backend_uploads", "generated_images")
os.makedirs(generated_images_dir, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=generated_images_dir), name="images")
app.mount("/api/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# Include Routers
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(doc_routes.router)
app.include_router(settings_routes.router)
app.include_router(xray_routes.router)
app.include_router(export_routes.router)


@app.get("/")
def root():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "documentation": "/docs"
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "database": "connected",
        "hosted_llm": settings.DEFAULT_MODEL_NAME
    }

