from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

from app.models import MutationOp, NetworkModel
from app.store import normalize_payload

load_dotenv()

MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")

SCHEMA_HINT = """
Architecture hiérarchique OBLIGATOIRE:
  Zone
    ├── power_stations[]   (centrale)
    │     └── generators[] (générateur / source / inverter / battery)
    │           └── production: {P_min, P_max, P_eff} en Watts
    └── loads[]            (charge / switch / meter)
          └── demand: {P_demand} en Watts
  lines[] entre zones:
    transport: {P_max limite, P_flow puissance envoyée} en Watts
    loss: {c0, c1, c2} — pertes P_loss = c0 + c1*|P| + c2*P² (W)
    énergie reçue = P_flow - P_loss
  Zone.balance (recalculé serveur): P_production, P_demand, P_surplus, P_in, P_out, P_exportable

Tu NE dois PAS mettre les générateurs à plat dans la zone : ils vont DANS une power_station.
Les charges vont dans loads[] de la zone.

Mutation format: {"op":"<op>","payload":{...}}

Ops:
- add_zone: {"id":"zone6","label":"Zone 6"}
- remove_zone: {"id":"zone5"}
- add_line: {"id":"line6","from_zone":"zone4","to_zone":"zone6","kind":"feeds","P_max":1000,"c0":5,"c1":0.02,"c2":0.0000001}
- remove_line: {"id":"line5"}
- add_power_station: {"zone_id":"zone1","id":"ps1","label":"Power Station 1"}
- remove_power_station: {"zone_id":"zone1","id":"ps1"}
- add_generator: {"zone_id":"zone1","power_station_id":"ps1","id":"gen1","type":"generator","label":"G1","P_min":500,"P_max":5000,"P_eff":3000}
- remove_generator: {"zone_id":"zone1","id":"gen1"}
- add_load: {"zone_id":"zone1","id":"load1","type":"load","label":"Charge 1","P_demand":1500}
- remove_load: {"zone_id":"zone1","id":"load1"}
- update_production: {"zone_id":"zone1","id":"gen1","P_min":500,"P_max":5000,"P_eff":3200}
- update_demand: {"zone_id":"zone1","id":"load1","P_demand":1800}
- update_line_transport: {"id":"line1","P_max":1000}
- update_line_loss: {"id":"line1","c0":5,"c1":0.02,"c2":0.0000001}
- recompute_balance: {}

Generator type MUST be one of: source | generator | inverter | battery
Load type MUST be one of: load | meter | switch | bus
Puissances en Watts (nombres). P_eff doit respecter P_min ≤ P_eff ≤ P_max.

Rules:
- Reuse existing IDs from the snapshot.
- Never claim a change in message without operations[].
- ONLY valid JSON, no markdown.
"""

_OP_ALIASES = {
    "delete_zone": "remove_zone",
    "delete_line": "remove_line",
    "delete_power_station": "remove_power_station",
    "delete_generator": "remove_generator",
    "delete_load": "remove_load",
    "create_zone": "add_zone",
    "create_line": "add_line",
    "create_power_station": "add_power_station",
    "create_generator": "add_generator",
    "create_load": "add_load",
    "add_component": "add_component",
    "delete_component": "remove_component",
}


def _client():
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY manquante. Définir la clé dans backend/.env")
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


def _coerce_op(raw: dict[str, Any]) -> MutationOp | None:
    if "payload" not in raw and "op" in raw:
        op_name = raw.get("op") or raw.get("action") or raw.get("type")
        payload = {k: v for k, v in raw.items() if k not in ("op", "action", "type")}
        raw = {"op": op_name, "payload": payload}
    elif "op" not in raw and "action" in raw:
        raw = {
            "op": raw["action"],
            "payload": raw.get("payload")
            or {k: v for k, v in raw.items() if k not in ("action", "payload")},
        }

    op_name = str(raw.get("op") or "").strip()
    op_name = _OP_ALIASES.get(op_name, op_name)
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    payload = normalize_payload(op_name, payload)

    try:
        return MutationOp.model_validate({"op": op_name, "payload": payload})
    except Exception:
        return None


def chat_to_operations(message: str, snapshot: NetworkModel) -> tuple[str, list[MutationOp]]:
    client = _client()
    prompt = f"""{SCHEMA_HINT}

Current network snapshot:
{snapshot.model_dump_json(indent=2)}

User request:
{message}

Return JSON:
{{
  "message": "confirmation courte en français basée UNIQUEMENT sur operations[]",
  "operations": []
}}
"""
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text or "{}"
    data = _extract_json(text)
    raw_ops = data.get("operations") or []
    ops: list[MutationOp] = []
    skipped = 0
    for o in raw_ops:
        if not isinstance(o, dict):
            skipped += 1
            continue
        coerced = _coerce_op(o)
        if coerced is None:
            skipped += 1
            continue
        ops.append(coerced)

    msg = str(data.get("message") or "OK")
    if not ops:
        msg = (
            f"{msg}\n\n⚠ Aucune mutation valide reçue"
            + (f" ({skipped} opération(s) ignorée(s))." if skipped else ".")
            + " Le réseau n'a PAS été modifié."
        )
    return msg, ops


def image_to_network(image_bytes: bytes, mime_type: str, snapshot: NetworkModel) -> NetworkModel:
    from google.genai import types

    client = _client()
    prompt = f"""{SCHEMA_HINT}

Current network (merge; reuse IDs when same zones/stations/lines):
{snapshot.model_dump_json(indent=2)}

Analyze the diagram. Extract hierarchical structure:
zones → power_stations (with generators inside) → loads in zones → lines between zones.
Return ONLY a NetworkModel JSON object.
"""
    part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = client.models.generate_content(model=MODEL, contents=[part, prompt])
    text = response.text or "{}"
    data = _extract_json(text)
    return NetworkModel.model_validate(data)
