"""conftest.py centralizado para pruebas del backend SIGRAM-AM.

Centraliza:
- Motor SQLite exclusivo de pruebas (en memoria con conexión compartida).
- PRAGMA foreign_keys=ON para el motor de pruebas.
- Creación y eliminación de tablas por cada prueba.
- Override de get_db.
- Creación del TestClient.
- Limpieza de app.dependency_overrides al finalizar cada prueba.

La base de desarrollo (backend/data/sigram_poc.db) nunca se toca durante Pytest.
No se deja test_sigram.db en la raíz del proyecto.
"""
import os
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.database import Base, get_db

# Motor SQLite en memoria con StaticPool: una sola conexión compartida
# para evitar que las tablas desaparezcan entre sesiones distintas.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Activar PRAGMA foreign_keys=ON también en el motor de pruebas
@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma_test(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _get_dev_db_hash() -> str | None:
    """Calcula SHA-256 de la base de desarrollo si existe, para verificar que no cambia."""
    db_path = os.path.join("backend", "data", "sigram_poc.db")
    if not os.path.exists(db_path):
        return None
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(autouse=True)
def setup_db():
    """Crea tablas antes de cada prueba, limpia todo al finalizar.

    Garantiza:
    - Tablas frescas para cada prueba.
    - Override de get_db apunta al motor de pruebas.
    - Limpieza de dependency_overrides para evitar contaminación entre pruebas.
    - La base de desarrollo no cambia durante la ejecución.
    - No queda test_sigram.db en la raíz.
    """
    # Hash de la base de desarrollo antes de la prueba
    dev_hash_before = _get_dev_db_hash()

    # Crear tablas en el motor de pruebas
    Base.metadata.create_all(bind=test_engine)

    # Override de get_db
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    # Destruir tablas del motor de pruebas
    Base.metadata.drop_all(bind=test_engine)

    # Limpiar dependency_overrides para evitar efectos entre pruebas
    app.dependency_overrides.clear()

    # Verificar que la base de desarrollo no fue modificada
    dev_hash_after = _get_dev_db_hash()
    assert dev_hash_before == dev_hash_after, (
        "ERROR: La base de desarrollo backend/data/sigram_poc.db fue modificada durante Pytest."
    )

    # Asegurar que no queda test_sigram.db residual
    if os.path.exists("./test_sigram.db"):
        os.remove("./test_sigram.db")


@pytest.fixture
def client():
    """TestClient para hacer solicitudes HTTP contra la aplicación."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Sesión de base de datos de pruebas para verificaciones directas."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
