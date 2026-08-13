import type {
  CatalogCriterion,
  CatalogMedication,
  CatalogSummary,
  ClinicalCase,
  ClinicalCaseInput,
  ClinicalCaseSummary,
  EvaluationExecution,
  PilotCasePrefill,
  PilotEvaluationResponse,
  PilotResearchData,
  PilotPatient,
  EssiSimulator,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Error HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      // Mantener el mensaje HTTP cuando el backend no devuelve JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  listCases: () => request<ClinicalCaseSummary[]>("/cases"),
  getCase: (caseId: number) => request<ClinicalCase>(`/cases/${caseId}`),
  createCase: (payload: ClinicalCaseInput) =>
    request<ClinicalCase>("/cases", { method: "POST", body: JSON.stringify(payload) }),
  evaluateCase: (caseId: number) =>
    request<EvaluationExecution>(`/cases/${caseId}/evaluate`, { method: "POST" }),
  previewCase: (payload: ClinicalCaseInput) =>
    request<{ case: ClinicalCase; evaluation: EvaluationExecution }>("/cases/preview", { method: "POST", body: JSON.stringify(payload) }),
  getLatestResults: (caseId: number) =>
    request<EvaluationExecution>(`/cases/${caseId}/results`),
  listCriteria: (system?: "beers" | "stopp_start") =>
    request<CatalogCriterion[]>(`/catalog/v1/criteria${system ? `?system=${system}` : ""}`),
  listCatalogMedications: () => request<CatalogMedication[]>("/catalog/v1/medications"),
  getCatalogSummary: () => request<CatalogSummary>("/catalog/v1/summary"),
  listPilotPatients: () => request<PilotPatient[]>("/pilot/v1/sample-patients"),
  evaluatePilotPatient: (patientCode: string, clinicalContext: Record<string, unknown> = {}) =>
    request<PilotEvaluationResponse>(`/pilot/v1/sample-patients/${encodeURIComponent(patientCode)}/evaluate`, {
      method: "POST",
      body: JSON.stringify({ clinical_context: clinicalContext }),
    }),
  getPilotResearchData: (patientCode: string) =>
    request<PilotResearchData>(`/pilot/v1/sample-patients/${encodeURIComponent(patientCode)}/research-data`),
  getPilotCasePrefill: (patientCode: string) =>
    request<PilotCasePrefill>(`/pilot/v1/sample-patients/${encodeURIComponent(patientCode)}/case-prefill`),
  getEssiSimulator: () => request<EssiSimulator>("/simulator/essi"),
  updateEssiSimulator: (payload: ClinicalCaseInput & { note: string }) =>
    request<EssiSimulator>("/simulator/essi", { method: "PUT", body: JSON.stringify(payload) }),
  resetEssiSimulator: () => request<EssiSimulator>("/simulator/essi/reset", { method: "POST" }),
};
