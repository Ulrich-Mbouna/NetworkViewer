from __future__ import annotations

import os
from collections import defaultdict

from app.balance import recompute_balance
from app.models import NetworkModel, ValidationIssue, ValidationReport


def validate_network(network: NetworkModel) -> ValidationReport:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    cycle_as_error = os.getenv("CYCLE_AS_ERROR", "true").lower() in ("1", "true", "yes")
    # garantir bilan à jour avant contrôles énergétiques
    network = recompute_balance(network.model_copy(deep=True))

    zone_ids = [z.id for z in network.zones]
    seen_zones: set[str] = set()
    for zid in zone_ids:
        if zid in seen_zones:
            errors.append(
                ValidationIssue(
                    code="duplicate_zone_id",
                    message=f"ID de zone dupliqué: {zid}",
                    path=f"zones.{zid}",
                )
            )
        seen_zones.add(zid)

    component_ids: set[str] = set()
    ps_ids: set[str] = set()
    for z in network.zones:
        if z.parent_id and z.parent_id not in seen_zones:
            errors.append(
                ValidationIssue(
                    code="invalid_parent",
                    message=f"parent_id inconnu '{z.parent_id}' pour zone {z.id}",
                    path=f"zones.{z.id}.parent_id",
                )
            )
        has_content = bool(z.power_stations or z.loads or z.components)
        if not has_content:
            warnings.append(
                ValidationIssue(
                    code="empty_zone",
                    message=f"Zone vide: {z.id}",
                    path=f"zones.{z.id}",
                )
            )
        for ps in z.power_stations:
            if ps.id in ps_ids:
                errors.append(
                    ValidationIssue(
                        code="duplicate_power_station_id",
                        message=f"ID power station dupliqué: {ps.id}",
                        path=f"zones.{z.id}.power_stations.{ps.id}",
                    )
                )
            ps_ids.add(ps.id)
            if not ps.generators:
                warnings.append(
                    ValidationIssue(
                        code="empty_power_station",
                        message=f"Power station sans générateur: {ps.id} ({z.id})",
                        path=f"zones.{z.id}.power_stations.{ps.id}",
                    )
                )
            for c in ps.generators:
                if c.id in component_ids:
                    errors.append(
                        ValidationIssue(
                            code="duplicate_component_id",
                            message=f"ID de composant dupliqué: {c.id}",
                            path=f"zones.{z.id}.power_stations.{ps.id}.{c.id}",
                        )
                    )
                component_ids.add(c.id)
                _check_production(c, z.id, ps.id, errors, warnings)
        for c in z.loads + z.components:
            if c.id in component_ids:
                errors.append(
                    ValidationIssue(
                        code="duplicate_component_id",
                        message=f"ID de composant dupliqué: {c.id}",
                        path=f"zones.{z.id}.loads.{c.id}",
                    )
                )
            component_ids.add(c.id)
            if c.demand.P_demand is not None and c.demand.P_demand < 0:
                errors.append(
                    ValidationIssue(
                        code="negative_demand",
                        message=f"Demande négative sur {c.id}: {c.demand.P_demand} W",
                        path=f"zones.{z.id}.loads.{c.id}.demand",
                    )
                )

    line_ids: set[str] = set()
    pair_seen: set[tuple[str, str]] = set()
    graph: dict[str, list[str]] = defaultdict(list)

    for ln in network.lines:
        if ln.id in line_ids:
            errors.append(
                ValidationIssue(
                    code="duplicate_line_id",
                    message=f"ID de ligne dupliqué: {ln.id}",
                    path=f"lines.{ln.id}",
                )
            )
        line_ids.add(ln.id)

        if ln.from_zone not in seen_zones:
            errors.append(
                ValidationIssue(
                    code="invalid_from_zone",
                    message=f"from_zone inconnu '{ln.from_zone}' (ligne {ln.id})",
                    path=f"lines.{ln.id}.from_zone",
                )
            )
        if ln.to_zone not in seen_zones:
            errors.append(
                ValidationIssue(
                    code="invalid_to_zone",
                    message=f"to_zone inconnu '{ln.to_zone}' (ligne {ln.id})",
                    path=f"lines.{ln.id}.to_zone",
                )
            )

        pair = (ln.from_zone, ln.to_zone)
        if pair in pair_seen:
            warnings.append(
                ValidationIssue(
                    code="duplicate_line_pair",
                    message=f"Ligne doublon {ln.from_zone} → {ln.to_zone}",
                    path=f"lines.{ln.id}",
                )
            )
        pair_seen.add(pair)

        if ln.from_zone in seen_zones and ln.to_zone in seen_zones:
            graph[ln.from_zone].append(ln.to_zone)

        tmax = ln.transport.P_max
        tflow = ln.transport.P_flow
        if tmax is not None and tmax < 0:
            errors.append(
                ValidationIssue(
                    code="negative_line_limit",
                    message=f"Limite de transport négative sur {ln.id}",
                    path=f"lines.{ln.id}.transport.P_max",
                )
            )
        if tmax is not None and tflow is not None and abs(tflow) > tmax + 1e-6:
            errors.append(
                ValidationIssue(
                    code="line_overload",
                    message=(
                        f"Surcharge ligne {ln.id}: flux {tflow:.0f} W > limite {tmax:.0f} W"
                    ),
                    path=f"lines.{ln.id}.transport",
                )
            )
        elif tmax is None and tflow is not None and abs(tflow) > 0:
            warnings.append(
                ValidationIssue(
                    code="line_no_limit",
                    message=f"Ligne {ln.id} sans limite P_max (flux {tflow:.0f} W)",
                    path=f"lines.{ln.id}.transport",
                )
            )

    for z in network.zones:
        bal = z.balance
        # déficit net après imports/exports
        if bal.P_surplus is not None and bal.P_surplus < -1e-6:
            warnings.append(
                ValidationIssue(
                    code="zone_deficit",
                    message=(
                        f"Déficit zone {z.id}: prod {bal.P_production or 0:.0f} W + "
                        f"P_in {bal.P_in or 0:.0f} W < demande {bal.P_demand or 0:.0f} W "
                        f"(net {bal.P_surplus:.0f} W, P_out {bal.P_out or 0:.0f})"
                    ),
                    path=f"zones.{z.id}.balance",
                )
            )
        # exportable non évacué (pas de ligne / saturation)
        exportable = bal.P_exportable or 0.0
        out = bal.P_out or 0.0
        if exportable > out + 1e-6:
            trapped = exportable - out
            has_out = any(ln.from_zone == z.id for ln in network.lines)
            warnings.append(
                ValidationIssue(
                    code="zone_surplus_trapped",
                    message=(
                        f"Surplus non entièrement exporté zone {z.id}: "
                        f"{trapped:.0f} W restants"
                        + (" (aucune ligne sortante)" if not has_out else " (lignes saturées)")
                    ),
                    path=f"zones.{z.id}.balance",
                )
            )

    cycles = _find_cycles(graph, list(seen_zones))
    for cycle in cycles:
        issue = ValidationIssue(
            code="cycle_detected",
            message=f"Cycle détecté: {' → '.join(cycle)}",
            path="lines",
        )
        if cycle_as_error:
            errors.append(issue)
        else:
            warnings.append(issue)

    connected = set()
    for ln in network.lines:
        connected.add(ln.from_zone)
        connected.add(ln.to_zone)
    for zid in seen_zones:
        if zid not in connected and len(network.lines) > 0:
            warnings.append(
                ValidationIssue(
                    code="isolated_zone",
                    message=f"Zone isolée (aucune ligne): {zid}",
                    path=f"zones.{zid}",
                )
            )

    return ValidationReport(ok=len(errors) == 0, errors=errors, warnings=warnings)


