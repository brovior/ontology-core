"""온톨로지 레지스트리 — EntityDef/RelationshipDef/DerivedConceptDef 등록 및 조회."""

from __future__ import annotations

from ontology_core.schema import CodeConceptDef, DerivedConceptDef, EntityDef, ModuleDef, RelationshipDef, RelationshipEvidenceDef, SqlDef


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
        self._relationship_evidence: dict[str, RelationshipEvidenceDef] = {}
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

    def register_relationship_evidence(self, evidence_def: RelationshipEvidenceDef) -> None:
        """관계 근거를 등록한다. 기존 이름은 덮어쓰지 않고 ValueError를 낸다."""
        if not isinstance(evidence_def, RelationshipEvidenceDef):
            raise TypeError("evidence_def는 RelationshipEvidenceDef이어야 합니다.")
        if evidence_def.name in self._relationship_evidence:
            raise ValueError(f"이미 등록된 관계 근거: '{evidence_def.name}'")
        self._relationship_evidence[evidence_def.name] = evidence_def

    def get_relationship_evidence(self, name: str) -> RelationshipEvidenceDef:
        """이름으로 관계 근거를 조회한다. 없으면 KeyError."""
        if name not in self._relationship_evidence:
            raise KeyError(f"등록되지 않은 관계 근거: '{name}'")
        return self._relationship_evidence[name]

    def list_relationship_evidence(self) -> list[str]:
        """등록된 관계 근거 이름을 등록 순서로 반환한다."""
        return list(self._relationship_evidence)

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

        errors.extend(self._validate_relationship_evidence())
        return errors

    def _validate_relationship_evidence(self) -> list[str]:
        """논리 끝점·그룹·기준 관계 참조를 추론 없이 검증한다."""
        errors: list[str] = []
        groups: dict[tuple[tuple[str, ...], str], list[RelationshipEvidenceDef]] = {}
        for evidence in self._relationship_evidence.values():
            for endpoint in (evidence.source_endpoint, evidence.target_endpoint):
                if endpoint.entity_ref:
                    entity = self._entities.get(endpoint.entity_ref)
                    if entity is None:
                        errors.append(f"근거 '{evidence.name}'의 entity_ref '{endpoint.entity_ref}'가 등록되지 않았습니다.")
                    elif entity.table_name != endpoint.table_ref:
                        errors.append(f"근거 '{evidence.name}'의 table_ref '{endpoint.table_ref}'가 엔티티 테이블과 다릅니다.")
            pair = tuple(sorted((evidence.source_endpoint.table_ref, evidence.target_endpoint.table_ref)))
            groups.setdefault((pair, evidence.group_id), []).append(evidence)

        for (pair, group_id), members in groups.items():
            active_members = [e for e in members if e.role in {"CANONICAL", "SUPPORTING_OBSERVATION"}]
            canonicals = [e for e in active_members if e.role == "CANONICAL"]
            if active_members and len(canonicals) != 1:
                errors.append(f"근거 그룹 '{group_id}' {pair}에는 CANONICAL이 정확히 1개 필요합니다.")
            if any(not e.source_endpoint.entity_ref or not e.target_endpoint.entity_ref for e in members):
                if any(e.relationship_name for e in members):
                    errors.append(f"근거 그룹 '{group_id}' {pair}의 미물질화 끝점에는 활성 관계 참조를 허용하지 않습니다.")

        for evidence in self._relationship_evidence.values():
            rel = self._relationships.get(evidence.relationship_name)
            if evidence.relationship_name and rel is None:
                errors.append(f"근거 '{evidence.name}'의 relationship_name '{evidence.relationship_name}'이 등록되지 않았습니다.")
            canonical = evidence
            if evidence.canonical_evidence_name:
                canonical = self._relationship_evidence.get(evidence.canonical_evidence_name)
                if canonical is None or canonical.role != "CANONICAL":
                    errors.append(f"근거 '{evidence.name}'의 canonical_evidence_name은 실제 CANONICAL을 참조해야 합니다.")
                    continue
                same_pair = sorted((evidence.source_endpoint.table_ref, evidence.target_endpoint.table_ref)) == sorted((canonical.source_endpoint.table_ref, canonical.target_endpoint.table_ref))
                if evidence.group_id != canonical.group_id or not same_pair:
                    errors.append(f"근거 '{evidence.name}'은 CANONICAL과 같은 그룹·논리 끝점을 가져야 합니다.")
                if evidence.relationship_name and evidence.relationship_name != canonical.relationship_name:
                    errors.append(f"근거 '{evidence.name}'의 relationship_name은 CANONICAL의 관계와 같아야 합니다.")

            if rel is None:
                continue
            source = canonical.source_endpoint.entity_ref
            target = canonical.target_endpoint.entity_ref
            keys = set(canonical.join_keys)
            forward = (rel.source_entity, rel.target_entity) == (source, target) and set(rel.join_keys) == keys
            reverse = (rel.source_entity, rel.target_entity) == (target, source) and set(rel.join_keys) == {(right, left) for left, right in keys}
            if not (forward or reverse):
                errors.append(f"근거 '{evidence.name}'의 활성 관계 끝점·기준 join_keys가 CANONICAL과 다릅니다.")
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
