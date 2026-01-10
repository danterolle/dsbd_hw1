"""This script defines the database models for the User Manager microservice.

It includes the model for users.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Text, func, ForeignKey


class Base(DeclarativeBase):
    """Base class for declarative models."""

    pass


db = SQLAlchemy(model_class=Base)


class User(db.Model):
    """Represents a user of the application."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(120), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    tax_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=True)
    iban: Mapped[str] = mapped_column(String(27), nullable=True)
    telegram_chat_id: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=True
    )

    def to_dict(self) -> dict:
        """Converts the User object to a dictionary.

        Returns:
            dict: A dictionary representation of the user.
        """
        return {
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "tax_code": self.tax_code,
            "iban": self.iban,
            "telegram_chat_id": self.telegram_chat_id,
        }

    def __repr__(self) -> str:
        """Returns a string representation of the User object."""
        return f"<User {self.email}>"


class IdempotencyKey(db.Model):
    """Represents an idempotency key to ensure at-most-once execution."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), default="in-progress", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    response_code: Mapped[int] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str] = mapped_column(Text, nullable=True)
    user_email: Mapped[str] = mapped_column(String(120), nullable=False)

    def __repr__(self) -> str:
        """Returns a string representation of the IdempotencyKey object."""
        return f"<IdempotencyKey {self.key} - {self.status}>"
