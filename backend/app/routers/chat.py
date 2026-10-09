from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.gemma import chat_to_operations
from app.models import ChatRequest, ChatResponse
from app.store import MutationError, store
from app.suggestions import build_suggestions
from app.validator import validate_network

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")

    before = store.get()
    before_ids = {z.id for z in before.zones}

    try:
        message, ops = chat_to_operations(req.message, before)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Échec Gemma: {e}") from e

    try:
        network = store.apply_operations(ops) if ops else store.get()
    except MutationError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                "Gemma a proposé une mutation incomplète "
                f"(champs manquants). Réessaie avec plus de précision. Détail: {e}"
            ),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Impossible d'appliquer les mutations: {e}",
        ) from e

    after_ids = {z.id for z in network.zones}
    removed = sorted(before_ids - after_ids)
    added = sorted(after_ids - before_ids)
    facts = []
    if ops:
        facts.append(f"{len(ops)} opération(s) appliquée(s)")
    if removed:
        facts.append(f"zones retirées: {', '.join(removed)}")
    if added:
        facts.append(f"zones ajoutées: {', '.join(added)}")
    if facts:
        message = f"{message}\n\n✓ État réel: " + " · ".join(facts)
    else:
        message = f"{message}\n\n✓ État réel: inchangé ({len(network.zones)} zones)"

    validation = validate_network(network)
    return ChatResponse(
        message=message,
        operations=ops,
        network=network,
        validation=validation,
        suggestions=build_suggestions(network, validation),
    )
