"""OntologyQuery — 온톨로지 메타데이터를 이용한 데이터 조회 엔진."""

from __future__ import annotations

from ontology_core.data_source import DataSource
from ontology_core.registry import Ontology


class OntologyQuery:
    """Ontology 메타데이터와 DataSource를 결합한 쿼리 엔진."""

    def __init__(self, ontology: Ontology, data_source: DataSource) -> None:
        """Ontology 레지스트리와 DataSource 구현체를 주입받아 초기화한다."""
        self._ontology = ontology
        self._data_source = data_source

    def get(self, entity_name: str, key: dict) -> dict | None:
        """primary_key 필드 존재 검증 후 단건 레코드를 반환한다. 없으면 None."""
        entity_def = self._ontology.get_entity(entity_name)
        for pk_field in entity_def.primary_key:
            if pk_field not in key:
                raise KeyError(
                    f"엔티티 '{entity_name}'의 primary_key '{pk_field}'가 "
                    f"key 딕셔너리에 없습니다."
                )
        return self._data_source.fetch(entity_name, key)

    def fetch_many(self, entity_name: str, filter: dict) -> list[dict]:
        """필터 조건에 맞는 레코드 목록을 반환한다."""
        self._ontology.get_entity(entity_name)  # 엔티티 등록 여부 검증
        return self._data_source.fetch_many(entity_name, filter)

    def fetch_all(self, entity_name: str) -> list[dict]:
        """엔티티의 모든 레코드를 반환한다."""
        self._ontology.get_entity(entity_name)  # 엔티티 등록 여부 검증
        return self._data_source.fetch_all(entity_name)

    def traverse(self, rel_name: str, source_key: dict) -> list[dict]:
        """RelationshipDef를 해석하고 연결된 타겟 레코드 목록을 반환한다."""
        self._ontology.get_relationship(rel_name)  # 관계 등록 여부 검증
        return self._data_source.join(rel_name, source_key)

    def derive(self, concept_name: str, **records: object) -> object:
        """DerivedConceptDef의 formula_ref를 호출하여 파생 값을 계산한다."""
        concept_def = self._ontology.get_derived_concept(concept_name)
        return concept_def.formula_ref(**records)
