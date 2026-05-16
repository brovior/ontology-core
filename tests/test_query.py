"""query.py 단위 테스트 — 합성 in-memory DataSource 사용."""

import pytest
from ontology_core.data_source import DataSource
from ontology_core.query import OntologyQuery
from ontology_core.registry import Ontology
from ontology_core.schema import AttributeDef, DerivedConceptDef, EntityDef, RelationshipDef


# ---------------------------------------------------------------------------
# 합성 in-memory DataSource 구현체
# ---------------------------------------------------------------------------

class InMemoryDataSource:
    """테스트용 인메모리 DataSource 구현체."""

    def __init__(self, tables: dict[str, list[dict]], joins: dict[str, list[dict]]) -> None:
        """tables는 entity_name → 레코드 목록, joins는 rel_name → 레코드 목록."""
        self._tables = tables
        self._joins = joins

    def fetch(self, entity_name: str, key: dict) -> dict | None:
        """key의 모든 조건을 만족하는 첫 번째 레코드를 반환한다."""
        for row in self._tables.get(entity_name, []):
            if all(row.get(k) == v for k, v in key.items()):
                return row
        return None

    def fetch_many(self, entity_name: str, filter: dict) -> list[dict]:
        """filter 조건을 만족하는 레코드 목록을 반환한다."""
        return [
            row for row in self._tables.get(entity_name, [])
            if all(row.get(k) == v for k, v in filter.items())
        ]

    def fetch_all(self, entity_name: str) -> list[dict]:
        """엔티티의 모든 레코드를 반환한다."""
        return list(self._tables.get(entity_name, []))

    def join(self, rel_name: str, source_key: dict) -> list[dict]:
        """rel_name에 대해 미리 준비한 레코드 목록을 반환한다."""
        return list(self._joins.get(rel_name, []))


# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------

def _attr(name: str, unit: str = "none") -> AttributeDef:
    return AttributeDef(name=name, column_name=name.upper(), description="", data_type="str", unit=unit)


@pytest.fixture()
def ontology() -> Ontology:
    """테스트용 Ontology 픽스처."""
    onto = Ontology()
    onto.register_entity(EntityDef(
        name="MODEL",
        table_name="T_MODEL",
        description="모델",
        domain="test",
        primary_key=("model_cd",),
        attributes=(_attr("model_cd"), _attr("model_nm")),
    ))
    onto.register_entity(EntityDef(
        name="PLANT",
        table_name="T_PLANT",
        description="공장",
        domain="test",
        primary_key=("plant_cd",),
        attributes=(_attr("plant_cd"), _attr("plant_nm")),
    ))
    onto.register_entity(EntityDef(
        name="MODEL_PLANT_MAP",
        table_name="T_MODEL_PLANT_MAP",
        description="모델-공장 매핑",
        domain="test",
        primary_key=("model_cd", "plant_cd"),
        attributes=(_attr("model_cd"), _attr("plant_cd")),
    ))
    onto.register_relationship(RelationshipDef(
        name="MODEL_TO_PLANTS",
        source_entity="MODEL",
        target_entity="PLANT",
        cardinality="M:N",
        join_keys=(("model_cd", "model_cd"),),
        via_entity="MODEL_PLANT_MAP",
    ))
    onto.register_derived_concept(DerivedConceptDef(
        name="efficiency",
        formula_ref=lambda real_ct, st: round(st / real_ct, 4) if real_ct else 0.0,
        inputs=("real_ct", "st"),
        formula_text="st / real_ct",
    ))
    return onto


@pytest.fixture()
def data_source() -> InMemoryDataSource:
    """테스트용 인메모리 DataSource 픽스처."""
    tables: dict[str, list[dict]] = {
        "MODEL": [
            {"model_cd": "M001", "model_nm": "알파"},
            {"model_cd": "M002", "model_nm": "베타"},
        ],
        "PLANT": [
            {"plant_cd": "P1", "plant_nm": "서울공장"},
            {"plant_cd": "P2", "plant_nm": "부산공장"},
        ],
    }
    joins: dict[str, list[dict]] = {
        "MODEL_TO_PLANTS": [
            {"plant_cd": "P1", "plant_nm": "서울공장"},
            {"plant_cd": "P2", "plant_nm": "부산공장"},
        ],
    }
    return InMemoryDataSource(tables=tables, joins=joins)


@pytest.fixture()
def query(ontology: Ontology, data_source: InMemoryDataSource) -> OntologyQuery:
    """테스트용 OntologyQuery 픽스처."""
    return OntologyQuery(ontology=ontology, data_source=data_source)


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

class TestOntologyQueryGet:
    def test_get_existing(self, query: OntologyQuery) -> None:
        """존재하는 레코드 단건 조회."""
        result = query.get("MODEL", {"model_cd": "M001"})
        assert result is not None
        assert result["model_nm"] == "알파"

    def test_get_not_found(self, query: OntologyQuery) -> None:
        """없는 레코드 조회 시 None 반환."""
        result = query.get("MODEL", {"model_cd": "MISSING"})
        assert result is None

    def test_get_missing_pk_field(self, query: OntologyQuery) -> None:
        """primary_key 필드 누락 시 KeyError."""
        with pytest.raises(KeyError, match="primary_key"):
            query.get("MODEL", {"wrong_key": "M001"})

    def test_get_unknown_entity(self, query: OntologyQuery) -> None:
        """미등록 엔티티 조회 시 KeyError."""
        with pytest.raises(KeyError, match="등록되지 않은 엔티티"):
            query.get("UNKNOWN", {"id": "1"})


class TestOntologyQueryFetch:
    def test_fetch_many(self, query: OntologyQuery) -> None:
        """필터 조건으로 다건 조회."""
        results = query.fetch_many("MODEL", {"model_cd": "M001"})
        assert len(results) == 1
        assert results[0]["model_nm"] == "알파"

    def test_fetch_all(self, query: OntologyQuery) -> None:
        """전체 레코드 조회."""
        results = query.fetch_all("MODEL")
        assert len(results) == 2

    def test_fetch_all_unknown_entity(self, query: OntologyQuery) -> None:
        """미등록 엔티티 전체 조회 시 KeyError."""
        with pytest.raises(KeyError, match="등록되지 않은 엔티티"):
            query.fetch_all("UNKNOWN")


class TestOntologyQueryTraverse:
    def test_traverse(self, query: OntologyQuery) -> None:
        """관계를 통한 타겟 레코드 조회."""
        results = query.traverse("MODEL_TO_PLANTS", {"model_cd": "M001"})
        assert len(results) == 2
        plant_cds = {r["plant_cd"] for r in results}
        assert plant_cds == {"P1", "P2"}

    def test_traverse_unknown_rel(self, query: OntologyQuery) -> None:
        """미등록 관계 traverse 시 KeyError."""
        with pytest.raises(KeyError, match="등록되지 않은 관계"):
            query.traverse("UNKNOWN_REL", {"id": "1"})


class TestOntologyQueryDerive:
    def test_derive(self, query: OntologyQuery) -> None:
        """파생 개념 계산."""
        result = query.derive("efficiency", real_ct=10.0, st=8.0)
        assert result == pytest.approx(0.8)

    def test_derive_zero_real_ct(self, query: OntologyQuery) -> None:
        """real_ct가 0이면 0.0 반환."""
        result = query.derive("efficiency", real_ct=0.0, st=8.0)
        assert result == 0.0

    def test_derive_unknown_concept(self, query: OntologyQuery) -> None:
        """미등록 파생 개념 호출 시 KeyError."""
        with pytest.raises(KeyError, match="등록되지 않은 파생 개념"):
            query.derive("unknown_concept")
