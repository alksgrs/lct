from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from shapely.geometry import Point
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from greenplan.config.overrides import ALLOWED_KINDS, validate_overrides
from greenplan import visual
from greenplan.constraints.constraints import BOUNDARY_LABELS
from greenplan.models import FeatureKind, RuleKind
from greenplan.pipeline import SPECIES_ORDER, plan_species, prepare_site
from greenplan.planner.config import load_planting_config
from greenplan.planner.greening import load_greening_config, plan_greening
from greenplan.planner.hex_grid import AreaTooLarge
from greenplan.planner.point_checker import find_violation_detail
from greenplan.planner.rationale import check_point
from greenplan.rules.loader import load_pending_rules, load_rules
from greenplan.rules.rule_selector import get_rules
from greenplan.writer.dxf_writer import LAYERS as OUTPUT_LAYERS
from greenplan.writer.dxf_writer import write_plan
from greenplan.writer.geometry import geometry_to_json
from greenplan.writer.serialize import OBJECT_LABELS, greening_to_dict, lower_first, rejection_reason, ru, rule_to_dict

BASE_DIR = Path(__file__).resolve().parent
RULES_PATH = Path(os.environ.get("GREENPLAN_RULES", BASE_DIR / "data" / "rules" / "regulations.yaml"))
PLANTING_PATH = Path(os.environ.get("GREENPLAN_PLANTING", BASE_DIR / "data" / "rules" / "planting.yaml"))
LAYERS_PATH = Path(os.environ.get("GREENPLAN_LAYERS", BASE_DIR / "data" / "config" / "layers.yaml"))
RUNS_DIR = Path(os.environ.get("GREENPLAN_RUNS_DIR", BASE_DIR / ".greenplan_runs"))
RUNS_DIR.mkdir(parents=True, exist_ok=True)

CORS_ORIGINS = os.environ.get(
    "GREENPLAN_CORS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
).split(",")

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
SPECIES_LABELS = {"tree": "Дерево", "shrub": "Кустарник"}
KIND_LABELS = {**OBJECT_LABELS, "ANNOTATION": "Не учитывать"}

