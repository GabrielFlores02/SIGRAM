from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import settings

# Configurar motor de SQLite con consideraciones de hilos para desarrollo local
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

# PASO 4: Activar integridad referencial en SQLite mediante evento de conexión.
# Sin este pragma, SQLite ignora las restricciones de clave foránea por defecto.
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Generador de sesiones de base de datos para inyección de dependencias."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Inicializa la base de datos creando las tablas registradas en Base."""
    Base.metadata.create_all(bind=engine)
    # Migración mínima para bases SQLite creadas por la PoC 0.1.
    if settings.DATABASE_URL.startswith("sqlite"):
        inspector = inspect(engine)
        if "clinical_cases" in inspector.get_table_names():
            case_columns = {
                column["name"] for column in inspector.get_columns("clinical_cases")
            }
            if "clinical_context" not in case_columns:
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "ALTER TABLE clinical_cases "
                        "ADD COLUMN clinical_context JSON NOT NULL DEFAULT '{}'"
                    )
        if "evaluation_executions" in inspector.get_table_names():
            execution_columns = {
                column["name"]
                for column in inspector.get_columns("evaluation_executions")
            }
            if "criteria_report" not in execution_columns:
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "ALTER TABLE evaluation_executions "
                        "ADD COLUMN criteria_report JSON NOT NULL DEFAULT '[]'"
                    )
