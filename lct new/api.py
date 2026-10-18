from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

import ezdxf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from shapely.geometry import Point

from greenplan.parser.dxf_parser import parse_dxf
from greenplan.pipeline import build_plan
from greenplan.constraints.constraints import get_site_boundary
from greenplan.planner.config import load_planting_config
from greenplan.planner.point_checker import find_violation
from greenplan.rules.loader import load_rules
from greenplan.rules.rule_selector import get_rules

BASE_DIR = Path(__file__).resolve().parent
RULES_PATH = BASE_DIR / "data" / "rules" / "sp42.yaml"
PLANTING_PATH = BASE_DIR / "data" / "rules" / "planting.yaml"
LAYERS_PATH = BASE_DIR / "data" / "config" / "layers.yaml"
RUNS_DIR = BASE_DIR / ".greenplan_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

SPECIES_TYPES = ("tree", "shrub", "groundcover")
LAYER_NAMES = {
    "tree": "PLANTING_TREES",
    "shrub": "PLANTING_SHRUBS",
    "groundcover": "PLANTING_GROUNDCOVER",
}
SPECIES_LABELS = {
    "tree": "Дерево",
    "shrub": "Кустарник",
    "groundcover": "Покрытие",
}
KIND_MAP = {
    "BUILDING": "building", "ROAD": "road", "PIPE_WATER": "water_pipe",
    "PIPE_GAS": "gas_pipe", "CABLE": "cable", "POWERLINE": "powerline",
    "SITE_BOUNDARY": "site_boundary", "UNKNOWN": "unknown",
}