app = FastAPI(
    title="GreenPlan API",
    version="3.0.0",
    description="Расчёт плана озеленения по DXF с проверкой нормативных отступов до сетей и объектов.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


class PlacementEdit(BaseModel):
    id: str
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class NewPlacement(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    species_type: str


class EditsRequest(BaseModel):
    placements: list[PlacementEdit] = Field(default_factory=list)
    added: list[NewPlacement] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)


class CheckRequest(BaseModel):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    species_type: str
    id: str | None = None


class VisualizeRequest(BaseModel):
    season: Literal["summer", "autumn", "winter"] = "summer"
    seed: int | None = Field(default=None, ge=0, le=2**31)
    provider: Literal["yandexart", "gigachat", "kandinsky", "pollinations"] | None = None


class LayersRequest(BaseModel):
    overrides: dict[str, str] = Field(default_factory=dict)
    boundary_layer: str | None = None


def set_job(job_id: str, **values: Any) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(values)


def get_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Расчёт не найден")
        return dict(job)


def completed_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job["status"] == "failed":
        raise HTTPException(status_code=409, detail=job.get("error") or "Расчёт завершился ошибкой")
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Расчёт ещё не завершён")
    return job


def tightest(checks) -> dict[str, Any] | None:
    best = None
    for check in checks:
        margin = check.margin_m
        if check.status != "allowed" or margin is None:
            continue
        if best is None or margin < best[1]:
            best = (check.rule.id, margin, check.distance_m)
    if best is None:
        return None
    return {"rule_id": best[0], "margin_m": round(best[1], 3), "distance_m": round(best[2], 3)}


def placement_record(placement_id: str, x: float, y: float, species_type: str, checks) -> dict[str, Any]:
    return {
        "id": placement_id,
        "x": round(float(x), 3),
        "y": round(float(y), 3),
        "species_type": species_type,
        "tightest": tightest(checks),
    }


def feature_records(features) -> list[dict[str, Any]]:
    records = []
    for index, feature in enumerate(features):
        geometry = geometry_to_json(feature.geom)
        if geometry is None:
            continue
        records.append({
            "id": f"f{index}",
            "kind": feature.kind.value,
            "layer": feature.source_layer,
            "method": feature.match_method,
            "geometry": geometry,
        })
    return records


def rule_summary(rules, site, placements_by_species, rejections) -> list[dict[str, Any]]:
    rejected = {}
    for rejection in rejections:
        rejected[rejection.violated.id] = rejected.get(rejection.violated.id, 0) + 1

    closest: dict[str, float] = {}
    for species_type, placements in placements_by_species.items():
        for placement in placements:
            for check in placement.rule_checks:
                if check.distance_m is None:
                    continue
                current = closest.get(check.rule.id)
                if current is None or check.distance_m < current:
                    closest[check.rule.id] = check.distance_m

    summary = []
    for rule in rules:
        data = rule_to_dict(rule)
        present = site.index.has(rule.object)
        if rule.kind == RuleKind.NOT_REGULATED:
            state = "not_regulated" if present else "not_applicable"
        else:
            state = "applied" if present else "not_applicable"
        data.update({
            "state": state,
            "objects_found": present,
            "rejected": rejected.get(rule.id, 0),
            "closest_m": None if rule.id not in closest else round(closest[rule.id], 3),
        })
        summary.append(data)
    return summary


def layer_records(parsed) -> list[dict[str, Any]]:
    unresolved = {item["layer"]: item for item in parsed.unresolved_layers}
    records = []
    for layer in parsed.layers:
        kind = layer["kind"]
        records.append({
            "layer": layer["layer"],
            "kind": kind,
            "kind_label": KIND_LABELS.get(kind, "") if kind else None,
            "method": layer["method"],
            "entity_count": layer["entity_count"],
            "entity_types": layer["entity_types"],
            "typed_by_block": layer.get("typed_by_block", 0),
            "tokens": unresolved.get(layer["layer"], {}).get("tokens", []),
        })
    return records


def allowed_kinds() -> list[dict[str, str]]:
    order = list(KIND_LABELS)
    kinds = sorted(ALLOWED_KINDS, key=lambda value: order.index(value) if value in order else len(order))
    return [{"value": kind, "label": KIND_LABELS.get(kind, kind)} for kind in kinds]


def pending_rules() -> list[dict[str, Any]]:
    return [{**rule, "object_label": OBJECT_LABELS.get(rule["object"], rule["object"])}
            for rule in load_pending_rules(str(RULES_PATH))]


def build_result(job_id: str, job: dict[str, Any], site, rules, placements_by_species, rejections,
                 started: float, greening=None) -> dict[str, Any]:
    placements = []
    for species_type, items in placements_by_species.items():
        for index, placement in enumerate(items):
            placements.append(placement_record(f"{species_type}-{index}", placement.point.x,
                                               placement.point.y, species_type, placement.rule_checks))

    rejection_records = [
        {
            "id": f"r{index}",
            "x": round(float(rejection.point.x), 3),
            "y": round(float(rejection.point.y), 3),
            "species_type": rejection.species_type,
            "rule_id": rejection.violated.id,
            "distance_m": None if rejection.distance_m is None else round(rejection.distance_m, 3),
            "shortfall_m": None if rejection.distance_m is None
            else round(rejection.violated.limit_m - rejection.distance_m, 3),
            "reason": rejection_reason(rejection),
        }
        for index, rejection in enumerate(rejections)
    ]

    parsed = site.parsed
    layers = layer_records(parsed)
    summary = {
        "trees": len(placements_by_species.get("tree", [])),
        "shrubs": len(placements_by_species.get("shrub", [])),
        "rejections": len(rejection_records),
        "features": len(parsed.features),
        "layers_total": len(layers),
        "layers_unresolved": len(parsed.unresolved_layers),
        "area_m2": round(site.boundary.area, 1),
        "lawn_m2": round(greening.lawn_area_m2, 1) if greening else 0.0,
        "hedges_m": round(greening.hedge_length_m, 1) if greening else 0.0,
        "flowerbeds": len(greening.flowerbeds) if greening else 0,
        "duration_s": round(time.monotonic() - started, 1),
    }
    return {
        "run_id": job_id,
        "filename": job.get("filename"),
        "status": "completed",
        "summary": summary,
        "site": {
            "method": site.boundary_method,
            "method_label": BOUNDARY_LABELS.get(site.boundary_method, site.boundary_method),
            "outliers": site.boundary_outliers,
            "area_m2": summary["area_m2"],
            "geometry": geometry_to_json(site.boundary, 0.05),
        },
        "rules": rule_summary(rules, site, placements_by_species, rejections),
        "greening": greening_to_dict(greening),
        "pending_rules": pending_rules(),
        "placements": placements,
        "rejections": rejection_records,
        "features": feature_records(parsed.features),
        "layers": layers,
        "allowed_kinds": allowed_kinds(),
        "overrides": job.get("overrides", {}),
        "boundary_layer": job.get("boundary_layer"),
        "species_labels": SPECIES_LABELS,
    }


def run_calculation(job_id: str) -> None:
    job = get_job(job_id)
    input_path = Path(job["input_path"])
    output_path = input_path.with_name("result.dxf")
    started = time.monotonic()
    for stale in (output_path, input_path.with_name("result_edited.dxf")):
        stale.unlink(missing_ok=True)
    try:
        set_job(job_id, status="processing", progress=5, stage="Чтение DXF и распознавание слоёв")
        site = prepare_site(str(input_path), str(LAYERS_PATH), job.get("overrides") or None,
                            job.get("boundary_layer"))
        set_job(job_id, site=site, layers=layer_records(site.parsed), progress=30,
                stage="Граница участка и допустимые зоны")

        rules = load_rules(str(RULES_PATH))
        config = load_planting_config(str(PLANTING_PATH))
        placements_by_species, rejections, trees = {}, [], []
        for step, species_type in enumerate(SPECIES_ORDER):
            set_job(job_id, progress=40 + step * 25,
                    stage="Размещение деревьев" if species_type == "tree" else "Размещение кустарников")
            placements, rejected = plan_species(
                site, rules, config, species_type,
                obstacles=trees if species_type == "shrub" else None,
            )
            if species_type == "tree":
                trees = [p.point for p in placements]
            placements_by_species[species_type] = placements
            rejections.extend(rejected)

        set_job(job_id, progress=82, stage="Газоны, изгороди, цветники")
        greening, placements_by_species["shrub"] = plan_greening(
            site, rules, load_greening_config(str(PLANTING_PATH)), trees, placements_by_species["shrub"],
        )

        set_job(job_id, progress=92, stage="Сбор результата")
        result = build_result(job_id, job, site, rules, placements_by_species, rejections, started, greening)
        (input_path.parent / "result.json").write_text(
            json.dumps({k: v for k, v in result.items() if k != "features"}, ensure_ascii=False),
            encoding="utf-8",
        )
        set_job(job_id, status="completed", progress=100, stage="Готово", error=None, result=result,
                rules=rules, config=config, dxf_path=str(output_path),
                edited_dxf_path=str(input_path.with_name("result_edited.dxf")), has_saved_edits=False,
                original_placements=list(result["placements"]), edited_placements=None)
    except AreaTooLarge as error:
        set_job(job_id, status="failed", progress=100, stage="Нужна граница участка",
                error=f"{error} Укажите слой с контуром границы участка или назначьте типы слоям.",
                needs_layers=True)
    except ValueError as error:
        set_job(job_id, status="failed", progress=100, stage="Ошибка исходных данных",
                error=str(error), needs_layers=True)
    except Exception as error:
        set_job(job_id, status="failed", progress=100, stage="Ошибка расчёта",
                error=f"Не удалось обработать файл: {error}", needs_layers=False)


def start_calculation(job_id: str) -> None:
    threading.Thread(target=run_calculation, args=(job_id,), daemon=True).start()


def check_records(point: Point, species_type: str, site, rules) -> list[dict[str, Any]]:
    records = []
    for check in check_point(point, get_rules(rules, species_type), site.index):
        nearest = None
        if check.status != "not_applicable":
            geometry = site.index.nearest(point, check.rule.object)
            if geometry is not None:
                target = nearest_points(point, geometry)[1]
                nearest = [round(target.x, 3), round(target.y, 3)]
        records.append({
            "rule_id": check.rule.id,
            "status": check.status,
            "distance_m": None if check.distance_m is None else round(check.distance_m, 3),
            "margin_m": None if check.margin_m is None else round(check.margin_m, 3),
            "nearest": nearest,
            "message": check.message,
        })
    return records


def spacing_issues(candidate: dict[str, dict], edited_ids: set[str], config) -> list[dict[str, Any]]:
    issues = []
    groups: dict[str, list[dict]] = {}
    for item in candidate.values():
        groups.setdefault(item["species_type"], []).append(item)

    trees = {species: (STRtree([Point(p["x"], p["y"]) for p in items]), items)
             for species, items in groups.items()}

    for placement_id in sorted(edited_ids):
        item = candidate[placement_id]
        point = Point(item["x"], item["y"])
        species_type = item["species_type"]
        limit = float(config[species_type]["min_spacing_m"])
        tree, items = trees[species_type]
        for found in tree.query(point, predicate="dwithin", distance=limit - 1e-9):
            other = items[int(found)]
            if other["id"] == placement_id:
                continue
            distance = point.distance(Point(other["x"], other["y"]))
            issues.append({
                "id": placement_id, "other_id": other["id"], "code": "plant_spacing",
                "message": f"До соседней посадки {ru(distance, 2)} м, нужно не меньше {ru(limit)} м",
            })
            break

        tree_gap = float(config.get("shrub", {}).get("min_distance_to_trees_m", 0))
        if tree_gap <= 0 or "tree" not in trees or "shrub" not in trees:
            continue
        other_species = "tree" if species_type == "shrub" else "shrub"
        tree, items = trees[other_species]
        for found in tree.query(point, predicate="dwithin", distance=tree_gap - 1e-9):
            other = items[int(found)]
            distance = point.distance(Point(other["x"], other["y"]))
            issues.append({
                "id": placement_id, "other_id": other["id"], "code": "tree_shrub_gap",
                "message": f"Кустарник и дерево в {ru(distance, 2)} м друг от друга, нужно не меньше {ru(tree_gap)} м",
            })
            break
    return issues


def validate_edits(job: dict[str, Any], request: EditsRequest) -> dict[str, Any]:
    result = job["result"]
    existing = {p["id"]: p for p in result["placements"]}
    edits = request.placements
    ids = [e.id for e in edits]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="В запросе повторяются ID посадок")
    unknown = [i for i in ids + request.removed if i not in existing]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Неизвестные ID посадок: {', '.join(unknown[:10])}")
    added_ids = [item.id for item in request.added]
    if len(set(added_ids)) != len(added_ids) or set(added_ids) & set(existing):
        raise HTTPException(status_code=422, detail="ID новых посадок должны быть уникальными")
    if any(item.species_type not in SPECIES_ORDER for item in request.added):
        raise HTTPException(status_code=422, detail="species_type: tree или shrub")

    removed = set(request.removed)
    candidate = {key: dict(value) for key, value in existing.items() if key not in removed}
    edited = set()
    for edit in edits:
        if edit.id in removed:
            continue
        item = candidate[edit.id]
        if abs(item["x"] - edit.x) > 1e-6 or abs(item["y"] - edit.y) > 1e-6:
            item["x"], item["y"] = round(float(edit.x), 3), round(float(edit.y), 3)
            edited.add(edit.id)
    for item in request.added:
        candidate[item.id] = {"id": item.id, "x": round(item.x, 3), "y": round(item.y, 3),
                              "species_type": item.species_type, "tightest": None}
        edited.add(item.id)

    site, rules, config = job["site"], job["rules"], job["config"]
    boundary = site.boundary.buffer(1e-6)
    issues = []
    for placement_id in sorted(edited):
        item = candidate[placement_id]
        point = Point(item["x"], item["y"])
        if not boundary.covers(point):
            issues.append({"id": placement_id, "code": "outside_site",
                           "message": "Точка за границей участка"})
            continue
        if site.index.contains(point, FeatureKind.MAF):
            issues.append({"id": placement_id, "code": "inside_maf",
                           "message": "Точка внутри малой архитектурной формы"})
            continue
        rule, distance = find_violation_detail(point, get_rules(rules, item["species_type"]), site.index)
        if rule is not None:
            label = lower_first(OBJECT_LABELS.get(rule.object.value, rule.object.value))
            if rule.kind == RuleKind.BAN:
                message = f"Точка в охранной зоне {ru(rule.zone_m)} м: {label}"
            else:
                message = f"До объекта «{label}» {ru(distance, 2)} м, нужно не меньше {ru(rule.limit_m)} м"
            issues.append({"id": placement_id, "code": "norm", "rule_id": rule.id, "message": message})

    issues.extend(spacing_issues(candidate, edited, config))

    for placement_id in edited:
        item = candidate[placement_id]
        checks = check_point(Point(item["x"], item["y"]), get_rules(rules, item["species_type"]), site.index)
        item["tightest"] = tightest(checks)

    return {"valid": not issues, "issues": issues, "placements": list(candidate.values()),
            "edited": sorted(edited), "removed": sorted(removed)}


