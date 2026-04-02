"""SQLModel ORM models — maps directly to database tables."""

import uuid
from datetime import datetime, time
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    patient_profile: str
    status: str = "pending"  # pending | complete | error

    glucose_readings: list["GlucoseReading"] = Relationship(back_populates="session")
    meal_configs: list["MealConfig"] = Relationship(back_populates="session")


class GlucoseReading(SQLModel, table=True):
    __tablename__ = "glucose_readings"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    timestamp: datetime
    glucose_mg_dl: float

    session: Optional[Session] = Relationship(back_populates="glucose_readings")


class MealConfig(SQLModel, table=True):
    __tablename__ = "meal_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    meal_name: str
    meal_time: time          # HH:MM stored as TIME
    window_before_min: int
    window_after_min: int

    session: Optional[Session] = Relationship(back_populates="meal_configs")
