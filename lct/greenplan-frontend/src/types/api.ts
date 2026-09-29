export type PlantingType = "tree" | "shrub" | "groundcover";

export type JobStatus =
  | "UPLOADED"
  | "QUEUED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED";

export interface Rule {
  id: string;
  object: string;
  planting: PlantingType;
  min_distance_m: number;
  source: {
    act: string;
    clause: string;
  };
  verified: boolean;
}

export interface Placement {
  id: number;
  x: number;
  y: number;
  species_type: PlantingType;
  species: string | null;
  allowed: boolean;
  rationale: Rule[];
  distances: Array<{
    feature: string;
    distance_m: number;
    required_m: number;
    passed: boolean;
  }>;
}

export interface Rejection {
  id: number;
  x: number;
  y: number;
  species_type: PlantingType;
  violated: Rule;
  reason: string;
}

export interface JobParameters {
  mode: "automatic";
}

export interface Job {
  id: string;
  status: JobStatus;
  stage?: string;
  progress?: number;
  inputFile: string;
  parameters: JobParameters;
  error?: string;
}

export interface JobResult {
  job: Job;

  placements: Placement[];

  rejections: Rejection[];

  summary: {
    totalPlacements: number;
    trees: number;
    shrubs: number;
    groundcovers: number;
    groundcoversAreaM2?: number;
    rejections: number;
    normsPassed?: boolean;
  };

  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };

  features: Array<{
    id: string;
    type:
      | "site"
      | "building"
      | "water"
      | "gas"
      | "cable"
      | "powerline"
      | "road";
    points: Array<{
      x: number;
      y: number;
    }>;
  }>;
}
