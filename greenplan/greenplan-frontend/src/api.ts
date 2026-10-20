import type {
  CheckResult,
  EditIssue,
  EditsPayload,
  ImageProvider,
  Job,
  Placement,
  PlanResult,
  RulesCatalog,
  Season,
  Species,
  VisualStatus,
  Visualization,
} from "./types";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  issues: EditIssue[];

  constructor(message: string, status: number, issues: EditIssue[] = []) {
    super(message);
    this.status = status;
    this.issues = issues;
  }
}

async function readError(response: Response): Promise<ApiError> {
  let message = `Сервер ответил ${response.status}`;
  let issues: EditIssue[] = [];
  try {
    const data = await response.json();
    const detail = data?.detail;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      message = detail.message ?? message;
      issues = Array.isArray(detail.issues) ? detail.issues : [];
    } else if (Array.isArray(detail)) {
      message = detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join("; ") || message;
    }
  } catch {
    return new ApiError(message, response.status);
  }
  return new ApiError(message, response.status, issues);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(`Нет связи с сервером расчёта (${API_URL})`, 0);
  }
  if (!response.ok) {
    throw await readError(response);
  }
  return response.json() as Promise<T>;
}

function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return call<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

const run = (id: string) => `/runs/${encodeURIComponent(id)}`;

export function fetchRules(): Promise<RulesCatalog> {
  return call<RulesCatalog>("/rules");
}

export function createRun(file: File): Promise<Job> {
  const form = new FormData();
  form.append("file", file, file.name);
  return call<Job>("/runs", { method: "POST", body: form });
}

export function fetchJob(id: string): Promise<Job> {
  return call<Job>(run(id));
}

export function fetchResult(id: string): Promise<PlanResult> {
  return call<PlanResult>(`${run(id)}/result`);
}

export function assignLayers(
  id: string,
  overrides: Record<string, string>,
  boundaryLayer: string | null,
): Promise<Job> {
  return post<Job>(`${run(id)}/layers`, { overrides, boundary_layer: boundaryLayer });
}

export function checkPoint(
  id: string,
  point: { x: number; y: number; species_type: Species; id?: string },
  signal?: AbortSignal,
): Promise<CheckResult> {
  return post<CheckResult>(`${run(id)}/check`, point, signal);
}

export function validateEdits(
  id: string,
  payload: EditsPayload,
  signal?: AbortSignal,
): Promise<{ valid: boolean; issues: EditIssue[]; edited: string[] }> {
  return post(`${run(id)}/validate-edits`, payload, signal);
}

export function saveEdits(
  id: string,
  payload: EditsPayload,
): Promise<{ saved: boolean; placements: Placement[]; edited: string[]; removed: string[] }> {
  return post(`${run(id)}/save-edits`, payload);
}

export function fetchVisualStatus(): Promise<VisualStatus> {
  return call<VisualStatus>("/visualize/status");
}

export function visualize(
  id: string,
  season: Season,
  provider: ImageProvider | null,
  signal?: AbortSignal,
): Promise<Visualization> {
  return post<Visualization>(`${run(id)}/visualize`, { season, provider }, signal);
}

function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition") ?? "";
  const encoded = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1]);
    } catch {
      return fallback;
    }
  }
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : fallback;
}

export async function download(id: string, kind: "original-dxf" | "edited-dxf" | "report"): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${run(id)}/${kind}`);
  } catch {
    throw new ApiError("Нет связи с сервером расчёта", 0);
  }
  if (!response.ok) {
    throw await readError(response);
  }
  const fallback = kind === "report" ? "greenplan.json" : "greenplan.dxf";
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFrom(response, fallback);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}
