"""Script to create the initial superadmin user."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.session import AsyncSessionLocal
from app.db.models.user import UserRole
from app.services.auth import AuthService
from app.schemas.user import UserCreate


async def main():
    email = input("Admin email: ")
    username = input("Admin username: ")
    password = input("Admin password: ")
    async with AsyncSessionLocal() as db:
        svc = AuthService(db)
        user = await svc.register(UserCreate(
            email=email, username=username,
            password=password, role=UserRole.ADMIN
        ))
        await db.commit()
        print(f"Created admin user: {user.id}")


if __name__ == "__main__":
    asyncio.run(main())
