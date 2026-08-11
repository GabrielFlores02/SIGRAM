"""Pruebas del endpoint de index y health.

Utiliza el conftest.py centralizado para fixtures y aislamiento.
"""

from backend.app.config import settings


def test_index_endpoint(client):
    """Prueba que el endpoint raíz responda correctamente con la advertencia clínica."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "SIGRAM-AM"
    assert data["version"] == "1.0.0"
    assert data["status"] == "proof-of-concept"
    assert "warning" in data
    assert data["warning"] == "No utilizar para decisiones clínicas"


def test_health_endpoint(client):
    """Prueba que el endpoint de salud responda con la versión de la app, estado ok y BD disponible."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["application"] == "SIGRAM-AM"
    assert data["version"] == "1.0.0"
    assert data["environment"] == settings.APP_ENV
    assert data["database"] == "available"
    assert "python_version" in data
