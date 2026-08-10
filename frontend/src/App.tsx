import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  AnalysisSystem,
  AlertResult,
  CatalogCriterion,
  CatalogMedication,
  CatalogSummary,
  ClinicalCase,
  ClinicalCaseInput,
  ClinicalCaseSummary,
  CriterionResult,
  EvaluationExecution,
  LabEvidence,
  MedicationInput,
  PilotEvaluationResponse,
  PilotPatient,
  PilotResearchData,
  RequiredData,
} from "./types";

type Page = "cases" | "new" | "history" | "research" | "results";
type VisibleSystem = AnalysisSystem;
type DDInterLevel = "MAJOR" | "MODERATE" | "MINOR" | "UNKNOWN" | "UNSPECIFIED";

const EMPTY_MEDICATION: MedicationInput = {
  entered_name: "",
  normalized_active_ingredient: "",
  dose: "",
  dose_unit: "mg",
  frequency: "C/24h",
  duration: "",
  route: "Oral",
};

const NUMERIC_CONTEXT_FIELDS = new Set([
  "egfr_ml_min_1_73m2",
  "potassium_mmol_l",
  "sodium_mmol_l",
  "corrected_calcium_mmol_l",
  "tsh_miu_l",
  "proteinuria_mg_24h",
  "systolic_bp_mm_hg",
  "diastolic_bp_mm_hg",
  "heart_rate_bpm",
  "qtc_ms",
  "bmi",
  "medication_duration_days",
  "daily_dose_mg",
]);

const BOOLEAN_CONTEXT_FIELDS = new Set([
  "free_t4_normal",
  "falls_history",
  "cognitive_impairment",
  "delirium",
  "orthostatic_hypotension",
  "syncope_history",
  "adherence_known",
  "indication_confirmed",
  "gastroprotection",
  "peptic_ulcer_history",
  "primary_prevention",
  "av_block",
  "gout_history",
  "potassium_monitoring",
  "life_expectancy_lt_3_years",
  "cardiovascular_history",
  "bleeding_risk",
  "atrial_fibrillation",
  "coronary_stent_or_stenosis",
  "stable_vascular_disease",
  "constipation",
  "copd",
  "respiratory_failure",
  "osteoarthritis",
  "prior_paracetamol_trial",
  "upper_gi_disease",
  "first_line_treatment",
  "neuropathic_pain",
  "chronic_liver_disease",
  "reduced_ejection_fraction",
  "severe_gerd_or_stricture",
  "osteoporosis_or_fragility_fracture",
  "bph_urinary_symptoms",
  "opioid_regular_use",
]);

function formatDate(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
    new Date(value),
  );
}

function sexLabel(value: string) {
  const normalized = value.toLowerCase();
  if (normalized.startsWith("f")) return "F";
  if (normalized.startsWith("m")) return "M";
  return value;
}

function statusLabel(status: CriterionResult["status"]) {
  return {
    alert: "Advertencia",
    no_alert: "Sin hallazgo en los datos observados",
    not_evaluable: "Requiere información adicional",
    manual_review: "Revisión manual",
  }[status];
}

function ddinterLevel(alert: AlertResult): DDInterLevel {
  const value = alert.trace_data.catalog_level;
  if (typeof value === "string") {
    const normalized = value.toUpperCase();
    if (normalized === "MAJOR" || normalized === "MODERATE" || normalized === "MINOR" || normalized === "UNKNOWN") {
      return normalized;
    }
  }
  return "UNSPECIFIED";
}

function ddinterLevelLabel(level: DDInterLevel) {
  return {
    MAJOR: "Major",
    MODERATE: "Moderate",
    MINOR: "Minor",
    UNKNOWN: "Unknown",
    UNSPECIFIED: "No informado",
  }[level];
}

