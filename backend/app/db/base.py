"""SQLAlchemy declarative base for ACE database models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class shared by all ACE ORM models."""

    pass