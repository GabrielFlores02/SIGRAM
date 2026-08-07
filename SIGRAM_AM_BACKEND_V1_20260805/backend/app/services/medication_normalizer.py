import re


def normalize_active_ingredient(ingredient: str) -> str:
    """Normaliza un principio activo sin inferir equivalencias clínicas.

    Elimina espacios extremos, colapsa espacios internos, convierte a
    mayúsculas y conserva tildes. Los sinónimos entre ESSI y DDInter se manejan
    en un archivo de mapeo explícito y auditable.
    """
    if not ingredient or not ingredient.strip():
        raise ValueError("El principio activo normalizado es obligatorio.")
    cleaned = re.sub(r"\s+", " ", ingredient.strip())
    return cleaned.upper()
