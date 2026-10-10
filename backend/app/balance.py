from __future__ import annotations

from app.models import Line, LineCost, NetworkModel, ZoneBalance


def line_cost_value(cost: LineCost, p_flow: float | None) -> float:
    """cost(|P|) = c0 + c1*|P| + c2*P²."""
    p = abs(float(p_flow or 0.0))
    return float(cost.c0) + float(cost.c1) * p + float(cost.c2) * (p * p)


def recompute_balance(network: NetworkModel, estimate_flows: bool = True) -> NetworkModel:
    """
    Recalcule production / demande locales, estime les flux (niveaux + transit),
    puis P_in / P_out / surplus net et coûts de ligne.

    Bilan zone :
      disponible = P_production + P_in - P_demand
      P_surplus  = disponible - P_out   (net après export)
      P_exportable = max(0, disponible)
    Une zone qui reçoit plus qu'elle ne consomme réexporte l'excédent.
    """
    # 1) production / demande locales
    local: dict[str, tuple[float, float]] = {}
    for z in network.zones:
        prod = 0.0
        for g in z.all_generators():
            if g.production.P_eff is not None:
                prod += float(g.production.P_eff)
            elif g.electrical.P is not None:
                prod += float(g.electrical.P)
        dem = 0.0
        for load in z.loads:
            if load.demand.P_demand is not None:
                dem += float(load.demand.P_demand)
            elif load.electrical.P is not None:
                dem += float(load.electrical.P)
        local[z.id] = (prod, dem)
        z.balance = ZoneBalance(
            P_production=prod,
            P_demand=dem,
            P_surplus=prod - dem,
            P_in=0.0,
            P_out=0.0,
            P_exportable=max(0.0, prod - dem),
        )

    # 2) flux lignes (cascade : import → surplus → réexport)
    if estimate_flows:
        _estimate_line_flows(network, local)

    # 3) agréger P_in / P_out et surplus net
    pin: dict[str, float] = {z.id: 0.0 for z in network.zones}
    pout: dict[str, float] = {z.id: 0.0 for z in network.zones}
    for ln in network.lines:
        flow = ln.transport.P_flow
        if flow is None:
            continue
        flow = float(flow)
        if ln.from_zone in pout:
            pout[ln.from_zone] += max(0.0, flow)
        if ln.to_zone in pin:
            pin[ln.to_zone] += max(0.0, flow)

    for z in network.zones:
        prod, dem = local[z.id]
        zin = pin.get(z.id, 0.0)
        zout = pout.get(z.id, 0.0)
        disponible = prod + zin - dem
        z.balance = ZoneBalance(
            P_production=prod,
            P_demand=dem,
            P_in=zin,
            P_out=zout,
            P_surplus=disponible - zout,  # net après export
            P_exportable=max(0.0, disponible),
        )

    # 4) coûts de transport
    total = 0.0
    for ln in network.lines:
        ln.cost.cost = line_cost_value(ln.cost, ln.transport.P_flow)
        total += ln.cost.cost
    network.meta.total_line_cost = total

    return network


def _remaining_capacity(ln: Line) -> float:
    cap = ln.transport.P_max
    used = float(ln.transport.P_flow or 0.0)
    if cap is None:
        return float("inf")
    return max(0.0, float(cap) - used)


def _estimate_line_flows(
    network: NetworkModel, local: dict[str, tuple[float, float]]
) -> None:
    """
    Cascade itérative :
      residual[z] = prod - demand   (puis + imports − exports au fil des itérations)
    Une zone avec residual > 0 pousse sur ses lignes sortantes (capacité restante).
    La destination voit residual augmenter : déficit réduit, ou surplus à réexporterer.
    """
    for ln in network.lines:
        ln.transport.P_flow = 0.0

    residual: dict[str, float] = {
        zid: prod - dem for zid, (prod, dem) in local.items()
    }
    zone_ids = list(residual.keys())
    max_iters = max(8, len(zone_ids) * 2 + len(network.lines))

    for _ in range(max_iters):
        progressed = False
        exporters = sorted(
            (zid for zid, r in residual.items() if r > 1e-9),
            key=lambda zid: -residual[zid],
        )
        for zid in exporters:
            out_lines = [
                ln
                for ln in network.lines
                if ln.from_zone == zid and _remaining_capacity(ln) > 1e-9
            ]
            if not out_lines:
                continue

            # Priorité : zones en déficit, puis celles pouvant encore réexporterer
            def sort_key(ln: Line) -> tuple:
                dest_r = residual.get(ln.to_zone, 0.0)
                deficit = dest_r < -1e-9
                transit = sum(
                    _remaining_capacity(x)
                    for x in network.lines
                    if x.from_zone == ln.to_zone
                )
                return (0 if deficit else 1, 0 if transit > 1e-9 else 1, -_remaining_capacity(ln))

            out_lines.sort(key=sort_key)

            for ln in out_lines:
                avail = residual[zid]
                if avail <= 1e-9:
                    break
                room = _remaining_capacity(ln)
                if room <= 1e-9:
                    continue

                dest = ln.to_zone
                dest_r = residual.get(dest, 0.0)
                dest_need = max(0.0, -dest_r)
                transit_room = sum(
                    _remaining_capacity(x)
                    for x in network.lines
                    if x.from_zone == dest
                )

                if dest_need > 1e-9:
                    # couvrir le déficit + laisser transiter l'excédent si possible
                    want = min(avail, room, dest_need + transit_room)
                elif transit_room > 1e-9:
                    # zone déjà à l'équilibre / surplus : uniquement du transit
                    want = min(avail, room, transit_room)
                else:
                    # pas de besoin ni de sortie : ne pas y envoyer
                    continue

                add = min(want, room, avail)
                if add <= 1e-9:
                    continue

                ln.transport.P_flow = float(ln.transport.P_flow or 0.0) + add
                residual[zid] -= add
                residual[dest] = residual.get(dest, 0.0) + add
                progressed = True

        if not progressed:
            break