def build_report(job: dict[str, Any]) -> dict[str, Any]:
    result = job["result"]
    site, rules = job["site"], job["rules"]
    placements = []
    not_applicable = set()
    for item in result["placements"]:
        checks = []
        for check in check_point(Point(item["x"], item["y"]), get_rules(rules, item["species_type"]),
                                 site.index):
            if check.status == "not_applicable":
                not_applicable.add(check.rule.id)
                continue
            checks.append({
                "rule_id": check.rule.id,
                "status": check.status,
                "distance_m": None if check.distance_m is None else round(check.distance_m, 3),
                "margin_m": None if check.margin_m is None else round(check.margin_m, 3),
            })
        placements.append({**{k: item[k] for k in ("id", "x", "y", "species_type")}, "checks": checks})
    return {
        "run_id": result["run_id"],
        "input": result["filename"],
        "edited": job.get("has_saved_edits", False),
        "summary": result["summary"],
        "site": {k: v for k, v in result["site"].items() if k != "geometry"},
        "rules": result["rules"],
        "pending_rules": result["pending_rules"],
        "not_applicable_rules": sorted(not_applicable),
        "placements": placements,
        "rejections": result["rejections"],
        "greening": result.get("greening"),
        "layers": result["layers"],
        "overrides": result["overrides"],
    }


