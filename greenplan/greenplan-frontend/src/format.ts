import type { Rule, Species } from "./types";

export const TIGHT_MARGIN_M = 0.5;

const formatters = new Map<number, Intl.NumberFormat>();

export function num(value: number, digits = 0): string {
  let formatter = formatters.get(digits);
  if (!formatter) {
    formatter = new Intl.NumberFormat("ru-RU", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    formatters.set(digits, formatter);
  }
  return formatter.format(value);
}

export function meters(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${num(value, digits)} м`;
}

export function normValue(value: number): string {
  return num(value, Number.isInteger(Math.round(value * 1000) / 100) ? 1 : 2);
}

export function norm(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${normValue(value)} м`;
}

export function area(value: number): string {
  if (value >= 10000) return `${num(value / 10000, 2)} га`;
  return `${num(value, 0)} м²`;
}

export function plural(value: number, forms: [string, string, string]): string {
  const n = Math.abs(value) % 100;
  const last = n % 10;
  if (n > 10 && n < 20) return forms[2];
  if (last > 1 && last < 5) return forms[1];
  if (last === 1) return forms[0];
  return forms[2];
}

export function count(value: number, forms: [string, string, string]): string {
  return `${num(value)} ${plural(value, forms)}`;
}

export function lowerFirst(text: string): string {
  if (text.length > 1 && text[1] === text[1].toUpperCase() && text[1] !== text[1].toLowerCase()) return text;
  return text.charAt(0).toLowerCase() + text.slice(1);
}

export const SPECIES_NAME: Record<Species, string> = {
  tree: "Дерево",
  shrub: "Кустарник",
};

export const PLANTING_LABEL: Record<string, string> = {
  tree: "деревья",
  shrub: "кустарники",
  any: "любые посадки",
};

export const METHOD_LABEL: Record<string, string> = {
  config: "шаблон",
  dictionary: "словарь",
  fuzzy: "похоже",
  override: "вручную",
  content: "только надписи",
  block: "блок",
  unknown: "не распознан",
};

export function ruleNorm(rule: Pick<Rule, "kind" | "min_distance_m" | "zone_m">): string {
  if (rule.kind === "ban") return `зона ${norm(rule.zone_m)}`;
  if (rule.kind === "not_regulated") return "не нормируется";
  return `не менее ${norm(rule.min_distance_m)}`;
}

export function marginTone(margin: number | null | undefined): "ok" | "tight" | "stop" | "none" {
  if (margin === null || margin === undefined) return "none";
  if (margin < 0) return "stop";
  if (margin < TIGHT_MARGIN_M) return "tight";
  return "ok";
}

export type LayerGroup = "buildings" | "roads" | "networks" | "power" | "green" | "other";

export const GROUP_LABEL: Record<LayerGroup, string> = {
  buildings: "Здания и МАФ",
  roads: "Проезды и дорожки",
  networks: "Подземные сети",
  power: "ВЛ и освещение",
  green: "Газоны",
  other: "Прочее",
};

export const KIND_GROUP: Record<string, LayerGroup> = {
  BUILDING: "buildings",
  MAF: "buildings",
  RETAINING_WALL: "buildings",
  SLOPE: "other",
  ROAD: "roads",
  PAVEMENT: "roads",
  TRAM_TRACK: "roads",
  PIPE_WATER: "networks",
  PIPE_SEWER: "networks",
  PIPE_DRAINAGE: "networks",
  PIPE_GAS: "networks",
  PIPE_HEAT: "networks",
  CABLE: "networks",
  POWERLINE: "power",
  POWERLINE_04KV: "power",
  POWERLINE_6_10KV: "power",
  POWERLINE_35KV: "power",
  POWERLINE_110KV: "power",
  LIGHTING: "power",
  EXISTING_GREEN: "green",
  BIN: "other",
  SITE_BOUNDARY: "other",
};

export interface KindStyle {
  token: string;
  width: number;
  dash?: number[];
  fill?: string;
}

export const KIND_STYLE: Record<string, KindStyle> = {
  BUILDING: { token: "--k-building", width: 1.2, fill: "--k-building-fill" },
  MAF: { token: "--k-maf", width: 0.8 },
  RETAINING_WALL: { token: "--k-building", width: 1.6 },
  SLOPE: { token: "--k-other", width: 0.9, dash: [2, 3] },
  ROAD: { token: "--k-road", width: 1.1 },
  PAVEMENT: { token: "--k-pavement", width: 0.8 },
  TRAM_TRACK: { token: "--k-road", width: 1.4, dash: [6, 3] },
  PIPE_WATER: { token: "--k-water", width: 1.4 },
  PIPE_SEWER: { token: "--k-sewer", width: 1.4 },
  PIPE_DRAINAGE: { token: "--k-drain", width: 1.2, dash: [5, 3] },
  PIPE_GAS: { token: "--k-gas", width: 1.4, dash: [8, 3] },
  PIPE_HEAT: { token: "--k-heat", width: 1.4 },
  CABLE: { token: "--k-cable", width: 1.1, dash: [3, 3] },
  POWERLINE: { token: "--k-power", width: 1.4, dash: [10, 4, 2, 4] },
  POWERLINE_04KV: { token: "--k-power", width: 1.4, dash: [10, 4, 2, 4] },
  POWERLINE_6_10KV: { token: "--k-power", width: 1.6, dash: [10, 4, 2, 4] },
  POWERLINE_35KV: { token: "--k-power", width: 1.8, dash: [10, 4, 2, 4] },
  POWERLINE_110KV: { token: "--k-power", width: 2, dash: [10, 4, 2, 4] },
  LIGHTING: { token: "--k-light", width: 1 },
  EXISTING_GREEN: { token: "--k-green", width: 0.6, fill: "--k-green-fill" },
  BIN: { token: "--k-other", width: 1 },
  SITE_BOUNDARY: { token: "--k-other", width: 0.8, dash: [4, 4] },
};

export const FALLBACK_STYLE: KindStyle = { token: "--k-other", width: 0.8 };