def _check_production(c, zone_id: str, ps_id: str, errors: list, warnings: list) -> None:
    prod = c.production
    path = f"zones.{zone_id}.power_stations.{ps_id}.{c.id}.production"
    if prod.P_min is not None and prod.P_max is not None and prod.P_min > prod.P_max:
        errors.append(
            ValidationIssue(
                code="invalid_production_range",
                message=f"P_min > P_max sur {c.id} ({prod.P_min} > {prod.P_max})",
                path=path,
            )
        )
    if prod.P_eff is not None:
        if prod.P_min is not None and prod.P_eff + 1e-9 < prod.P_min:
            errors.append(
                ValidationIssue(
                    code="production_below_min",
                    message=f"P_eff {prod.P_eff} W < P_min {prod.P_min} W ({c.id})",
                    path=path,
                )
            )
        if prod.P_max is not None and prod.P_eff > prod.P_max + 1e-9:
            errors.append(
                ValidationIssue(
                    code="production_above_max",
                    message=f"P_eff {prod.P_eff} W > P_max {prod.P_max} W ({c.id})",
                    path=path,
                )
            )
        if prod.P_eff < 0:
            errors.append(
                ValidationIssue(
                    code="negative_production",
                    message=f"P_eff négatif sur {c.id}",
                    path=path,
                )
            )
    elif prod.P_max is not None or prod.P_min is not None:
        warnings.append(
            ValidationIssue(
                code="missing_p_eff",
                message=f"Générateur {c.id} sans P_eff (min/max définis)",
                path=path,
            )
        )


def _find_cycles(graph: dict[str, list[str]], nodes: list[str]) -> list[list[str]]:
    """Return simple directed cycles via DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    parent: dict[str, str | None] = {n: None for n in nodes}
    cycles: list[list[str]] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in graph.get(u, []):
            if v not in color:
                continue
            if color[v] == WHITE:
                parent[v] = u
                dfs(v)
            elif color[v] == GRAY:
                # reconstruct cycle u -> ... -> v -> u? actually edge u->v closes
                path = [v]
                cur = u
                while cur is not None and cur != v:
                    path.append(cur)
                    cur = parent.get(cur)
                path.append(v)
                path.reverse()
                cycles.append(path)
        color[u] = BLACK

    for n in nodes:
        if color[n] == WHITE:
            dfs(n)
    return cycles
