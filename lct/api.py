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

from greenplan.pipeline import build_plan
from greenplan.parser.dxf_parser import read_dxf


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

RULES_PATH = (
    BASE_DIR
    / "data"
    / "rules"
    / "sp42.yaml"
)

PLANTING_PATH = (
    BASE_DIR
    / "data"
    / "rules"
    / "planting.yaml"
)

RUNS_DIR = BASE_DIR / ".greenplan_runs"

RUNS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ---------------------------------------------------------
# APP
# ---------------------------------------------------------

app = FastAPI(
    title="GreenPlan API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# JOB STORAGE
# ---------------------------------------------------------

jobs: dict[str, dict[str, Any]] = {}

jobs_lock = threading.Lock()


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

SPECIES_TYPES = [
    "tree",
    "shrub",
    "groundcover",
]


SPECIES_LABELS = {
    "tree": "Дерево",
    "shrub": "Кустарник",
    "groundcover": "Почвопокровное",
}


LAYER_NAMES = {
    "tree": "PLANTING_TREES",
    "shrub": "PLANTING_SHRUBS",
    "groundcover": "PLANTING_GROUNDCOVER",
}


def set_job(
    job_id: str,
    **values: Any
) -> None:
    with jobs_lock:
        if job_id not in jobs:
            return

        jobs[job_id].update(values)


def get_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        job = jobs.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Расчёт не найден"
            )

        return dict(job)


def geometry_to_geojson(
    geometry
) -> dict[str, Any] | None:
    """
    Преобразует Shapely geometry
    в простой GeoJSON-подобный объект,
    который понимает фронтенд.
    """

    if geometry is None:
        return None

    geometry_type = geometry.geom_type

    if geometry_type == "Point":
        return {
            "type": "Point",
            "coordinates": [
                geometry.x,
                geometry.y
            ]
        }

    if geometry_type == "LineString":
        return {
            "type": "LineString",
            "coordinates": [
                [
                    point[0],
                    point[1]
                ]
                for point in geometry.coords
            ]
        }

    if geometry_type == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        point[0],
                        point[1]
                    ]
                    for point in ring.coords
                ]
                for ring in [
                    geometry.exterior,
                    *geometry.interiors
                ]
            ]
        }

    return None


def feature_to_json(
    feature,
    index: int
) -> dict[str, Any] | None:

    geometry = geometry_to_geojson(
        feature.geom
    )

    if geometry is None:
        return None

    kind_map = {
        "BUILDING": "building",
        "ROAD": "road",
        "PIPE_WATER": "water_pipe",
        "PIPE_GAS": "gas_pipe",
        "CABLE": "cable",
        "POWERLINE": "powerline",
        "SITE_BOUNDARY": "site_boundary",
        "UNKNOWN": "unknown",
    }

    kind = kind_map.get(
        feature.kind.value,
        "unknown"
    )

    return {
        "id": f"feature-{index}",
        "kind": kind,
        "source_layer": feature.source_layer,
        "confidence": feature.confidence,
        "geometry": geometry,
    }


def rule_to_json(rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "object": rule.object.value,
        "planting": rule.planting,
        "min_distance_m": rule.min_distance_m,
        "source": rule.act,
        "clause": rule.clause,
        "verified": rule.verified,
    }


def placement_to_json(
    placement,
    index: int
) -> dict[str, Any]:

    return {
        "id": (
            f"{placement.species_type}"
            f"-{index}"
        ),
        "x": placement.point.x,
        "y": placement.point.y,
        "species_type": placement.species_type,
        "species": placement.species,
        "status": "allowed",
        "rationale": [
            rule_to_json(rule)
            for rule in placement.rationale
        ],
    }


def rejection_to_json(
    rejection,
    index: int
) -> dict[str, Any]:

    violated = rejection.violated

    object_labels = {
        "PIPE_WATER": "водопроводу",
        "PIPE_GAS": "газопроводу",
        "CABLE": "кабелю",
        "POWERLINE": "ЛЭП",
        "BUILDING": "зданию",
        "ROAD": "дороге",
        "SITE_BOUNDARY": "границе участка",
    }

    object_name = object_labels.get(
        violated.object.value,
        "объекту"
    )

    reason = (
        "Точка находится ближе "
        f"{violated.min_distance_m:g} м "
        f"к {object_name}."
    )

    return {
        "id": (
            f"rejection-"
            f"{rejection.species_type}-"
            f"{index}"
        ),
        "x": rejection.point.x,
        "y": rejection.point.y,
        "species_type": rejection.species_type,
        "violated": rule_to_json(
            violated
        ),
        "reason": reason,
    }


