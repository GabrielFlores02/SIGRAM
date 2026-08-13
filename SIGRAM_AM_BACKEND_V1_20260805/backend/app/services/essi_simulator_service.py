from sqlalchemy.orm import Session

from backend.app.models.models import ClinicalCase, Medication, SimulationHistoryEvent
from backend.app.schemas.cases import ClinicalCaseCreate, ClinicalContext
from backend.app.schemas.simulator import EssiSimulatorUpdate
from backend.app.services.case_service import CaseService
from backend.app.services.medication_normalizer import normalize_active_ingredient
from backend.app.services.pilot_sample_service import PilotSampleService
from backend.app.services.renal_function_service import enrich_with_cockcroft_gault


SIMULATOR_CODE = "SIM-ESSI-001"
SOURCE_PILOT_CODE = "PILOT-96CBA7BBFA883815"


class EssiSimulatorService:
    @staticmethod
    def _snapshot(case: ClinicalCase) -> dict:
        return {
            "case_code": case.case_code, "age": case.age, "sex": case.sex,
            "diagnoses": case.diagnoses, "clinical_context": case.clinical_context,
            "medications": [{
                "entered_name": med.entered_name,
                "normalized_active_ingredient": med.normalized_active_ingredient,
                "dose": med.dose, "dose_unit": med.dose_unit, "frequency": med.frequency,
                "duration": med.duration, "route": med.route,
            } for med in case.medications],
        }

    @classmethod
    def _event(cls, db: Session, case: ClinicalCase, event_type: str, note: str) -> None:
        db.add(SimulationHistoryEvent(case_id=case.id, event_type=event_type, note=note, snapshot=cls._snapshot(case)))

    @staticmethod
    def _baseline_data() -> ClinicalCaseCreate:
        prefill = PilotSampleService().case_prefill(SOURCE_PILOT_CODE)
        return ClinicalCaseCreate(
            case_code=SIMULATOR_CODE, age=prefill["age"], sex=prefill["sex"], diagnoses=prefill["diagnoses"],
            clinical_context=ClinicalContext.model_validate(prefill["clinical_context"]),
            medications=prefill["medications"], is_simulated=True,
        )

    @classmethod
    def get_or_initialize(cls, db: Session) -> ClinicalCase:
        case = db.query(ClinicalCase).filter(ClinicalCase.case_code == SIMULATOR_CODE).first()
        if case:
            return case
        case = CaseService.create_case(db, cls._baseline_data())
        case.status = "essi_simulator"
        cls._event(db, case, "baseline_import", f"Línea base importada de {SOURCE_PILOT_CODE}; la cohorte piloto permanece intacta.")
        db.commit(); db.refresh(case)
        return case

    @classmethod
    def update(cls, db: Session, update: EssiSimulatorUpdate) -> ClinicalCase:
        case = cls.get_or_initialize(db)
        case.age, case.sex, case.diagnoses = update.age, update.sex, update.diagnoses
        case.clinical_context = enrich_with_cockcroft_gault(update.clinical_context.model_dump(), age=update.age, sex=update.sex)
        case.medications.clear()
        for med in update.medications:
            case.medications.append(Medication(
                entered_name=med.entered_name, normalized_active_ingredient=normalize_active_ingredient(med.normalized_active_ingredient),
                dose=med.dose, dose_unit=med.dose_unit, frequency=med.frequency, duration=med.duration, route=med.route,
            ))
        db.flush()
        cls._event(db, case, "clinical_update", update.note or "Actualización de atención simulada")
        db.commit(); db.refresh(case)
        return case

    @classmethod
    def reset(cls, db: Session) -> ClinicalCase:
        case = cls.get_or_initialize(db)
        baseline = cls._baseline_data()
        case.age, case.sex, case.diagnoses = baseline.age, baseline.sex, baseline.diagnoses
        case.clinical_context = enrich_with_cockcroft_gault(baseline.clinical_context.model_dump(), age=baseline.age, sex=baseline.sex)
        case.medications.clear()
        for med in baseline.medications:
            case.medications.append(Medication(**med.model_dump()))
        db.flush()
        cls._event(db, case, "reset_to_baseline", f"Se restauró la línea base de {SOURCE_PILOT_CODE}.")
        db.commit(); db.refresh(case)
        return case

    @staticmethod
    def response(case: ClinicalCase) -> dict:
        return {"case": case, "history": case.simulation_history_events}
