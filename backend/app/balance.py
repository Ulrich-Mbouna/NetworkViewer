from __future__ import annotations

from app.models import LineTransport, NetworkModel, ZoneBalance


def recompute_balance(network: NetworkModel, estimate_flows: bool = True) -> NetworkModel:
    """
    Recalcule pour chaque zone :
      P_production, P_demand, P_surplus, P_in, P_out, P_exportable
    et optionnellement estime P_flow sur les lignes (export du surplus, plafonné par P_max).
    """
    zones = {z.id: z for z in network.zones}

    # 1) production / demande locales
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
        surplus = prod - dem
        z.balance = ZoneBalance(
            P_production=prod,
            P_demand=dem,
            P_surplus=surplus,
            P_in=0.0,
            P_out=0.0,
            P_exportable=max(0.0, surplus),
        )

    # 2) flux lignes
    if estimate_flows:
        _estimate_line_flows(network, zones)

    # 3) agréger P_in / P_out depuis les flux
    pin: dict[str, float] = {zid: 0.0 for zid in zones}
    pout: dict[str, float] = {zid: 0.0 for zid in zones}
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
        z.balance.P_in = pin.get(z.id, 0.0)
        z.balance.P_out = pout.get(z.id, 0.0)
        # exportable = surplus local encore « sorti » ou potentiel
        surplus = z.balance.P_surplus or 0.0
        out = z.balance.P_out or 0.0
        z.balance.P_exportable = max(0.0, surplus) if surplus > 0 else 0.0
        # si on a exporté via lignes, garder la trace
        if out > 0:
            z.balance.P_exportable = max(z.balance.P_exportable or 0.0, out)

    return network


def _estimate_line_flows(network: NetworkModel, zones: dict) -> None:
    """Répartit le surplus de chaque zone sur ses lignes sortantes, plafonné par P_max."""
    # reset flows that were only estimates (always re-estimate for consistency)
    for ln in network.lines:
        ln.transport.P_flow = 0.0

    for z in network.zones:
        surplus = z.balance.P_surplus or 0.0
        if surplus <= 0:
            continue
        out_lines = [ln for ln in network.lines if ln.from_zone == z.id]
        if not out_lines:
            continue

        # capacités
        caps = []
        for ln in out_lines:
            cap = ln.transport.P_max
            caps.append(float(cap) if cap is not None else float("inf"))

        remaining = surplus
        # répartition égale puis clamp
        share = remaining / len(out_lines)
        for ln, cap in zip(out_lines, caps):
            flow = min(share, cap) if cap != float("inf") else share
            ln.transport.P_flow = (ln.transport.P_flow or 0.0) + flow
            remaining -= flow

        # second pass: dump rest on lines with residual capacity
        if remaining > 1e-9:
            for ln, cap in zip(out_lines, caps):
                if remaining <= 1e-9:
                    break
                used = ln.transport.P_flow or 0.0
                room = (cap - used) if cap != float("inf") else remaining
                if room <= 0:
                    continue
                add = min(remaining, room)
                ln.transport.P_flow = used + add
                remaining -= add
