from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from notebook_backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


def get_db():
    with SessionLocal() as session:
        yield session
