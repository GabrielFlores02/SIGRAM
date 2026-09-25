import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type {
  AnalysisSystem,
  AlertResult,
  CatalogCriterion,
  CatalogMedication,
  DoctorReviewDetail,
  CatalogSummary,
  ClinicalCase,
  ClinicalCaseInput,
  ClinicalCaseSummary,
  CriterionResult,
  EvaluationExecution,
  LabEvidence,
  MedicationInput,
  PilotCasePrefill,
  PilotEvaluationResponse,
  PilotPatient,
  PilotResearchData,
  RequiredData,
} from "./types";

type Page = "cases" | "new" | "new-minimal" | "history" | "research" | "results";
type DDInterLevel = "MAJOR" | "MODERATE" | "MINOR" | "UNKNOWN" | "UNSPECIFIED";
type Cie10Option = { code: string; description: string };

const EMPTY_MEDICATION: MedicationInput = {
  entered_name: "",
  normalized_active_ingredient: "",
  dose: "",
  dose_unit: "mg",
  frequency: "C/24h",
  duration: "",
  route: "Oral",
};

const EMPTY_MINIMAL_MEDICATION: MedicationInput = {
  entered_name: "",
  normalized_active_ingredient: "",
  dose: "no estructurada",
  dose_unit: "no estructurada",
  frequency: "no estructurada",
  route: "no estructurada",
};

const ESSI_SIMULATOR_CODE = "SIM-ESSI-001";

function normalizeClinicalSearch(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es").trim();
}

const NUMERIC_CONTEXT_FIELDS = new Set([
  "egfr_ml_min_1_73m2",
  "creatinine_clearance_ml_min",
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
  "weight_kg",
  "height_cm",
  "serum_creatinine_mg_dl",
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
  "chronic_kidney_disease_stage_3a_or_higher",
  "opioid_regular_use",
]);

function formatDate(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
    new Date(value),
  );
}

function formatCalendarDate(value?: string) {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : formatDate(value);
}

function sexLabel(value: string) {
  const normalized = value.toLowerCase();
  if (normalized.startsWith("f")) return "F";
  if (normalized.startsWith("m")) return "M";
  return value;
}

function statusLabel(status: CriterionResult["status"]) {
  return {
    alert: "Criterio activado",
    activated: "Criterio activado",
    no_alert: "Sin hallazgo en los datos observados",
    not_evaluable: "Requiere información adicional",
    manual_review: "Requiere revisión clínica",
    out_of_scope: "Fuera del ámbito AGS Beers 2023",
    supporting_classification: "Clasificación de apoyo",
    not_applicable: "Criterio no aplicable",
  }[status];
}

function beersRecommendationLabel(criterion: CriterionResult) {
  const labels: Record<string, string> = {
    avoid: "Evitar",
    use_with_caution: "Usar con precaución",
    reduce_dose: "Reducir dosis",
    monitor: "Monitorizar",
    conditional: "Condicional",
    classification_only: "Anticolinérgico fuerte",
  };
  return labels[criterion.recommendation_type ?? ""] ?? criterion.recommendation_text ?? "Pendiente de validación clínica";
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

function doctorReviewDetails(alert: AlertResult): DoctorReviewDetail[] {
  const details = alert.trace_data.doctor_review_details;
  if (!Array.isArray(details)) return [];
  return details.filter((item): item is DoctorReviewDetail => Boolean(
    item && typeof item === "object" && typeof (item as DoctorReviewDetail).description === "string",
  ));
}

function criterionSourceDetails(criterion: CriterionResult) {
  return criterion.review_details ?? [];
}

function criterionDisplayCode(criterion: CriterionResult) {
  const details = criterionSourceDetails(criterion);
  if (!details.length) return criterion.criterion_code;
  return details.map((detail) => `${detail.source_system.toUpperCase()}-${String(detail.source_code).padStart(3, "0")}`).join(" / ");
}

function criterionSourceDescription(criterion: CriterionResult) {
  const descriptions = Array.from(new Set(criterionSourceDetails(criterion).map((detail) => detail.description).filter(Boolean)));
  return descriptions.join("\n\n") || criterion.statement;
}

const CLINICAL_CONTEXT_LABELS: Record<string, string> = {
  egfr_ml_min_1_73m2: "TFGe / TFG (reportada o calculada)",
  creatinine_clearance_ml_min: "Depuración de creatinina (CrCl)",
  serum_creatinine_mg_dl: "Creatinina sérica",
  serum_creatinine_date: "Fecha de creatinina",
  medication_duration_days: "Duración estructurada del tratamiento",
  daily_dose_mg: "Dosis diaria",
  indication_confirmed: "Indicación clínica confirmada",
  gastroprotection: "Gastroprotección",
  heart_failure_status: "Estado de insuficiencia cardiaca",
  cognitive_impairment: "Deterioro cognitivo",
  falls_history: "Antecedente de caídas",
  peptic_ulcer_history: "Antecedente de úlcera péptica",
  bleeding_risk: "Riesgo de sangrado",
};

function clinicalFieldLabel(field: string) {
  return CLINICAL_CONTEXT_LABELS[field] ?? field.replace(/_/g, " ");
}

function recordedValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "No registrado";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (Array.isArray(value)) return value.length ? value.map((item) => String(item)).join(", ") : "No registrado";
  if (typeof value === "object") return "Registrado";
  return String(value);
}

function medicationNamesMatch(left: string, right: string) {
  const a = normalizeClinicalSearch(left).replace(/[^a-z0-9]/g, "");
  const b = normalizeClinicalSearch(right).replace(/[^a-z0-9]/g, "");
  return Boolean(a && b && (a.includes(b) || b.includes(a)));
}

function sortCatalogMedications(rows: CatalogMedication[]) {
  const unique = new Map<string, CatalogMedication>();
  rows.forEach((item) => {
    const key = normalizeClinicalSearch(item.medication).replace(/[^a-z0-9]+/g, "");
    if (!key) return;
    const existing = unique.get(key);
    if (!existing) {
      unique.set(key, { ...item });
      return;
    }
    const groups = new Set(
      [existing.pharmacologic_group, item.pharmacologic_group]
        .flatMap((value) => value.split(" | "))
        .map((value) => value.trim())
        .filter(Boolean),
    );
    unique.set(key, {
      ...existing,
      pharmacologic_group: [...groups].sort((left, right) => left.localeCompare(right, "es", { sensitivity: "base" })).join(" | "),
      beers_codes: [...new Set([...existing.beers_codes, ...item.beers_codes])],
      stopp_codes: [...new Set([...existing.stopp_codes, ...item.stopp_codes])],
      start_codes: [...new Set([...existing.start_codes, ...item.start_codes])],
      clinical_rules_validated: Boolean(existing.clinical_rules_validated || item.clinical_rules_validated),
      reference_group_only: Boolean(existing.reference_group_only && item.reference_group_only),
    });
  });
  return [...unique.values()].sort((left, right) => left.medication.localeCompare(right.medication, "es", { sensitivity: "base" }));
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
    "Direct TFG reported by ESSI has priority; when it is absent, SIGRAM may calculate eGFR from serum creatinine with CKD-EPI 2021.": "La TFG reportada directamente por ESSI tiene prioridad; si no existe, SIGRAM puede calcular TFGe desde creatinina sérica con CKD-EPI 2021.",
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
          <button className={page === "new-minimal" ? "active" : ""} onClick={() => onNavigate("new-minimal")}>Nuevo caso simple</button>
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

function InfoTip({ text }: { text: string }) {
  return <span className="info-tip" tabIndex={0} aria-label={`Información: ${text}`}>
    <span aria-hidden="true">i</span>
    <span className="info-tip-content" role="tooltip">{text}</span>
  </span>;
}

function CasesPage({ onNew, onPilotReview }: { onNew: () => void; onPilotReview: (response: PilotEvaluationResponse) => void }) {
  const [pilotPatients, setPilotPatients] = useState<PilotPatient[]>([]);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyCode, setBusyCode] = useState("");
  const [error, setError] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<PilotPatient>();

  useEffect(() => {
    api.listPopulationPatients(offset, 50, search)
      .then((page) => { setPilotPatients(page.items); setTotal(page.total); })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [offset, search]);

  const filteredPatients = pilotPatients;

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
          <span className="eyebrow">Cohorte Rebagliati 2025</span>
          <h1>Evaluación de prescripción en adultos mayores</h1>
          <p>Directorio paginado de 181,356 pacientes pseudonimizados. Los datos clínicos se consultan por paciente.</p>
        </div>
        <span className="pilot-badge">ⓘ Piloto de investigación</span>
      </div>

      <div className="toolbar-row">
        <span className="sample-label">{total.toLocaleString("es-PE")} pacientes · Rebagliati 2025</span>
        <div className="toolbar-actions">
          <label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { setSearch(query); setOffset(0); } }} placeholder="Buscar por código..." /></label>
          <button className="secondary-button" onClick={() => { setSearch(query); setOffset(0); }}>Buscar</button>
          <button className="primary-button" onClick={onNew}>＋ Nuevo caso simulado</button>
        </div>
      </div>

      <div className="table-card">
        {loading ? <div className="empty-state">Cargando muestra…</div> : (
          <div className="table-scroll"><table>
            <thead><tr><th>Código pseudonimizado</th><th>Paciente</th><th>Polifarmacia</th><th>Máx. simultáneos</th><th>Tamizaje Beers</th><th>Tamizaje DDInter</th><th>Acción</th></tr></thead>
            <tbody>{filteredPatients.map((patient) => (
              <tr key={patient.patient_code}>
                <td><span className="case-code">{patient.patient_code}</span></td>
                <td>{patient.age} años<br /><small>{patient.sex}</small></td>
                <td>{patient.polypharmacy_level ?? "No informado"}</td>
                <td>{patient.max_simultaneous_top_medications}</td>
                <td>{patient.beers_screening_flag ? "Posible exposición" : "Sin bandera"}</td>
                <td>{patient.ddinter_screening_flag ? "Posible interacción" : "Sin bandera"}</td>
                <td><div className="table-actions"><button className="link-button" disabled={busyCode === patient.patient_code} onClick={() => evaluateSample(patient)}>{busyCode === patient.patient_code ? "Evaluando…" : "Evaluar →"}</button><button className="secondary-link" disabled={busyCode === patient.patient_code} onClick={() => setSelectedPatient(patient)}>Contexto clínico</button></div></td>
              </tr>
            ))}</tbody>
          </table>{filteredPatients.length === 0 && <div className="empty-state">No hay registros para la búsqueda.</div>}</div>
        )}
      </div>
      <div className="table-footer">Mostrando {total ? offset + 1 : 0}–{Math.min(offset + pilotPatients.length, total)} de {total.toLocaleString("es-PE")} pacientes <span><button className="secondary-button" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</button> <button className="secondary-button" disabled={offset + pilotPatients.length >= total || loading} onClick={() => setOffset(offset + 50)}>Siguiente</button></span></div>
      {selectedPatient && <PilotContextDrawer patient={selectedPatient} onClose={() => setSelectedPatient(undefined)} onEvaluate={async (context) => { await evaluateSample(selectedPatient, context); setSelectedPatient(undefined); }} />}
    </section>
  );
}

