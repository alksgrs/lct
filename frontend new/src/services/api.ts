const API_URL =
  import.meta.env.VITE_API_URL ??
  "http://127.0.0.1:8000";

// ---------------------------------------------------------
// TYPES
// ---------------------------------------------------------

export interface Job {
  id: string;

  status:
    | "QUEUED"
    | "PROCESSING"
    | "COMPLETED"
    | "FAILED"
    | "queued"
    | "processing"
    | "completed"
    | "failed";

  progress: number;
  stage: string;
  error?: string | null;
}

export interface Rule {
  id: string;
  object: string;

  planting:
    | "tree"
    | "shrub"
    | "groundcover";

  min_distance_m: number;
  source: string;
  clause: string;
  verified: boolean;
}

export interface Placement {
  id: string;
  x: number;
  y: number;

  species_type:
    | "tree"
    | "shrub"
    | "groundcover";

  species: string | null;

  status:
    | "allowed"
    | "rejected"
    | "warning";

  rationale: Rule[];
}

export interface PlacementEdit {
  id: string;
  x: number;
  y: number;
}

export interface Rejection {
  id: string;
  x: number;
  y: number;

  species_type:
    | "tree"
    | "shrub"
    | "groundcover";

  violated: Rule;
  reason: string;
}

export interface Feature {
  id: string;

  kind:
    | "building"
    | "road"
    | "water_pipe"
    | "gas_pipe"
    | "cable"
    | "powerline"
    | "site_boundary"
    | "unknown";

  source_layer: string;
  confidence: number;

  geometry?:
    | {
        type: "Point";
        coordinates: [number, number];
      }
    | {
        type: "LineString";
        coordinates: [number, number][];
      }
    | {
        type: "Polygon";
        coordinates: [number, number][][][];
      };
}

export interface JobResult {
  run_id: string;

  status:
    | "completed"
    | "failed";

  placements: Placement[];
  rejections: Rejection[];
  features: Feature[];

  statistics: {
    trees: number;
    shrubs: number;
    groundcovers_area_m2: number;
    total_green_area_m2: number;
    allowed_zones: number;
    rejected_count: number;
  };

  progress?: {
    stage: string;
    progress: number;
  };
}

export interface EditValidationIssue {
  message?: string;
  placement_id?: string;
  id?: string;
  reason?: string;
  [key: string]: unknown;
}

export interface ValidateEditsResponse {
  valid: boolean;
  issues: EditValidationIssue[];
}

export interface SaveEditsResponse {
  saved: boolean;
  valid: boolean;
  result: JobResult;
  dxf_url: string;
  original_dxf_url: string;
  edited_dxf_url: string;
}

