from __future__ import annotations

import re
from typing import Optional

from app.models import MutationOp, NetworkModel, Suggestion, ValidationIssue, ValidationReport
from app.validator import validate_network


def build_suggestions(
    network: NetworkModel, report: Optional[ValidationReport] = None
) -> list[Suggestion]:
    report = report or validate_network(network)
    issues = list(report.errors) + list(report.warnings)
    out: list[Suggestion] = []
    for issue in issues:
        s = _for_issue(network, issue)
        if s:
            out.append(s)
    return out


def _zone_id_from_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    m = re.match(r"zones\.([^.]+)", path)
    return m.group(1) if m else None


def _line_id_from_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    m = re.match(r"lines\.([^.]+)", path)
    return m.group(1) if m else None


def _for_issue(network: NetworkModel, issue: ValidationIssue) -> Optional[Suggestion]:
    code = issue.code
    path = issue.path

    if code == "empty_zone":
        zid = _zone_id_from_path(path) or _extract_id(issue.message, r"Zone vide:\s*(\S+)")
        if not zid:
            return None
        ps_id = f"ps_{zid}"
        gen_id = f"gen_{zid}"
        load_id = f"load_{zid}"
        return Suggestion(
            id=f"sug-empty-{zid}",
            issue_code=code,
            severity="warning",
            title=f"Structurer {zid} (PS + générateur + charge)",
            description=(
                f"La zone « {zid} » est vide. Proposition : power station « {ps_id} » "
                f"avec générateur « {gen_id} », plus charge « {load_id} »."
            ),
            operations=[
                MutationOp(
                    op="add_power_station",
                    payload={"zone_id": zid, "id": ps_id, "label": f"Power Station {zid}"},
                ),
                MutationOp(
                    op="add_generator",
                    payload={
                        "zone_id": zid,
                        "power_station_id": ps_id,
                        "id": gen_id,
                        "type": "generator",
                        "label": f"Générateur {zid}",
                    },
                ),
                MutationOp(
                    op="add_load",
                    payload={
                        "zone_id": zid,
                        "id": load_id,
                        "type": "load",
                        "label": f"Charge {zid}",
                    },
                ),
            ],
        )

    if code == "empty_power_station":
        # path zones.{zid}.power_stations.{psid}
        m = re.match(r"zones\.([^.]+)\.power_stations\.([^.]+)", path or "")
        if not m:
            return None
        zid, psid = m.group(1), m.group(2)
        gid = f"gen_{psid}"
        return Suggestion(
            id=f"sug-empty-ps-{psid}",
            issue_code=code,
            severity="warning",
            title=f"Ajouter un générateur dans {psid}",
            description=f"La power station « {psid} » n'a aucun générateur.",
            operations=[
                MutationOp(
                    op="add_generator",
                    payload={
                        "zone_id": zid,
                        "power_station_id": psid,
                        "id": gid,
                        "type": "generator",
                        "label": f"Générateur {psid}",
                    },
                )
            ],
        )

    if code == "isolated_zone":
        zid = _zone_id_from_path(path) or _extract_id(
            issue.message, r"Zone isolée \(aucune ligne\):\s*(\S+)"
        )
        if not zid or not network.zones:
            return None
        # connect to first other zone
        others = [z.id for z in network.zones if z.id != zid]
        if not others:
            return None
        target = others[0]
        lid = f"line_{zid}_{target}"
        return Suggestion(
            id=f"sug-iso-{zid}",
            issue_code=code,
            severity="warning",
            title=f"Relier {zid} → {target}",
            description=(
                f"La zone « {zid} » n'est reliée à aucune ligne. "
                f"Proposition : créer « {lid} » vers « {target} »."
            ),
            operations=[
                MutationOp(
                    op="add_line",
                    payload={
                        "id": lid,
                        "from_zone": zid,
                        "to_zone": target,
                        "kind": "feeds",
                    },
                )
            ],
        )

    if code == "cycle_detected":
        # Suggest removing the last edge mentioned in the cycle path message
        # message like: "Cycle détecté: b → a → b"
        parts = re.findall(r"[A-Za-z0-9_-]+", issue.message.split(":", 1)[-1])
        # filter arrow noise already handled; parts are zone ids
        zones_in_cycle = [p for p in parts if p != "Cycle"]
        if len(zones_in_cycle) < 2:
            return None
        # last closing edge: second-to-last -> last (often same as first)
        a, b = zones_in_cycle[-2], zones_in_cycle[-1]
        line = next(
            (ln for ln in network.lines if ln.from_zone == a and ln.to_zone == b),
            None,
        )
        if not line and len(zones_in_cycle) >= 2:
            a, b = zones_in_cycle[0], zones_in_cycle[1]
            line = next(
                (ln for ln in network.lines if ln.from_zone == a and ln.to_zone == b),
                None,
            )
        if not line:
            return None
        return Suggestion(
            id=f"sug-cycle-{line.id}",
            issue_code=code,
            severity="error",
            title=f"Rompre le cycle (retirer {line.id})",
            description=(
                f"Un cycle d'alimentation a été détecté. "
                f"Proposition : supprimer la ligne « {line.id} » ({line.from_zone} → {line.to_zone})."
            ),
            operations=[MutationOp(op="remove_line", payload={"id": line.id})],
        )

    if code == "duplicate_line_pair":
        lid = _line_id_from_path(path) or _extract_id(issue.message, r"\(ligne (\S+)\)")
        # message: Ligne doublon a → b — path lines.{id}
        lid = lid or _line_id_from_path(path)
        if not lid:
            # find duplicate by scanning
            seen: set[tuple[str, str]] = set()
            for ln in network.lines:
                pair = (ln.from_zone, ln.to_zone)
                if pair in seen:
                    lid = ln.id
                    break
                seen.add(pair)
        if not lid:
            return None
        return Suggestion(
            id=f"sug-dupline-{lid}",
            issue_code=code,
            severity="warning",
            title=f"Supprimer la ligne doublon {lid}",
            description=f"Plusieurs lignes relient la même paire de zones. Retirer « {lid} ».",
            operations=[MutationOp(op="remove_line", payload={"id": lid})],
        )

    if code in ("invalid_from_zone", "invalid_to_zone"):
        lid = _line_id_from_path(path)
        if not lid:
            return None
        return Suggestion(
            id=f"sug-badref-{lid}",
            issue_code=code,
            severity="error",
            title=f"Supprimer la ligne invalide {lid}",
            description=(
                f"La ligne « {lid} » référence une zone inexistante. "
                "Proposition : la supprimer."
            ),
            operations=[MutationOp(op="remove_line", payload={"id": lid})],
        )

    if code == "invalid_parent":
        zid = _zone_id_from_path(path)
        if not zid:
            return None
        return Suggestion(
            id=f"sug-parent-{zid}",
            issue_code=code,
            severity="error",
            title=f"Retirer parent_id de {zid}",
            description=f"Le parent de « {zid} » est inconnu. Proposition : le mettre à null.",
            operations=[
                MutationOp(op="update_zone", payload={"id": zid, "parent_id": None})
            ],
        )

    if code == "production_above_max":
        gid = _component_id_from_prod_path(path)
        zid = _zone_id_from_path(path)
        if not gid or not zid:
            return None
        gen = _find_gen(network, zid, gid)
        if not gen or gen.production.P_max is None:
            return None
        return Suggestion(
            id=f"sug-peff-max-{gid}",
            issue_code=code,
            severity="error",
            title=f"Plafonner P_eff de {gid}",
            description=f"Mettre P_eff = P_max ({gen.production.P_max} W).",
            operations=[
                MutationOp(
                    op="update_production",
                    payload={"zone_id": zid, "id": gid, "P_eff": gen.production.P_max},
                )
            ],
        )

    if code == "production_below_min":
        gid = _component_id_from_prod_path(path)
        zid = _zone_id_from_path(path)
        if not gid or not zid:
            return None
        gen = _find_gen(network, zid, gid)
        if not gen or gen.production.P_min is None:
            return None
        return Suggestion(
            id=f"sug-peff-min-{gid}",
            issue_code=code,
            severity="error",
            title=f"Relever P_eff de {gid}",
            description=f"Mettre P_eff = P_min ({gen.production.P_min} W).",
            operations=[
                MutationOp(
                    op="update_production",
                    payload={"zone_id": zid, "id": gid, "P_eff": gen.production.P_min},
                )
            ],
        )

    if code == "line_overload":
        lid = _line_id_from_path(path)
        if not lid:
            return None
        ln = next((x for x in network.lines if x.id == lid), None)
        if not ln or ln.transport.P_flow is None:
            return None
        return Suggestion(
            id=f"sug-overload-{lid}",
            issue_code=code,
            severity="error",
            title=f"Augmenter la limite de {lid}",
            description=f"Porter P_max à au moins {abs(ln.transport.P_flow):.0f} W.",
            operations=[
                MutationOp(
                    op="update_line_transport",
                    payload={"id": lid, "P_max": abs(ln.transport.P_flow)},
                )
            ],
        )

    if code == "missing_p_eff":
        gid = _component_id_from_prod_path(path)
        zid = _zone_id_from_path(path)
        if not gid or not zid:
            return None
        gen = _find_gen(network, zid, gid)
        if not gen:
            return None
        mid = gen.production.P_max
        if mid is None:
            mid = gen.production.P_min
        if mid is None:
            return None
        return Suggestion(
            id=f"sug-missing-peff-{gid}",
            issue_code=code,
            severity="warning",
            title=f"Définir P_eff pour {gid}",
            description=f"Initialiser P_eff à {mid} W.",
            operations=[
                MutationOp(
                    op="update_production",
                    payload={"zone_id": zid, "id": gid, "P_eff": mid},
                )
            ],
        )

    return None


def _component_id_from_prod_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    # zones.{zid}.power_stations.{ps}.{gid}.production
    parts = path.split(".")
    if len(parts) >= 5 and parts[0] == "zones":
        return parts[4]
    return None


def _find_gen(network: NetworkModel, zid: str, gid: str):
    for z in network.zones:
        if z.id != zid:
            continue
        for ps in z.power_stations:
            for g in ps.generators:
                if g.id == gid:
                    return g
    return None


def _extract_id(message: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, message)
    return m.group(1) if m else None