function traceStringList(alert: AlertResult, field: string) {
  const value = alert.trace_data[field];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function labFieldLabel(field: string) {
  return {
    egfr_ml_min_1_73m2: "TFGe / TFG",
    potassium_mmol_l: "Potasio",
    sodium_mmol_l: "Sodio",
    tsh_miu_l: "TSH",
    free_t4_normal: "T4 libre en rango",
    proteinuria_mg_24h: "Proteinuria de 24 horas",
  }[field] ?? field;
}

function labValueLabel(evidence: LabEvidence) {
  if (typeof evidence.value === "boolean") return evidence.value ? "Sí" : "No";
  return `${evidence.source_value_raw || evidence.value} ${evidence.source_unit || evidence.standardized_unit}`.trim();
}

function labWarningLabel(warning: string) {
  const messages: Record<string, string> = {
    "VALID_RESULT is preserved but its value semantics are not documented.": "VALID_RESULT se conserva, pero su semántica no está documentada.",
    "Only direct mappings are used; eGFR is accepted only when ESSI reports TFG directly and is not calculated from creatinine.": "Solo se usan mapeos directos; TFGe se acepta únicamente si ESSI reporta TFG directamente y no se calcula desde creatinina.",
    "The 365-day lookback is a provisional pilot rule requiring clinical validation.": "La ventana retrospectiva de 365 días es una regla provisional que requiere validación clínica.",
  };
  return messages[warning] ?? warning;
}

function Shell({ page, onNavigate, children }: { page: Page; onNavigate: (page: Page) => void; children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-main">
          <div className="brand-lockup">
            <div className="essalud-logo-wrap">
              <img className="essalud-logo" src="/essalud-logo.png" alt="EsSalud — Humanizando el Seguro Social" />
            </div>
            <span className="brand-divider" />
            <span className="product-name">SIGRAM-AM | Piloto de investigación</span>
          </div>
        </div>
        <nav className="main-nav" aria-label="Navegación principal">
          <button className={`research-nav ${page === "cases" ? "active" : ""}`} onClick={() => onNavigate("cases")}>Casos del piloto</button>
          <button className={page === "new" ? "active" : ""} onClick={() => onNavigate("new")}>Nuevo caso</button>
          <button className={page === "history" ? "active" : ""} onClick={() => onNavigate("history")}>Historial</button>
          <button className={`research-nav ${page === "research" ? "active" : ""}`} onClick={() => onNavigate("research")}>Validación de datos</button>
        </nav>
      </header>
      <main className="page-container">{children}</main>
      <footer className="research-warning">
        <span aria-hidden="true">⚠</span>
        <p>Prototipo de investigación. Los resultados son tamizajes y requieren revisión por un profesional de salud. No utilizar para decisiones clínicas.</p>
      </footer>
    </div>
  );
}

function ErrorNotice({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="error-notice" role="alert">
      <span>⚠</span><span>{message}</span><button onClick={onClose} aria-label="Cerrar mensaje">×</button>
    </div>
  );
}

function CasesPage({ onNew, onPilotReview }: { onNew: () => void; onPilotReview: (response: PilotEvaluationResponse) => void }) {
  const [pilotPatients, setPilotPatients] = useState<PilotPatient[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyCode, setBusyCode] = useState("");
  const [error, setError] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<PilotPatient>();

  useEffect(() => {
    api.listPilotPatients()
      .then(setPilotPatients)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredPatients = pilotPatients.filter((item) => item.patient_code.toLowerCase().includes(query.toLowerCase()));

  async function evaluateSample(patient: PilotPatient, clinicalContext: Record<string, unknown> = {}) {
    setBusyCode(patient.patient_code);
    setError("");
    try {
      const response = await api.evaluatePilotPatient(patient.patient_code, clinicalContext);
      sessionStorage.setItem(`sigram-pilot-evaluation-${response.case.id}`, JSON.stringify(response));
      onPilotReview(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo evaluar la muestra.");
    } finally {
      setBusyCode("");
    }
  }

  return (
    <section>
      {error && <ErrorNotice message={error} onClose={() => setError("")} />}
      <div className="section-hero">
        <div>
          <span className="eyebrow">Casos del piloto</span>
          <h1>Evaluación de prescripción en adultos mayores</h1>
          <p>Muestra pseudonimizada del periodo 2025 disponible para evaluación controlada.</p>
        </div>
        <span className="pilot-badge">ⓘ Piloto de investigación</span>
      </div>

      <div className="toolbar-row">
        <span className="sample-label">Muestra piloto pseudonimizada</span>
        <div className="toolbar-actions">
          <label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por código..." /></label>
          <button className="primary-button" onClick={onNew}>＋ Nuevo caso simulado</button>
        </div>
      </div>

      <div className="table-card">
        {loading ? <div className="empty-state">Cargando muestra…</div> : (
          <div className="table-scroll"><table>
            <thead><tr><th>Código pseudonimizado</th><th>Paciente</th><th>Medicamentos simultáneos</th><th>Fecha índice</th><th>Laboratorios 2025</th><th>CIE-10 2025</th><th>Acción</th></tr></thead>
            <tbody>{filteredPatients.map((patient) => (
              <tr key={patient.patient_code}>
                <td><span className="case-code">{patient.patient_code}</span></td>
                <td>{patient.age} años<br /><small>{patient.sex}</small></td>
                <td>{patient.max_simultaneous_top_medications}</td>
                <td>{patient.index_date ?? "—"}</td>
                <td>{patient.raw_lab_rows_2025}</td>
                <td>{patient.raw_diagnosis_rows_2025}<br /><small>{patient.distinct_diagnosis_codes_2025} códigos</small></td>
                <td><div className="table-actions"><button className="link-button" disabled={busyCode === patient.patient_code} onClick={() => evaluateSample(patient)}>{busyCode === patient.patient_code ? "Evaluando…" : "Evaluar →"}</button><button className="secondary-link" disabled={busyCode === patient.patient_code} onClick={() => setSelectedPatient(patient)}>Contexto clínico</button></div></td>
              </tr>
            ))}</tbody>
          </table>{filteredPatients.length === 0 && <div className="empty-state">No hay registros disponibles en la muestra.</div>}</div>
        )}
      </div>
      {selectedPatient && <PilotContextDrawer patient={selectedPatient} onClose={() => setSelectedPatient(undefined)} onEvaluate={async (context) => { await evaluateSample(selectedPatient, context); setSelectedPatient(undefined); }} />}
    </section>
  );
}

function PilotContextDrawer({ patient, onClose, onEvaluate }: { patient: PilotPatient; onClose: () => void; onEvaluate: (context: Record<string, unknown>) => Promise<void> }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const fields = [
    ["egfr_ml_min_1_73m2", "TFGe / TFG (mL/min/1.73 m²)", "number"],
    ["potassium_mmol_l", "Potasio (mmol/L)", "number"],
    ["sodium_mmol_l", "Sodio (mmol/L)", "number"],
    ["tsh_miu_l", "TSH (mIU/L)", "number"],
    ["proteinuria_mg_24h", "Proteinuria de 24 h (mg/24 h)", "number"],
  ] as const;
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    const context: Record<string, unknown> = {};
    for (const [field] of fields) if (values[field] !== undefined && values[field] !== "") context[field] = Number(values[field]);
    if (values.free_t4_normal) context.free_t4_normal = values.free_t4_normal === "true";
    try { await onEvaluate(context); } finally { setSubmitting(false); }
  }
  return <div className="drawer-layer" role="dialog" aria-modal="true" aria-labelledby="pilot-context-title">
    <button className="drawer-backdrop" onClick={onClose} aria-label="Cerrar contexto clínico" />
    <aside className="detail-drawer pilot-context-drawer"><header><div><span className="status-dot" /><h2 id="pilot-context-title">Contexto clínico manual</h2></div><button onClick={onClose} aria-label="Cerrar">×</button></header>
      <form className="drawer-content" onSubmit={submit}><p className="drawer-intro">Paciente pseudonimizado <b>{patient.patient_code}</b>. Los valores ingresados aquí tienen prioridad sobre el laboratorio mapeado por el backend.</p><div className="drawer-form-grid">{fields.map(([field, label, type]) => <label key={field}>{label}<input type={type} step="any" value={values[field] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))} placeholder="No registrado" /></label>)}<label>T4 libre en rango de referencia<select value={values.free_t4_normal ?? ""} onChange={(event) => setValues((current) => ({ ...current, free_t4_normal: event.target.value }))}><option value="">No registrado</option><option value="true">Sí</option><option value="false">No</option></select></label></div><p className="field-help">Registre solo datos verificables de la fuente clínica autorizada. Deje vacío lo no disponible.</p><footer><button type="button" className="secondary-button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting}>{submitting ? "Evaluando…" : "Evaluar con contexto"}</button></footer></form>
    </aside>
  </div>;
}

function HistoryPage({ onReview }: { onReview: (item: ClinicalCaseSummary) => void }) {
  const [cases, setCases] = useState<ClinicalCaseSummary[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.listCases().then(setCases).catch((reason: Error) => setError(reason.message)); }, []);
  const rows = cases.filter((item) => `${item.case_code} ${item.diagnoses}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="history-page">
    <div className="section-hero history-hero">
      <div><span className="eyebrow">Historial de evaluaciones</span><h1>Casos analizados del piloto</h1><p>Registro de los casos simulados que ya fueron creados y evaluados en SIGRAM-AM.</p></div>
      <span className="pilot-badge">Zona de simulación</span>
    </div>
    {error && <ErrorNotice message={error} onClose={() => setError("")} />}
    <div className="history-toolbar"><label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por código o diagnóstico…" /></label><span>{rows.length} casos</span></div>
    <div className="table-card history-card"><div className="table-scroll"><table><thead><tr><th>Código de caso</th><th>Paciente</th><th>Diagnósticos registrados</th><th>Fecha de creación</th><th>Acción</th></tr></thead><tbody>{rows.map((item) => <tr key={item.id}><td><span className="case-code">{item.case_code}</span></td><td>{item.age} años<br /><small>{item.sex}</small></td><td className="diagnoses-cell">{item.diagnoses}</td><td>{formatDate(item.created_at)}</td><td><button className="link-button" onClick={() => onReview(item)}>Ver resultados →</button></td></tr>)}</tbody></table>{rows.length === 0 && <div className="empty-state">Aún no hay casos analizados registrados.</div>}</div></div>
  </section>;
}

function ResearchDataPage() {
  const [patients, setPatients] = useState<PilotPatient[]>([]);
  const [selectedCode, setSelectedCode] = useState("");
  const [data, setData] = useState<PilotResearchData>();
  const [criteria, setCriteria] = useState<CatalogCriterion[]>([]);
  const [medications, setMedications] = useState<CatalogMedication[]>([]);
  const [view, setView] = useState<"laboratories" | "medications" | "criteria">("laboratories");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.listPilotPatients(), api.listCriteria(), api.listCatalogMedications()])
      .then(([patientRows, criterionRows, medicationRows]) => {
        setPatients(patientRows);
        setCriteria(criterionRows);
        setMedications(medicationRows);
        setSelectedCode(patientRows[0]?.patient_code ?? "");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCode) return;
    setData(undefined);
    api.getPilotResearchData(selectedCode).then(setData).catch((reason: Error) => setError(reason.message));
  }, [selectedCode]);

  return <section className="research-page">
    <div className="section-hero research-hero"><div><span className="eyebrow">Validación de investigación</span><h1>Datos pseudonimizados y trazabilidad</h1><p>Consulta técnica de insumos del piloto para revisión clínica y metodológica.</p></div><span className="pilot-badge">Solo investigación</span></div>
    {error && <ErrorNotice message={error} onClose={() => setError("")} />}
    <div className="research-notice"><strong>Alcance:</strong> esta vista no es asistencial. Muestra únicamente registros pseudonimizados, catálogos controlados y evidencia de mapeo del backend V2.</div>
    <div className="research-controls"><label>Paciente de muestra<select value={selectedCode} disabled={loading} onChange={(event) => setSelectedCode(event.target.value)}>{patients.map((patient) => <option key={patient.patient_code} value={patient.patient_code}>{patient.patient_code} · {patient.age} años · {patient.sex}</option>)}</select></label>{data && <span>Fecha índice: <b>{data.medication_index_date}</b></span>}</div>
    <div className="criteria-tabs research-tabs"><button className={view === "laboratories" ? "active" : ""} onClick={() => setView("laboratories")}>Exámenes en crudo</button><button className={view === "medications" ? "active" : ""} onClick={() => setView("medications")}>Medicamentos y catálogo</button><button className={view === "criteria" ? "active" : ""} onClick={() => setView("criteria")}>Criterios</button></div>
    {view === "laboratories" && <div className="research-stack">
      <div className="research-summary"><span>Filas de laboratorio: <b>{data?.raw_laboratory_rows.length ?? "—"}</b></span><span>Campos aceptados: <b>{data?.lab_mapping.mapped_lab_fields.length ?? "—"}</b></span><span>Rechazadas: <b>{data?.lab_mapping.relevant_lab_rows_rejected ?? "—"}</b></span><span>Futuras excluidas: <b>{data?.lab_mapping.future_relevant_lab_rows_excluded ?? "—"}</b></span></div>
      <div className="results-card"><div className="results-toolbar"><div><strong>Resultados aceptados por el mapeo</strong></div></div><div className="table-scroll"><table><thead><tr><th>Campo</th><th>Valor original</th><th>Fecha</th><th>Código ESSI</th><th>Analito</th><th>Estado</th></tr></thead><tbody>{data?.lab_mapping.mapped_lab_fields.map((item) => <tr key={item.source_row_sha256}><td>{labFieldLabel(item.field)}</td><td>{labValueLabel(item)}</td><td>{formatDate(item.result_date)}</td><td>{item.exam_code}</td><td>{item.source_analyte}</td><td>{item.applied ? "Aplicado" : "Prioridad manual"}</td></tr>)}</tbody></table>{data && data.lab_mapping.mapped_lab_fields.length === 0 && <div className="empty-state">No hay campos de laboratorio aceptados para esta fecha índice.</div>}</div></div>
      <div className="results-card"><div className="results-toolbar"><div><strong>Laboratorios de origen</strong><span>{data?.raw_laboratory_rows.length ?? 0} filas</span></div></div><div className="table-scroll"><table className="research-table"><thead><tr><th>Fecha</th><th>Prueba</th><th>Código ESSI</th><th>Analito</th><th>Valor</th><th>Unidad</th><th>Rango</th><th>Validación</th></tr></thead><tbody>{data?.raw_laboratory_rows.map((item, index) => <tr key={`${item.exam_code}-${item.result_date_raw}-${index}`}><td>{item.result_date_raw ?? "—"}</td><td>{item.test_description ?? "—"}</td><td>{item.exam_code ?? "—"}</td><td>{item.analyte ?? "—"}</td><td>{item.result_value_raw ?? "—"}</td><td>{item.unit ?? "—"}</td><td>{item.normal_value_raw || item.other_normal_value_raw || "—"}</td><td>{item.validation_status ?? "—"}</td></tr>)}</tbody></table></div></div>
      {data?.lab_mapping.lab_mapping_warnings.map((warning) => <div className="method-note" key={warning}>ⓘ {labWarningLabel(warning)}</div>)}
    </div>}
    {view === "medications" && <div className="research-stack"><div className="results-card"><div className="results-toolbar"><div><strong>Medicamentos activos en la fecha índice</strong></div></div><div className="table-scroll"><table><thead><tr><th>Medicamento</th><th>Fecha de despacho</th><th>Duración (días)</th><th>Diagnóstico asociado</th></tr></thead><tbody>{data?.active_medications.map((item, index) => <tr key={`${item.medication}-${index}`}><td>{item.medication}</td><td>{item.fecha_despacho ?? "—"}</td><td>{item.duracion_dias ?? "—"}</td><td>{item.diagnosis_code ?? "—"}</td></tr>)}</tbody></table></div></div><CatalogMedicationTable medications={medications} /></div>}
    {view === "criteria" && <CatalogCriteriaTable criteria={criteria} />}
  </section>;
}

function CatalogMedicationTable({ medications }: { medications: CatalogMedication[] }) {
  return <div className="results-card"><div className="results-toolbar"><div><strong>Catálogo controlado de medicamentos</strong><span>{medications.length} medicamentos</span></div></div><div className="table-scroll"><table><thead><tr><th>Medicamento</th><th>Grupo farmacológico</th><th>Beers</th><th>STOPP</th><th>START</th></tr></thead><tbody>{medications.map((item) => <tr key={item.order}><td>{item.medication}</td><td>{item.pharmacologic_group}</td><td>{item.beers_codes.join(", ") || "—"}</td><td>{item.stopp_codes.join(", ") || "—"}</td><td>{item.start_codes.join(", ") || "—"}</td></tr>)}</tbody></table></div></div>;
}

function CatalogCriteriaTable({ criteria }: { criteria: CatalogCriterion[] }) {
  return <div className="results-card"><div className="results-toolbar"><div><strong>Catálogo de criterios</strong><span>{criteria.length} criterios</span></div></div><div className="table-scroll"><table className="research-table"><thead><tr><th>Código</th><th>Sistema</th><th>Tipo</th><th>Automatización</th><th>Datos requeridos</th><th>Fuente</th></tr></thead><tbody>{criteria.map((item) => <tr key={item.code}><td>{item.code}</td><td>{item.system === "beers" ? "Beers" : "STOPP/START"}</td><td>{item.system === "beers" ? "—" : item.criterion_type}</td><td>{item.automation_status === "automated_v1" ? "Automático V1" : "Contexto / revisión"}</td><td>{item.required_data.map((entry) => entry.label).join(", ") || "—"}</td><td>{item.source_location}</td></tr>)}</tbody></table></div></div>;
}

function NewCasePage({ onCompleted }: { onCompleted: (clinicalCase: ClinicalCase, evaluation: EvaluationExecution) => void }) {
  const [caseCode, setCaseCode] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [diagnoses, setDiagnoses] = useState("");
  const [medications, setMedications] = useState<MedicationInput[]>([{ ...EMPTY_MEDICATION }]);
  const [criteria, setCriteria] = useState<CatalogCriterion[]>([]);
  const [catalogMedications, setCatalogMedications] = useState<CatalogMedication[]>([]);
  const [catalogSummary, setCatalogSummary] = useState<CatalogSummary>();
  const [pilotPatients, setPilotPatients] = useState<PilotPatient[]>([]);
  const [selectedPatientCode, setSelectedPatientCode] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyNotice, setHistoryNotice] = useState("");
  const [historyMedications, setHistoryMedications] = useState<MedicationInput[]>([]);
  const [contextOpen, setContextOpen] = useState(false);
  const [clinicalContext, setClinicalContext] = useState<Record<string, string>>(Object.create(null));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.listCriteria(), api.listCatalogMedications(), api.getCatalogSummary(), api.listPilotPatients()])
      .then(([criteriaRows, medicationRows, summary, patientRows]) => {
        setCriteria(criteriaRows);
        setCatalogMedications(medicationRows);
        setCatalogSummary(summary);
        setPilotPatients(patientRows);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const requiredContext = useMemo(() => {
    const unique = new Map<string, RequiredData>();
    criteria.flatMap((criterion) => criterion.required_data).forEach((item) => unique.set(item.field, item));
    return [...unique.values()].sort((a, b) => a.label.localeCompare(b.label, "es"));
  }, [criteria]);

  const editableContext = requiredContext.filter((item) => item.field !== "medication_duration_days");
  const recordedContext = editableContext.filter((item) => (clinicalContext[item.field] ?? "") !== "");
  const unrecordedContext = editableContext.filter((item) => (clinicalContext[item.field] ?? "") === "");

  const minimumComplete = Boolean(
    caseCode.trim() && Number(age) >= 60 && sex && diagnoses.trim() && medications.length &&
    medications.every((item) => item.entered_name.trim() && item.normalized_active_ingredient.trim() && item.dose.trim() && item.dose_unit && item.frequency && item.route),
  );

  function updateMedication(index: number, field: keyof MedicationInput, value: string) {
    setMedications((current) => current.map((item, position) => position === index ? { ...item, [field]: value } : item));
  }

  function selectCatalogMedication(index: number, value: string) {
    const selected = catalogMedications.find((item) => item.medication === value);
    setMedications((current) => current.map((item, position) => position === index ? {
      ...item,
      entered_name: value,
      normalized_active_ingredient: selected?.medication ?? "",
    } : item));
  }

  async function selectPatientHistory(patientCode: string) {
    setSelectedPatientCode(patientCode);
    setError("");
    if (!patientCode) {
      setAge("");
      setSex("");
      setDiagnoses("");
      setMedications([{ ...EMPTY_MEDICATION }]);
      setHistoryMedications([]);
      setClinicalContext(Object.create(null));
      setContextOpen(false);
      setHistoryNotice("");
      return;
    }

    setHistoryLoading(true);
    setHistoryNotice("");
    try {
      const prefill = await api.getPilotCasePrefill(patientCode);
      setAge(String(prefill.age));
      setSex(prefill.sex);
      setDiagnoses(prefill.diagnoses);
      setMedications([{ ...EMPTY_MEDICATION }]);
      setHistoryMedications(prefill.medications);
      const mappedContext: Record<string, string> = Object.create(null);
      for (const [field, value] of Object.entries(prefill.clinical_context)) {
        if (value === null || value === undefined || Array.isArray(value) || typeof value === "object") continue;
        mappedContext[field] = String(value);
      }
      setClinicalContext(mappedContext);
      setContextOpen(true);
      setHistoryNotice(`Historia pseudonimizada ${patientCode} cargada. Se incluyeron los medicamentos activos en ${formatDate(prefill.medication_index_date)}; puede agregar la nueva receta para evaluar polifarmacia.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cargar la historia del paciente.");
    } finally {
      setHistoryLoading(false);
    }
  }

  function serializeContext() {
    const result: Record<string, unknown> = {};
    for (const [field, rawValue] of Object.entries(clinicalContext)) {
      if (rawValue === "") continue;
      if (BOOLEAN_CONTEXT_FIELDS.has(field)) result[field] = rawValue === "true";
      else if (NUMERIC_CONTEXT_FIELDS.has(field)) result[field] = Number(rawValue);
      else result[field] = rawValue;
    }
    const medicationFacts = [...historyMedications, ...medications].flatMap((medication) => {
      const durationMatch = medication.duration?.match(/^\s*(\d+)\s*(?:d[ií]as?)?\s*$/i);
      return [{
        active_ingredient: medication.normalized_active_ingredient,
        ...(durationMatch ? { duration_days: Number(durationMatch[1]) } : {}),
        regular_use: medication.frequency !== "Según necesidad",
      }];
    });
    if (medicationFacts.length) result.medication_facts = medicationFacts;
    return result;
  }

  function renderContextFields(items: RequiredData[]) {
    return <div className="context-grid">
      {items.map((item) => <label key={item.field}>{item.label}
        {BOOLEAN_CONTEXT_FIELDS.has(item.field) ? (
          <select value={clinicalContext[item.field] ?? ""} onChange={(event) => setClinicalContext((current) => ({ ...current, [item.field]: event.target.value }))}><option value="">No registrado</option><option value="true">Sí</option><option value="false">No</option></select>
        ) : (
          <input type={NUMERIC_CONTEXT_FIELDS.has(item.field) ? "number" : "text"} step="any" value={clinicalContext[item.field] ?? ""} onChange={(event) => setClinicalContext((current) => ({ ...current, [item.field]: event.target.value }))} placeholder="No registrado" />
        )}
      </label>)}
    </div>;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!minimumComplete) return;
    setSubmitting(true);
    setError("");
    const payload: ClinicalCaseInput = {
      case_code: caseCode.trim(),
      age: Number(age),
      sex,
      diagnoses: diagnoses.trim(),
      clinical_context: serializeContext(),
      is_simulated: true,
      medications: [...historyMedications, ...medications].map((item) => ({ ...item, duration: item.duration?.trim() || undefined })),
    };
    try {
      const created = await api.createCase(payload);
      const evaluation = await api.evaluateCase(created.id);
      onCompleted(created, evaluation);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo procesar el caso.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <ErrorNotice message={error} onClose={() => setError("")} />}
      <div className="intro-row"><span className="intro-icon">⚗</span><div><h1>Evaluar caso simulado</h1><p>Ingrese los datos clínicos para ejecutar el algoritmo de tamizaje de prescripciones potencialmente inapropiadas en el adulto mayor.</p></div></div>

      <div className="catalog-notice" role="status">
        <span>▤</span>
        <div><strong>Catálogo clínico controlado: {catalogSummary?.medication_count ?? 54} medicamentos</strong><p>Fuente: top_meds_list_beers_stopp_start_v3-20260730.xlsx. ATC y cuarto nivel farmacológico pendientes de validación clínica; no se infieren automáticamente.</p></div>
      </div>

      <section className="form-card">
        <h2>▣ Datos del caso</h2>
        <div className="case-grid">
          <label className="full-width">Historia para la simulación
            <select value={selectedPatientCode} disabled={historyLoading} onChange={(event) => selectPatientHistory(event.target.value)}>
              <option value="">Crear paciente nuevo sin historial</option>
              {pilotPatients.map((patient) => <option key={patient.patient_code} value={patient.patient_code}>{patient.patient_code} — {patient.age} años, {patient.sex} — {patient.max_simultaneous_top_medications} medicamentos activos</option>)}
            </select>
            <small className="field-help">Seleccione uno de los 10 pacientes pseudonimizados para cargar la información disponible y sumar medicamentos a su tratamiento activo.</small>
          </label>
          <label>Código del caso *<input value={caseCode} onChange={(event) => setCaseCode(event.target.value)} placeholder="Ej. CASO-2025-001" /></label>
          <label>Edad (años) *<div className="suffix-input"><input type="number" min="60" value={age} onChange={(event) => setAge(event.target.value)} placeholder="≥ 60" /><span>AÑOS</span></div></label>
          <label>Sexo *<select value={sex} onChange={(event) => setSex(event.target.value)}><option value="">Seleccione…</option><option>Masculino</option><option>Femenino</option></select></label>
          <label className="full-width">Diagnósticos / condiciones clínicas *<textarea value={diagnoses} onChange={(event) => setDiagnoses(event.target.value)} placeholder="Ingrese los diagnósticos o condiciones clínicas relevantes…" /></label>
        </div>
        {historyLoading && <p className="field-help">Cargando historia pseudonimizada…</p>}
        {historyNotice && <div className="catalog-notice" role="status"><span>ⓘ</span><div><strong>Historia cargada para simulación</strong><p>{historyNotice}</p></div></div>}
      </section>

      <section className="form-card medication-card">
        <div className="card-heading"><h2>▤ Medicamentos activos</h2><button type="button" className="small-primary" onClick={() => setMedications((current) => [...current, { ...EMPTY_MEDICATION }])}>＋ Agregar</button></div>
        <div className="medication-list">
          {medications.map((medication, index) => (
            <div className="medication-row" key={index}>
              <label>Medicamento del catálogo *<select value={medication.entered_name} onChange={(event) => selectCatalogMedication(index, event.target.value)}><option value="">Seleccione…</option>{!catalogMedications.some((item) => item.medication === medication.entered_name) && medication.entered_name && <option value={medication.entered_name}>{medication.entered_name} (historia cargada)</option>}{catalogMedications.map((item) => <option key={item.order} value={item.medication}>{item.medication}</option>)}</select></label>
              <label>Nombre normalizado<input readOnly value={medication.normalized_active_ingredient} placeholder="Se completa desde el catálogo" /></label>
              <label>Dosis<input value={medication.dose} onChange={(event) => updateMedication(index, "dose", event.target.value)} placeholder="10" /></label>
              <label>Unidad<select value={medication.dose_unit} onChange={(event) => updateMedication(index, "dose_unit", event.target.value)}>{medication.dose_unit === "no estructurada" && <option>no estructurada</option>}<option>mg</option><option>mcg</option><option>g</option><option>mL</option></select></label>
              <label>Frecuencia<select value={medication.frequency} onChange={(event) => updateMedication(index, "frequency", event.target.value)}>{medication.frequency === "no estructurada" && <option>no estructurada</option>}<option>C/24h</option><option>C/12h</option><option>C/8h</option><option>Según necesidad</option></select></label>
              <label>Vía<select value={medication.route} onChange={(event) => updateMedication(index, "route", event.target.value)}>{medication.route === "no estructurada" && <option>no estructurada</option>}<option>Oral</option><option>IV</option><option>SC</option><option>IM</option><option>Tópica</option></select></label>
              <label>Duración (opcional)<input value={medication.duration ?? ""} onChange={(event) => updateMedication(index, "duration", event.target.value)} placeholder="Ej. 30 días" /></label>
              <button type="button" className="delete-button" aria-label={`Eliminar medicamento ${index + 1}`} disabled={medications.length === 1} onClick={() => setMedications((current) => current.filter((_, position) => position !== index))}>⌫</button>
            </div>
          ))}
        </div>
        <p className="field-help">ⓘ Las pruebas de esta versión están restringidas al catálogo de 54 medicamentos validado por el equipo clínico. Si registra duración, use un número de días (ej. “120 días”) para que el backend la reciba como dato estructurado.</p>
      </section>

      {selectedPatientCode && historyMedications.length > 0 && <details className="history-medications">
        <summary>Medicamentos en uso ({historyMedications.length})</summary>
        <p>Medicamentos activos registrados en la historia pseudonimizada. Se incluyen en la evaluación junto con los medicamentos nuevos de arriba.</p>
        <ul>{historyMedications.map((medication, index) => <li key={`${medication.entered_name}-${index}`}><strong>{medication.entered_name}</strong><span>{medication.normalized_active_ingredient}{medication.duration ? ` · ${medication.duration}` : " · duración no estructurada"}</span></li>)}</ul>
      </details>}

      <section className="context-card">
        <button type="button" className="context-toggle" onClick={() => setContextOpen((value) => !value)} aria-expanded={contextOpen}>
          <span className="context-icon">♨</span><span><strong>Contexto clínico (opcional)</strong><small>Valores de laboratorio y condiciones específicas del paciente.</small></span><em>Recomendado para STOPP/START</em><b>{contextOpen ? "⌃" : "⌄"}</b>
        </button>
        {contextOpen && <div className="context-groups">
          {requiredContext.length === 0 && <p>Cargando campos requeridos desde el catálogo clínico…</p>}
          {requiredContext.length > 0 && <>
            <details className="context-group" open={recordedContext.length > 0}>
              <summary>Exámenes y datos clínicos realizados ({recordedContext.length})</summary>
              {recordedContext.length ? renderContextFields(recordedContext) : <p>No hay exámenes o datos clínicos registrados en la historia cargada.</p>}
            </details>
            <details className="context-group">
              <summary>Exámenes y datos clínicos no realizados / no registrados ({unrecordedContext.length})</summary>
              {unrecordedContext.length ? renderContextFields(unrecordedContext) : <p>Todos los campos disponibles tienen un valor registrado.</p>}
            </details>
          </>}
        </div>}
      </section>

      <div className="submit-bar"><span className={minimumComplete ? "complete" : "incomplete"}>{minimumComplete ? "✓ Datos mínimos completos" : "Complete los campos obligatorios"}</span><button className="primary-button" disabled={!minimumComplete || submitting}>{submitting ? "Procesando tamizaje…" : "▣ Crear caso y ejecutar tamizaje"}</button></div>
    </form>
  );
}

