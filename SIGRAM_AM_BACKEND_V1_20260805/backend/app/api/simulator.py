from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.simulator import EssiSimulatorRead, EssiSimulatorUpdate
from backend.app.services.essi_simulator_service import EssiSimulatorService

router = APIRouter(prefix="/api/simulator/essi", tags=["ESSI simulator"])

@router.get("", response_model=EssiSimulatorRead)
def get_simulator(db: Session = Depends(get_db)):
    return EssiSimulatorService.response(EssiSimulatorService.get_or_initialize(db))

@router.put("", response_model=EssiSimulatorRead)
def update_simulator(payload: EssiSimulatorUpdate, db: Session = Depends(get_db)):
    return EssiSimulatorService.response(EssiSimulatorService.update(db, payload))

@router.post("/reset", response_model=EssiSimulatorRead)
def reset_simulator(db: Session = Depends(get_db)):
    return EssiSimulatorService.response(EssiSimulatorService.reset(db))
