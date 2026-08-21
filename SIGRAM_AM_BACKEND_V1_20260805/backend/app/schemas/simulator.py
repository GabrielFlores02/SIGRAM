from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from backend.app.schemas.cases import ClinicalCaseCreate, ClinicalCaseRead


class EssiSimulatorUpdate(ClinicalCaseCreate):
    """La atención actual reemplaza la lista activa; el estado previo queda en el historial."""
    note: str = Field(default="Actualización de atención simulada", max_length=500)


class SimulationHistoryEventRead(BaseModel):
    id: int
    event_type: str
    note: str
    snapshot: dict
    created_at: datetime
    model_config = {"from_attributes": True}


class EssiSimulatorRead(BaseModel):
    case: ClinicalCaseRead
    history: List[SimulationHistoryEventRead]
