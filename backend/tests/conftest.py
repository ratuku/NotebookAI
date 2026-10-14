import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from notebook_backend.database import Base, get_db
from notebook_backend.main import app
from notebook_backend.models.entities import User


@pytest.fixture()
def db():
    # PostgreSQL runs against already-migrated tables inside rollback-only transactions.
    # The default SQLite path keeps a fast, zero-service unit-test option available.
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
        connection = engine.connect()
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()
        connection.close()
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(User(id="00000000-0000-0000-0000-000000000001", username="admin"))
            session.commit()
            yield session
    engine.dispose()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def notebook(client):
    response = client.post("/api/v1/notebooks", json={"title": "Research"})
    assert response.status_code == 201
    return response.json()["id"]
