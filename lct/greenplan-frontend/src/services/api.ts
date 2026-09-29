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

        coordinates: [
          number,
          number
        ];
      }
    | {
        type: "LineString";

        coordinates: [
          number,
          number
        ][];
      }
    | {
        type: "Polygon";

        coordinates: [
          [
            number,
            number
          ][]
        ][];
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


// ---------------------------------------------------------
// HTTP HELPER
// ---------------------------------------------------------

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {

  let response: Response;

  try {
    response = await fetch(
      `${API_URL}${path}`,
      options
    );
  } catch {
    throw new Error(
      "Не удалось подключиться к бекенду. " +
      "Убедитесь, что GreenPlan API запущен на порту 8000."
    );
  }

  if (!response.ok) {
    let message =
      `Ошибка API: ${response.status}`;

    try {
      const data =
        await response.json();

      if (
        typeof data?.detail ===
        "string"
      ) {
        message = data.detail;
      }
    } catch {
      // Ответ не JSON — оставляем
      // стандартное сообщение.
    }

    throw new Error(
      message
    );
  }

  return response.json() as Promise<T>;
}


// ---------------------------------------------------------
// NORMALIZE JOB
// ---------------------------------------------------------

function normalizeJob(
  data: any
): Job {

  const rawStatus =
    String(
      data?.status ?? "queued"
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
    id:
      data?.id ??
      data?.run_id,

    status,

    progress:
      Number(
        data?.progress ?? 0
      ),

    stage:
      data?.stage ??
      "",

    error:
      data?.error ??
      null,
  };
}


// ---------------------------------------------------------
// CREATE JOB
// ---------------------------------------------------------

export async function createJob(
  file: File
): Promise<Job> {

  const formData =
    new FormData();

  formData.append(
    "file",
    file,
    file.name
  );

  const data =
    await request<any>(
      "/runs",
      {
        method: "POST",
        body: formData,
      }
    );

  return normalizeJob(
    data
  );
}


// ---------------------------------------------------------
// GET JOB STATUS
// ---------------------------------------------------------

export async function getJob(
  jobId: string
): Promise<Job> {

  const data =
    await request<any>(
      `/runs/${encodeURIComponent(
        jobId
      )}`
    );

  return normalizeJob(
    data
  );
}


// ---------------------------------------------------------
// GET RESULT
// ---------------------------------------------------------

export async function getResult(
  jobId: string
): Promise<JobResult> {

  return request<JobResult>(
    `/runs/${encodeURIComponent(
      jobId
    )}/result`
  );
}


// ---------------------------------------------------------
// DOWNLOAD DXF
// ---------------------------------------------------------

export async function downloadDxf(
  jobId: string
): Promise<void> {

  const response =
    await fetch(
      `${API_URL}/runs/${encodeURIComponent(
        jobId
      )}/dxf`
    );

  if (!response.ok) {
    let message =
      `Не удалось скачать DXF: ${response.status}`;

    try {
      const data =
        await response.json();

      if (
        typeof data?.detail ===
        "string"
      ) {
        message = data.detail;
      }
    } catch {
      // ignore
    }

    throw new Error(
      message
    );
  }

  const blob =
    await response.blob();

  const url =
    URL.createObjectURL(
      blob
    );

  const link =
    document.createElement(
      "a"
    );

  link.href = url;

  link.download =
    "greenplan_result.dxf";

  document.body.appendChild(
    link
  );

  link.click();

  link.remove();

  URL.revokeObjectURL(
    url
  );
}


// ---------------------------------------------------------
// HEALTH CHECK
// ---------------------------------------------------------

export async function checkApi():
  Promise<boolean> {

  try {
    await request(
      "/health"
    );

    return true;
  } catch {
    return false;
  }
}
