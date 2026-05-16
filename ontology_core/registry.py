"""온톨로지 레지스트리 — EntityDef/RelationshipDef/DerivedConceptDef 등록 및 조회."""

from __future__ import annotations

from ontology_core.schema import DerivedConceptDef, EntityDef, RelationshipDef


class Ontology:
    """등록된 엔티티·관계·파생 개념을 보관하는 중앙 레지스트리."""

    def __init__(self) -> None:
        """내부 딕셔너리를 초기화한다."""
        self._entities: dict[str, EntityDef] = {}
        self._relationships: dict[str, RelationshipDef] = {}
        self._derived_concepts: dict[str, DerivedConceptDef] = {}

    def register_entity(self, entity_def: EntityDef) -> None:
        """EntityDef를 이름 기준으로 등록한다."""
        self._entities[entity_def.name] = entity_def

    def register_relationship(self, rel_def: RelationshipDef) -> None:
        """RelationshipDef를 이름 기준으로 등록한다."""
        self._relationships[rel_def.name] = rel_def

    def register_derived_concept(self, concept_def: DerivedConceptDef) -> None:
        """DerivedConceptDef를 이름 기준으로 등록한다."""
        self._derived_concepts[concept_def.name] = concept_def

    def get_entity(self, name: str) -> EntityDef:
        """이름으로 EntityDef를 조회한다. 없으면 KeyError."""
        if name not in self._entities:
            raise KeyError(f"등록되지 않은 엔티티: '{name}'")
        return self._entities[name]

    def get_relationship(self, name: str) -> RelationshipDef:
        """이름으로 RelationshipDef를 조회한다. 없으면 KeyError."""
        if name not in self._relationships:
            raise KeyError(f"등록되지 않은 관계: '{name}'")
        return self._relationships[name]

    def get_derived_concept(self, name: str) -> DerivedConceptDef:
        """이름으로 DerivedConceptDef를 조회한다. 없으면 KeyError."""
        if name not in self._derived_concepts:
            raise KeyError(f"등록되지 않은 파생 개념: '{name}'")
        return self._derived_concepts[name]

    def validate(self) -> list[str]:
        """등록된 메타데이터의 정합성을 검증하고 오류 메시지 목록을 반환한다."""
        errors: list[str] = []

        # EntityDef: primary_key 필드가 attributes에 존재하는지 확인
        for entity in self._entities.values():
            attr_names = entity.attribute_names
            for pk_field in entity.primary_key:
                if pk_field not in attr_names:
                    errors.append(
                        f"엔티티 '{entity.name}'의 primary_key '{pk_field}'가 "
                        f"attributes에 정의되지 않았습니다."
                    )

        # RelationshipDef: source/target/via_entity가 등록된 엔티티인지 확인
        for rel in self._relationships.values():
            if rel.source_entity not in self._entities:
                errors.append(
                    f"관계 '{rel.name}'의 source_entity '{rel.source_entity}'가 "
                    f"등록되지 않은 엔티티입니다."
                )
            if rel.target_entity not in self._entities:
                errors.append(
                    f"관계 '{rel.name}'의 target_entity '{rel.target_entity}'가 "
                    f"등록되지 않은 엔티티입니다."
                )
            if rel.via_entity and rel.via_entity not in self._entities:
                errors.append(
                    f"관계 '{rel.name}'의 via_entity '{rel.via_entity}'가 "
                    f"등록되지 않은 엔티티입니다."
                )

        return errors
