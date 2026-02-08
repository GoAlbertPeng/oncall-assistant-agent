"""Database initialization script."""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.database import engine, Base, AsyncSessionLocal
from app.models import User, DataSource, AnalysisSession, Ticket
from app.services.auth_service import hash_password


async def init_database():
    """Create all tables and seed initial data."""
    print("Creating database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Tables created successfully!")
    
    # Seed admin user
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        
        # Check if admin user exists
        result = await db.execute(select(User).where(User.email == "admin@oncall.example.com"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("Creating admin user...")
            admin = User(
                email="admin@oncall.example.com",
                password_hash=hash_password("admin123"),
            )
            db.add(admin)
            await db.commit()
            print("Admin user created: admin@oncall.example.com / admin123")
        else:
            print("Admin user already exists.")
    
    print("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(init_database())
