from __future__ import annotations

from app.models import Line, LineLoss, NetworkModel, ZoneBalance


def line_loss_watts(loss: LineLoss, p_flow: float | None) -> float:
    """P_loss(|P|) = c0 + c1*|P| + c2*P², borné à [0, |P|]. Nul si P=0."""
    p = abs(float(p_flow or 0.0))
    if p <= 1e-12:
        return 0.0
    raw = float(loss.c0) + float(loss.c1) * p + float(loss.c2) * (p * p)
    return max(0.0, min(raw, p))


def line_received(loss: LineLoss, p_flow: float | None) -> float:
    """Puissance arrivant à destination."""
    p = abs(float(p_flow or 0.0))
    return max(0.0, p - line_loss_watts(loss, p))


def send_for_receive(loss: LineLoss, target_recv: float, max_send: float) -> float:
    """Plus petit envoi S ∈ [0, max_send] tel que reçu(S) ≥ target_recv (approx. dichoto)."""
    target_recv = max(0.0, float(target_recv))
    max_send = max(0.0, float(max_send))
    if target_recv <= 1e-12 or max_send <= 1e-12:
        return 0.0
    if line_received(loss, max_send) < target_recv - 1e-9:
        return max_send
    lo, hi = 0.0, max_send
    for _ in range(48):
        mid = (lo + hi) / 2.0
        if line_received(loss, mid) < target_recv:
            lo = mid
        else:
            hi = mid
    return hi


def recompute_balance(network: NetworkModel, estimate_flows: bool = True) -> NetworkModel:
    """
    Recalcule production / demande, estime les flux avec pertes de ligne,
    puis P_in / P_out / surplus net.

    Sur une ligne : P_flow = puissance envoyée, P_loss = pertes, reçu = P_flow - P_loss.
    P_out source compte P_flow ; P_in destination compte le reçu.
    """
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

    if estimate_flows:
        _estimate_line_flows(network, local)

    pin: dict[str, float] = {z.id: 0.0 for z in network.zones}
    pout: dict[str, float] = {z.id: 0.0 for z in network.zones}
    total_loss = 0.0
    for ln in network.lines:
        flow = float(ln.transport.P_flow or 0.0)
        ploss = line_loss_watts(ln.loss, flow)
        ln.loss.P_loss = ploss
        total_loss += ploss
        recv = max(0.0, flow - ploss)
        if ln.from_zone in pout:
            pout[ln.from_zone] += max(0.0, flow)
        if ln.to_zone in pin:
            pin[ln.to_zone] += recv

    network.meta.total_line_loss = total_loss

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
            P_surplus=disponible - zout,
            P_exportable=max(0.0, disponible),
        )

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
    Cascade : residual = prod - demand (+ reçu − envoyé).
    L'énergie reçue à destination = flux − pertes(ligne).
    """
    for ln in network.lines:
        ln.transport.P_flow = 0.0
        ln.loss.P_loss = 0.0

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

            def sort_key(ln: Line) -> tuple:
                dest_r = residual.get(ln.to_zone, 0.0)
                deficit = dest_r < -1e-9
                transit = sum(
                    _remaining_capacity(x)
                    for x in network.lines
                    if x.from_zone == ln.to_zone
                )
                return (
                    0 if deficit else 1,
                    0 if transit > 1e-9 else 1,
                    -_remaining_capacity(ln),
                )

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
                    target_recv_delta = min(dest_need + transit_room, line_received(ln.loss, avail))
                elif transit_room > 1e-9:
                    target_recv_delta = min(transit_room, line_received(ln.loss, avail))
                else:
                    continue

                if target_recv_delta <= 1e-9:
                    continue

                old_flow = float(ln.transport.P_flow or 0.0)
                old_recv = line_received(ln.loss, old_flow)
                target_total_recv = old_recv + target_recv_delta
                max_new_flow = old_flow + min(avail, room)
                new_flow = send_for_receive(ln.loss, target_total_recv, max_new_flow)
                # ne pas dépasser ce qu'on peut encore envoyer
                new_flow = min(new_flow, max_new_flow)
                add = new_flow - old_flow
                if add <= 1e-9:
                    continue

                new_recv = line_received(ln.loss, new_flow)
                recv_delta = new_recv - old_recv

                ln.transport.P_flow = new_flow
                residual[zid] -= add
                residual[dest] = residual.get(dest, 0.0) + recv_delta
                progressed = True

        if not progressed:
            break
