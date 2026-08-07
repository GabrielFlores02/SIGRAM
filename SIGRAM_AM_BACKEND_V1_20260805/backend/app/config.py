import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "SIGRAM-AM"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///backend/data/sigram_poc.db"
    API_PREFIX: str = "/api"
    DDINTER_DATA_DIR: str = "data/raw/ddinter2"
    DDINTER_ALIAS_FILE: str = "data/mappings/ddinter_name_aliases.csv"
    DDINTER_INCLUDE_UNKNOWN: bool = False
    CLINICAL_CATALOG_FILE: str = "data/catalogs/v1/clinical_catalog_v1.json"
    PILOT_COHORT_FILE: str = "data/raw/cohorte.parquet"
    PILOT_LABS_FILE: str = "data/raw/sigram.parquet"
    PILOT_DIAGNOSES_FILE: str = (
        "docs/ESTUDIO DE polifarmacia de referencia/6.1 polifarmacia/"
        "bd_limpia_polifarmacia/data_analitica_limpia/atenmed.parquet"
    )
    PILOT_SAMPLE_DIR: str = "data/processed/v1_handoff"
    PILOT_OBSERVATION_YEAR: int = 2025
    PILOT_LAB_LOOKBACK_DAYS: int = 365
    CIE10_CONTEXT_MAPPING_FILE: str = "data/mappings/cie10_clinical_context_v1.json"
    PILOT_DIAGNOSIS_LOOKBACK_DAYS: int = 365

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Garantizar que la carpeta de destino de SQLite exista
if settings.DATABASE_URL.startswith("sqlite:///"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    # Si la ruta contiene directorios, los creamos
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