app = FastAPI(title="GreenPlan API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


class PlacementEdit(BaseModel):
    id: str
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class EditsRequest(BaseModel):
    placements: list[PlacementEdit]


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


def geometry_to_json(geometry) -> dict[str, Any] | None:
    if geometry is None or geometry.is_empty:
        return None
    kind = geometry.geom_type
    if kind == "Point":
        return {"type": "Point", "coordinates": [geometry.x, geometry.y]}
    if kind == "LineString":
        return {"type": "LineString", "coordinates": [[p[0], p[1]] for p in geometry.coords]}
    if kind == "Polygon":
        rings = [geometry.exterior, *geometry.interiors]
        return {"type": "Polygon", "coordinates": [[[p[0], p[1]] for p in ring.coords] for ring in rings]}
    if kind == "MultiLineString":
        return {"type": "MultiLineString", "coordinates": [[[p[0], p[1]] for p in line.coords] for line in geometry.geoms]}
    if kind == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": [[[[p[0], p[1]] for p in ring.coords] for ring in [poly.exterior, *poly.interiors]] for poly in geometry.geoms]}
    return None


def feature_to_json(feature, index: int) -> dict[str, Any] | None:
    geometry = geometry_to_json(feature.geom)
    if geometry is None:
        return None
    kind_value = getattr(feature.kind, "value", str(feature.kind))
    return {
        "id": f"feature-{index}",
        "kind": KIND_MAP.get(kind_value, kind_value.lower()),
        "source_layer": feature.source_layer,
        "confidence": feature.confidence,
        "geometry": geometry,
    }


def rule_to_json(rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "object": getattr(rule.object, "value", str(rule.object)),
        "planting": rule.planting,
        "min_distance_m": rule.min_distance_m,
        "source": rule.act,
        "clause": rule.clause,
        "verified": rule.verified,
    }


def placement_to_json(placement, index: int) -> dict[str, Any]:
    return {
        "id": f"{placement.species_type}-{index}",
        "x": float(placement.point.x), "y": float(placement.point.y),
        "species_type": placement.species_type,
        "species": placement.species,
        "status": "allowed",
        "rationale": [rule_to_json(rule) for rule in placement.rationale],
    }


def rejection_to_json(rejection, index: int) -> dict[str, Any]:
    rule = rejection.violated
    return {
        "id": f"rejection-{rejection.species_type}-{index}",
        "x": float(rejection.point.x), "y": float(rejection.point.y),
        "species_type": rejection.species_type,
        "violated": rule_to_json(rule),
        "reason": f"Точка нарушает минимальный отступ {rule.min_distance_m:g} м от объекта {getattr(rule.object, 'value', rule.object)}.",
    }


def write_result_dxf(input_path: Path, output_path: Path, placements: list[dict[str, Any]]) -> None:
    """Create output from the original DXF; remove previous GreenPlan output layers first."""
    doc = ezdxf.readfile(str(input_path))
    msp = doc.modelspace()
    for layer in LAYER_NAMES.values():
        if layer not in doc.layers:
            doc.layers.add(layer)
    # Remove prior generated entities on GreenPlan planting layers, so saving twice doesn't duplicate them.
    for entity in list(msp):
        if entity.dxf.layer in LAYER_NAMES.values():
            msp.delete_entity(entity)
    for item in placements:
        layer = LAYER_NAMES[item["species_type"]]
        msp.add_circle(center=(float(item["x"]), float(item["y"])), radius=1.0, dxfattribs={"layer": layer})
    doc.saveas(str(output_path))


def create_result(job_id: str, input_path: Path, output_path: Path) -> dict[str, Any]:
    parsed = parse_dxf(str(input_path), str(LAYERS_PATH))
    all_placements, all_rejections = [], []
    warnings = [f"Неизвестный слой: {item.get('layer', 'неизвестно')}" for item in parsed.unresolved_layers]
    for species_type in SPECIES_TYPES:
        placements, rejections = build_plan(
            input_path=str(input_path), rules_path=str(RULES_PATH),
            planting_path=str(PLANTING_PATH), species_type=species_type,
            layers_path=str(LAYERS_PATH), warnings=warnings,
        )
        all_placements.extend(placements)
        all_rejections.extend(rejections)
    placements_data = [placement_to_json(item, index) for index, item in enumerate(all_placements)]
    rejections_data = [rejection_to_json(item, index) for index, item in enumerate(all_rejections)]
    write_result_dxf(input_path, output_path, placements_data)
    features_data = [item for i, feature in enumerate(parsed.features) if (item := feature_to_json(feature, i)) is not None]
    statistics = {
        "trees": sum(p["species_type"] == "tree" for p in placements_data),
        "shrubs": sum(p["species_type"] == "shrub" for p in placements_data),
        "groundcovers_area_m2": 0,
        "total_green_area_m2": 0,
        "allowed_zones": 1,
        "rejected_count": len(rejections_data),
    }
    return {
        "run_id": job_id, "status": "completed", "placements": placements_data,
        "rejections": rejections_data, "features": features_data,
        "statistics": statistics, "warnings": warnings,
        "progress": {"stage": "Расчёт завершён", "progress": 100},
    }


def run_calculation(job_id: str, input_path: Path, output_path: Path) -> None:
    try:
        set_job(job_id, status="processing", progress=10, stage="Анализ DXF")
        set_job(job_id, progress=35, stage="Расчёт допустимых зон")
        set_job(job_id, progress=50, stage="Размещение посадок")
        result = create_result(job_id, input_path, output_path)
        result_path = input_path.parent / "result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        # result.dxf is the immutable version generated by the service.
        # User edits are stored in a separate result_edited.dxf file.
        edited_path = output_path.with_name("result_edited.dxf")
        set_job(job_id, status="completed", progress=100, stage="Расчёт завершён", result=result,
                result_path=str(result_path), dxf_path=str(output_path),
                original_dxf_path=str(output_path), edited_dxf_path=str(edited_path),
                input_path=str(input_path), has_saved_edits=False,
                original_placements=json.loads(json.dumps(result["placements"])),
                edit_validation=None)
    except Exception as exc:
        set_job(job_id, status="failed", progress=100, stage="Ошибка расчёта", error=str(exc))


def validate_edits(job: dict[str, Any], edits: list[PlacementEdit]) -> dict[str, Any]:
    result = job["result"]
    existing = {p["id"]: p for p in result["placements"]}
    if len({e.id for e in edits}) != len(edits):
        raise HTTPException(status_code=422, detail="В запросе повторяются ID посадок")
    unknown = [e.id for e in edits if e.id not in existing]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Неизвестные ID посадок: {', '.join(unknown[:10])}")

    # Accept only changed coordinates; all omitted points retain their last saved positions.
    candidate = {key: dict(value) for key, value in existing.items()}
    for edit in edits:
        candidate[edit.id]["x"] = float(edit.x)
        candidate[edit.id]["y"] = float(edit.y)

    input_path = Path(job["input_path"])
    parsed = parse_dxf(str(input_path), str(LAYERS_PATH))
    features = parsed.features
    site_boundary, _ = get_site_boundary(features)
    rules = load_rules(str(RULES_PATH))
    planting_config = load_planting_config(str(PLANTING_PATH))
    issues: list[dict[str, Any]] = []

    for placement_id, item in candidate.items():
        point = Point(item["x"], item["y"])
        species_type = item["species_type"]
        if not site_boundary.covers(point):
            issues.append({"id": placement_id, "code": "outside_site", "message": "Точка находится за границей участка."})
            continue
        species_rules = get_rules(rules, species_type)
        violated = find_violation(point, features, species_rules)
        if violated is not None:
            issues.append({
                "id": placement_id, "code": "min_distance",
                "message": f"Недостаточный отступ от объекта: требуется {violated.min_distance_m:g} м.",
                "rule": rule_to_json(violated),
            })

    # Check spacing between all placements of the same species type.
    for species_type in SPECIES_TYPES:
        group = [p for p in candidate.values() if p["species_type"] == species_type]
        min_spacing = float(planting_config[species_type]["min_spacing_m"])
        for i, first in enumerate(group):
            p1 = Point(first["x"], first["y"])
            for second in group[i + 1:]:
                p2 = Point(second["x"], second["y"])
                if p1.distance(p2) < min_spacing:
                    issues.append({"id": first["id"], "other_id": second["id"], "code": "plant_spacing",
                                   "message": f"Между посадками требуется не менее {min_spacing:g} м."})
    return {"valid": not issues, "issues": issues, "placements": list(candidate.values())}


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.post("/runs")
async def create_run(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="Нужен DXF-файл")
    job_id = uuid.uuid4().hex
    job_dir = RUNS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.dxf"
    output_path = job_dir / "result.dxf"
    input_path.write_bytes(await file.read())
    with jobs_lock:
        jobs[job_id] = {"id": job_id, "status": "queued", "progress": 0, "stage": "Файл загружен", "filename": file.filename}
    threading.Thread(target=run_calculation, args=(job_id, input_path, output_path), daemon=True).start()
    return {"id": job_id, "status": "queued", "progress": 0, "stage": "Файл загружен"}


@app.get("/runs/{job_id}")
def get_run(job_id: str):
    job = get_job(job_id)
    return {"id": job["id"], "status": job["status"], "progress": job.get("progress", 0),
            "stage": job.get("stage", ""), "error": job.get("error")}


@app.get("/runs/{job_id}/result")
def get_result(job_id: str):
    job = get_job(job_id)
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Ошибка расчёта"))
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Расчёт ещё не завершён")
    return job["result"]


@app.post("/runs/{job_id}/validate-edits")
def validate_run_edits(job_id: str, request: EditsRequest):
    job = get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Сначала дождитесь завершения расчёта")
    validation = validate_edits(job, request.placements)
    set_job(job_id, edit_validation=validation)
    return {"valid": validation["valid"], "issues": validation["issues"]}


@app.post("/runs/{job_id}/save-edits")
def save_run_edits(job_id: str, request: EditsRequest):
    job = get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Сначала дождитесь завершения расчёта")
    validation = validate_edits(job, request.placements)
    if not validation["valid"]:
        raise HTTPException(status_code=422, detail={"message": "Есть нарушения ограничений", "issues": validation["issues"]})

    # Save the edited version separately. Never overwrite the service-generated DXF.
    edited_path = Path(job["edited_dxf_path"])
    temp_path = edited_path.with_name("result_edited.tmp.dxf")
    write_result_dxf(Path(job["input_path"]), temp_path, validation["placements"])
    temp_path.replace(edited_path)

    result = dict(job["result"])
    result["placements"] = validation["placements"]
    result["status"] = "completed"
    result_path = Path(job["result_path"])
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    set_job(job_id, result=result, edit_validation=validation,
            has_saved_edits=True, edited_dxf_path=str(edited_path))
    return {"saved": True, "valid": True, "result": result,
            "dxf_url": f"/runs/{job_id}/edited-dxf",
            "original_dxf_url": f"/runs/{job_id}/original-dxf",
            "edited_dxf_url": f"/runs/{job_id}/edited-dxf"}


@app.get("/runs/{job_id}/original-dxf")
def download_original_dxf(job_id: str):
    """Download the immutable DXF generated by the initial calculation."""
    job = get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="DXF ещё не готов")
    dxf_path = Path(job.get("original_dxf_path", job["dxf_path"]))
    if not dxf_path.exists():
        raise HTTPException(status_code=404, detail="Исходный DXF не найден")
    return FileResponse(path=dxf_path, media_type="application/dxf", filename="greenplan_original.dxf")


