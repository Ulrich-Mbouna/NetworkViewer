from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.excalidraw_export import export_excalidraw
from app.gemma import image_to_network
from app.models import (
    ApplyOpsRequest,
    ApplyOpsResponse,
    NetworkModel,
    Suggestion,
    ValidationReport,
)
from app.store import MutationError, store
from app.suggestions import build_suggestions
from app.validator import validate_network

router = APIRouter(prefix="/api", tags=["network"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/network", response_model=NetworkModel)
def get_network() -> NetworkModel:
    return store.get()


@router.put("/network", response_model=NetworkModel)
def put_network(network: NetworkModel) -> NetworkModel:
    return store.set(network)


@router.get("/validate", response_model=ValidationReport)
def get_validate() -> ValidationReport:
    return validate_network(store.get())


@router.get("/suggestions", response_model=list[Suggestion])
def get_suggestions() -> list[Suggestion]:
    net = store.get()
    return build_suggestions(net, validate_network(net))


@router.post("/ops", response_model=ApplyOpsResponse)
def apply_ops(req: ApplyOpsRequest) -> ApplyOpsResponse:
    if not req.operations:
        raise HTTPException(status_code=400, detail="Aucune opération")
    try:
        network = store.apply_operations(req.operations)
    except MutationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    validation = validate_network(network)
    return ApplyOpsResponse(
        network=network,
        validation=validation,
        suggestions=build_suggestions(network, validation),
    )


@router.get("/export/excalidraw")
def get_excalidraw() -> JSONResponse:
    scene = export_excalidraw(store.get())
    return JSONResponse(
        content=scene,
        headers={
            "Content-Disposition": 'attachment; filename="reseau.excalidraw"',
        },
    )


@router.post("/network/from-image")
async def network_from_image(file: UploadFile = File(...)) -> dict:
    mime = file.content_type or "image/png"
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit être une image")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Image vide")
    try:
        extracted = image_to_network(data, mime, store.get())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Échec extraction Gemma: {e}"
        ) from e
    network = store.merge(extracted)
    validation = validate_network(network)
    return {
        "network": network,
        "validation": validation,
        "suggestions": build_suggestions(network, validation),
    }
