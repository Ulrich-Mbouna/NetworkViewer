from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ComponentType(str, Enum):
    source = "source"
    generator = "generator"
    inverter = "inverter"
    battery = "battery"
    load = "load"
    meter = "meter"
    switch = "switch"
    bus = "bus"


COMPONENT_TYPE_ALIASES: dict[str, ComponentType] = {
    "centrale": ComponentType.generator,
    "gen": ComponentType.generator,
    "groupe": ComponentType.generator,
    "groupe_electrogene": ComponentType.generator,
    "ge": ComponentType.generator,
    "solar": ComponentType.source,
    "pv": ComponentType.source,
    "panneau": ComponentType.source,
    "panneau_solaire": ComponentType.source,
    "photovoltaique": ComponentType.source,
    "onduleur": ComponentType.inverter,
    "batterie": ComponentType.battery,
    "storage": ComponentType.battery,
    "charge": ComponentType.load,
    "consumer": ComponentType.load,
    "consommation": ComponentType.load,
    "compteur": ComponentType.meter,
    "interrupteur": ComponentType.switch,
    "disjoncteur": ComponentType.switch,
    "breaker": ComponentType.switch,
    "jeu_de_barres": ComponentType.bus,
    "barbus": ComponentType.bus,
}

_GENERATION_TYPES = {
    ComponentType.generator,
    ComponentType.source,
    ComponentType.inverter,
    ComponentType.battery,
}


def normalize_component_type(value: Any) -> ComponentType:
    if isinstance(value, ComponentType):
        return value
    raw = str(value or "load").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in ("power_station", "powerstation", "station", "ps"):
        return ComponentType.generator
    if raw in ComponentType.__members__:
        return ComponentType[raw]
    try:
        return ComponentType(raw)
    except ValueError:
        pass
    if raw in COMPONENT_TYPE_ALIASES:
        return COMPONENT_TYPE_ALIASES[raw]
    for key, mapped in COMPONENT_TYPE_ALIASES.items():
        if key in raw or raw in key:
            return mapped
    return ComponentType.load


class LineKind(str, Enum):
    feeds = "feeds"
    connects = "connects"


class ElectricalState(BaseModel):
    """Grandeurs électriques générales (U, I, f) + P générique optionnelle."""

    P: Optional[float] = None
    U: Optional[float] = None
    I: Optional[float] = None
    f: Optional[float] = None


class ProductionRating(BaseModel):
    """Puissance d'un générateur (W)."""

    P_min: Optional[float] = None
    P_max: Optional[float] = None
    P_eff: Optional[float] = None  # production effective


class DemandRating(BaseModel):
    """Demande d'une charge (W)."""

    P_demand: Optional[float] = None


class LineTransport(BaseModel):
    """Limites et flux sur une ligne (W)."""

    P_max: Optional[float] = None  # limite de transport
    P_flow: Optional[float] = None  # flux effectif (from → to), estimé ou fixé


class ZoneBalance(BaseModel):
    """Bilan énergétique d'une zone (W) — recalculé par le moteur de bilan."""

    P_production: Optional[float] = None  # somme P_eff générateurs
    P_demand: Optional[float] = None  # somme P_demand charges
    P_surplus: Optional[float] = None  # production - demande (négatif = déficit)
    P_in: Optional[float] = None  # énergie entrante (lignes)
    P_out: Optional[float] = None  # énergie sortante / export
    P_exportable: Optional[float] = None  # surplus exportable après saturation lignes


class Component(BaseModel):
    id: str
    type: ComponentType
    label: str = ""
    electrical: ElectricalState = Field(default_factory=ElectricalState)
    production: ProductionRating = Field(default_factory=ProductionRating)
    demand: DemandRating = Field(default_factory=DemandRating)

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, v: Any) -> ComponentType:
        return normalize_component_type(v)


class PowerStation(BaseModel):
    id: str
    label: str = "Power Station"
    generators: list[Component] = Field(default_factory=list)
    electrical: ElectricalState = Field(default_factory=ElectricalState)


class Zone(BaseModel):
    id: str
    label: str = ""
    power_stations: list[PowerStation] = Field(default_factory=list)
    loads: list[Component] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    electrical: ElectricalState = Field(default_factory=ElectricalState)
    balance: ZoneBalance = Field(default_factory=ZoneBalance)
    parent_id: Optional[str] = None

    @model_validator(mode="after")
    def _migrate_flat_components(self) -> Zone:
        if not self.components:
            return self
        gens = [c for c in self.components if c.type in _GENERATION_TYPES]
        other = [c for c in self.components if c.type not in _GENERATION_TYPES]
        if gens:
            if self.power_stations:
                self.power_stations[0].generators.extend(gens)
            else:
                self.power_stations.append(
                    PowerStation(
                        id=f"ps_{self.id}",
                        label=f"Power Station {self.id}",
                        generators=gens,
                    )
                )
        if other:
            self.loads.extend(other)
        self.components = []
        return self

    def all_generators(self) -> list[Component]:
        out: list[Component] = []
        for ps in self.power_stations:
            out.extend(ps.generators)
        return out

    def all_leaf_components(self) -> list[Component]:
        return self.all_generators() + list(self.loads)


class Line(BaseModel):
    id: str
    from_zone: str
    to_zone: str
    kind: LineKind = LineKind.feeds
    transport: LineTransport = Field(default_factory=LineTransport)
    attrs: dict[str, Any] = Field(default_factory=dict)


class Meta(BaseModel):
    name: str = "Réseau"
    version: int = 1


class Actors(BaseModel):
    groupe_electrogene: Optional[str] = None
    compteur: Optional[str] = None
    dashboard: Optional[str] = None
    consommateurs: list[str] = Field(default_factory=list)


class NetworkModel(BaseModel):
    meta: Meta = Field(default_factory=Meta)
    zones: list[Zone] = Field(default_factory=list)
    lines: list[Line] = Field(default_factory=list)
    actors: Actors = Field(default_factory=Actors)


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: Optional[str] = None


class ValidationReport(BaseModel):
    ok: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)


OperationType = Literal[
    "add_zone",
    "update_zone",
    "remove_zone",
    "add_line",
    "update_line",
    "remove_line",
    "add_power_station",
    "remove_power_station",
    "add_generator",
    "remove_generator",
    "add_load",
    "remove_load",
    "add_component",
    "update_component",
    "remove_component",
    "update_electrical",
    "update_production",
    "update_demand",
    "update_line_transport",
    "recompute_balance",
]


class MutationOp(BaseModel):
    op: OperationType
    payload: dict[str, Any] = Field(default_factory=dict)


class Suggestion(BaseModel):
    id: str
    issue_code: str
    severity: Literal["error", "warning"] = "warning"
    title: str
    description: str
    operations: list[MutationOp] = Field(default_factory=list)


class ApplyOpsRequest(BaseModel):
    operations: list[MutationOp] = Field(default_factory=list)


class ApplyOpsResponse(BaseModel):
    network: NetworkModel
    validation: ValidationReport
    suggestions: list[Suggestion] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    operations: list[MutationOp] = Field(default_factory=list)
    network: NetworkModel
    validation: ValidationReport
    suggestions: list[Suggestion] = Field(default_factory=list)