def job_status(job: dict[str, Any]) -> dict[str, Any]:
    data = {
        "id": job["id"],
        "filename": job.get("filename"),
        "status": job["status"],
        "progress": job.get("progress", 0),
        "stage": job.get("stage", ""),
        "error": job.get("error"),
    }
    if job["status"] == "failed" and job.get("needs_layers") and job.get("layers"):
        data["layers"] = job["layers"]
        data["allowed_kinds"] = allowed_kinds()
        data["overrides"] = job.get("overrides", {})
        data["boundary_layer"] = job.get("boundary_layer")
    return data


@app.get("/health", tags=["Сервис"], summary="Проверка доступности")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/rules", tags=["Нормы"], summary="Справочник норм, по которому идёт расчёт")
def list_rules():
    return {
        "rules": [rule_to_dict(rule) for rule in load_rules(str(RULES_PATH))],
        "pending_rules": pending_rules(),
    }


@app.post("/runs", tags=["Расчёт"], summary="Загрузить DXF и запустить расчёт")
async def create_run(file: UploadFile = File(...), boundary_layer: str | None = Form(None)):
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="Нужен файл в формате DXF")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл пустой")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 200 МБ")

    job_id = uuid.uuid4().hex
    job_dir = RUNS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.dxf"
    input_path.write_bytes(content)
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id, "status": "queued", "progress": 0, "stage": "Файл загружен",
            "filename": file.filename, "input_path": str(input_path), "overrides": {},
            "boundary_layer": boundary_layer or None,
        }
    start_calculation(job_id)
    return job_status(get_job(job_id))


