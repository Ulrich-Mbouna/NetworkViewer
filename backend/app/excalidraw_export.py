from __future__ import annotations

import math
import uuid
from typing import Any

from app.models import NetworkModel


def _id() -> str:
    return uuid.uuid4().hex[:16]


def export_excalidraw(network: NetworkModel) -> dict[str, Any]:
    """Build an Excalidraw scene: zones as ellipses, lines as arrows, components inside."""
    elements: list[dict[str, Any]] = []
    n = max(len(network.zones), 1)
    cols = math.ceil(math.sqrt(n))
    spacing_x, spacing_y = 280, 220
    zone_w, zone_h = 160, 100
    positions: dict[str, tuple[float, float]] = {}

    for i, zone in enumerate(network.zones):
        col, row = i % cols, i // cols
        x = 80 + col * spacing_x
        y = 80 + row * spacing_y
        positions[zone.id] = (x + zone_w / 2, y + zone_h / 2)

        group_ids = [_id()]
        ellipse_id = _id()
        text_id = _id()

        elements.append(
            {
                "id": ellipse_id,
                "type": "ellipse",
                "x": x,
                "y": y,
                "width": zone_w,
                "height": zone_h,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "#a5d8ff",
                "fillStyle": "solid",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "groupIds": group_ids,
                "frameId": None,
                "roundness": {"type": 2},
                "seed": abs(hash(zone.id)) % 10_000_000,
                "versionNonce": abs(hash(zone.id + "v")) % 10_000_000,
                "isDeleted": False,
                "boundElements": [{"id": text_id, "type": "text"}],
                "updated": 1,
                "link": None,
                "locked": False,
            }
        )
        label = zone.label or zone.id
        elements.append(
            {
                "id": text_id,
                "type": "text",
                "x": x + 20,
                "y": y + zone_h / 2 - 12,
                "width": zone_w - 40,
                "height": 24,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 0,
                "opacity": 100,
                "groupIds": group_ids,
                "frameId": None,
                "roundness": None,
                "seed": abs(hash(zone.id + "t")) % 10_000_000,
                "versionNonce": abs(hash(zone.id + "tv")) % 10_000_000,
                "isDeleted": False,
                "boundElements": None,
                "updated": 1,
                "link": None,
                "locked": False,
                "text": label,
                "fontSize": 18,
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "containerId": ellipse_id,
                "originalText": label,
                "lineHeight": 1.25,
                "baseline": 18,
            }
        )

        # Power stations (rect) + generators (circles) + loads (diamonds)
        j = 0
        for ps in zone.power_stations:
            psx, psy = x + 8, y + zone_h + 8 + j * 40
            elements.append(
                {
                    "id": _id(),
                    "type": "rectangle",
                    "x": psx,
                    "y": psy,
                    "width": max(40, 28 * max(len(ps.generators), 1) + 12),
                    "height": 34,
                    "angle": 0,
                    "strokeColor": "#2f9e44",
                    "backgroundColor": "#d3f9d8",
                    "fillStyle": "solid",
                    "strokeWidth": 1,
                    "strokeStyle": "solid",
                    "roughness": 1,
                    "opacity": 100,
                    "groupIds": group_ids,
                    "frameId": None,
                    "roundness": {"type": 3},
                    "seed": abs(hash(ps.id)) % 10_000_000,
                    "versionNonce": abs(hash(ps.id + "v")) % 10_000_000,
                    "isDeleted": False,
                    "boundElements": None,
                    "updated": 1,
                    "link": None,
                    "locked": False,
                }
            )
            for gi, gen in enumerate(ps.generators):
                elements.append(
                    {
                        "id": _id(),
                        "type": "ellipse",
                        "x": psx + 6 + gi * 28,
                        "y": psy + 4,
                        "width": 24,
                        "height": 24,
                        "angle": 0,
                        "strokeColor": "#2f9e44",
                        "backgroundColor": "#b2f2bb",
                        "fillStyle": "solid",
                        "strokeWidth": 1,
                        "strokeStyle": "solid",
                        "roughness": 1,
                        "opacity": 100,
                        "groupIds": group_ids,
                        "frameId": None,
                        "roundness": {"type": 2},
                        "seed": abs(hash(gen.id)) % 10_000_000,
                        "versionNonce": abs(hash(gen.id + "v")) % 10_000_000,
                        "isDeleted": False,
                        "boundElements": None,
                        "updated": 1,
                        "link": None,
                        "locked": False,
                    }
                )
            j += 1
        for li, load in enumerate(zone.loads):
            elements.append(
                {
                    "id": _id(),
                    "type": "diamond",
                    "x": x + 8 + li * 32,
                    "y": y + zone_h + 8 + j * 40,
                    "width": 26,
                    "height": 26,
                    "angle": 0,
                    "strokeColor": "#e67700",
                    "backgroundColor": "#ffec99",
                    "fillStyle": "solid",
                    "strokeWidth": 1,
                    "strokeStyle": "solid",
                    "roughness": 1,
                    "opacity": 100,
                    "groupIds": group_ids,
                    "frameId": None,
                    "roundness": None,
                    "seed": abs(hash(load.id)) % 10_000_000,
                    "versionNonce": abs(hash(load.id + "v")) % 10_000_000,
                    "isDeleted": False,
                    "boundElements": None,
                    "updated": 1,
                    "link": None,
                    "locked": False,
                }
            )

    for ln in network.lines:
        if ln.from_zone not in positions or ln.to_zone not in positions:
            continue
        x1, y1 = positions[ln.from_zone]
        x2, y2 = positions[ln.to_zone]
        arrow_id = _id()
        label_id = _id()
        elements.append(
            {
                "id": arrow_id,
                "type": "arrow",
                "x": x1,
                "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
                "angle": 0,
                "strokeColor": "#364fc7",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "groupIds": [],
                "frameId": None,
                "roundness": {"type": 2},
                "seed": abs(hash(ln.id)) % 10_000_000,
                "versionNonce": abs(hash(ln.id + "v")) % 10_000_000,
                "isDeleted": False,
                "boundElements": None,
                "updated": 1,
                "link": None,
                "locked": False,
                "points": [[0, 0], [x2 - x1, y2 - y1]],
                "lastCommittedPoint": None,
                "startBinding": None,
                "endBinding": None,
                "startArrowhead": None,
                "endArrowhead": "arrow",
            }
        )
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        elements.append(
            {
                "id": label_id,
                "type": "text",
                "x": mx - 20,
                "y": my - 20,
                "width": 60,
                "height": 20,
                "angle": 0,
                "strokeColor": "#364fc7",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 0,
                "opacity": 100,
                "groupIds": [],
                "frameId": None,
                "roundness": None,
                "seed": abs(hash(ln.id + "t")) % 10_000_000,
                "versionNonce": abs(hash(ln.id + "tv")) % 10_000_000,
                "isDeleted": False,
                "boundElements": None,
                "updated": 1,
                "link": None,
                "locked": False,
                "text": ln.id,
                "fontSize": 14,
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "containerId": None,
                "originalText": ln.id,
                "lineHeight": 1.25,
                "baseline": 14,
            }
        )

    title = network.meta.name or "Réseau"
    elements.insert(
        0,
        {
            "id": _id(),
            "type": "text",
            "x": 80,
            "y": 20,
            "width": 400,
            "height": 32,
            "angle": 0,
            "strokeColor": "#1e1e1e",
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 1,
            "strokeStyle": "solid",
            "roughness": 0,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "roundness": None,
            "seed": 1,
            "versionNonce": 2,
            "isDeleted": False,
            "boundElements": None,
            "updated": 1,
            "link": None,
            "locked": False,
            "text": title,
            "fontSize": 24,
            "fontFamily": 1,
            "textAlign": "left",
            "verticalAlign": "top",
            "containerId": None,
            "originalText": title,
            "lineHeight": 1.25,
            "baseline": 24,
        },
    )

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "reseau-electrique",
        "elements": elements,
        "appState": {
            "viewBackgroundColor": "#ffffff",
            "gridSize": None,
        },
        "files": {},
    }