@app.get("/runs/{job_id}/edited-dxf")
def download_edited_dxf(job_id: str):
    """Download the latest saved user-edited DXF; unsaved edits are never included."""
    job = get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="DXF ещё не готов")
    if not job.get("has_saved_edits", False):
        raise HTTPException(status_code=404, detail="Отредактированная версия ещё не сохранена")
    dxf_path = Path(job["edited_dxf_path"])
    if not dxf_path.exists():
        raise HTTPException(status_code=404, detail="Отредактированный DXF не найден")
    return FileResponse(path=dxf_path, media_type="application/dxf", filename="greenplan_edited.dxf")


@app.get("/runs/{job_id}/dxf")
def download_dxf(job_id: str):
    """Backward-compatible endpoint: edited version if saved, otherwise original."""
    job = get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="DXF ещё не готов")
    if job.get("has_saved_edits", False):
        dxf_path = Path(job["edited_dxf_path"])
        filename = "greenplan_edited.dxf"
    else:
        dxf_path = Path(job.get("original_dxf_path", job["dxf_path"]))
        filename = "greenplan_original.dxf"
    if not dxf_path.exists():
        raise HTTPException(status_code=404, detail="Результирующий DXF не найден")
    return FileResponse(path=dxf_path, media_type="application/dxf", filename=filename)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