@app.get("/runs/{job_id}", tags=["Расчёт"], summary="Статус расчёта")
def get_run(job_id: str):
    return job_status(get_job(job_id))


@app.get("/runs/{job_id}/result", tags=["Расчёт"], summary="Результат: посадки, отказы, нормы, слои")
def get_result(job_id: str):
    job = completed_job(job_id)
    return {**job["result"], "has_saved_edits": job.get("has_saved_edits", False)}


@app.post("/runs/{job_id}/layers", tags=["Слои"],
          summary="Назначить типы слоям вручную и пересчитать план")
def assign_layers(job_id: str, request: LayersRequest):
    job = get_job(job_id)
    if job["status"] in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="Расчёт ещё идёт")
    try:
        overrides = validate_overrides(request.overrides)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    set_job(job_id, status="queued", progress=0, stage="Пересчёт с новыми типами слоёв", error=None,
            overrides=overrides, boundary_layer=request.boundary_layer or None, needs_layers=False,
            has_saved_edits=False)
    start_calculation(job_id)
    return job_status(get_job(job_id))


@app.post("/runs/{job_id}/check", tags=["Проверка"],
          summary="Проверить одну точку по всем нормам")
def check_location(job_id: str, request: CheckRequest):
    job = completed_job(job_id)
    if request.species_type not in SPECIES_ORDER:
        raise HTTPException(status_code=422, detail="species_type: tree или shrub")
    site, rules = job["site"], job["rules"]
    point = Point(request.x, request.y)
    checks = check_records(point, request.species_type, site, rules)
    inside = site.boundary.buffer(1e-6).covers(point)
    in_maf = site.index.contains(point, FeatureKind.MAF)
    blocking = [c for c in checks if c["status"] in ("violated", "banned_zone")]
    return {
        "x": request.x,
        "y": request.y,
        "species_type": request.species_type,
        "inside_site": inside,
        "inside_maf": in_maf,
        "valid": inside and not in_maf and not blocking,
        "checks": checks,
    }


