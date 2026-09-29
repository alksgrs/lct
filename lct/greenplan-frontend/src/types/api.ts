export type PlantingType =
  | "tree"
  | "shrub"
  | "groundcover";

export type JobStatus =
  | "QUEUED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED";

export interface Rule {
  id: string;
  object: string;
  planting: PlantingType;
  min_distance_m: number;
  source: string;
  clause: string;
  verified: boolean;
}

export interface Placement {
  id: string;
  x: number;
  y: number;

  species_type: PlantingType;
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

  species_type: PlantingType;

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

export interface Job {
  id: string;

  status:
    | "QUEUED"
    | "PROCESSING"
    | "COMPLETED"
    | "FAILED";

  progress: number;

  stage: string;

  error?: string | null;
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
