from alembic import context
from sqlalchemy import create_engine

from notebook_backend.config import settings
from notebook_backend.database import Base
from notebook_backend.models import entities  # noqa: F401

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
