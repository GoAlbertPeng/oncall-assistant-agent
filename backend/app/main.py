"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.config import get_settings
from app.database import init_db, AsyncSessionLocal
from app.api import api_router
from app.models.user import User
from app.services.auth_service import hash_password

settings = get_settings()


async def create_admin_user():
    """Create default admin user if not exists."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == "admin@oncall.example.com")
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = User(
                email="admin@oncall.example.com",
                password_hash=hash_password("admin123"),
            )
            db.add(admin)
            await db.commit()
            print("Admin user created: admin@oncall.example.com / admin123")
        else:
            print("Admin user already exists")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    await create_admin_user()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="OnCall Assistant Agent - AI-powered alert analysis and incident management",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