def create_result(
    job_id: str,
    input_path: Path,
    output_path: Path
) -> dict[str, Any]:

    features = read_dxf(
        str(input_path)
    )

    all_placements = []
    all_rejections = []

    # -----------------------------------------------------
    # RUN EXISTING GREENPLAN ALGORITHM
    # -----------------------------------------------------

    for species_type in SPECIES_TYPES:
        placements, rejections = build_plan(
            input_path=str(input_path),
            rules_path=str(RULES_PATH),
            planting_path=str(PLANTING_PATH),
            species_type=species_type,
        )

        all_placements.extend(
            placements
        )

        all_rejections.extend(
            rejections
        )

    # -----------------------------------------------------
    # CREATE RESULT DXF
    # -----------------------------------------------------

    doc = ezdxf.readfile(
        str(input_path)
    )

    modelspace = doc.modelspace()

    for species_type in SPECIES_TYPES:
        layer_name = LAYER_NAMES[
            species_type
        ]

        if layer_name not in doc.layers:
            doc.layers.add(
                layer_name
            )

    for placement in all_placements:
        layer_name = LAYER_NAMES[
            placement.species_type
        ]

        modelspace.add_circle(
            center=(
                placement.point.x,
                placement.point.y
            ),
            radius=1.0,
            dxfattribs={
                "layer": layer_name
            }
        )

    doc.saveas(
        str(output_path)
    )

    # -----------------------------------------------------
    # SERIALIZE FEATURES
    # -----------------------------------------------------

    features_data = []

    for index, feature in enumerate(
        features
    ):
        item = feature_to_json(
            feature,
            index
        )

        if item is not None:
            features_data.append(
                item
            )

    # -----------------------------------------------------
    # SERIALIZE PLACEMENTS
    # -----------------------------------------------------

    placements_data = [
        placement_to_json(
            placement,
            index
        )
        for index, placement in enumerate(
            all_placements
        )
    ]

    # -----------------------------------------------------
    # SERIALIZE REJECTIONS
    # -----------------------------------------------------

    rejections_data = [
        rejection_to_json(
            rejection,
            index
        )
        for index, rejection in enumerate(
            all_rejections
        )
    ]

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    trees = sum(
        1
        for placement in all_placements
        if placement.species_type == "tree"
    )

    shrubs = sum(
        1
        for placement in all_placements
        if placement.species_type == "shrub"
    )

    groundcovers = sum(
        1
        for placement in all_placements
        if placement.species_type == "groundcover"
    )

    # Backend currently returns point placements
    # for groundcover rather than a polygon area.
    # Therefore we do not invent an area value.
    groundcovers_area_m2 = 0

    statistics = {
        "trees": trees,
        "shrubs": shrubs,
        "groundcovers_area_m2": (
            groundcovers_area_m2
        ),
        "total_green_area_m2": 0,
        "allowed_zones": 1,
        "rejected_count": len(
            rejections_data
        ),
    }

    result = {
        "run_id": job_id,
        "status": "completed",
        "placements": placements_data,
        "rejections": rejections_data,
        "features": features_data,
        "statistics": statistics,
        "progress": {
            "stage": "Расчёт завершён",
            "progress": 100,
        },
    }

    return result


# ---------------------------------------------------------
# BACKGROUND CALCULATION
# ---------------------------------------------------------

def run_calculation(
    job_id: str,
    input_path: Path,
    output_path: Path
) -> None:

    try:
        set_job(
            job_id,
            status="processing",
            progress=10,
            stage="Анализ DXF"
        )

        set_job(
            job_id,
            progress=20,
            stage="Определение объектов участка"
        )

        set_job(
            job_id,
            progress=35,
            stage="Расчёт допустимых зон"
        )

        set_job(
            job_id,
            progress=50,
            stage="Размещение деревьев"
        )

        # Actual calculation happens inside
        # the existing GreenPlan pipeline.
        result = create_result(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path
        )

        result_path = (
            input_path.parent
            / "result.json"
        )

        with open(
            result_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                result,
                file,
                ensure_ascii=False,
                indent=2
            )

        set_job(
            job_id,
            status="completed",
            progress=100,
            stage="Расчёт завершён",
            result=result,
            result_path=str(
                result_path
            ),
            dxf_path=str(
                output_path
            )
        )

    except Exception as exc:
        set_job(
            job_id,
            status="failed",
            progress=100,
            stage="Ошибка расчёта",
            error=str(exc)
        )


# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/runs")
async def create_run(
    file: UploadFile = File(...)
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="DXF-файл не выбран"
        )

    if not file.filename.lower().endswith(
        ".dxf"
    ):
        raise HTTPException(
            status_code=400,
            detail="Нужен DXF-файл"
        )

    job_id = uuid.uuid4().hex

    job_dir = (
        RUNS_DIR
        / job_id
    )

    job_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    input_path = (
        job_dir
        / "input.dxf"
    )

    output_path = (
        job_dir
        / "result.dxf"
    )

    contents = await file.read()

    with open(
        input_path,
        "wb"
    ) as saved_file:
        saved_file.write(
            contents
        )

    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "stage": "Файл загружен",
            "filename": file.filename,
        }

    thread = threading.Thread(
        target=run_calculation,
        args=(
            job_id,
            input_path,
            output_path
        ),
        daemon=True
    )

    thread.start()

    return {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "stage": "Файл загружен",
    }


@app.get("/runs/{job_id}")
def get_run(
    job_id: str
):
    job = get_job(
        job_id
    )

    return {
        "id": job["id"],
        "status": job["status"],
        "progress": job.get(
            "progress",
            0
        ),
        "stage": job.get(
            "stage",
            ""
        ),
        "error": job.get(
            "error"
        ),
    }


@app.get("/runs/{job_id}/result")
def get_result(
    job_id: str
):
    job = get_job(
        job_id
    )

    if job["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=job.get(
                "error",
                "Ошибка расчёта"
            )
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="Расчёт ещё не завершён"
        )

    return job["result"]


@app.get("/runs/{job_id}/dxf")
def download_dxf(
    job_id: str
):
    job = get_job(
        job_id
    )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="DXF ещё не готов"
        )

    dxf_path = Path(
        job["dxf_path"]
    )

    if not dxf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Результирующий DXF не найден"
        )

    return FileResponse(
        path=dxf_path,
        media_type=(
            "application/dxf"
        ),
        filename="greenplan_result.dxf"
    )


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )
