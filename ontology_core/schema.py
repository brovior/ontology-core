"""온톨로지 메타데이터 구조 정의 — EntityDef/AttributeDef/RelationshipDef/DerivedConceptDef."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttributeDef:
    """논리 컬럼 단위 메타데이터."""

    name: str
    column_name: str
    description: str
    data_type: str
    unit: str
    nullable: bool = True
    enum_values: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """unit 값 유효성 검증."""
        allowed_units = {"sec", "pct", "count", "grade", "weeks", "none"}
        if self.unit not in allowed_units:
            raise ValueError(f"허용되지 않는 unit: '{self.unit}'. 허용값: {allowed_units}")


@dataclass(frozen=True)
class EntityDef:
    """논리 엔티티(테이블) 단위 메타데이터."""

    name: str
    table_name: str
    description: str
    domain: str
    primary_key: tuple[str, ...]
    attributes: tuple[AttributeDef, ...]

    def get_attribute(self, attr_name: str) -> AttributeDef:
        """이름으로 AttributeDef를 조회한다. 없으면 KeyError."""
        for attr in self.attributes:
            if attr.name == attr_name:
                return attr
        raise KeyError(f"엔티티 '{self.name}'에 속성 '{attr_name}'이 존재하지 않습니다.")

    @property
    def attribute_names(self) -> set[str]:
        """모든 속성 이름의 집합을 반환한다."""
        return {attr.name for attr in self.attributes}


@dataclass(frozen=True)
class RelationshipDef:
    """두 엔티티 간의 관계 메타데이터."""

    name: str
    source_entity: str
    target_entity: str
    cardinality: str
    join_keys: tuple[tuple[str, str], ...]
    via_entity: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        """cardinality 값 유효성 검증."""
        allowed = {"1:1", "1:N", "M:N"}
        if self.cardinality not in allowed:
            raise ValueError(f"허용되지 않는 cardinality: '{self.cardinality}'. 허용값: {allowed}")


@dataclass(frozen=True)
class DerivedConceptDef:
    """파생 개념(계산 지표) 메타데이터."""

    name: str
    formula_ref: Callable[..., object]
    inputs: tuple[str, ...]
    formula_text: str
    description: str = ""
