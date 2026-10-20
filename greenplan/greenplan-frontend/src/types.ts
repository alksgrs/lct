export type Species = "tree" | "shrub";
export type RuleKind = "distance" | "not_regulated" | "ban";
export type RuleState = "applied" | "not_regulated" | "not_applicable";
export type CheckStatus = "allowed" | "violated" | "not_applicable" | "not_regulated" | "banned_zone";
export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface Rule {
  rule_id: string;
  object: string;
  object_label: string;
  planting: Species | "any";
  kind: RuleKind;
  min_distance_m: number | null;
  zone_m: number | null;
  limit_m: number | null;
  act: string;
  clause: string;
  note: string | null;
  verified: boolean;
  verified_by: string | null;
  verified_at: string | null;
  source_url?: string | null;
  state?: RuleState;
  objects_found?: boolean;
  rejected?: number;
  closest_m?: number | null;
}

export interface PendingRule {
  rule_id: string;
  object: string;
  object_label: string;
  planting: Species | "any";
  kind: RuleKind;
  min_distance_m: number | null;
  zone_m: number | null;
  act: string | null;
  clause: string | null;
  note: string | null;
}

export interface Tightest {
  rule_id: string;
  margin_m: number;
  distance_m: number;
}

export interface Placement {
  id: string;
  x: number;
  y: number;
  species_type: Species;
  tightest: Tightest | null;
}

export interface Rejection {
  id: string;
  x: number;
  y: number;
  species_type: Species;
  rule_id: string;
  distance_m: number | null;
  shortfall_m: number | null;
  reason: string;
}

export type Position = [number, number];

export type Geometry =
  | { type: "Point"; coordinates: Position }
  | { type: "MultiPoint"; coordinates: Position[] }
  | { type: "LineString"; coordinates: Position[] }
  | { type: "MultiLineString"; coordinates: Position[][] }
  | { type: "Polygon"; coordinates: Position[][] }
  | { type: "MultiPolygon"; coordinates: Position[][][] }
  | { type: "GeometryCollection"; geometries: Geometry[] };

export interface Feature {
  id: string;
  kind: string;
  layer: string;
  method: string;
  geometry: Geometry;
}

export interface LayerInfo {
  layer: string;
  kind: string | null;
  kind_label: string | null;
  method: string;
  entity_count: number;
  entity_types: Record<string, number>;
  typed_by_block?: number;
  tokens: string[];
}

export interface KindOption {
  value: string;
  label: string;
}

export interface Summary {
  trees: number;
  shrubs: number;
  rejections: number;
  features: number;
  layers_total: number;
  layers_unresolved: number;
  area_m2: number;
  lawn_m2: number;
  hedges_m: number;
  flowerbeds: number;
  duration_s: number;
}

export interface Hedge {
  id: string;
  length_m: number;
  coordinates: Position[];
}

export interface Flowerbed {
  id: string;
  x: number;
  y: number;
  radius_m: number;
}

export interface Greening {
  lawn: Geometry | null;
  lawn_area_m2: number;
  lawn_offsets_m: Record<string, number>;
  hedges: Hedge[];
  hedge_length_m: number;
  hedge_rule_ids: string[];
  flowerbeds: Flowerbed[];
  shrubs_replaced: number;
}

export interface Site {
  method: string;
  method_label: string;
  outliers: number;
  area_m2: number;
  geometry: Geometry | null;
}

export interface PlanResult {
  run_id: string;
  filename: string | null;
  status: "completed";
  summary: Summary;
  site: Site;
  rules: Rule[];
  pending_rules: PendingRule[];
  greening: Greening | null;
  placements: Placement[];
  rejections: Rejection[];
  features: Feature[];
  layers: LayerInfo[];
  allowed_kinds: KindOption[];
  overrides: Record<string, string>;
  boundary_layer: string | null;
  has_saved_edits: boolean;
}

export interface Job {
  id: string;
  filename: string | null;
  status: JobStatus;
  progress: number;
  stage: string;
  error: string | null;
  layers?: LayerInfo[];
  allowed_kinds?: KindOption[];
  overrides?: Record<string, string>;
  boundary_layer?: string | null;
}

export interface Check {
  rule_id: string;
  status: CheckStatus;
  distance_m: number | null;
  margin_m: number | null;
  nearest: Position | null;
  message: string | null;
}

export interface CheckResult {
  x: number;
  y: number;
  species_type: Species;
  inside_site: boolean;
  inside_maf: boolean;
  valid: boolean;
  checks: Check[];
}

export interface EditIssue {
  id: string;
  code: string;
  message: string;
  rule_id?: string;
  other_id?: string;
}

export interface EditsPayload {
  placements: { id: string; x: number; y: number }[];
  added: { id: string; x: number; y: number; species_type: Species }[];
  removed: string[];
}

export interface RulesCatalog {
  rules: Rule[];
  pending_rules: PendingRule[];
}

export type Season = "summer" | "autumn" | "winter";

export type ImageProvider = "yandexart" | "gigachat" | "kandinsky" | "pollinations";

export interface VisualStatus {
  available: boolean;
  provider: ImageProvider | null;
  providers: ImageProvider[];
  message: string | null;
}

export interface Visualization {
  image: string;
  prompt: string;
  provider: ImageProvider;
  provider_name: string;
  skipped: string[];
  elapsed_s: number;
  season: Season;
}