// ---------------------------------------------------------
// HTTP HELPERS
// ---------------------------------------------------------

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}${path}`,
      options,
    );
  } catch {
    throw new Error(
      "Не удалось подключиться к бэкенду. " +
        "Убедитесь, что GreenPlan API запущен на порту 8000.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(
        response,
        `Ошибка API: ${response.status}`,
    ));
  }

  return response.json() as Promise<T>;
}

async function getErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const data = await response.json();
    const detail = data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (detail && typeof detail === "object") {
      const messages = [
        typeof detail.message === "string"
          ? detail.message
          : "",
        ...(Array.isArray(detail.issues)
          ? detail.issues.map(
              (issue: EditValidationIssue) =>
                issue.message ?? issue.reason ?? "",
            )
          : []),
      ].filter(Boolean);

      if (messages.length > 0) {
        return messages.join(" ");
      }
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: { msg?: string }) => item.msg ?? "")
        .filter(Boolean);

      if (messages.length > 0) {
        return messages.join(" ");
      }
    }
  } catch {
    // Ответ не JSON — используем сообщение по умолчанию.
  }

  return fallback;
}

// ---------------------------------------------------------
// NORMALIZE JOB
// ---------------------------------------------------------

function normalizeJob(data: any): Job {
  const rawStatus = String(
    data?.status ?? "queued",
  ).toLowerCase();

  let status: Job["status"];

  switch (rawStatus) {
    case "completed":
      status = "COMPLETED";
      break;

    case "processing":
      status = "PROCESSING";
      break;

    case "failed":
      status = "FAILED";
      break;

    case "queued":
    default:
      status = "QUEUED";
      break;
  }

  return {
    id: data?.id ?? data?.run_id ?? "",
    status,
    progress: Number(data?.progress ?? 0),
    stage: data?.stage ?? "",
    error: data?.error ?? null,
  };
}

// ---------------------------------------------------------
// CREATE JOB
// ---------------------------------------------------------

export async function createJob(
  file: File,
): Promise<Job> {
  const formData = new FormData();

  formData.append(
    "file",
    file,
    file.name,
  );

  const data = await request<any>(
    "/runs",
    {
      method: "POST",
      body: formData,
    },
  );

  return normalizeJob(data);
}

// ---------------------------------------------------------
// GET JOB STATUS
// ---------------------------------------------------------

export async function getJob(
  jobId: string,
): Promise<Job> {
  const data = await request<any>(
    `/runs/${encodeURIComponent(jobId)}`,
  );

  return normalizeJob(data);
}

// ---------------------------------------------------------
// GET RESULT
// ---------------------------------------------------------

export async function getResult(
  jobId: string,
): Promise<JobResult> {
  return request<JobResult>(
    `/runs/${encodeURIComponent(jobId)}/result`,
  );
}

// ---------------------------------------------------------
// EDITS: PREPARE PAYLOAD
// ---------------------------------------------------------

function preparePlacementEdits(
  placements: PlacementEdit[],
): PlacementEdit[] {
  return placements.map(({ id, x, y }) => ({
    id,
    x,
    y,
  }));
}

// ---------------------------------------------------------
// VALIDATE EDITS
// ---------------------------------------------------------

export async function validateEdits(
  jobId: string,
  placements: PlacementEdit[],
): Promise<ValidateEditsResponse> {
  return request<ValidateEditsResponse>(
    `/runs/${encodeURIComponent(jobId)}/validate-edits`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        placements: preparePlacementEdits(placements),
      }),
    },
  );
}

// ---------------------------------------------------------
// SAVE EDITS
// ---------------------------------------------------------

export async function saveEdits(
  jobId: string,
  placements: PlacementEdit[],
): Promise<SaveEditsResponse> {
  return request<SaveEditsResponse>(
    `/runs/${encodeURIComponent(jobId)}/save-edits`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        placements: preparePlacementEdits(placements),
      }),
    },
  );
}

// ---------------------------------------------------------
// DOWNLOAD DXF HELPER
// ---------------------------------------------------------

async function downloadDxfVersion(
  jobId: string,
  version:
    | "dxf"
    | "original-dxf"
    | "edited-dxf",
  filename: string,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}/runs/${encodeURIComponent(jobId)}/${version}`,
    );
  } catch {
    throw new Error(
      "Не удалось подключиться к бэкенду при скачивании DXF.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(
        response,
        `Не удалось скачать DXF: ${response.status}`,
      ),
    );
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  link.remove();

  // Освобождаем URL после того, как браузер начал скачивание.
  window.setTimeout(() => {
    URL.revokeObjectURL(objectUrl);
  }, 1000);
}

// ---------------------------------------------------------
// DOWNLOAD ORIGINAL DXF
// ---------------------------------------------------------

export function downloadOriginalDxf(
  jobId: string,
): Promise<void> {
  return downloadDxfVersion(
    jobId,
    "original-dxf",
    "greenplan_original.dxf",
  );
}

// ---------------------------------------------------------
// DOWNLOAD EDITED DXF
// ---------------------------------------------------------

export function downloadEditedDxf(
  jobId: string,
): Promise<void> {
  return downloadDxfVersion(
    jobId,
    "edited-dxf",
    "greenplan_edited.dxf",
  );
}

// ---------------------------------------------------------
// BACKWARD-COMPATIBLE DXF DOWNLOAD
// ---------------------------------------------------------

// Сохраняем старую функцию, чтобы существующие компоненты
// продолжали работать без изменения импортов.
// Бэкенд отдаёт сохранённую редакцию, если она существует;
// иначе отдаёт исходный результат расчёта.

export function downloadDxf(
  jobId: string,
): Promise<void> {
  return downloadDxfVersion(
    jobId,
    "dxf",
    "greenplan_result.dxf",
  );
}

// ---------------------------------------------------------
// HEALTH CHECK
// ---------------------------------------------------------

export async function checkApi(): Promise<boolean> {
  try {
    await request<unknown>("/health");
    return true;
  } catch {
    return false;
  }
}
