"""Pydantic domain models for the Auth Service.

These are the in-memory representations used by the business logic layer.
They are independent of the database ORM model.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class User(BaseModel):
    """Domain model representing an authenticated user."""

    id: uuid.UUID
    email: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}