function PilotContextDrawer({ patient, onClose, onEvaluate }: { patient: PilotPatient; onClose: () => void; onEvaluate: (context: Record<string, unknown>) => Promise<void> }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const fields = [
    ["egfr_ml_min_1_73m2", "TFGe / TFG (mL/min/1.73 m²)", "number"],
    ["creatinine_clearance_ml_min", "Depuración de creatinina - CrCl (mL/min)", "number"],
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
    if (values.chronic_kidney_disease_stage_3a_or_higher) context.chronic_kidney_disease_stage_3a_or_higher = values.chronic_kidney_disease_stage_3a_or_higher === "true";
    try { await onEvaluate(context); } finally { setSubmitting(false); }
  }
  return <div className="drawer-layer" role="dialog" aria-modal="true" aria-labelledby="pilot-context-title">
    <button className="drawer-backdrop" onClick={onClose} aria-label="Cerrar contexto clínico" />
    <aside className="detail-drawer pilot-context-drawer"><header><div><span className="status-dot" /><h2 id="pilot-context-title">Contexto clínico manual</h2></div><button onClick={onClose} aria-label="Cerrar">×</button></header>
      <form className="drawer-content" onSubmit={submit}><p className="drawer-intro">Paciente pseudonimizado <b>{patient.patient_code}</b>. Los valores ingresados aquí tienen prioridad sobre el laboratorio mapeado por el backend.</p><div className="drawer-form-grid">{fields.map(([field, label, type]) => <label key={field}>{label}<input type={type} step="any" value={values[field] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))} placeholder="No registrado" /></label>)}<label>T4 libre en rango de referencia<select value={values.free_t4_normal ?? ""} onChange={(event) => setValues((current) => ({ ...current, free_t4_normal: event.target.value }))}><option value="">No registrado</option><option value="true">Sí</option><option value="false">No</option></select></label><label>ERC estadio 3a o mayor confirmada<select value={values.chronic_kidney_disease_stage_3a_or_higher ?? ""} onChange={(event) => setValues((current) => ({ ...current, chronic_kidney_disease_stage_3a_or_higher: event.target.value }))}><option value="">No registrado</option><option value="true">Sí</option><option value="false">No</option></select></label></div><p className="field-help">Para B08, B19 y B20 ingrese CrCl documentada; SIGRAM no la calcula ni sustituye automáticamente por TFGe. Para B21, confirme ERC estadio 3a o mayor. Deje vacío lo no disponible.</p><footer><button type="button" className="secondary-button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting}>{submitting ? "Evaluando…" : "Evaluar con contexto"}</button></footer></form>
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
  const [cie10Options, setCie10Options] = useState<Cie10Option[]>([]);
  const [cie10Status, setCie10Status] = useState<"loading" | "ready" | "error">("loading");
  const [diagnosisMenuOpen, setDiagnosisMenuOpen] = useState(false);
  const [activeDiagnosisIndex, setActiveDiagnosisIndex] = useState(0);
  const diagnosisInputRef = useRef<HTMLTextAreaElement>(null);
  const [medications, setMedications] = useState<MedicationInput[]>([{ ...EMPTY_MEDICATION }]);
  const [criteria, setCriteria] = useState<CatalogCriterion[]>([]);
  const [catalogMedications, setCatalogMedications] = useState<CatalogMedication[]>([]);
  const [catalogSummary, setCatalogSummary] = useState<CatalogSummary>();
  const [pilotPatients, setPilotPatients] = useState<PilotPatient[]>([]);
  const [historySort, setHistorySort] = useState<"engine_alerts" | "alerts" | "patient_code">("engine_alerts");
  const [historyOptionsLoading, setHistoryOptionsLoading] = useState(false);
  const [selectedPatientCode, setSelectedPatientCode] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyNotice, setHistoryNotice] = useState("");
  const [simulationHistory, setSimulationHistory] = useState<Array<{ id: number; event_type: string; note: string; created_at: string; snapshot: Record<string, unknown> }>>([]);
  const [attentionNote, setAttentionNote] = useState("");
  const [historyMedications, setHistoryMedications] = useState<MedicationInput[]>([]);
  const [contextOpen, setContextOpen] = useState(false);
  const [clinicalContext, setClinicalContext] = useState<Record<string, string>>(Object.create(null));
  const [committedContextFields, setCommittedContextFields] = useState<Set<string>>(new Set());
  const recordedContextRef = useRef<HTMLDetailsElement>(null);
  const [weightKg, setWeightKg] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [serumCreatinineMgDl, setSerumCreatinineMgDl] = useState("");
  const [serumCreatinineDate, setSerumCreatinineDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.listCriteria(), api.listCatalogMedications(), api.getCatalogSummary()])
      .then(([criteriaRows, medicationRows, summary]) => {
        setCriteria(criteriaRows);
        setCatalogMedications(sortCatalogMedications(medicationRows));
        setCatalogSummary(summary);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${import.meta.env.BASE_URL}data/cie10_minsa_oficial.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
        return response.json() as Promise<Cie10Option[]>;
      })
      .then((rows) => {
        if (cancelled) return;
        setCie10Options(rows.filter((row) => typeof row?.code === "string" && typeof row?.description === "string"));
        setCie10Status("ready");
      })
      .catch(() => { if (!cancelled) setCie10Status("error"); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setHistoryOptionsLoading(true);
    api.listPilotPatients(historySort)
      .then(setPilotPatients)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setHistoryOptionsLoading(false));
  }, [historySort]);

  const requiredContext = useMemo(() => {
    const unique = new Map<string, RequiredData>();
    criteria.flatMap((criterion) => criterion.required_data).forEach((item) => unique.set(item.field, item));
    return [...unique.values()].sort((a, b) => a.label.localeCompare(b.label, "es"));
  }, [criteria]);

  const editableContext = requiredContext.filter((item) => ![
    "medication_duration_days",
    "creatinine_clearance_ml_min",
  ].includes(item.field));
  const recordedContext = editableContext.filter((item) =>
    (clinicalContext[item.field] ?? "") !== "" && committedContextFields.has(item.field)
  );
  const unrecordedContext = editableContext.filter((item) =>
    (clinicalContext[item.field] ?? "") === "" || !committedContextFields.has(item.field)
  );

  const diagnosisQuery = diagnoses.split(/\r?\n/).slice(-1)[0]?.trim() ?? "";
  const diagnosisSuggestions = useMemo(() => {
    const query = normalizeClinicalSearch(diagnosisQuery);
    if (query.length < 2) return [];
    const codeQuery = query.replace(/[^a-z0-9]/g, "");
    const ranked: Array<{ option: Cie10Option; rank: number }> = [];
    for (const option of cie10Options) {
      const code = option.code.toLocaleLowerCase("es");
      const description = normalizeClinicalSearch(option.description);
      let rank = -1;
      if (codeQuery && code === codeQuery) rank = 0;
      else if (codeQuery && code.startsWith(codeQuery)) rank = 1;
      else if (description.startsWith(query)) rank = 2;
      else if (description.split(/\s+/).some((word) => word.startsWith(query))) rank = 3;
      else if (description.includes(query)) rank = 4;
      if (rank >= 0) ranked.push({ option, rank });
    }
    return ranked
      .sort((left, right) => left.rank - right.rank || left.option.code.localeCompare(right.option.code, "es"))
      .slice(0, 10)
      .map((item) => item.option);
  }, [cie10Options, diagnosisQuery]);

  function selectDiagnosis(option: Cie10Option) {
    const lines = diagnoses.split(/\r?\n/);
    lines[lines.length - 1] = `${option.code} — ${option.description}`;
    setDiagnoses(`${lines.join("\n")}\n`);
    setDiagnosisMenuOpen(false);
    setActiveDiagnosisIndex(0);
    requestAnimationFrame(() => diagnosisInputRef.current?.focus());
  }

  function formatHistoricalDiagnoses(value: string) {
    const descriptionsByCode = new Map(
      cie10Options.map((option) => [option.code.replace(/[^a-z0-9]/gi, "").toUpperCase(), option.description.trim()])
    );
    return value
      .split(/[\r\n,;]+/)
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => {
        const match = entry.match(/^([A-Z]\d{2}(?:\.[A-Z0-9]{1,4}|\d{1,2})?)(?:\s*[—-]\s*(.+))?$/i);
        if (!match) return entry;
        const code = match[1].toUpperCase();
        const normalizedCode = code.replace(/[^A-Z0-9]/g, "");
        const fallbackDescription = normalizedCode.length === 3
          ? cie10Options.find((option) => option.code.replace(/[^a-z0-9]/gi, "").toUpperCase().startsWith(normalizedCode))?.description.trim()
          : undefined;
        const description = match[2]?.trim() || descriptionsByCode.get(normalizedCode) || fallbackDescription;
        return description ? `${code} — ${description}` : code;
      })
      .join("\n");
  }

  function handleDiagnosisKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (!diagnosisMenuOpen || diagnosisSuggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveDiagnosisIndex((current) => (current + 1) % diagnosisSuggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveDiagnosisIndex((current) => (current - 1 + diagnosisSuggestions.length) % diagnosisSuggestions.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectDiagnosis(diagnosisSuggestions[activeDiagnosisIndex] ?? diagnosisSuggestions[0]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setDiagnosisMenuOpen(false);
    }
  }

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
      normalized_active_ingredient: selected?.medication ?? value.trim(),
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
      setCommittedContextFields(new Set());
      setWeightKg("");
      setHeightCm("");
      setSerumCreatinineMgDl("");
      setSerumCreatinineDate("");
      setContextOpen(false);
      setHistoryNotice("");
      setSimulationHistory([]);
      setAttentionNote("");
      return;
    }

    setHistoryLoading(true);
    setHistoryNotice("");
    try {
      if (patientCode === ESSI_SIMULATOR_CODE) {
        const simulator = await api.getEssiSimulator();
        const loaded = simulator.case;
        setAge(String(loaded.age)); setSex(loaded.sex); setDiagnoses(formatHistoricalDiagnoses(loaded.diagnoses)); setCaseCode(loaded.case_code);
        setMedications(loaded.medications.map(({ id: _id, case_id: _caseId, created_at: _createdAt, ...medication }) => medication));
        const mappedContext: Record<string, string> = Object.create(null);
        for (const [field, value] of Object.entries(loaded.clinical_context)) {
          if (value === null || value === undefined || Array.isArray(value) || typeof value === "object") continue;
          mappedContext[field] = String(value);
        }
        setClinicalContext(mappedContext); setCommittedContextFields(new Set(Object.keys(mappedContext))); setWeightKg(mappedContext.weight_kg ?? ""); setHeightCm(mappedContext.height_cm ?? "");
        setSerumCreatinineMgDl(mappedContext.serum_creatinine_mg_dl ?? ""); setSerumCreatinineDate(mappedContext.serum_creatinine_date ?? "");
        setHistoryMedications([]); setSimulationHistory(simulator.history); setContextOpen(true);
        setHistoryNotice("Simulador ESSI cargado: esta copia conserva cada atención y su lista histórica de medicamentos. La cohorte piloto original no se modifica.");
        return;
      }
      const prefill = await api.getPilotCasePrefill(patientCode);
      setAge(String(prefill.age));
      setSex(prefill.sex);
      setDiagnoses(formatHistoricalDiagnoses(prefill.diagnoses));
      setCaseCode(patientCode);
      // La cohorte piloto se presenta como historia previa de solo lectura.
      // Las filas de arriba representan exclusivamente la nueva receta a simular.
      setMedications([{ ...EMPTY_MEDICATION }]);
      setHistoryMedications(prefill.medications);
      const mappedContext: Record<string, string> = Object.create(null);
      for (const [field, value] of Object.entries(prefill.clinical_context)) {
        if (value === null || value === undefined || Array.isArray(value) || typeof value === "object") continue;
        mappedContext[field] = String(value);
      }
      setClinicalContext(mappedContext);
      setCommittedContextFields(new Set(Object.keys(mappedContext)));
      setWeightKg(mappedContext.weight_kg ?? "");
      setHeightCm(mappedContext.height_cm ?? "");
      setSerumCreatinineMgDl(mappedContext.serum_creatinine_mg_dl ?? "");
      setSerumCreatinineDate(mappedContext.serum_creatinine_date ?? "");
      setContextOpen(true);
      setSimulationHistory([]);
      setHistoryNotice(`Historia pseudonimizada ${patientCode} cargada. Sus medicamentos activos se muestran abajo como “Medicamentos en uso”; agregue arriba la nueva receta para evaluar la polifarmacia. Al finalizar, los cambios se descartan.`);
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

  function updateTriage(field: "weight" | "height", value: string) {
    const nextWeight = field === "weight" ? value : weightKg;
    const nextHeight = field === "height" ? value : heightCm;
    if (field === "weight") setWeightKg(value); else setHeightCm(value);
    const kilograms = Number(nextWeight);
    const meters = Number(nextHeight) / 100;
    setClinicalContext((current) => ({
      ...current,
      weight_kg: field === "weight" ? value : current.weight_kg ?? "",
      height_cm: field === "height" ? value : current.height_cm ?? "",
      ...(kilograms > 0 && meters > 0 ? { bmi: (kilograms / (meters * meters)).toFixed(1) } : {}),
    }));
  }

  function updateSerumCreatinine(value: string) {
    setSerumCreatinineMgDl(value);
    setClinicalContext((current) => ({ ...current, serum_creatinine_mg_dl: value }));
  }

  function updateSerumCreatinineDate(value: string) {
    setSerumCreatinineDate(value);
    setClinicalContext((current) => ({ ...current, serum_creatinine_date: value }));
  }

  const estimatedCrCl = useMemo(() => {
    const years = Number(age);
    const weight = Number(weightKg);
    const creatinine = Number(serumCreatinineMgDl);
    if (!(years > 0 && weight > 0 && creatinine > 0) || !sex) return null;
    const base = ((140 - years) * weight) / (72 * creatinine);
    return (sex === "Femenino" ? base * 0.85 : base).toFixed(1);
  }, [age, sex, weightKg, serumCreatinineMgDl]);

  const estimatedEgfr = useMemo(() => {
    const years = Number(age);
    const creatinine = Number(serumCreatinineMgDl);
    if (!(years >= 18 && creatinine > 0) || !sex) return null;
    const female = sex === "Femenino";
    const kappa = female ? 0.7 : 0.9;
    const alpha = female ? -0.241 : -0.302;
    const ratio = creatinine / kappa;
    const estimate = 142 * Math.min(ratio, 1) ** alpha * Math.max(ratio, 1) ** -1.2 * 0.9938 ** years * (female ? 1.012 : 1);
    return estimate.toFixed(1);
  }, [age, sex, serumCreatinineMgDl]);

  function setContextValue(field: string, value: string, commit = false) {
    setClinicalContext((current) => ({ ...current, [field]: value }));
    if (!value) {
      setCommittedContextFields((current) => {
        const next = new Set(current);
        next.delete(field);
        return next;
      });
    } else if (commit) {
      setCommittedContextFields((current) => new Set(current).add(field));
    }
  }

  function commitContextField(field: string, value: string) {
    if (!value.trim()) return;
    setCommittedContextFields((current) => new Set(current).add(field));
    requestAnimationFrame(() => {
      if (recordedContextRef.current) {
        recordedContextRef.current.open = true;
        recordedContextRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  }

  function renderContextFields(items: RequiredData[]) {
    return <div className="context-grid">
      {items.map((item) => <label key={item.field}>{item.label}
        {BOOLEAN_CONTEXT_FIELDS.has(item.field) ? (
          <select value={clinicalContext[item.field] ?? ""} onChange={(event) => setContextValue(item.field, event.target.value, true)}><option value="">No registrado</option><option value="true">Sí</option><option value="false">No</option></select>
        ) : (
          <input type={NUMERIC_CONTEXT_FIELDS.has(item.field) ? "number" : "text"} step="any" value={clinicalContext[item.field] ?? ""} onChange={(event) => setContextValue(item.field, event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); commitContextField(item.field, event.currentTarget.value); } }} placeholder="No registrado" />
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
      if (selectedPatientCode === ESSI_SIMULATOR_CODE) {
        const simulator = await api.updateEssiSimulator({ ...payload, case_code: ESSI_SIMULATOR_CODE, note: attentionNote.trim() || "Atención ESSI simulada" });
        const evaluation = await api.evaluateCase(simulator.case.id);
        setSimulationHistory(simulator.history);
        onCompleted(simulator.case, evaluation);
      } else if (selectedPatientCode) {
        const preview = await api.previewCase(payload);
        onCompleted(preview.case, preview.evaluation);
      } else {
        const created = await api.createCase(payload);
        const evaluation = await api.evaluateCase(created.id);
        onCompleted(created, evaluation);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo procesar el caso.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <ErrorNotice message={error} onClose={() => setError("")} />}
      <div className="intro-row"><span className="intro-icon">⚗</span><div><h1 className="heading-with-info">Evaluar caso simulado <InfoTip text="Ingrese los datos clínicos para ejecutar el algoritmo de tamizaje de prescripciones potencialmente inapropiadas en el adulto mayor." /></h1></div></div>

      <div className="catalog-notice compact-notice" role="status">
        <span>▤</span>
        <div><strong className="heading-with-info">Catálogo farmacológico: {catalogSummary?.pharmacologic_group_medication_count ?? catalogMedications.length} medicamentos; {catalogSummary?.clinical_medication_count ?? 57} con reglas clínicas <InfoTip text="El listado incluye el catálogo disponible y suplementos clínicos revisados aunque no figuren en el stock institucional. También puede escribir un medicamento no listado; solo activará reglas cuando exista una asociación clínica validada." /></strong></div>
      </div>

      <section className="form-card">
        <h2>▣ Datos del caso</h2>
        <div className="case-grid">
          <div className="full-width history-selection-grid">
            <label><span className="label-with-info">Historia para la simulación <InfoTip text="Se muestran 50 historias pseudonimizadas según el orden elegido. SIM-ESSI-001 guarda versiones sin alterar la cohorte fuente." /></span>
              <select value={selectedPatientCode} disabled={historyLoading || historyOptionsLoading} onChange={(event) => selectPatientHistory(event.target.value)}>
                <option value="">Crear paciente nuevo sin historial</option>
                <optgroup label="Pacientes Rebagliati — simulación temporal (no guarda cambios)">
                  {pilotPatients.map((patient) => <option key={patient.patient_code} value={patient.patient_code}>{patient.patient_code} — {patient.age} años, {patient.sex} — {patient.max_simultaneous_top_medications} medicamentos simultáneos{patient.engine_alert_count != null ? ` — motor: ${patient.engine_alert_count} alertas (${patient.engine_beers_alert_count ?? 0} Beers + ${patient.engine_stopp_start_alert_count ?? 0} STOPP/START + ${patient.engine_ddinter_alert_count ?? 0} DDInter)` : patient.screening_alert_count != null ? ` — anual: ${patient.beers_screening_group_count ?? 0} grupos Beers + ${patient.ddinter_potential_count ?? 0} pares DDInter` : ""}</option>)}
                </optgroup>
                <optgroup label="Simulador longitudinal ESSI">
                  <option value={ESSI_SIMULATOR_CODE}>SIM-ESSI-001 — paciente editable con historia persistente</option>
                </optgroup>
              </select>
            </label>
            <label><span className="label-with-info">Orden de pacientes <InfoTip text="El orden recalcula Beers, STOPP/START y DDInter sobre los medicamentos simultáneos de los 200 pacientes con mayor carga anual. Es un priorizador de tamizaje; la evaluación completa puede variar al añadir contexto clínico." /></span>
              <select value={historySort} disabled={historyOptionsLoading} onChange={(event) => setHistorySort(event.target.value as typeof historySort)}>
                <option value="engine_alerts">Más alertas producidas por el motor</option>
                <option value="alerts">Mayor carga anual precalculada</option>
                <option value="patient_code">Código de paciente</option>
              </select>
            </label>
          </div>
          <label>Código del caso *<input value={caseCode} onChange={(event) => setCaseCode(event.target.value)} placeholder="Ej. CASO-2025-001" /></label>
          <label>Edad (años) *<div className="suffix-input"><input type="number" min="60" value={age} onChange={(event) => setAge(event.target.value)} placeholder="≥ 60" /><span>AÑOS</span></div></label>
          <label>Sexo *<select value={sex} onChange={(event) => setSex(event.target.value)}><option value="">Seleccione…</option><option>Masculino</option><option>Femenino</option></select></label>
          <div className="full-width diagnosis-field">
            <label htmlFor="case-diagnoses">Diagnósticos / condiciones clínicas *</label>
            <div className="cie10-combobox">
              <textarea
                ref={diagnosisInputRef}
                id="case-diagnoses"
                value={diagnoses}
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={diagnosisMenuOpen && diagnosisQuery.length >= 2}
                aria-controls="cie10-suggestions"
                aria-activedescendant={diagnosisSuggestions.length ? `cie10-option-${activeDiagnosisIndex}` : undefined}
                onFocus={() => setDiagnosisMenuOpen(true)}
                onBlur={() => setDiagnosisMenuOpen(false)}
                onChange={(event) => { setDiagnoses(event.target.value); setDiagnosisMenuOpen(true); setActiveDiagnosisIndex(0); }}
                onKeyDown={handleDiagnosisKeyDown}
                placeholder="Escriba un código o una descripción CIE-10…"
              />
              {diagnosisMenuOpen && diagnosisQuery.length >= 2 && <div id="cie10-suggestions" className="cie10-suggestions" role="listbox" aria-label="Coincidencias CIE-10">
                {cie10Status === "loading" && <p className="cie10-suggestion-status">Cargando catálogo CIE-10…</p>}
                {cie10Status === "error" && <p className="cie10-suggestion-status error">No se pudo cargar el catálogo CIE-10.</p>}
                {cie10Status === "ready" && diagnosisSuggestions.length === 0 && <p className="cie10-suggestion-status">No se encontraron coincidencias.</p>}
                {diagnosisSuggestions.map((option, index) => <button
                  id={`cie10-option-${index}`}
                  type="button"
                  role="option"
                  aria-selected={index === activeDiagnosisIndex}
                  className={index === activeDiagnosisIndex ? "active" : ""}
                  key={option.code}
                  onMouseDown={(event) => { event.preventDefault(); selectDiagnosis(option); }}
                  onMouseEnter={() => setActiveDiagnosisIndex(index)}
                ><span>{option.code}</span><strong>{option.description}</strong></button>)}
              </div>}
            </div>
            <small className="cie10-help">Busque por descripción o código. Seleccione una opción para agregarla y continúe en la línea siguiente.</small>
          </div>
        </div>
        <div className="clinical-entry-panels">
          <section className="pilot-triage-panel">
            <div className="pilot-panel-heading"><span>ETAPA PILOTO</span><strong className="heading-with-info">Datos de triaje <InfoTip text="Ingreso manual para pruebas; en ESSI estos datos se cargarán automáticamente." /></strong></div>
            <div className="triage-grid"><label>Peso (kg)<input type="number" min="1" step="0.1" value={weightKg} onChange={(event) => updateTriage("weight", event.target.value)} placeholder="Ej. 68.5" /></label><label>Talla (cm)<input type="number" min="1" step="0.1" value={heightCm} onChange={(event) => updateTriage("height", event.target.value)} placeholder="Ej. 160" /></label><label>Índice de masa corporal<input readOnly value={clinicalContext.bmi ?? ""} placeholder="Se calcula con peso y talla" /></label></div>
          </section>
          <section className="pilot-renal-panel">
            <div className="pilot-panel-heading"><span>ETAPA PILOTO</span><strong className="heading-with-info">Creatinina y función renal <InfoTip text="La TFGe se calcula con CKD-EPI 2021 (edad, sexo y creatinina). La CrCl se calcula por separado con Cockcroft–Gault y además requiere peso; ambas estimaciones quedan trazables." /></strong></div>
            <div className="renal-grid"><label>Creatinina sérica (mg/dL)<input type="number" min="0.1" step="0.01" value={serumCreatinineMgDl} onChange={(event) => updateSerumCreatinine(event.target.value)} placeholder="Ej. 1.20" /></label><label>Fecha de creatinina<input type="date" value={serumCreatinineDate} onChange={(event) => updateSerumCreatinineDate(event.target.value)} /></label><label>TFGe CKD-EPI 2021 (mL/min/1.73 m²)<input readOnly value={estimatedEgfr ?? ""} placeholder="Complete edad, sexo y creatinina" /></label><label>CrCl Cockcroft–Gault (mL/min)<input readOnly value={estimatedCrCl ?? ""} placeholder="Además complete el peso" /></label></div>
          </section>
        </div>
        {historyLoading && <p className="field-help">Cargando historia pseudonimizada…</p>}
        {historyNotice && <div className="catalog-notice" role="status"><span>ⓘ</span><div><strong>Historia cargada para simulación</strong><p>{historyNotice}</p></div></div>}
        {selectedPatientCode === ESSI_SIMULATOR_CODE && <><label className="full-width">Resumen de esta atención simulada<textarea value={attentionNote} onChange={(event) => setAttentionNote(event.target.value)} placeholder="Ej. Se añadió un medicamento y se actualizó el resultado de creatinina." /></label><div className="simulator-actions"><button type="button" className="secondary-button" onClick={async () => { if (!window.confirm("¿Restaurar SIM-ESSI-001 a su línea base? El historial seguirá siendo auditable.")) return; try { const simulator = await api.resetEssiSimulator(); setSimulationHistory(simulator.history); await selectPatientHistory(ESSI_SIMULATOR_CODE); } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo restaurar el simulador."); } }}>Restablecer simulador a línea base</button></div>{simulationHistory.length > 0 && <details className="history-medications"><summary>Historial de atenciones guardadas ({simulationHistory.length})</summary><ul>{simulationHistory.map((item) => <li key={item.id}><strong>{new Date(item.created_at).toLocaleString("es-PE")}</strong><span>{item.note} · {Array.isArray(item.snapshot.medications) ? item.snapshot.medications.length : 0} medicamentos en esa versión.</span></li>)}</ul></details>}</>}
      </section>

      <section className="form-card medication-card">
        <div className="card-heading"><h2 className="heading-with-info">▤ Medicamentos activos <InfoTip text="La lista se presenta en orden alfabético. Si el medicamento no aparece, puede escribirlo; las reglas clínicas solo se activan cuando existe una asociación validada. Si registra duración, use un número de días, por ejemplo: 120 días." /></h2><button type="button" className="small-primary" onClick={() => setMedications((current) => [...current, { ...EMPTY_MEDICATION }])}>＋ Agregar</button></div>
        <div className="medication-list">
          {medications.map((medication, index) => (
            <div className="medication-row" key={index}>
              <label>Medicamento *<input list="new-case-medication-catalog" value={medication.entered_name} onChange={(event) => selectCatalogMedication(index, event.target.value)} placeholder="Seleccione o escriba un medicamento" /></label>
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
        <datalist id="new-case-medication-catalog">{catalogMedications.map((item) => <option key={item.order} value={item.medication} />)}</datalist>
      </section>

      {selectedPatientCode && historyMedications.length > 0 && <details className="history-medications">
        <summary>Medicamentos en uso ({historyMedications.length})</summary>
        <p>Medicamentos activos registrados en la historia pseudonimizada. Se incluyen en la evaluación junto con los medicamentos nuevos de arriba.</p>
        <ul>{historyMedications.map((medication, index) => <li key={`${medication.entered_name}-${index}`}><strong>{medication.entered_name}</strong><span>{medication.normalized_active_ingredient}{medication.duration ? ` · ${medication.duration}` : " · duración no estructurada"}</span></li>)}</ul>
      </details>}

      <section className="context-card">
        <button type="button" className="context-toggle" onClick={() => setContextOpen((value) => !value)} aria-expanded={contextOpen}>
          <span className="context-icon">♨</span><span><strong>Contexto clínico (opcional)</strong><small>Valores de laboratorio y condiciones específicas del paciente.</small></span><em>Mejora Beers y STOPP/START</em><b>{contextOpen ? "⌃" : "⌄"}</b>
        </button>
        {contextOpen && <div className="context-groups">
          {requiredContext.length === 0 && <p>Cargando campos requeridos desde el catálogo clínico…</p>}
          {requiredContext.length > 0 && <>
            <div className="context-scope-compact"><strong>Alcance del contexto clínico</strong><InfoTip text={`El catálogo activo reúne Beers y STOPP/START y requiere ${editableContext.length} campos clínicos únicos. Un dato ausente queda como no evaluable; nunca se interpreta como normal.`} /></div>
            <details className="context-group" ref={recordedContextRef} open={recordedContext.length > 0}>
              <summary>Exámenes y datos clínicos realizados ({recordedContext.length})</summary>
              {recordedContext.length ? renderContextFields(recordedContext) : <p>No hay exámenes o datos clínicos registrados en la historia cargada.</p>}
            </details>
            <details className="context-group">
              <summary>Exámenes y datos clínicos no realizados / no registrados ({unrecordedContext.length})</summary>
              {unrecordedContext.length ? renderContextFields(unrecordedContext) : <p>Todos los campos disponibles tienen un valor registrado.</p>}
            </details>
            <p className="context-entry-help">Escriba el valor completo y presione Enter para moverlo a “realizados”.</p>
          </>}
        </div>}
      </section>

      <div className="submit-bar"><span className={minimumComplete ? "complete" : "incomplete"}>{minimumComplete ? "✓ Datos mínimos completos" : "Complete los campos obligatorios"}</span><button className="primary-button" disabled={!minimumComplete || submitting}>{submitting ? "Procesando tamizaje…" : selectedPatientCode === ESSI_SIMULATOR_CODE ? "▣ Guardar atención ESSI y ejecutar tamizaje" : selectedPatientCode ? "▣ Ejecutar simulación temporal" : "▣ Crear caso y ejecutar tamizaje"}</button></div>
    </form>
  );
}

function MinimalCasePage() {
  const [patients, setPatients] = useState<PilotPatient[]>([]);
  const [patientQuery, setPatientQuery] = useState("");
  const [selectedPatientCode, setSelectedPatientCode] = useState("");
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [loadingPatientData, setLoadingPatientData] = useState(false);
  const [prefill, setPrefill] = useState<PilotCasePrefill>();
  const [catalogMedications, setCatalogMedications] = useState<CatalogMedication[]>([]);
  const [historyMedications, setHistoryMedications] = useState<MedicationInput[]>([]);
  const [medications, setMedications] = useState<MedicationInput[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ patient: PilotPatient; evaluation: EvaluationExecution }>();
  const [selectedAlertId, setSelectedAlertId] = useState<number>();

  useEffect(() => {
    api.listCatalogMedications()
      .then((rows) => setCatalogMedications(sortCatalogMedications(rows)))
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
    async function loadPatients() {
      setLoadingPatients(true);
      setError("");
      try {
        const nextPatients = await api.listSimplePatients(patientQuery);
        if (!cancelled) setPatients(nextPatients);
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "No se pudo consultar la cohorte.");
      } finally {
        if (!cancelled) setLoadingPatients(false);
      }
    }
    loadPatients();
    }, 300);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [patientQuery]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedPatientCode) {
      setPrefill(undefined);
      setHistoryMedications([]);
      setMedications([]);
      setLoadingPatientData(false);
      return () => { cancelled = true; };
    }
    setLoadingPatientData(true);
    setError("");
    api.getPilotCasePrefill(selectedPatientCode)
      .then((nextPrefill) => {
        if (cancelled) return;
        setPrefill(nextPrefill);
        setHistoryMedications(nextPrefill.medications);
        setMedications([{ ...EMPTY_MINIMAL_MEDICATION }]);
      })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoadingPatientData(false); });
    return () => { cancelled = true; };
  }, [selectedPatientCode]);

  const selectedPatient = patients.find((patient) => patient.patient_code === selectedPatientCode);
  const patientOptionLabel = (patient: PilotPatient) => {
    const alertCount = patient.estimated_alert_count ?? patient.engine_alert_count;
    const diagnosis = patient.example_cie10_code
      ? ` — ${patient.example_cie10_code} ${patient.example_cie10_description ?? patient.example_cie10_syndrome ?? ""}`.trimEnd()
      : "";
    return `${patient.patient_code} — ${patient.age} años, ${patient.sex} — ${patient.max_simultaneous_top_medications} medicamentos simultáneos${alertCount != null ? ` — ${alertCount} alertas estimadas` : ""}${diagnosis}`;
  };
  const withoutPolypharmacy = patients.filter((patient) => patient.simple_example_group === "without_polypharmacy");
  const prioritizedPatients = patients.filter((patient) => patient.simple_example_group === "prioritized");
  const searchPatients = patients.filter((patient) => !["without_polypharmacy", "prioritized"].includes(patient.simple_example_group ?? "search"));
  const additionalMedications = medications.filter((medication) => medication.entered_name.trim());
  const totalMedications = historyMedications.length + additionalMedications.length;
  const canSubmit = Boolean(selectedPatient && prefill && totalMedications > 0);

  function selectMinimalMedication(index: number, name: string) {
    setMedications((current) => current.map((medication, position) => position === index
      ? name ? { ...EMPTY_MINIMAL_MEDICATION, entered_name: name, normalized_active_ingredient: name } : { ...EMPTY_MINIMAL_MEDICATION }
      : medication));
    setResult(undefined);
  }

  async function submitMinimal(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || !selectedPatient || !prefill) return;
    setSubmitting(true);
    setError("");
    setResult(undefined);
    setSelectedAlertId(undefined);
    try {
      const response = await api.previewCase({
        case_code: `MIN-${selectedPatientCode}`,
        age: prefill.age,
        sex: prefill.sex,
        diagnoses: prefill.diagnoses,
        clinical_context: prefill.clinical_context,
        is_simulated: true,
        medications: [...historyMedications, ...additionalMedications],
      });
      setResult({ patient: selectedPatient, evaluation: response.evaluation });
      setSelectedAlertId(response.evaluation.alerts.find((alert) => ["beers", "stopp_start", "ddinter"].includes(alert.analysis_system))?.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo ejecutar el tamizaje rápido.");
    } finally {
      setSubmitting(false);
    }
  }

  return <form className="minimal-case-page" onSubmit={submitMinimal}>
    {error && <ErrorNotice message={error} onClose={() => setError("")} />}
    <div className="intro-row"><span className="intro-icon">◇</span><div><h1>Nuevo caso simple</h1><p>Seleccione un paciente pseudonimizado; SIGRAM cargará su historia disponible sin solicitar datos esenciales manuales.</p></div></div>
    <section className="form-card minimal-card">
      <h2>▣ Seleccionar paciente</h2>
      <div className="minimal-patient-picker">
        <label>Buscar por código de paciente
          <input value={patientQuery} onChange={(event) => setPatientQuery(event.target.value)} placeholder="Ej.: REB-045177" />
        </label>
        <label>Paciente priorizado por alertas
          <select value={selectedPatientCode} disabled={loadingPatients} onChange={(event) => { setSelectedPatientCode(event.target.value); setResult(undefined); }}>
            <option value="">{loadingPatients ? "Buscando pacientes…" : "Seleccione un paciente…"}</option>
            {withoutPolypharmacy.length > 0 && <optgroup label="Ejemplos sin polifarmacia (0–4 medicamentos)">{withoutPolypharmacy.map((patient) => <option key={patient.patient_code} value={patient.patient_code}>{patientOptionLabel(patient)}</option>)}</optgroup>}
            {prioritizedPatients.length > 0 && <optgroup label="Pacientes priorizados por alertas">{prioritizedPatients.map((patient) => <option key={patient.patient_code} value={patient.patient_code}>{patientOptionLabel(patient)}</option>)}</optgroup>}
            {searchPatients.length > 0 && <optgroup label={patientQuery.trim() ? "Resultados de búsqueda" : "Otros pacientes"}>{searchPatients.map((patient) => <option key={patient.patient_code} value={patient.patient_code}>{patientOptionLabel(patient)}</option>)}</optgroup>}
          </select>
        </label>
        {!loadingPatients && patients.length === 0 && <p className="minimal-empty">No se encontraron pacientes con ese código.</p>}
        {selectedPatient && <div className="minimal-patient-summary"><strong>{selectedPatient.patient_code}</strong><span>{selectedPatient.age} años · {selectedPatient.sex}</span><span>{selectedPatient.polypharmacy_level ?? "Polifarmacia no informada"} · máximo {selectedPatient.max_simultaneous_top_medications} medicamentos simultáneos</span>{prefill && <span className="minimal-index-date"><b>Fecha índice:</b> {formatCalendarDate(prefill.medication_index_date)}</span>}</div>}
      </div>
    </section>
    {selectedPatientCode && <section className="form-card minimal-card">
      <div className="card-heading"><h2>▤ Medicamentos a evaluar</h2><button type="button" className="small-primary" disabled={loadingPatientData} onClick={() => { setMedications((current) => [...current, { ...EMPTY_MINIMAL_MEDICATION }]); setResult(undefined); }}>＋ Agregar</button></div>
      {loadingPatientData ? <div className="empty-state">Preparando medicamentos…</div> : <div className="minimal-medications">
        {medications.map((medication, index) => {
          const isCatalogMedication = catalogMedications.some((item) => item.medication === medication.entered_name);
          return <div className="minimal-medication-row" key={`minimal-medication-${index}`}>
            <label>Seleccionar medicamento {index + 1}
              <select value={isCatalogMedication ? medication.entered_name : ""} onChange={(event) => selectMinimalMedication(index, event.target.value)}>
                <option value="">Seleccione del catálogo…</option>
                {catalogMedications.map((item) => <option value={item.medication} key={item.order}>{item.medication}</option>)}
              </select>
            </label>
            <label>Ingresar medicamento no listado
              <input value={isCatalogMedication ? "" : medication.entered_name} onChange={(event) => selectMinimalMedication(index, event.target.value)} placeholder="Escriba el nombre del medicamento" />
            </label>
            <button type="button" className="delete-button" aria-label={`Eliminar medicamento ${index + 1}`} disabled={medications.length === 1} onClick={() => { setMedications((current) => current.filter((_, position) => position !== index)); setResult(undefined); }}>⌫</button>
          </div>;
        })}
      </div>}
      {!loadingPatientData && <p className="minimal-warning">Opcional: elija un medicamento del desplegable o ingrese por escrito uno que no figure en el catálogo.</p>}
    </section>}
    {selectedPatientCode && !loadingPatientData && historyMedications.length > 0 && <details className="history-medications minimal-history-medications">
      <summary>Medicamentos cargados del paciente ({historyMedications.length})</summary>
      <p>Medicamentos activos registrados en la historia pseudonimizada. Se evaluarán junto con los medicamentos nuevos seleccionados arriba.</p>
      <ul>{historyMedications.map((medication, index) => <li key={`${medication.entered_name}-${index}`}><strong>{medication.entered_name}</strong><span>{medication.normalized_active_ingredient}{medication.duration ? ` · ${medication.duration}` : " · duración no estructurada"}</span></li>)}</ul>
    </details>}
    <div className="submit-bar minimal-submit"><span className={canSubmit ? "complete" : "incomplete"}>{canSubmit ? `✓ ${totalMedications} medicamentos listos` : selectedPatientCode ? "Espere la carga de la historia" : "Seleccione un paciente"}</span><button className="primary-button" disabled={!canSubmit || submitting}>{submitting ? "Validando…" : "✓ Validar prescripción"}</button></div>
    {result && <QuickScreeningToast result={result} indexDate={prefill?.medication_index_date} selectedAlertId={selectedAlertId} onSelectAlert={setSelectedAlertId} onClose={() => { setResult(undefined); setSelectedAlertId(undefined); }} />}
  </form>;
}

function QuickScreeningToast({ result, indexDate, selectedAlertId, onSelectAlert, onClose }: { result: { patient: PilotPatient; evaluation: EvaluationExecution }; indexDate?: string; selectedAlertId?: number; onSelectAlert: (id?: number) => void; onClose: () => void }) {
  type QuickTab = "mpi" | "opp" | "ifp";
  type MpiGroup = { key: string; alerts: AlertResult[]; representative: AlertResult };
  const duplicateFamilies: Record<string, string> = {
    B09: "aspirin-primary-prevention", "STOPP-C16": "aspirin-primary-prevention",
    B07: "nsaid-ulcer-no-gastroprotection", "STOPP-H1": "nsaid-ulcer-no-gastroprotection",
    B10: "long-acting-sulfonylurea", "STOPP-J1": "long-acting-sulfonylurea",
    B18: "multiple-anticholinergics", "STOPP-M1": "multiple-anticholinergics",
    B23: "alpha-blocker-syncope-orthostasis", "STOPP-I5": "alpha-blocker-syncope-orthostasis",
  };
  const alerts = result.evaluation.alerts.filter((alert) => ["beers", "stopp_start", "ddinter"].includes(alert.analysis_system));
  const mpiAlerts = alerts.filter((alert) => alert.analysis_system === "beers" || alert.rule_code.startsWith("STOPP-"));
  const mpiGroups = Array.from(mpiAlerts.reduce((groups, alert) => {
    const key = duplicateFamilies[alert.rule_code] ?? alert.rule_code;
    const current = groups.get(key) ?? [];
    current.push(alert);
    groups.set(key, current);
    return groups;
  }, new Map<string, AlertResult[]>())).map(([key, groupedAlerts]): MpiGroup => ({
    key,
    alerts: groupedAlerts,
    representative: groupedAlerts.find((alert) => alert.rule_code.startsWith("STOPP-")) ?? groupedAlerts[0],
  }));
  const oppAlerts = alerts.filter((alert) => alert.rule_code.startsWith("START-"));
  const ifpAlerts = alerts.filter((alert) => alert.analysis_system === "ddinter");
  const initiallySelected = alerts.find((alert) => alert.id === selectedAlertId);
  const initialTab: QuickTab = initiallySelected?.analysis_system === "ddinter" ? "ifp" : initiallySelected?.rule_code.startsWith("START-") ? "opp" : "mpi";
  const [activeTab, setActiveTab] = useState<QuickTab>(initialTab);
  const selectedMpiGroup = mpiGroups.find((group) => group.alerts.some((alert) => alert.id === selectedAlertId));
  const selectedOpp = oppAlerts.find((alert) => alert.id === selectedAlertId);
  const selectedIfp = ifpAlerts.find((alert) => alert.id === selectedAlertId);
  const visibleCount = activeTab === "mpi" ? mpiGroups.length : activeTab === "opp" ? oppAlerts.length : ifpAlerts.length;
  const totalFindings = mpiGroups.length + oppAlerts.length + ifpAlerts.length;
  const selectedClinicalAlerts = selectedMpiGroup?.alerts ?? (selectedOpp ? [selectedOpp] : []);
  const selectedReviewDetails = selectedClinicalAlerts.length
    ? Array.from(new Map(selectedClinicalAlerts.flatMap(doctorReviewDetails).map((detail) => [`${detail.source_system}-${detail.source_code}-${detail.description}`, detail])).values())
    : [];

  function selectTab(tab: QuickTab) {
    setActiveTab(tab);
    onSelectAlert(tab === "mpi" ? mpiGroups[0]?.representative.id : tab === "opp" ? oppAlerts[0]?.id : ifpAlerts[0]?.id);
  }

  return <aside className="quick-screening-toast" role="status" aria-live="polite" aria-label="Resultado del tamizaje rápido">
    <header><div><strong>{totalFindings} {totalFindings === 1 ? "hallazgo detectado" : "hallazgos detectados"}</strong><span>Paciente {result.patient.patient_code} · Fecha índice: {formatCalendarDate(indexDate)}</span></div><button type="button" onClick={onClose} aria-label="Cerrar resultado">×</button></header>
    <div className="quick-alert-tabs" role="tablist" aria-label="Tipo de hallazgo">{(["mpi", "opp", "ifp"] as QuickTab[]).map((tab) => {
      const label = tab === "mpi" ? "MPI" : tab === "opp" ? "OPP" : "IFP";
      const count = tab === "mpi" ? mpiGroups.length : tab === "opp" ? oppAlerts.length : ifpAlerts.length;
      const title = tab === "mpi" ? "Medicamentos potencialmente inapropiados" : tab === "opp" ? "Omisiones potenciales de prescripción" : "Interacciones farmacológicas potenciales";
      return <button type="button" role="tab" title={title} aria-label={`${title}: ${count}`} aria-selected={activeTab === tab} className={`quick-alert-tab tab-${tab} ${activeTab === tab ? "active" : ""}`} onClick={() => selectTab(tab)} key={tab}><span>{label}</span><b>{count}</b></button>;
    })}</div>
    {visibleCount > 0 ? <div className="quick-alert-list" role="tabpanel" aria-label={`Hallazgos ${activeTab.toUpperCase()}`}>
      {activeTab === "mpi" ? mpiGroups.map((group) => <button type="button" key={group.key} className={group.alerts.some((alert) => alert.id === selectedAlertId) ? "active" : ""} onClick={() => onSelectAlert(group.representative.id)}><span>MPI · {group.alerts.map((alert) => alert.rule_code).join(" + ")}</span><strong>{group.representative.problem_identified}</strong></button>) : activeTab === "opp" ? oppAlerts.map((alert) => <button type="button" key={alert.id} className={alert.id === selectedAlertId ? "active" : ""} onClick={() => onSelectAlert(alert.id)}><span>OPP · {alert.rule_code}</span><strong>{alert.problem_identified}</strong></button>) : ifpAlerts.map((alert) => <button type="button" key={alert.id} className={alert.id === selectedAlertId ? "active" : ""} onClick={() => onSelectAlert(alert.id)}><span>IFP · {alert.rule_code}</span><strong>{alert.problem_identified}</strong></button>)}
    </div> : <div className="quick-alert-empty" role="tabpanel">No se detectaron hallazgos {activeTab.toUpperCase()} con los datos disponibles.</div>}
    {activeTab === "mpi" && selectedMpiGroup && <section className="quick-alert-detail" aria-label="Detalle del MPI seleccionado">
      <div><span>MPI</span><b>{selectedMpiGroup.alerts.map((alert) => alert.rule_code).join(" + ")}</b></div>
      <strong>{selectedMpiGroup.representative.problem_identified}</strong>
      <p><b>Medicamentos:</b> {Array.from(new Set(selectedMpiGroup.alerts.flatMap((alert) => alert.implicated_medications))).join(", ") || "No consignados"}</p>
      {selectedMpiGroup.alerts.filter((alert) => alert.rule_code.startsWith("STOPP-")).map((alert) => <p key={`description-${alert.id}`}><b>Descripción STOPP ({alert.rule_code}):</b> {alert.problem_identified}</p>)}
      {selectedMpiGroup.representative.justification && <p><b>Motivo:</b> {selectedMpiGroup.representative.justification}</p>}
      {Array.from(new Set(selectedMpiGroup.alerts.map((alert) => alert.recommendation).filter(Boolean))).map((recommendation) => <p key={recommendation}><b>Orientación:</b> {recommendation}</p>)}
      {selectedReviewDetails.length > 0 && <details className="quick-review-more"><summary>Ver más</summary><div><b>Descripción ampliada revisada por el equipo clínico</b>{selectedReviewDetails.map((detail) => <article key={`${detail.source_system}-${detail.source_code}-${detail.source_row}`}><span>{detail.source_system} {detail.source_code}</span><p>{detail.description}</p></article>)}</div></details>}
    </section>}
    {activeTab === "opp" && selectedOpp && <section className="quick-alert-detail" aria-label="Detalle de la OPP seleccionada">
      <div><span>OPP</span><b>{selectedOpp.rule_code}</b></div><strong>{selectedOpp.problem_identified}</strong>
      <p><b>Medicamentos relacionados:</b> {selectedOpp.implicated_medications.join(", ") || "No consignados"}</p>
      {selectedOpp.justification && <p><b>Motivo:</b> {selectedOpp.justification}</p>}
      {selectedOpp.recommendation && <p><b>Orientación:</b> {selectedOpp.recommendation}</p>}
      {selectedReviewDetails.length > 0 && <details className="quick-review-more"><summary>Ver más</summary><div><b>Descripción ampliada revisada por el equipo clínico</b>{selectedReviewDetails.map((detail) => <article key={`${detail.source_system}-${detail.source_code}-${detail.source_row}`}><span>{detail.source_system} {detail.source_code}</span><p>{detail.description}</p></article>)}</div></details>}
    </section>}
    {activeTab === "ifp" && selectedIfp && <section className="quick-alert-detail" aria-label="Detalle de la IFP seleccionada">
      <div><span>IFP</span><b>{selectedIfp.rule_code}</b></div><strong>{selectedIfp.problem_identified}</strong>
      <p><b>Medicamentos:</b> {selectedIfp.implicated_medications.join(", ") || "No consignados"}</p>
      {selectedIfp.justification && <p><b>Motivo:</b> {selectedIfp.justification}</p>}
      {selectedIfp.recommendation && <p><b>Orientación:</b> {selectedIfp.recommendation}</p>}
    </section>}
  </aside>;
}

function ClinicalDataForReview({ clinicalCase, implicatedMedications, contextUsed = {} }: { clinicalCase: ClinicalCase; implicatedMedications: string[]; contextUsed?: Record<string, unknown> }) {
  const matchingMedications = clinicalCase.medications.filter((medication) => implicatedMedications.some((name) =>
    medicationNamesMatch(name, medication.entered_name) || medicationNamesMatch(name, medication.normalized_active_ingredient),
  ));
  const medicationsToShow = matchingMedications.length ? matchingMedications : clinicalCase.medications;
  const medicationFacts = Array.isArray(clinicalCase.clinical_context.medication_facts)
    ? clinicalCase.clinical_context.medication_facts.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const renalItems: Array<[string, unknown, string?]> = [
    ["Creatinina sérica", clinicalCase.clinical_context.serum_creatinine_mg_dl, "mg/dL"],
    ["Fecha de creatinina", clinicalCase.clinical_context.serum_creatinine_date],
    ["Depuración de creatinina (CrCl)", clinicalCase.clinical_context.creatinine_clearance_ml_min, "mL/min"],
    ["TFGe / TFG (reportada o calculada)", clinicalCase.clinical_context.egfr_ml_min_1_73m2, "mL/min/1.73 m²"],
  ];
  const usedItems = Object.entries(contextUsed).filter(([, value]) => value !== null && value !== undefined && value !== "");
  const medicationHeading = matchingMedications.length ? "Medicamentos relacionados con el criterio" : "Medicamentos registrados para el cruce";

  return <section className="criterion-clinical-data">
    <span className="drawer-label">Datos registrados para la revisión clínica</span>
    <dl>
      <div><dt>Diagnósticos / condiciones</dt><dd>{clinicalCase.diagnoses || "No registrados"}</dd></div>
      <div><dt>{medicationHeading}</dt><dd>{medicationsToShow.length ? <ul className="criterion-medication-list">{medicationsToShow.map((medication) => {
        const fact = medicationFacts.find((item) => typeof item.active_ingredient === "string" && medicationNamesMatch(item.active_ingredient, medication.normalized_active_ingredient));
        const duration = medication.duration || (fact ? recordedValue(fact.duration_days) : "No registrada");
        return <li key={medication.id}><b>{medication.entered_name}</b><span>Dosis: {medication.dose || "No registrada"} {medication.dose_unit || ""} · Frecuencia: {medication.frequency || "No registrada"} · Vía: {medication.route || "No registrada"} · Duración: {duration}</span></li>;
      })}</ul> : "No hay medicamentos registrados."}</dd></div>
      <div><dt>Función renal / creatinina</dt><dd><ul className="criterion-context-list">{renalItems.map(([label, value, unit]) => <li key={label}><b>{label}:</b> {recordedValue(value)}{value !== null && value !== undefined && value !== "" && unit ? ` ${unit}` : ""}</li>)}</ul></dd></div>
      {usedItems.length > 0 && <div><dt>Variables aplicadas por el motor</dt><dd><ul className="criterion-context-list">{usedItems.map(([field, value]) => <li key={field}><b>{clinicalFieldLabel(field)}:</b> {recordedValue(value)}</li>)}</ul></dd></div>}
    </dl>
  </section>;
}

function DetailDrawer({ criterion, alert, clinicalCase, onClose }: { criterion: CriterionResult; alert?: AlertResult; clinicalCase: ClinicalCase; onClose: () => void }) {
  const isBeers = criterion.system === "beers";
  return <div className="drawer-layer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
    <button className="drawer-backdrop" onClick={onClose} aria-label="Cerrar detalle" />
    <aside className="detail-drawer">
      <header><div><span className={`status-dot ${criterion.status}`} /><h2 id="drawer-title">Detalle del criterio {criterionDisplayCode(criterion)}</h2></div><button onClick={onClose} aria-label="Cerrar">×</button></header>
      <div className="drawer-content">
        <section><span className="drawer-label">{isBeers ? "Recomendación AGS Beers 2023" : "Estado"}</span>{isBeers ? <span className={`beers-recommendation ${criterion.recommendation_type ?? "conditional"}`}>{beersRecommendationLabel(criterion)}</span> : <span className={`status-pill ${criterion.status}`}>{statusLabel(criterion.status)}</span>}</section>
        <section><span className="drawer-label">{isBeers ? "Criterio / situación evaluada" : "Criterio"}</span><p>{isBeers ? criterion.evaluated_situation ?? criterion.statement : criterion.statement}</p></section>
        <section><span className="drawer-label">Descripción fuente</span><p className="source-description">{criterionSourceDescription(criterion)}</p></section>
        {isBeers && criterion.rationale && <section><span className="drawer-label">Fundamento clínico — rationale</span><p>{criterion.rationale}</p></section>}
        <section><span className="drawer-label">Medicamentos implicados</span><p>{criterion.implicated_medications.length ? criterion.implicated_medications.join(", ") : "Ninguno registrado"}</p></section>
        {isBeers && <section><span className="drawer-label">Motivo del hallazgo</span><p>{criterion.reason}</p></section>}
        <ClinicalDataForReview clinicalCase={clinicalCase} implicatedMedications={criterion.implicated_medications} contextUsed={criterion.context_used} />
        <section><span className="drawer-label">Datos faltantes</span>{criterion.missing_data.length ? <ul>{criterion.missing_data.map((item, index) => <li key={index}>{String(item.label ?? item.field ?? JSON.stringify(item))}</li>)}</ul> : <p>No se reportaron datos faltantes.</p>}</section>
        {(criterion.lab_evidence?.length ?? 0) > 0 && <section><span className="drawer-label">Exámenes usados por el backend</span><ul>{criterion.lab_evidence.map((item) => <li key={`${item.field}-${item.source_row_sha256}`}><b>{labFieldLabel(item.field)}:</b> {labValueLabel(item)}; {formatDate(item.result_date)}; código ESSI {item.exam_code}; {item.applied ? "aplicado" : "no aplicado (prioridad al contexto manual)"}.</li>)}</ul></section>}
        {criterion.diagnosis_evidence.length > 0 && <section><span className="drawer-label">Evidencia CIE-10</span><ul>{criterion.diagnosis_evidence.map((item, index) => <li key={`${item.field ?? "cie"}-${index}`}><b>{item.label ?? item.field ?? "Contexto clínico"}:</b> {item.matched_codes?.map((code) => code.code).filter(Boolean).join(", ") || "evidencia documentada"}.</li>)}</ul></section>}
        {criterion.protective_evidence.length > 0 && <section><span className="drawer-label">Protectores identificados</span><ul>{criterion.protective_evidence.map((item, index) => <li key={`${item.field ?? item.role ?? "protector"}-${index}`}>{item.label ?? item.field ?? item.role ?? "Protector documentado"}</li>)}</ul></section>}
        {criterion.exception_reason && <section><span className="drawer-label">Excepción / mitigación</span><p>{criterion.exception_reason}</p></section>}
        {!isBeers && criterion.recommended_actions.length > 0 && <section className="suggested-actions"><span className="drawer-label">Acciones sugeridas</span><ul>{criterion.recommended_actions.map((item, index) => <li key={index}>{item}</li>)}</ul></section>}
        <details className="detail-more"><summary>{isBeers ? "Ver fuente y trazabilidad" : "Ver más"}</summary><div>
          <section><span className="drawer-label">Fuente</span><p>{criterion.source_name ? `${criterion.source_name} ${criterion.source_year ?? ""}` : alert?.source || criterion.source_location || "No consignada"}</p></section>
          {isBeers && <section><span className="drawer-label">Tabla y sección</span><p>{[criterion.source_table, criterion.source_section, criterion.source_location].filter(Boolean).join(" · ")}</p></section>}
          {isBeers && criterion.quality_of_evidence && <section><span className="drawer-label">Calidad de la evidencia</span><span className="evidence-neutral">{criterion.quality_of_evidence === "High" ? "Alta ●●●" : criterion.quality_of_evidence === "Moderate" ? "Moderada ●●○" : criterion.quality_of_evidence === "Low" ? "Baja ●○○" : criterion.quality_of_evidence}</span></section>}
          {isBeers && criterion.strength_of_recommendation && <section><span className="drawer-label">Fuerza de la recomendación</span><span className="evidence-neutral">{criterion.strength_of_recommendation === "Strong" ? "Fuerte" : criterion.strength_of_recommendation === "Weak" ? "Débil" : criterion.strength_of_recommendation}</span></section>}
          {isBeers && <section><span className="drawer-label">Formulación operativa del catálogo SIGRAM</span><p>{criterion.operational_formulation ?? criterion.statement}</p></section>}
          <section><span className="drawer-label">Versión del catálogo</span><p>{alert?.rule_version || criterion.catalog_version}</p></section>
          {criterion.triggering_evidence.length > 0 && <section><span className="drawer-label">Evidencia activadora</span><ul>{criterion.triggering_evidence.map((item, index) => <li key={`${item.field ?? item.role ?? "trigger"}-${index}`}>{item.label ?? item.field ?? item.role ?? "Condición evaluada"}: {String(item.value ?? "documentada")}</li>)}</ul></section>}
          {criterion.medication_coverage_note && <section><span className="drawer-label">Cobertura farmacológica</span><p>{criterion.medication_coverage_note}</p></section>}
        </div></details>
      </div>
      <footer><button className="secondary-button" onClick={onClose}>Cerrar</button></footer>
    </aside>
  </div>;
}

function DDInterDetailDrawer({ alert, clinicalCase, onClose }: { alert: AlertResult; clinicalCase: ClinicalCase; onClose: () => void }) {
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
        <ClinicalDataForReview clinicalCase={clinicalCase} implicatedMedications={alert.implicated_medications} />
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
  type ResultCategory = "mpi" | "opp" | "ifp";
  const [system, setSystem] = useState<ResultCategory>("mpi");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | CriterionResult["status"]>("all");
  const [ddinterLevelFilter, setDdinterLevelFilter] = useState<"all" | DDInterLevel>("all");
  const [selected, setSelected] = useState<CriterionResult>();
  const [selectedInteraction, setSelectedInteraction] = useState<AlertResult>();

  const isClinicalCategory = system !== "ifp";
  const categoryMatches = (item: CriterionResult) => system === "mpi"
    ? item.system === "beers" || (item.system === "stopp_start" && item.criterion_type === "STOPP")
    : system === "opp" ? item.system === "stopp_start" && item.criterion_type === "START" : false;
  const visibleCriteria = (evaluation.clinical_findings ?? evaluation.criteria_report.filter((item) => item.status === "alert" || item.status === "activated")).filter(categoryMatches);
  const categoryCriteria = evaluation.criteria_report.filter(categoryMatches);
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
  function selectSystem(nextSystem: ResultCategory) {
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
    <div className="result-category-tabs" role="tablist" aria-label="Tipo de hallazgo"><button role="tab" aria-selected={system === "mpi"} className={`quick-alert-tab tab-mpi ${system === "mpi" ? "active" : ""}`} onClick={() => selectSystem("mpi")}><span>MPI</span><b>{(evaluation.clinical_findings ?? []).filter((item) => item.system === "beers" || (item.system === "stopp_start" && item.criterion_type === "STOPP")).length}</b></button><button role="tab" aria-selected={system === "opp"} className={`quick-alert-tab tab-opp ${system === "opp" ? "active" : ""}`} onClick={() => selectSystem("opp")}><span>OPP</span><b>{(evaluation.clinical_findings ?? []).filter((item) => item.system === "stopp_start" && item.criterion_type === "START").length}</b></button><button role="tab" aria-selected={system === "ifp"} className={`quick-alert-tab tab-ifp ${system === "ifp" ? "active" : ""}`} onClick={() => selectSystem("ifp")}><span>IFP</span><b>{ddinterAlerts.length}</b></button></div>
    {system === "ifp" ? <div className="ddinter-overview">
      <div><strong className="metric-alert">{ddinterAlerts.length}</strong><span>Interacciones detectadas</span></div>
      <div><strong>DDInter local</strong><span>Catálogo configurado en el backend</span></div>
      <div><strong>Coincidencia</strong><span>Exacta o alias provisional</span></div>
    </div> : <div className="metric-grid"><div><strong className="metric-alert">{visibleCriteria.length}</strong><span>Alertas confirmadas</span></div><div><strong className="metric-primary">{categoryCriteria.filter((item) => ["alert", "activated", "no_alert"].includes(item.status)).length}</strong><span>Evaluados</span></div><div><strong>{categoryCriteria.filter((item) => item.status === "not_evaluable").length}</strong><span>Requieren información adicional</span></div><div><strong className="metric-manual">{categoryCriteria.filter((item) => item.status === "manual_review").length}</strong><span>Revisión manual</span></div></div>}
    {system === "mpi" && clinicalCase.age < 65 && <div className="method-note">ⓘ Los criterios Beers se interpretan para 65 años o más; STOPP se mantiene como tamizaje de investigación.</div>}
    {system === "ifp" && <div className="method-note">ⓘ Interacciones farmacológicas potenciales según el catálogo DDInter local.</div>}
    {system === "ifp" ? <div className="results-card">
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
      <div className="results-toolbar"><div><strong>{system === "mpi" ? "Medicamentos potencialmente inapropiados" : "Omisiones potenciales de prescripción"}</strong><span>{visibleCriteria.length} alertas confirmadas</span></div><div><label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filtrar…" /></label></div></div>
      <div className="table-scroll"><table className="results-table"><thead><tr><th>Gravedad</th><th>Código fuente</th><th>Medicamento(s)</th><th>Estado</th><th>Descripción fuente</th><th>Acción</th></tr></thead><tbody>
        {rows.map((criterion) => {
          const alert = evaluation.alerts.find((item) => item.analysis_system === criterion.system && item.rule_code === criterion.criterion_code);
          const explanation = criterion.missing_data.length ? `Dato faltante: ${criterion.missing_data.map((item) => item.label ?? item.field).join(", ")}` : alert?.justification || criterion.reason;
          return <tr key={`${criterion.system}-${criterion.criterion_code}`} className={criterion.status === "no_alert" ? "no-alert-row" : ""}>
            <td><span className={`severity-bar ${criterion.status}`} title={statusLabel(criterion.status)} /></td>
            <td><code>{criterionDisplayCode(criterion)}</code></td>
            <td>{criterion.implicated_medications.length ? criterion.implicated_medications.join(", ") : "—"}</td>
            <td><span className={`status-pill ${criterion.status}`}>{statusLabel(criterion.status)}</span></td>
            <td><span>{criterionSourceDescription(criterion)}</span>{criterion.missing_data.length > 0 && <b className="missing-label">⚠ Dato faltante</b>}<small>{explanation || "Evaluación completada."}</small></td>
            <td><button className="outline-button" onClick={() => setSelected(criterion)}>Ver detalle</button></td>
          </tr>;
        })}
      </tbody></table>{rows.length === 0 && <div className="empty-state">No hay resultados para los filtros seleccionados.</div>}</div>
      <div className="table-footer">Mostrando {rows.length} de {visibleCriteria.length} registros</div>
    </div>}
    {isClinicalCategory && <details className="full-analysis"><summary>Ver más: análisis completo</summary><div className="full-analysis-content"><p><b>Requieren información adicional:</b> {categoryCriteria.filter((item) => item.status === "not_evaluable").length}. <b>Revisión manual:</b> {categoryCriteria.filter((item) => item.status === "manual_review").length}.</p><div className="table-scroll"><table><thead><tr><th>Código fuente</th><th>Estado</th><th>Descripción fuente</th><th>Acción</th></tr></thead><tbody>{categoryCriteria.map((item) => <tr key={`technical-${item.system}-${item.criterion_code}`}><td><code>{criterionDisplayCode(item)}</code></td><td><span className={`status-pill ${item.status}`}>{statusLabel(item.status)}</span></td><td>{criterionSourceDescription(item)}</td><td><button className="outline-button" onClick={() => setSelected(item)}>Ver detalle</button></td></tr>)}</tbody></table></div></div></details>}
    {selected && <DetailDrawer criterion={selected} alert={selectedAlert} clinicalCase={clinicalCase} onClose={() => setSelected(undefined)} />}
    {selectedInteraction && <DDInterDetailDrawer alert={selectedInteraction} clinicalCase={clinicalCase} onClose={() => setSelectedInteraction(undefined)} />}
  </section>;
}

function LaboratoryEvidencePanel({ availability }: { availability: PilotEvaluationResponse["data_availability"] }) {
  const evidence = availability.mapped_lab_fields ?? [];
  const diagnoses = availability.mapped_diagnosis_fields ?? [];
  const catalogMatchedPresentations = new Set(
    availability.medication_catalog_classification
      .filter((item) => item.matched_top_v1)
      .map((item) => item.essi_presentation),
  );
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
  {availability.medication_catalog_classification.length > 0 && <section className="laboratory-panel" aria-label="Medicamentos activos clasificados"><div className="laboratory-heading"><div><h2>Medicamentos activos en la fecha índice</h2><p>Cobertura del catálogo operativo: {catalogMatchedPresentations.size} de {availability.medications_loaded} medicamentos activos. Los no clasificados no fueron evaluados por Beers ni STOPP/START.</p></div></div><div className="table-scroll"><table><thead><tr><th>Presentación ESSI</th><th>Cobertura</th><th>Grupo farmacológico</th><th>Beers</th><th>STOPP/START</th></tr></thead><tbody>{availability.medication_catalog_classification.map((item, index) => <tr key={`${item.essi_presentation}-${index}`}><td><b>{item.essi_presentation}</b></td><td>{item.matched_top_v1 ? "Incluido" : "Fuera del catálogo operativo"}</td><td>{item.pharmacologic_group ?? "No clasificado"}</td><td>{item.beers_codes.join(", ") || "—"}</td><td>{[...item.stopp_codes, ...item.start_codes].join(", ") || "—"}</td></tr>)}</tbody></table></div></section>}
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
    {page === "new-minimal" && <MinimalCasePage />}
    {page === "history" && <HistoryPage onReview={reviewCase} />}
    {page === "research" && <ResearchDataPage />}
    {page === "results" && clinicalCase && evaluation && <ResultsPage clinicalCase={clinicalCase} evaluation={evaluation} dataAvailability={dataAvailability} />}
  </Shell>;
}
