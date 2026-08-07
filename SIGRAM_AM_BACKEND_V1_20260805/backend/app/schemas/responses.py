from pydantic import BaseModel

class IndexResponse(BaseModel):
    name: str
    version: str
    status: str
    warning: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "SIGRAM-AM",
                "version": "0.1.0",
                "status": "proof-of-concept",
                "warning": "No utilizar para decisiones clínicas"
            }
        }
    }


class HealthResponse(BaseModel):
    status: str
    application: str
    version: str
    environment: str
    python_version: str
    database: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "application": "SIGRAM-AM",
                "version": "0.1.0",
                "environment": "development",
                "python_version": "3.12.8",
                "database": "available"
            }
        }
    }
