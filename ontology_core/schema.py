"""온톨로지 메타데이터 구조 정의 — EntityDef/AttributeDef/RelationshipDef/DerivedConceptDef."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

ALLOWED_RELATION_TYPES = {"", "hierarchy", "reference", "code_reference"}


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
    entity_type: str = ""
    psl_tag: str = ""     # PSL(ISO 18629) 정합 태그 — 예: "activity", "subactivity"
    isa95_tag: str = ""   # ISA-95 정합 태그 — 예: "ProcessSegment", "Equipment"

    def __post_init__(self) -> None:
        """primary_key·attributes·entity_type 유효성 검증."""
        if not self.primary_key:
            raise ValueError("primary_key는 비어 있을 수 없습니다.")
        if not self.attributes:
            raise ValueError("attributes는 비어 있을 수 없습니다.")
        attr_names = [a.name for a in self.attributes]
        if len(attr_names) != len(set(attr_names)):
            raise ValueError("attributes에 중복된 name이 존재합니다.")
        allowed_types = {"M", "D", "P", "S", "C", "R"}
        if self.entity_type and self.entity_type not in allowed_types:
            raise ValueError(f"허용되지 않는 entity_type: '{self.entity_type}'. 허용값: {allowed_types}")

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
    """두 엔티티 간의 관계 메타데이터.

    relation_type 판정 예시:
    - HRNK_UNIQ_ID 자기참조 조인(계층 구조 탐색) → "hierarchy"
    - MODEL_CD 조인(단순 참조/FK 탐색) → "reference"
    - 코드 테이블(entity_type="C") 조인 → "code_reference"
    - 판정 불가/미분류 → "" (기본값)
    """

    name: str
    source_entity: str
    target_entity: str
    cardinality: str
    join_keys: tuple[tuple[str, str], ...]
    via_entity: str = ""
    description: str = ""
    relation_type: str = ""

    def __post_init__(self) -> None:
        """cardinality·relation_type 값 유효성 검증."""
        allowed = {"1:1", "1:N", "M:N"}
        if self.cardinality not in allowed:
            raise ValueError(f"허용되지 않는 cardinality: '{self.cardinality}'. 허용값: {allowed}")
        if self.relation_type not in ALLOWED_RELATION_TYPES:
            raise ValueError(
                f"허용되지 않는 relation_type: '{self.relation_type}'. 허용값: {ALLOWED_RELATION_TYPES}"
            )


@dataclass(frozen=True)
class DerivedConceptDef:
    """파생 개념(계산 지표) 메타데이터."""

    name: str
    formula_ref: Callable[..., object]
    inputs: tuple[str, ...]
    formula_text: str
    description: str = ""


@dataclass(frozen=True)
class SqlDef:
    """SQL 구문 단위 메타데이터."""

    name: str
    sql: str
    entity: str
    params: tuple[str, ...] = field(default_factory=tuple)
    sql_type: str = "SELECT"
    description: str = ""

    def __post_init__(self) -> None:
        """name/sql/entity 빈 문자열 및 sql_type 유효성 검증."""
        if not self.name:
            raise ValueError("name은 빈 문자열일 수 없습니다.")
        if not self.sql:
            raise ValueError("sql은 빈 문자열일 수 없습니다.")
        if not self.entity:
            raise ValueError("entity는 빈 문자열일 수 없습니다.")
        allowed_sql_types = {"SELECT", "INSERT", "UPDATE", "DELETE"}
        if self.sql_type not in allowed_sql_types:
            raise ValueError(f"허용되지 않는 sql_type: '{self.sql_type}'. 허용값: {allowed_sql_types}")


@dataclass(frozen=True)
class ModuleDef:
    """Java 소스 모듈 단위 메타데이터."""

    name: str
    layer: str
    file_path: str
    related_entities: tuple[str, ...] = field(default_factory=tuple)
    related_sqls: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    def __post_init__(self) -> None:
        """layer 값 유효성 검증."""
        allowed_layers = {"controller", "biz", "dao", "mapper"}
        if self.layer not in allowed_layers:
            raise ValueError(f"허용되지 않는 layer: '{self.layer}'. 허용값: {allowed_layers}")


@dataclass(frozen=True)
class CodeConceptDef:
    """코드값(enum) 단위 의미 메타데이터 — SKOS Concept에 대응."""

    scheme_name: str      # 코드그룹명 (SKOS ConceptScheme) — 예: "WORK_TYPE"
    code_value: str       # 코드값 — 예: "W"
    pref_label: str       # 코드명 (skos:prefLabel)
    definition: str = ""  # 복원된 업무 의미 (skos:definition)
    source_ref: str = ""  # 출처 식별자 (예: DAO 메서드명 / 코드 테이블명)

    def __post_init__(self) -> None:
        """scheme_name/code_value/pref_label 빈 문자열 검증."""
        if not self.scheme_name:
            raise ValueError("scheme_name은 빈 문자열일 수 없습니다.")
        if not self.code_value:
            raise ValueError("code_value는 빈 문자열일 수 없습니다.")
        if not self.pref_label:
            raise ValueError("pref_label은 빈 문자열일 수 없습니다.")
