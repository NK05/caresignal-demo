from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, create_database_engine


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:  # noqa: ANN001
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = test_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
