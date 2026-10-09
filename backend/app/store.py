from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.models import (
    Component,
    ComponentType,
    ElectricalState,
    Line,
    MutationOp,
    NetworkModel,
    PowerStation,
    Zone,
    normalize_component_type,
)


class MutationError(ValueError):
    """Payload de mutation invalide / incomplet."""


class NetworkStore:
    """In-memory store that reuses existing zone/line/PS/component IDs on merge."""

    def __init__(self) -> None:
        self._network = NetworkModel()

    def get(self) -> NetworkModel:
        return self._network.model_copy(deep=True)

    def set(self, network: NetworkModel) -> NetworkModel:
        self._network = network.model_copy(deep=True)
        return self.get()

    def load_fixture(self, path: Path) -> NetworkModel:
        data = json.loads(path.read_text(encoding="utf-8"))
        return self.set(NetworkModel.model_validate(data))

    def merge(self, incoming: NetworkModel) -> NetworkModel:
        current = self._network
        zones_by_id = {z.id: z for z in current.zones}
        for z in incoming.zones:
            if z.id in zones_by_id:
                existing = zones_by_id[z.id]
                ps_by_id = {ps.id: ps for ps in existing.power_stations}
                for ps in z.power_stations:
                    if ps.id in ps_by_id:
                        gens = {g.id: g for g in ps_by_id[ps.id].generators}
                        for g in ps.generators:
                            gens[g.id] = g
                        ps_by_id[ps.id] = PowerStation(
                            id=ps.id,
                            label=ps.label or ps_by_id[ps.id].label,
                            generators=list(gens.values()),
                            electrical=_merge_electrical(
                                ps_by_id[ps.id].electrical, ps.electrical
                            ),
                        )
                    else:
                        ps_by_id[ps.id] = ps
                loads = {c.id: c for c in existing.loads}
                for c in z.loads:
                    loads[c.id] = c
                # legacy components still migrate via Zone validator
                zones_by_id[z.id] = Zone(
                    id=z.id,
                    label=z.label or existing.label,
                    power_stations=list(ps_by_id.values()),
                    loads=list(loads.values()),
                    components=z.components,
                    electrical=_merge_electrical(existing.electrical, z.electrical),
                    parent_id=z.parent_id if z.parent_id is not None else existing.parent_id,
                )
            else:
                zones_by_id[z.id] = z

        lines_by_id = {ln.id: ln for ln in current.lines}
        for ln in incoming.lines:
            lines_by_id[ln.id] = ln

        actors = current.actors.model_copy(deep=True)
        if incoming.actors.groupe_electrogene:
            actors.groupe_electrogene = incoming.actors.groupe_electrogene
        if incoming.actors.compteur:
            actors.compteur = incoming.actors.compteur
        if incoming.actors.dashboard:
            actors.dashboard = incoming.actors.dashboard
        if incoming.actors.consommateurs:
            actors.consommateurs = list(
                dict.fromkeys(actors.consommateurs + incoming.actors.consommateurs)
            )

        meta = incoming.meta if incoming.meta.name else current.meta
        return self.set(
            NetworkModel(
                meta=meta,
                zones=list(zones_by_id.values()),
                lines=list(lines_by_id.values()),
                actors=actors,
            )
        )

    def apply_operations(self, ops: list[MutationOp]) -> NetworkModel:
        net = self._network.model_copy(deep=True)
        for op in ops:
            net = _apply_one(net, op)
        if ops:
            net.meta.version = int(net.meta.version or 0) + 1
        return self.set(net)


def _merge_electrical(a: ElectricalState, b: ElectricalState) -> ElectricalState:
    return ElectricalState(
        P=b.P if b.P is not None else a.P,
        U=b.U if b.U is not None else a.U,
        I=b.I if b.I is not None else a.I,
        f=b.f if b.f is not None else a.f,
    )


def _find_zone(net: NetworkModel, zone_id: str) -> Optional[Zone]:
    for z in net.zones:
        if z.id == zone_id:
            return z
    return None


def _find_ps(zone: Zone, ps_id: str) -> Optional[PowerStation]:
    for ps in zone.power_stations:
        if ps.id == ps_id:
            return ps
    return None


