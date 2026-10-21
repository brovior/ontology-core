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

    cardinality 값 의미:
    - "1:1" / "1:N" / "M:N": 구조적으로 증명(또는 판정)된 카디널리티.
    - "UNKNOWN": 관계 자체는 관측·복원됐으나 카디널리티가 미증명 — 소비자가
      단정 대신 정직한 공백을 기록할 때 사용한다. (판정 대기 같은 파이프라인의
      일시 상태(예: "REVIEW")는 관계의 속성이 아니므로 허용하지 않는다.)

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
    source_ref: str = ""  # 출처 식별자 (예: 관계를 관측한 DAO 메서드명; 검증 없는 열린 값)

    def __post_init__(self) -> None:
        """cardinality·relation_type 값 유효성 검증."""
        allowed = {"1:1", "1:N", "M:N", "UNKNOWN"}
        if self.cardinality not in allowed:
            raise ValueError(f"허용되지 않는 cardinality: '{self.cardinality}'. 허용값: {allowed}")
        if self.relation_type not in ALLOWED_RELATION_TYPES:
            raise ValueError(
                f"허용되지 않는 relation_type: '{self.relation_type}'. 허용값: {ALLOWED_RELATION_TYPES}"
            )


ALLOWED_UNMATERIALIZED_REASONS = frozenset({
    "OUT_OF_SCOPE", "NOT_WHITELISTED", "PK_UNKNOWN", "DICT_MISSING",
    "NO_COLUMNS", "PK_COL_MISSING",
})
ALLOWED_EVIDENCE_ROLES = frozenset({"CANONICAL", "SUPPORTING_OBSERVATION", "HOLD", "EXCLUDED"})
ALLOWED_ASSESSMENT_STATUSES = frozenset({"UNASSESSED", "RESOLVED", "UNRESOLVED", "CONFLICT"})


def _check_text(name: str, value: str, *, required: bool = False) -> None:
    """새 근거 필드의 문자열 타입과 필수 식별자를 검증한다."""
    if not isinstance(value, str):
        raise TypeError(f"{name}은 문자열이어야 합니다.")
    if required and not value.strip():
        raise ValueError(f"{name}은 비어 있을 수 없습니다.")


@dataclass(frozen=True)
class EvidenceEndpointDef:
    """관측 테이블의 논리 끝점과 선택적 실제 엔티티 참조."""

    table_ref: str
    entity_ref: str = ""
    unmaterialized_reason: str = ""

    def __post_init__(self) -> None:
        """끝점 식별자와 물질화 상태의 구조적 일관성을 검증한다."""
        _check_text("table_ref", self.table_ref, required=True)
        _check_text("entity_ref", self.entity_ref)
        _check_text("unmaterialized_reason", self.unmaterialized_reason)
        if self.entity_ref:
            if not self.entity_ref.strip():
                raise ValueError("entity_ref는 공백 식별자일 수 없습니다.")
            if self.unmaterialized_reason:
                raise ValueError("entity_ref가 있으면 unmaterialized_reason은 공란이어야 합니다.")
        elif self.unmaterialized_reason not in ALLOWED_UNMATERIALIZED_REASONS:
            raise ValueError(f"허용되지 않는 unmaterialized_reason: '{self.unmaterialized_reason}'")


@dataclass(frozen=True)
class EvidenceSourceDef:
    """출처·문맥·입력 스냅샷의 대응을 보존하는 불변 레코드."""

    source_ref: str
    context_ref: str = ""
    snapshot_ref: str = ""

    def __post_init__(self) -> None:
        """출처 필수값과 문자열 타입을 검증한다."""
        _check_text("source_ref", self.source_ref, required=True)
        _check_text("context_ref", self.context_ref)
        _check_text("snapshot_ref", self.snapshot_ref)


@dataclass(frozen=True)
class RelationshipEvidenceDef:
    """전체 관측 시그니처·전문가 분류·평가 상태를 보존하는 관계 근거.

    CANONICAL은 그룹 대표이며 안전한 기본 조인을 뜻하지 않는다. 이 타입은
    관계를 활성화하거나 카디널리티를 추론하지 않는다.
    """

    name: str
    source_endpoint: EvidenceEndpointDef
    target_endpoint: EvidenceEndpointDef
    join_keys: tuple[tuple[str, str], ...]
    role: str
    group_id: str = ""
    canonical_evidence_name: str = ""
    relationship_name: str = ""
    sources: tuple[EvidenceSourceDef, ...] = ()
    review_status: str = ""
    reason_code: str = ""
    description: str = ""
    assessment_status: str = "UNASSESSED"
    assessment_method: str = ""

    def __post_init__(self) -> None:
        """불변 컬렉션·중첩 타입·분류 및 역할별 필수값을 검증한다."""
        for name in ("name", "role", "group_id", "canonical_evidence_name", "relationship_name",
                     "review_status", "reason_code", "description", "assessment_status", "assessment_method"):
            _check_text(name, getattr(self, name), required=name in {"name", "role", "assessment_status"})
        for name in ("group_id", "canonical_evidence_name", "relationship_name"):
            if getattr(self, name) and not getattr(self, name).strip():
                raise ValueError(f"{name}은 공백 식별자일 수 없습니다.")
        for name in ("source_endpoint", "target_endpoint"):
            if not isinstance(getattr(self, name), EvidenceEndpointDef):
                raise TypeError(f"{name}은 EvidenceEndpointDef이어야 합니다.")
        if not isinstance(self.join_keys, tuple):
            raise TypeError("join_keys는 tuple이어야 합니다.")
        if not self.join_keys:
            raise ValueError("join_keys는 비어 있을 수 없습니다.")
        for pair in self.join_keys:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise TypeError("join_keys 항목은 2원 tuple이어야 합니다.")
            for column in pair:
                _check_text("join_keys 컬럼", column, required=True)
        if len(set(self.join_keys)) != len(self.join_keys):
            raise ValueError("join_keys에 중복 컬럼쌍이 있습니다.")
        if not isinstance(self.sources, tuple) or any(not isinstance(s, EvidenceSourceDef) for s in self.sources):
            raise TypeError("sources는 EvidenceSourceDef tuple이어야 합니다.")
        if self.role not in ALLOWED_EVIDENCE_ROLES:
            raise ValueError(f"허용되지 않는 role: '{self.role}'")
        if self.assessment_status not in ALLOWED_ASSESSMENT_STATUSES:
            raise ValueError(f"허용되지 않는 assessment_status: '{self.assessment_status}'")
        if self.role in {"CANONICAL", "SUPPORTING_OBSERVATION"} and not self.group_id:
            raise ValueError("CANONICAL/SUPPORTING_OBSERVATION에는 group_id가 필요합니다.")
        if self.role == "CANONICAL" and self.canonical_evidence_name:
            raise ValueError("CANONICAL은 canonical_evidence_name을 지정할 수 없습니다.")
        if self.role == "SUPPORTING_OBSERVATION" and not self.canonical_evidence_name:
            raise ValueError("SUPPORTING_OBSERVATION에는 canonical_evidence_name이 필요합니다.")
        if self.role in {"HOLD", "EXCLUDED"} and self.relationship_name:
            raise ValueError("HOLD/EXCLUDED는 relationship_name을 지정할 수 없습니다.")


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