function DetailDrawer({ criterion, alert, onClose }: { criterion: CriterionResult; alert?: AlertResult; onClose: () => void }) {
  return <div className="drawer-layer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
    <button className="drawer-backdrop" onClick={onClose} aria-label="Cerrar detalle" />
    <aside className="detail-drawer">
      <header><div><span className={`status-dot ${criterion.status}`} /><h2 id="drawer-title">Detalle del criterio {criterion.criterion_code}</h2></div><button onClick={onClose} aria-label="Cerrar">×</button></header>
      <div className="drawer-content">
        <section><span className="drawer-label">Estado</span><span className={`status-pill ${criterion.status}`}>{statusLabel(criterion.status)}</span></section>
        <section><span className="drawer-label">Criterio</span><p>{criterion.statement}</p></section>
        <section><span className="drawer-label">Medicamentos implicados</span><p>{criterion.implicated_medications.length ? criterion.implicated_medications.join(", ") : "Ninguno registrado"}</p></section>
        <section><span className="drawer-label">Datos faltantes</span>{criterion.missing_data.length ? <ul>{criterion.missing_data.map((item, index) => <li key={index}>{String(item.label ?? item.field ?? JSON.stringify(item))}</li>)}</ul> : <p>No se reportaron datos faltantes.</p>}</section>
        {(criterion.lab_evidence?.length ?? 0) > 0 && <section><span className="drawer-label">Exámenes usados por el backend</span><ul>{criterion.lab_evidence.map((item) => <li key={`${item.field}-${item.source_row_sha256}`}><b>{labFieldLabel(item.field)}:</b> {labValueLabel(item)}; {formatDate(item.result_date)}; código ESSI {item.exam_code}; {item.applied ? "aplicado" : "no aplicado (prioridad al contexto manual)"}.</li>)}</ul></section>}
        {criterion.diagnosis_evidence.length > 0 && <section><span className="drawer-label">Evidencia CIE-10</span><ul>{criterion.diagnosis_evidence.map((item, index) => <li key={`${item.field ?? "cie"}-${index}`}><b>{item.label ?? item.field ?? "Contexto clínico"}:</b> {item.matched_codes?.map((code) => code.code).filter(Boolean).join(", ") || "evidencia documentada"}.</li>)}</ul></section>}
        {criterion.protective_evidence.length > 0 && <section><span className="drawer-label">Protectores identificados</span><ul>{criterion.protective_evidence.map((item, index) => <li key={`${item.field ?? item.role ?? "protector"}-${index}`}>{item.label ?? item.field ?? item.role ?? "Protector documentado"}</li>)}</ul></section>}
        {criterion.exception_reason && <section><span className="drawer-label">Excepción / mitigación</span><p>{criterion.exception_reason}</p></section>}
        {criterion.recommended_actions.length > 0 && <section><span className="drawer-label">Acciones sugeridas</span><ul>{criterion.recommended_actions.map((item, index) => <li key={index}>{item}</li>)}</ul></section>}
        <details className="detail-more"><summary>Ver más</summary><div>
          <section><span className="drawer-label">Justificación de la evaluación</span><p>{alert?.justification || criterion.reason || "Sin detalle adicional."}</p></section>
          <section><span className="drawer-label">Fuente</span><p>{alert?.source || criterion.source_location || "No consignada"}</p></section>
          <section><span className="drawer-label">Versión</span><p>{alert?.rule_version || criterion.catalog_version}</p></section>
          {criterion.triggering_evidence.length > 0 && <section><span className="drawer-label">Evidencia activadora</span><ul>{criterion.triggering_evidence.map((item, index) => <li key={`${item.field ?? item.role ?? "trigger"}-${index}`}>{item.label ?? item.field ?? item.role ?? "Condición evaluada"}: {String(item.value ?? "documentada")}</li>)}</ul></section>}
          {criterion.medication_coverage_note && <section><span className="drawer-label">Cobertura farmacológica</span><p>{criterion.medication_coverage_note}</p></section>}
        </div></details>
      </div>
      <footer><button className="secondary-button" onClick={onClose}>Cerrar</button></footer>
    </aside>
  </div>;
}

function DDInterDetailDrawer({ alert, onClose }: { alert: AlertResult; onClose: () => void }) {
  const level = ddinterLevel(alert);
  const catalogIds = traceStringList(alert, "catalog_ids");
  const catalogFiles = traceStringList(alert, "catalog_files");

  return <div className="drawer-layer" role="dialog" aria-modal="true" aria-labelledby="ddinter-drawer-title">
    <button className="drawer-backdrop" onClick={onClose} aria-label="Cerrar detalle" />
    <aside className="detail-drawer">
      <header><div><span className={`status-dot ddinter-${level.toLowerCase()}`} /><h2 id="ddinter-drawer-title">Detalle de interacción DDInter</h2></div><button onClick={onClose} aria-label="Cerrar">×</button></header>
      <div className="drawer-content">
        <section><span className="drawer-label">Nivel DDInter</span><span className={`ddinter-level ddinter-${level.toLowerCase()}`}>{ddinterLevelLabel(level)}</span></section>
        <section><span className="drawer-label">Código de interacción</span><p><code>{alert.rule_code}</code></p></section>
        <section><span className="drawer-label">Medicamentos implicados</span><p>{alert.implicated_medications.join(", ") || "No consignados"}</p></section>
        <section><span className="drawer-label">Hallazgo</span><p>{alert.problem_identified}</p></section>
        <section><span className="drawer-label">Orientación del catálogo</span><p>{alert.recommendation}</p></section>
        <section><span className="drawer-label">Justificación</span><p>{alert.justification}</p></section>
        <section><span className="drawer-label">Fuente</span><p>{alert.source}</p></section>
        <section><span className="drawer-label">Versión</span><p>{alert.rule_version}</p></section>
        <section><span className="drawer-label">Identificadores DDInter</span><p>{catalogIds.length ? catalogIds.join(", ") : "No informados"}</p></section>
        <section><span className="drawer-label">Archivos de catálogo consultados</span><p>{catalogFiles.length ? catalogFiles.join(", ") : "No informados"}</p></section>
        <section><span className="drawer-label">Origen del hallazgo</span><p>{alert.is_demo ? "Prueba técnica del backend" : "Catálogo local DDInter"}</p></section>
      </div>
      <footer><button className="secondary-button" onClick={onClose}>Cerrar</button></footer>
    </aside>
  </div>;
}

function ResultsPage({ clinicalCase, evaluation, dataAvailability }: { clinicalCase: ClinicalCase; evaluation: EvaluationExecution; dataAvailability?: PilotEvaluationResponse["data_availability"] }) {
  const [system, setSystem] = useState<VisibleSystem>("beers");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | CriterionResult["status"]>("all");
  const [ddinterLevelFilter, setDdinterLevelFilter] = useState<"all" | DDInterLevel>("all");
  const [selected, setSelected] = useState<CriterionResult>();
  const [selectedInteraction, setSelectedInteraction] = useState<AlertResult>();

  const analysis = evaluation.analysis_results.find((item) => item.system === system);
  const visibleCriteria = (evaluation.clinical_findings ?? evaluation.criteria_report.filter((item) => item.status === "alert")).filter((item) => item.system === system);
  const ddinterAlerts = evaluation.alerts.filter((item) => item.analysis_system === "ddinter");
  const rows = visibleCriteria.filter((item) => {
    const haystack = `${item.criterion_code} ${item.statement} ${item.reason} ${item.implicated_medications.join(" ")}`.toLowerCase();
    return haystack.includes(query.toLowerCase()) && (statusFilter === "all" || item.status === statusFilter);
  });
  const interactionRows = ddinterAlerts.filter((item) => {
    const haystack = `${item.rule_code} ${item.problem_identified} ${item.justification} ${item.implicated_medications.join(" ")}`.toLowerCase();
    return haystack.includes(query.toLowerCase()) && (ddinterLevelFilter === "all" || ddinterLevel(item) === ddinterLevelFilter);
  });
  const selectedAlert = selected ? evaluation.alerts.find((item) => item.analysis_system === selected.system && item.rule_code === selected.criterion_code) : undefined;

  function selectSystem(nextSystem: VisibleSystem) {
    setSystem(nextSystem);
    setQuery("");
    setStatusFilter("all");
    setDdinterLevelFilter("all");
    setSelected(undefined);
    setSelectedInteraction(undefined);
  }

  return <section>
    <div className="result-summary">
      <div><h1>Caso <span>{clinicalCase.case_code}</span></h1><p>{clinicalCase.age} años, {sexLabel(clinicalCase.sex)} <i>|</i> Diagnósticos registrados <i>|</i> {clinicalCase.medications.length} {clinicalCase.medications.length === 1 ? "medicamento" : "medicamentos"} <i>|</i> {formatDate(clinicalCase.created_at)}</p></div>
      {evaluation.processing_time_ms != null && <span className="processing-time">◴ Procesado en {(evaluation.processing_time_ms / 1000).toFixed(2)} s</span>}
    </div>
    {dataAvailability && <div className="pilot-period"><span><b>Medicamentos activos:</b> {formatDate(dataAvailability.medication_index_date)}</span><span><b>Observación clínica:</b> {formatDate(dataAvailability.clinical_observation_start_date)} — {formatDate(dataAvailability.clinical_observation_end_date)}</span></div>}
    <div className="info-banner"><span>ⓘ</span><div><strong>Resultado de tamizaje</strong><p>Este reporte es una herramienta de apoyo y <b>requiere revisión por un profesional de salud</b>. No constituye una recomendación clínica directa.</p></div></div>
    {dataAvailability && <LaboratoryEvidencePanel availability={dataAvailability} />}
    <div className="criteria-tabs"><button className={system === "beers" ? "active" : ""} onClick={() => selectSystem("beers")}>Criterios Beers</button><button className={system === "stopp_start" ? "active" : ""} onClick={() => selectSystem("stopp_start")}>Criterios STOPP/START</button><button className={system === "ddinter" ? "active" : ""} onClick={() => selectSystem("ddinter")}>Interacciones DDInter</button></div>
    {system === "ddinter" ? <div className="ddinter-overview">
      <div><strong className="metric-alert">{analysis?.alert_count ?? 0}</strong><span>Interacciones detectadas</span></div>
      <div><strong>DDInter local</strong><span>{analysis?.catalog ?? "Catálogo no informado"}</span></div>
      <div><strong>Coincidencia</strong><span>Exacta o alias provisional</span></div>
    </div> : <div className="metric-grid">
      <div><strong className="metric-alert">{analysis?.alert_count ?? 0}</strong><span>Alertas</span></div>
      <div><strong className="metric-primary">{analysis?.evaluated_count ?? 0}</strong><span>Evaluados</span></div>
      <div><strong>{analysis?.not_evaluable_count ?? 0}</strong><span>Requieren información adicional</span></div>
      <div><strong className="metric-manual">{analysis?.manual_review_count ?? 0}</strong><span>Revisión manual</span></div>
    </div>}
    {system === "beers" && clinicalCase.age < 65 && <div className="method-note">ⓘ En pacientes de 60 a 64 años, la aplicación de Beers corresponde a una adaptación metodológica del piloto; el criterio fue diseñado para población de 65 años o más.</div>}
    {system === "stopp_start" && <div className="method-note">▧ Los resultados requieren interpretación clínica y no reemplazan el juicio profesional.</div>}
    {system === "ddinter" && <div className="method-note">ⓘ {analysis?.note ?? "El resultado DDInter se reporta según el catálogo local configurado en el backend."}</div>}
    {system === "ddinter" ? <div className="results-card">
      <div className="results-toolbar"><div><strong>Interacciones farmacológicas</strong><span>{ddinterAlerts.length} hallazgos</span></div><div><label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filtrar…" /></label><select aria-label="Filtrar por nivel DDInter" value={ddinterLevelFilter} onChange={(event) => setDdinterLevelFilter(event.target.value as typeof ddinterLevelFilter)}><option value="all">Todos los niveles</option><option value="MAJOR">Major</option><option value="MODERATE">Moderate</option><option value="MINOR">Minor</option><option value="UNKNOWN">Unknown</option></select></div></div>
      <div className="table-scroll"><table className="results-table"><thead><tr><th>Nivel DDInter</th><th>Código</th><th>Medicamentos implicados</th><th>Hallazgo</th><th>Fuente / trazabilidad</th><th>Acción</th></tr></thead><tbody>
        {interactionRows.map((alert) => {
          const level = ddinterLevel(alert);
          return <tr key={alert.id}>
            <td><span className={`ddinter-level ddinter-${level.toLowerCase()}`}>{ddinterLevelLabel(level)}</span></td>
            <td><code>{alert.rule_code}</code></td>
            <td>{alert.implicated_medications.join(", ")}</td>
            <td><span>{alert.problem_identified}</span>{alert.is_demo && <b className="technical-label">Prueba técnica</b>}</td>
            <td><span>{alert.source}</span><small>{alert.rule_version}</small></td>
            <td><button className="outline-button" onClick={() => setSelectedInteraction(alert)}>Ver detalle</button></td>
          </tr>;
        })}
      </tbody></table>{interactionRows.length === 0 && <div className="empty-state">No se detectaron interacciones DDInter para los medicamentos evaluados.</div>}</div>
      <div className="table-footer">Mostrando {interactionRows.length} de {ddinterAlerts.length} hallazgos</div>
    </div> : <div className="results-card">
      <div className="results-toolbar"><div><strong>Hallazgos clínicos</strong><span>{visibleCriteria.length} alertas confirmadas</span></div><div><label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filtrar…" /></label></div></div>
      <div className="table-scroll"><table className="results-table"><thead><tr><th>Gravedad</th><th>Código</th><th>Medicamento(s)</th><th>Estado</th><th>Justificación / Datos faltantes</th><th>Acción</th></tr></thead><tbody>
        {rows.map((criterion) => {
          const alert = evaluation.alerts.find((item) => item.analysis_system === criterion.system && item.rule_code === criterion.criterion_code);
          const explanation = criterion.missing_data.length ? `Dato faltante: ${criterion.missing_data.map((item) => item.label ?? item.field).join(", ")}` : alert?.justification || criterion.reason;
          return <tr key={`${criterion.system}-${criterion.criterion_code}`} className={criterion.status === "no_alert" ? "no-alert-row" : ""}>
            <td><span className={`severity-bar ${criterion.status}`} title={statusLabel(criterion.status)} /></td>
            <td><code>{criterion.criterion_code}</code></td>
            <td>{criterion.implicated_medications.length ? criterion.implicated_medications.join(", ") : "—"}</td>
            <td><span className={`status-pill ${criterion.status}`}>{statusLabel(criterion.status)}</span></td>
            <td>{criterion.missing_data.length > 0 && <b className="missing-label">⚠ Dato faltante</b>}<span>{explanation || "Evaluación completada."}</span></td>
            <td><button className="outline-button" onClick={() => setSelected(criterion)}>Ver detalle</button></td>
          </tr>;
        })}
      </tbody></table>{rows.length === 0 && <div className="empty-state">No hay resultados para los filtros seleccionados.</div>}</div>
      <div className="table-footer">Mostrando {rows.length} de {visibleCriteria.length} registros</div>
    </div>}
    {system !== "ddinter" && <details className="full-analysis"><summary>Ver más: análisis completo</summary><div className="full-analysis-content"><p><b>Requieren información adicional:</b> {(evaluation.data_gaps ?? []).filter((item) => item.system === system).length}. <b>Revisión manual:</b> {(evaluation.manual_review_findings ?? []).filter((item) => item.system === system).length}.</p><div className="table-scroll"><table><thead><tr><th>Código</th><th>Estado</th><th>Motivo</th><th>Acción</th></tr></thead><tbody>{evaluation.criteria_report.filter((item) => item.system === system).map((item) => <tr key={`technical-${item.system}-${item.criterion_code}`}><td><code>{item.criterion_code}</code></td><td><span className={`status-pill ${item.status}`}>{statusLabel(item.status)}</span></td><td>{item.reason}</td><td><button className="outline-button" onClick={() => setSelected(item)}>Ver detalle</button></td></tr>)}</tbody></table></div></div></details>}
    {selected && <DetailDrawer criterion={selected} alert={selectedAlert} onClose={() => setSelected(undefined)} />}
    {selectedInteraction && <DDInterDetailDrawer alert={selectedInteraction} onClose={() => setSelectedInteraction(undefined)} />}
  </section>;
}