def _first_str(payload: dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = payload.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _require(payload: dict[str, Any], op: str, *keys: str) -> str:
    value = _first_str(payload, *keys)
    if not value:
        raise MutationError(
            f"Opération « {op} » incomplète : champ manquant "
            f"({', '.join(keys)}). Payload reçu: {payload}"
        )
    return value


def normalize_payload(op: str, payload: dict[str, Any]) -> dict[str, Any]:
    p = dict(payload or {})
    for nest in ("component", "zone", "line", "data", "power_station", "generator", "load"):
        inner = p.get(nest)
        if isinstance(inner, dict):
            for k, v in inner.items():
                p.setdefault(k, v)

    if op in ("add_zone", "update_zone", "remove_zone"):
        zid = _first_str(p, "id", "zone_id", "zoneId", "zone")
        if zid:
            p["id"] = zid

    if op in ("add_line", "update_line", "remove_line"):
        lid = _first_str(p, "id", "line_id", "lineId", "line")
        if lid:
            p["id"] = lid
        frm = _first_str(p, "from_zone", "from", "source", "fromZone")
        to = _first_str(p, "to_zone", "to", "target", "toZone")
        if frm:
            p["from_zone"] = frm
        if to:
            p["to_zone"] = to

    if op in ("add_power_station", "remove_power_station"):
        pid = _first_str(p, "id", "power_station_id", "ps_id", "station_id")
        zid = _first_str(p, "zone_id", "zoneId", "zone")
        if pid:
            p["id"] = pid
        if zid:
            p["zone_id"] = zid

    if op in ("add_generator", "remove_generator"):
        gid = _first_str(p, "id", "generator_id", "component_id")
        zid = _first_str(p, "zone_id", "zoneId", "zone")
        pid = _first_str(p, "power_station_id", "ps_id", "station_id")
        if gid:
            p["id"] = gid
        if zid:
            p["zone_id"] = zid
        if pid:
            p["power_station_id"] = pid
        if "type" in p:
            p["type"] = normalize_component_type(p["type"]).value

    if op in ("add_load", "remove_load"):
        lid = _first_str(p, "id", "load_id", "component_id")
        zid = _first_str(p, "zone_id", "zoneId", "zone")
        if lid:
            p["id"] = lid
        if zid:
            p["zone_id"] = zid
        if "type" in p:
            p["type"] = normalize_component_type(p["type"]).value

    if op in ("add_component", "update_component", "remove_component"):
        cid = _first_str(p, "id", "component_id", "componentId", "component")
        zid = _first_str(p, "zone_id", "zoneId", "zone", "parent_zone")
        if cid:
            p["id"] = cid
        if zid:
            p["zone_id"] = zid
        if "type" not in p and "component_type" in p:
            p["type"] = p["component_type"]
        if "type" in p:
            p["type"] = normalize_component_type(p["type"]).value
        pid = _first_str(p, "power_station_id", "ps_id", "station_id")
        if pid:
            p["power_station_id"] = pid

    if op == "update_electrical":
        eid = _first_str(p, "id", "zone_id", "component_id")
        if eid:
            p["id"] = eid
        zid = _first_str(p, "zone_id", "zoneId", "zone")
        if zid:
            p["zone_id"] = zid

    return p


def _ensure_default_ps(zone: Zone) -> PowerStation:
    if zone.power_stations:
        return zone.power_stations[0]
    ps = PowerStation(id=f"ps_{zone.id}", label=f"Power Station {zone.id}", generators=[])
    zone.power_stations.append(ps)
    return ps


def _apply_one(net: NetworkModel, mutation: MutationOp) -> NetworkModel:
    op = mutation.op
    p = normalize_payload(op, mutation.payload)

    if op == "add_zone":
        zid = _require(p, op, "id", "zone_id")
        if any(z.id == zid for z in net.zones):
            for z in net.zones:
                if z.id == zid and "label" in p:
                    z.label = p["label"]
            return net
        net.zones.append(
            Zone(id=zid, label=p.get("label", zid), parent_id=p.get("parent_id"))
        )
        return net

    if op == "update_zone":
        z = _find_zone(net, _require(p, op, "id", "zone_id"))
        if z:
            if "label" in p:
                z.label = p["label"]
            if "parent_id" in p:
                z.parent_id = p.get("parent_id")
            if "electrical" in p:
                z.electrical = _merge_electrical(
                    z.electrical, ElectricalState.model_validate(p["electrical"])
                )
        return net

    if op == "remove_zone":
        zid = _require(p, op, "id", "zone_id")
        net.zones = [z for z in net.zones if z.id != zid]
        net.lines = [ln for ln in net.lines if ln.from_zone != zid and ln.to_zone != zid]
        return net

    if op == "add_line":
        lid = _require(p, op, "id", "line_id")
        frm = _require(p, op, "from_zone", "from")
        to = _require(p, op, "to_zone", "to")
        if any(ln.id == lid for ln in net.lines):
            for ln in net.lines:
                if ln.id == lid:
                    ln.from_zone, ln.to_zone = frm, to
            return net
        net.lines.append(
            Line(
                id=lid,
                from_zone=frm,
                to_zone=to,
                kind=p.get("kind", "feeds"),
                attrs=p.get("attrs", {}),
            )
        )
        return net

    if op == "update_line":
        lid = _require(p, op, "id", "line_id")
        for ln in net.lines:
            if ln.id == lid:
                if "from_zone" in p:
                    ln.from_zone = p["from_zone"]
                if "to_zone" in p:
                    ln.to_zone = p["to_zone"]
                if "kind" in p:
                    ln.kind = p["kind"]
        return net

    if op == "remove_line":
        lid = _require(p, op, "id", "line_id")
        net.lines = [ln for ln in net.lines if ln.id != lid]
        return net

    if op == "add_power_station":
        zid = _require(p, op, "zone_id", "zone")
        pid = _require(p, op, "id", "power_station_id")
        zone = _find_zone(net, zid)
        if not zone:
            raise MutationError(f"Zone introuvable: {zid}")
        if _find_ps(zone, pid):
            return net
        zone.power_stations.append(
            PowerStation(id=pid, label=p.get("label", f"Power Station {pid}"), generators=[])
        )
        return net

    if op == "remove_power_station":
        zid = _require(p, op, "zone_id", "zone")
        pid = _require(p, op, "id", "power_station_id")
        zone = _find_zone(net, zid)
        if zone:
            zone.power_stations = [ps for ps in zone.power_stations if ps.id != pid]
        return net

    if op == "add_generator":
        zid = _require(p, op, "zone_id", "zone")
        gid = _require(p, op, "id", "generator_id")
        zone = _find_zone(net, zid)
        if not zone:
            raise MutationError(f"Zone introuvable: {zid}")
        ps_id = _first_str(p, "power_station_id", "ps_id")
        ps = _find_ps(zone, ps_id) if ps_id else None
        if ps is None:
            ps = _ensure_default_ps(zone)
        ctype = normalize_component_type(p.get("type", "generator"))
        if any(g.id == gid for g in ps.generators):
            return net
        ps.generators.append(
            Component(id=gid, type=ctype, label=p.get("label", gid))
        )
        return net

    if op == "remove_generator":
        zid = _require(p, op, "zone_id", "zone")
        gid = _require(p, op, "id", "generator_id")
        zone = _find_zone(net, zid)
        if not zone:
            return net
        for ps in zone.power_stations:
            ps.generators = [g for g in ps.generators if g.id != gid]
        return net

    if op == "add_load":
        zid = _require(p, op, "zone_id", "zone")
        lid = _require(p, op, "id", "load_id")
        zone = _find_zone(net, zid)
        if not zone:
            raise MutationError(f"Zone introuvable: {zid}")
        ctype = normalize_component_type(p.get("type", "load"))
        if any(c.id == lid for c in zone.loads):
            return net
        zone.loads.append(Component(id=lid, type=ctype, label=p.get("label", lid)))
        return net

    if op == "remove_load":
        zid = _require(p, op, "zone_id", "zone")
        lid = _require(p, op, "id", "load_id")
        zone = _find_zone(net, zid)
        if zone:
            zone.loads = [c for c in zone.loads if c.id != lid]
        return net

    # Legacy add_component → route by type
    if op == "add_component":
        zid = _require(p, op, "zone_id", "zone")
        cid = _require(p, op, "id", "component_id")
        ctype = normalize_component_type(_first_str(p, "type", "component_type") or "load")
        routed = {
            "zone_id": zid,
            "id": cid,
            "label": p.get("label", cid),
            "type": ctype.value,
        }
        if p.get("power_station_id"):
            routed["power_station_id"] = p["power_station_id"]
        if ctype in (
            ComponentType.generator,
            ComponentType.source,
            ComponentType.inverter,
            ComponentType.battery,
        ):
            return _apply_one(net, MutationOp(op="add_generator", payload=routed))
        return _apply_one(net, MutationOp(op="add_load", payload=routed))

    if op == "remove_component":
        zid = _require(p, op, "zone_id", "zone")
        cid = _require(p, op, "id", "component_id")
        zone = _find_zone(net, zid)
        if not zone:
            return net
        zone.loads = [c for c in zone.loads if c.id != cid]
        for ps in zone.power_stations:
            ps.generators = [g for g in ps.generators if g.id != cid]
        return net

    if op == "update_component":
        zid = _require(p, op, "zone_id", "zone")
        cid = _require(p, op, "id", "component_id")
        zone = _find_zone(net, zid)
        if not zone:
            return net
        for bag in [zone.loads] + [ps.generators for ps in zone.power_stations]:
            for c in bag:
                if c.id == cid:
                    if "type" in p:
                        c.type = normalize_component_type(p["type"])
                    if "label" in p:
                        c.label = p["label"]
                    if "electrical" in p:
                        c.electrical = _merge_electrical(
                            c.electrical, ElectricalState.model_validate(p["electrical"])
                        )
        return net

    if op == "update_electrical":
        target = p.get("target", "zone")
        eid = _require(p, op, "id", "zone_id", "component_id")
        if target == "zone":
            z = _find_zone(net, eid)
            if z and "electrical" in p:
                z.electrical = _merge_electrical(
                    z.electrical, ElectricalState.model_validate(p["electrical"])
                )
        return net

    return net


store = NetworkStore()