@app.post("/runs/{job_id}/validate-edits", tags=["Редактирование"],
          summary="Проверить перемещённые точки")
def validate_run_edits(job_id: str, request: EditsRequest):
    job = completed_job(job_id)
    validation = validate_edits(job, request)
    return {"valid": validation["valid"], "issues": validation["issues"], "edited": validation["edited"]}


@app.post("/runs/{job_id}/save-edits", tags=["Редактирование"],
          summary="Сохранить правки в отдельный DXF")
def save_run_edits(job_id: str, request: EditsRequest):
    job = completed_job(job_id)
    validation = validate_edits(job, request)
    if not validation["valid"]:
        raise HTTPException(status_code=422,
                            detail={"message": "Есть нарушения", "issues": validation["issues"]})

    Path(job["edited_dxf_path"]).unlink(missing_ok=True)
    result = dict(job["result"])
    result["placements"] = validation["placements"]
    set_job(job_id, result=result, has_saved_edits=True, edited_placements=list(validation["placements"]))
    return {"saved": True, "placements": validation["placements"], "edited": validation["edited"],
            "removed": validation["removed"]}


file_locks: dict[str, threading.Lock] = {}


def _ensure_dxf(job: dict[str, Any], path_key: str, placements_key: str) -> Path:
    path = Path(job[path_key])
    with jobs_lock:
        lock = file_locks.setdefault(f"{job['id']}:{path_key}", threading.Lock())
    with lock:
        if not path.exists():
            temp = path.with_name(path.stem + ".tmp.dxf")
            write_plan(job["input_path"], str(temp), job[placements_key], job["result"].get("greening"))
            temp.replace(path)
    return path