function LaboratoryEvidencePanel({ availability }: { availability: PilotEvaluationResponse["data_availability"] }) {
  const evidence = availability.mapped_lab_fields ?? [];
  const diagnoses = availability.mapped_diagnosis_fields ?? [];
  return <>
  <section className="laboratory-panel" aria-label="Exámenes mapeados desde la muestra piloto">
    <div className="laboratory-heading"><div><h2>Exámenes disponibles para la evaluación</h2><p>Resultados de la muestra pseudonimizada, aceptados con fecha igual o anterior a la fecha índice.</p></div><span>{availability.lab_lookback_days} días de ventana</span></div>
    {evidence.length ? <div className="laboratory-grid">{evidence.map((item) => <article key={`${item.field}-${item.source_row_sha256}`} className={item.applied ? "lab-evidence applied" : "lab-evidence overridden"}>
      <strong>{labFieldLabel(item.field)}</strong>
      <b>{labValueLabel(item)}</b>
      <p>{formatDate(item.result_date)} · {item.age_days_at_index} días antes de la fecha índice</p>
      <small>Cód. ESSI {item.exam_code} · {item.applied ? "Aplicado" : "No aplicado: prioridad a dato manual"}</small>
      {item.temporal_relation_to_medication_index === "after_index" && item.used_under_pilot_full_year_rule && <em>Evidencia posterior a la fecha índice, considerada por la regla anual del piloto 2025.</em>}
      {item.quality_flags.length > 0 && <em>{item.quality_flags.join(", ")}</em>}
    </article>)}</div> : <div className="lab-empty">No se aplicaron exámenes aceptables para esta evaluación. Esto no significa que el paciente no tenga resultados; puede deberse a fecha, unidad, valor o mapeo no aceptados.</div>}
    <div className="laboratory-footnotes"><span>Filas relevantes rechazadas: {availability.relevant_lab_rows_rejected}</span><span>Resultados futuros excluidos: {availability.future_relevant_lab_rows_excluded}</span>{availability.lab_mapping_warnings.map((warning) => <span key={warning}>ⓘ {warning}</span>)}</div>
  </section>
  <section className="laboratory-panel" aria-label="Evidencia CIE-10 de la muestra piloto">
    <div className="laboratory-heading"><div><h2>Evidencia clínica CIE-10</h2><p>Se utiliza únicamente evidencia positiva documentada antes o en la fecha índice; la ausencia de un código no descarta una condición.</p></div><span>{availability.diagnosis_rows_considered} registros</span></div>
    {diagnoses.length ? <div className="laboratory-grid">{diagnoses.map((item) => <article key={`${item.field}-${item.first_attention_date}`} className={item.applied ? "lab-evidence applied" : "lab-evidence overridden"}>
      <strong>{item.label}</strong><b>{item.applied ? "Evidencia aplicada" : "Prioridad a dato manual"}</b>
      <p>{item.matched_codes.map((code) => code.code).join(", ")} · {formatDate(item.last_attention_date)}</p>
      <small>{item.source_rows_count} atenciones · {item.satisfies_context_field ? "Aporta al campo clínico" : "Requiere contexto clínico adicional"}</small>
      {item.temporal_relation_to_medication_index === "after_index" && item.used_under_pilot_full_year_rule && <em>Evidencia posterior a la fecha índice, considerada por la regla anual del piloto 2025.</em>}
      {item.quality_flags.length > 0 && <em>{item.quality_flags.join(", ")}</em>}
    </article>)}</div> : <div className="lab-empty">No se identificó evidencia CIE-10 mapeada para esta fecha índice. Esto no significa ausencia de enfermedad.</div>}
    <div className="laboratory-footnotes"><span>Códigos CIE-10 distintos: {availability.distinct_diagnosis_codes}</span><span>Registros futuros excluidos: {availability.future_diagnosis_rows_excluded}</span>{availability.diagnosis_mapping_warnings.map((warning) => <span key={warning}>ⓘ {warning}</span>)}</div>
  </section>
  {availability.medication_catalog_classification.length > 0 && <section className="laboratory-panel" aria-label="Medicamentos activos clasificados"><div className="laboratory-heading"><div><h2>Medicamentos activos en la fecha índice</h2><p>Clasificación del catálogo V1 para la presentación ESSI registrada.</p></div></div><div className="table-scroll"><table><thead><tr><th>Presentación ESSI</th><th>Grupo farmacológico</th><th>Beers</th><th>STOPP/START</th></tr></thead><tbody>{availability.medication_catalog_classification.map((item, index) => <tr key={`${item.essi_presentation}-${index}`}><td><b>{item.essi_presentation}</b></td><td>{item.pharmacologic_group ?? "No clasificado"}</td><td>{item.beers_codes.join(", ") || "—"}</td><td>{[...item.stopp_codes, ...item.start_codes].join(", ") || "—"}</td></tr>)}</tbody></table></div></section>}
  </>;
}

