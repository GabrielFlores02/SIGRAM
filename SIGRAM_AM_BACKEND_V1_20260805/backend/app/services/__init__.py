# Importaciones de conveniencia para backend.app.services.
# No se importan módulos eagerly aquí para evitar dependencias circulares
# entre schemas.cases ↔ services.case_service.
#
# Uso directo:
#   from backend.app.services.case_service import CaseService
#   from backend.app.services.medication_normalizer import normalize_active_ingredient

__all__ = ["CaseService", "normalize_active_ingredient"]