def _download(path: Path, filename: str, media_type: str = "application/dxf"):
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=path, media_type=media_type, filename=filename)


def _stem(job: dict[str, Any]) -> str:
    return Path(job.get("filename") or "plan.dxf").stem


@app.get("/runs/{job_id}/original-dxf", tags=["Файлы"], summary="DXF с посадками, как рассчитал сервис")
def download_original_dxf(job_id: str):
    job = completed_job(job_id)
    return _download(_ensure_dxf(job, "dxf_path", "original_placements"), f"{_stem(job)}_озеленение.dxf")


@app.get("/runs/{job_id}/edited-dxf", tags=["Файлы"], summary="DXF после ручных правок")
def download_edited_dxf(job_id: str):
    job = completed_job(job_id)
    if not job.get("has_saved_edits"):
        raise HTTPException(status_code=404, detail="Правки ещё не сохранены")
    return _download(_ensure_dxf(job, "edited_dxf_path", "edited_placements"), f"{_stem(job)}_озеленение_правки.dxf")


@app.get("/runs/{job_id}/dxf", tags=["Файлы"], summary="Последняя версия DXF")
def download_dxf(job_id: str):
    job = completed_job(job_id)
    if job.get("has_saved_edits"):
        return download_edited_dxf(job_id)
    return download_original_dxf(job_id)


@app.get("/runs/{job_id}/report", tags=["Файлы"], summary="Отчёт с обоснованием каждой посадки")
def download_report(job_id: str):
    job = completed_job(job_id)
    body = json.dumps(build_report(job), ensure_ascii=False)
    filename = f"{_stem(job)}_обоснование.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.get("/visualize/status", tags=["Визуализация"], summary="Подключён ли генератор изображений")
def visualize_status():
    return visual.status()


@app.post("/runs/{job_id}/visualize", tags=["Визуализация"],
          summary="ИИ-иллюстрация участка по параметрам рассчитанного плана")
def visualize_run(job_id: str, request: VisualizeRequest):
    job = completed_job(job_id)
    site = job["site"]
    objects = sorted({feature.kind.value for feature in site.parsed.features})
    summary = dict(job["result"]["summary"])
    placements = job["result"]["placements"]
    summary["trees"] = sum(p["species_type"] == "tree" for p in placements)
    summary["shrubs"] = len(placements) - summary["trees"]
    try:
        picture = visual.generate(summary, site.boundary_method, objects, request.season, request.seed,
                                  provider=request.provider)
    except visual.VisualizationUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))
    except visual.VisualizationFailed as error:
        raise HTTPException(status_code=502, detail=str(error))
    index = len(job.get("pictures", [])) + 1
    path = Path(job["input_path"]).with_name(f"visualization_{index}.{picture.extension}")
    path.write_bytes(picture.image)
    set_job(job_id, pictures=[*job.get("pictures", []), str(path)])
    return {
        "image": picture.data_url(),
        "prompt": picture.prompt,
        "provider": picture.provider,
        "provider_name": visual.NAMES.get(picture.provider, picture.provider),
        "skipped": picture.meta.get("failed", []),
        "elapsed_s": picture.elapsed_s,
        "season": request.season,
    }


@app.get("/layers/kinds", tags=["Слои"], summary="Типы, которые можно назначить слою")
def layer_kinds():
    return {"kinds": allowed_kinds(), "output_layers": {k: v[0] for k, v in OUTPUT_LAYERS.items()}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)))
