"""온톨로지 레지스트리 — EntityDef/RelationshipDef/DerivedConceptDef 등록 및 조회."""

from __future__ import annotations

from ontology_core.schema import CodeConceptDef, DerivedConceptDef, EntityDef, ModuleDef, RelationshipDef, SqlDef


class Ontology:
    """등록된 엔티티·관계·파생 개념을 보관하는 중앙 레지스트리.

    CodeConceptDef는 validate()의 교차 참조 검증 대상이 아니다: scheme_name은
    자유 문자열이라 참조할 등록 대상이 없고, 필수값은 생성 시점(__post_init__)에,
    유일성은 등록 시점(register_code_concept)에 이미 강제되기 때문이다.
    """

    def __init__(self) -> None:
        """내부 딕셔너리를 초기화한다."""
        self._entities: dict[str, EntityDef] = {}
        self._relationships: dict[str, RelationshipDef] = {}
        self._derived_concepts: dict[str, DerivedConceptDef] = {}
        self._sqls: dict[str, SqlDef] = {}
        self._modules: dict[str, ModuleDef] = {}
        self._code_concepts: dict[tuple[str, str], CodeConceptDef] = {}

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

    def register_sql(self, sql_def: SqlDef) -> None:
        """SqlDef를 이름 기준으로 등록한다."""
        self._sqls[sql_def.name] = sql_def

    def get_sql(self, name: str) -> SqlDef:
        """이름으로 SqlDef를 조회한다. 없으면 KeyError."""
        if name not in self._sqls:
            raise KeyError(f"등록되지 않은 SQL: '{name}'")
        return self._sqls[name]

    def register_module(self, module_def: ModuleDef) -> None:
        """ModuleDef를 이름 기준으로 등록한다."""
        self._modules[module_def.name] = module_def

    def get_module(self, name: str) -> ModuleDef:
        """이름으로 ModuleDef를 조회한다. 없으면 KeyError."""
        if name not in self._modules:
            raise KeyError(f"등록되지 않은 모듈: '{name}'")
        return self._modules[name]

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

        for sql in self._sqls.values():
            if sql.entity not in self._entities:
                errors.append(
                    f"SQL '{sql.name}'의 entity '{sql.entity}'가 등록되지 않은 엔티티입니다."
                )

        for mod in self._modules.values():
            for e in mod.related_entities:
                if e not in self._entities:
                    errors.append(
                        f"모듈 '{mod.name}'의 related_entity '{e}'가 등록되지 않은 엔티티입니다."
                    )
            for s in mod.related_sqls:
                if s not in self._sqls:
                    errors.append(
                        f"모듈 '{mod.name}'의 related_sql '{s}'가 등록되지 않은 SQL입니다."
                    )

        return errors

    def list_entities(self) -> list[str]:
        """등록된 EntityDef 이름 목록을 반환한다."""
        return list(self._entities)

    def list_relationships(self) -> list[str]:
        """등록된 RelationshipDef 이름 목록을 반환한다."""
        return list(self._relationships)

    def list_derived_concepts(self) -> list[str]:
        """등록된 DerivedConceptDef 이름 목록을 반환한다."""
        return list(self._derived_concepts)

    def list_sqls(self) -> list[str]:
        """등록된 SqlDef 이름 목록을 반환한다."""
        return list(self._sqls)

    def list_modules(self) -> list[str]:
        """등록된 ModuleDef 이름 목록을 반환한다."""
        return list(self._modules)

    def get_entities_by_domain(self, domain: str) -> list[EntityDef]:
        """domain이 일치하는 EntityDef 목록을 반환한다."""
        return [e for e in self._entities.values() if e.domain == domain]

    def get_modules_by_layer(self, layer: str) -> list[ModuleDef]:
        """layer가 일치하는 ModuleDef 목록을 반환한다."""
        return [m for m in self._modules.values() if m.layer == layer]

    def get_entities_by_type(self, entity_type: str) -> list[EntityDef]:
        """entity_type이 일치하는 EntityDef 목록을 반환한다."""
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def register_code_concept(self, concept_def: CodeConceptDef) -> None:
        """CodeConceptDef를 (scheme_name, code_value) 복합키로 등록한다.

        이미 등록된 키이면 ValueError를 발생시킨다(다른 register_* 메서드와
        달리 덮어쓰기를 허용하지 않는다).
        """
        key = (concept_def.scheme_name, concept_def.code_value)
        if key in self._code_concepts:
            raise ValueError(f"이미 등록된 코드 컨셉: {key}")
        self._code_concepts[key] = concept_def

    def get_code_concept(self, scheme_name: str, code_value: str) -> CodeConceptDef:
        """(scheme_name, code_value)로 CodeConceptDef를 조회한다. 없으면 KeyError."""
        key = (scheme_name, code_value)
        if key not in self._code_concepts:
            raise KeyError(f"등록되지 않은 코드 컨셉: {key}")
        return self._code_concepts[key]

    def get_concepts_by_scheme(self, scheme_name: str) -> tuple[CodeConceptDef, ...]:
        """scheme_name이 일치하는 CodeConceptDef를 등록 순서대로 반환한다."""
        return tuple(c for c in self._code_concepts.values() if c.scheme_name == scheme_name)

    @property
    def code_concepts(self) -> tuple[CodeConceptDef, ...]:
        """등록된 모든 CodeConceptDef를 등록 순서대로 반환한다."""
        return tuple(self._code_concepts.values())

    def list_schemes(self) -> list[str]:
        """등록된 CodeConceptDef의 고유 scheme_name 목록을 등록 순서로 반환한다."""
        schemes: list[str] = []
        for concept in self._code_concepts.values():
            if concept.scheme_name not in schemes:
                schemes.append(concept.scheme_name)
        return schemes