export default function App() {
  const [page, setPage] = useState<Page>("cases");
  const [clinicalCase, setClinicalCase] = useState<ClinicalCase>();
  const [evaluation, setEvaluation] = useState<EvaluationExecution>();
  const [dataAvailability, setDataAvailability] = useState<PilotEvaluationResponse["data_availability"]>();
  const [error, setError] = useState("");

  async function reviewCase(item: ClinicalCaseSummary | ClinicalCase) {
    setError("");
    try {
      const fullCase = "medications" in item ? item : await api.getCase(item.id);
      const pilotCached = sessionStorage.getItem(`sigram-pilot-evaluation-${fullCase.id}`);
      const cached = sessionStorage.getItem(`sigram-evaluation-${fullCase.id}`);
      let result: EvaluationExecution;
      if (pilotCached) {
        const pilotResponse = JSON.parse(pilotCached) as PilotEvaluationResponse;
        result = pilotResponse.evaluation;
        setDataAvailability(pilotResponse.data_availability);
      } else if (cached) {
        result = JSON.parse(cached) as EvaluationExecution;
        setDataAvailability(undefined);
      }
      else {
        try { result = await api.getLatestResults(fullCase.id); }
        catch { result = await api.evaluateCase(fullCase.id); }
        setDataAvailability(undefined);
      }
      setClinicalCase(fullCase);
      setEvaluation(result);
      setPage("results");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo abrir el caso.");
    }
  }

  function completeCase(created: ClinicalCase, result: EvaluationExecution) {
    setClinicalCase(created);
    setEvaluation(result);
    setDataAvailability(undefined);
    setPage("results");
  }

  function completePilotCase(response: PilotEvaluationResponse) {
    setClinicalCase(response.case);
    setEvaluation(response.evaluation);
    setDataAvailability(response.data_availability);
    setPage("results");
  }

  return <Shell page={page} onNavigate={setPage}>
    {error && <ErrorNotice message={error} onClose={() => setError("")} />}
    {page === "cases" && <CasesPage onNew={() => setPage("new")} onPilotReview={completePilotCase} />}
    {page === "new" && <NewCasePage onCompleted={completeCase} />}
    {page === "history" && <HistoryPage onReview={reviewCase} />}
    {page === "research" && <ResearchDataPage />}
    {page === "results" && clinicalCase && evaluation && <ResultsPage clinicalCase={clinicalCase} evaluation={evaluation} dataAvailability={dataAvailability} />}
  </Shell>;
}
