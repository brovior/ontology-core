"""registry.py 단위 테스트."""

import pytest
from ontology_core.registry import Ontology
from ontology_core.schema import AttributeDef, DerivedConceptDef, EntityDef, ModuleDef, RelationshipDef, SqlDef


def _attr(name: str) -> AttributeDef:
    """테스트용 AttributeDef 생성 헬퍼."""
    return AttributeDef(name=name, column_name=name.upper(), description="", data_type="str", unit="none")


def _entity(name: str, pk: str = "id") -> EntityDef:
    """테스트용 EntityDef 생성 헬퍼."""
    return EntityDef(
        name=name,
        table_name=f"T_{name}",
        description="",
        domain="test",
        primary_key=(pk,),
        attributes=(_attr(pk), _attr("name")),
    )


def _rel(name: str, src: str, tgt: str, cardinality: str = "1:N") -> RelationshipDef:
    """테스트용 RelationshipDef 생성 헬퍼."""
    return RelationshipDef(
        name=name,
        source_entity=src,
        target_entity=tgt,
        cardinality=cardinality,
        join_keys=(("id", "id"),),
    )


class TestOntologyRegisterAndGet:
    def test_register_and_get_entity(self) -> None:
        """EntityDef 등록 후 조회."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        assert onto.get_entity("MODEL").name == "MODEL"

    def test_get_entity_not_found(self) -> None:
        """미등록 엔티티 조회 시 KeyError."""
        onto = Ontology()
        with pytest.raises(KeyError, match="등록되지 않은 엔티티"):
            onto.get_entity("MISSING")

    def test_register_and_get_relationship(self) -> None:
        """RelationshipDef 등록 후 조회."""
        onto = Ontology()
        onto.register_relationship(_rel("MODEL_PLANT", "MODEL", "PLANT"))
        assert onto.get_relationship("MODEL_PLANT").source_entity == "MODEL"

    def test_get_relationship_not_found(self) -> None:
        """미등록 관계 조회 시 KeyError."""
        onto = Ontology()
        with pytest.raises(KeyError, match="등록되지 않은 관계"):
            onto.get_relationship("MISSING")

    def test_register_and_get_derived_concept(self) -> None:
        """DerivedConceptDef 등록 후 조회."""
        onto = Ontology()
        concept = DerivedConceptDef(
            name="efficiency",
            formula_ref=lambda real_ct, st: st / real_ct,
            inputs=("real_ct", "st"),
            formula_text="st / real_ct",
        )
        onto.register_derived_concept(concept)
        assert onto.get_derived_concept("efficiency").name == "efficiency"

    def test_get_derived_concept_not_found(self) -> None:
        """미등록 파생 개념 조회 시 KeyError."""
        onto = Ontology()
        with pytest.raises(KeyError, match="등록되지 않은 파생 개념"):
            onto.get_derived_concept("MISSING")


class TestOntologyValidate:
    def test_validate_clean(self) -> None:
        """정합성 문제 없으면 빈 리스트 반환."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        onto.register_entity(_entity("PLANT"))
        onto.register_relationship(_rel("MODEL_PLANT", "MODEL", "PLANT"))
        assert onto.validate() == []

    def test_validate_pk_not_in_attributes(self) -> None:
        """primary_key 필드가 attributes에 없으면 오류."""
        onto = Ontology()
        bad_entity = EntityDef(
            name="BAD",
            table_name="T_BAD",
            description="",
            domain="test",
            primary_key=("nonexistent_pk",),
            attributes=(_attr("id"),),
        )
        onto.register_entity(bad_entity)
        errors = onto.validate()
        assert any("nonexistent_pk" in e for e in errors)

    def test_validate_rel_source_missing(self) -> None:
        """관계의 source_entity가 미등록이면 오류."""
        onto = Ontology()
        onto.register_entity(_entity("PLANT"))
        onto.register_relationship(_rel("R", "MODEL", "PLANT"))
        errors = onto.validate()
        assert any("source_entity" in e and "MODEL" in e for e in errors)

    def test_validate_rel_target_missing(self) -> None:
        """관계의 target_entity가 미등록이면 오류."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        onto.register_relationship(_rel("R", "MODEL", "PLANT"))
        errors = onto.validate()
        assert any("target_entity" in e and "PLANT" in e for e in errors)

    def test_validate_rel_via_entity_missing(self) -> None:
        """관계의 via_entity가 미등록이면 오류."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        onto.register_entity(_entity("PLANT"))
        rel = RelationshipDef(
            name="R",
            source_entity="MODEL",
            target_entity="PLANT",
            cardinality="M:N",
            join_keys=(("id", "id"),),
            via_entity="MISSING_MAP",
        )
        onto.register_relationship(rel)
        errors = onto.validate()
        assert any("via_entity" in e and "MISSING_MAP" in e for e in errors)

    def test_validate_multiple_errors(self) -> None:
        """복수 오류 모두 수집."""
        onto = Ontology()
        bad = EntityDef(
            name="BAD",
            table_name="T_BAD",
            description="",
            domain="test",
            primary_key=("pk1", "pk2"),
            attributes=(_attr("id"),),
        )
        onto.register_entity(bad)
        errors = onto.validate()
        assert len(errors) == 2

    def test_validate_empty_registry_returns_empty(self) -> None:
        """빈 레지스트리에서 validate()는 빈 리스트를 반환한다."""
        assert Ontology().validate() == []


def _sql(name: str = "GET_MODEL", entity: str = "MODEL") -> SqlDef:
    """테스트용 SqlDef 생성 헬퍼."""
    return SqlDef(name=name, sql="SELECT * FROM T_MODEL WHERE MODEL_CD = :model_cd", entity=entity)


def _module(name: str = "ModelController", layer: str = "controller", **kwargs: object) -> ModuleDef:
    """테스트용 ModuleDef 생성 헬퍼."""
    return ModuleDef(name=name, layer=layer, file_path=f"com/example/{name}.java", **kwargs)  # type: ignore[arg-type]


class TestOntologySqlModule:
    def test_register_and_get_sql(self) -> None:
        """SqlDef 등록 후 이름으로 조회."""
        onto = Ontology()
        onto.register_sql(_sql("GET_MODEL", "MODEL"))
        assert onto.get_sql("GET_MODEL").entity == "MODEL"

    def test_get_sql_not_found(self) -> None:
        """미등록 SQL 조회 시 KeyError."""
        onto = Ontology()
        with pytest.raises(KeyError, match="등록되지 않은 SQL"):
            onto.get_sql("MISSING")

    def test_register_and_get_module(self) -> None:
        """ModuleDef 등록 후 이름으로 조회."""
        onto = Ontology()
        onto.register_module(_module("ModelController", "controller"))
        assert onto.get_module("ModelController").layer == "controller"

    def test_get_module_not_found(self) -> None:
        """미등록 모듈 조회 시 KeyError."""
        onto = Ontology()
        with pytest.raises(KeyError, match="등록되지 않은 모듈"):
            onto.get_module("MISSING")

    def test_validate_sql_unknown_entity(self) -> None:
        """SqlDef.entity가 미등록이면 validate()가 오류 반환."""
        onto = Ontology()
        onto.register_sql(_sql("Q", "UNKNOWN_ENTITY"))
        errors = onto.validate()
        assert any("UNKNOWN_ENTITY" in e for e in errors)

    def test_validate_module_unknown_entity(self) -> None:
        """ModuleDef.related_entities에 미등록 엔티티가 있으면 오류 반환."""
        onto = Ontology()
        onto.register_module(_module(related_entities=("GHOST",)))
        errors = onto.validate()
        assert any("GHOST" in e for e in errors)

    def test_validate_module_unknown_sql(self) -> None:
        """ModuleDef.related_sqls에 미등록 SQL이 있으면 오류 반환."""
        onto = Ontology()
        onto.register_module(_module(related_sqls=("GHOST_SQL",)))
        errors = onto.validate()
        assert any("GHOST_SQL" in e for e in errors)

    def test_validate_clean_with_sql_and_module(self) -> None:
        """모두 정상 등록 시 validate()가 빈 리스트 반환."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        onto.register_sql(_sql("GET_MODEL", "MODEL"))
        onto.register_module(_module(related_entities=("MODEL",), related_sqls=("GET_MODEL",)))
        assert onto.validate() == []


def _entity_domain(name: str, domain: str) -> EntityDef:
    """도메인 지정 EntityDef 생성 헬퍼."""
    pk = "id"
    return EntityDef(
        name=name, table_name=f"T_{name}", description="", domain=domain,
        primary_key=(pk,), attributes=(_attr(pk), _attr("name")),
    )


def _entity_typed(name: str, entity_type: str) -> EntityDef:
    """entity_type 지정 EntityDef 생성 헬퍼."""
    pk = "id"
    return EntityDef(
        name=name, table_name=f"T_{name}", description="", domain="test",
        primary_key=(pk,), attributes=(_attr(pk), _attr("name")),
        entity_type=entity_type,
    )


class TestOntologyListMethods:
    def test_list_entities_empty(self) -> None:
        """빈 레지스트리에서 list_entities()는 빈 리스트를 반환한다."""
        assert Ontology().list_entities() == []

    def test_list_entities(self) -> None:
        """등록된 엔티티 이름 목록을 반환한다."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        onto.register_entity(_entity("PLANT"))
        assert onto.list_entities() == ["MODEL", "PLANT"]

    def test_list_relationships(self) -> None:
        """등록된 관계 이름 목록을 반환한다."""
        onto = Ontology()
        onto.register_relationship(_rel("R1", "A", "B"))
        assert onto.list_relationships() == ["R1"]

    def test_list_derived_concepts(self) -> None:
        """등록된 파생 개념 이름 목록을 반환한다."""
        onto = Ontology()
        onto.register_derived_concept(
            DerivedConceptDef(name="eff", formula_ref=lambda x: x, inputs=("x",), formula_text="x")
        )
        assert onto.list_derived_concepts() == ["eff"]

    def test_list_sqls(self) -> None:
        """등록된 SQL 이름 목록을 반환한다."""
        onto = Ontology()
        onto.register_sql(_sql("Q1", "MODEL"))
        onto.register_sql(_sql("Q2", "MODEL"))
        assert onto.list_sqls() == ["Q1", "Q2"]

    def test_list_modules(self) -> None:
        """등록된 모듈 이름 목록을 반환한다."""
        onto = Ontology()
        onto.register_module(_module("Ctrl", "controller"))
        assert onto.list_modules() == ["Ctrl"]

    def test_get_entities_by_domain(self) -> None:
        """domain이 일치하는 엔티티 목록을 반환한다."""
        onto = Ontology()
        onto.register_entity(_entity_domain("MODEL", "제조"))
        onto.register_entity(_entity_domain("PLANT", "제조"))
        onto.register_entity(_entity_domain("USER", "인사"))
        result = onto.get_entities_by_domain("제조")
        assert len(result) == 2
        assert {e.name for e in result} == {"MODEL", "PLANT"}

    def test_get_entities_by_domain_no_match(self) -> None:
        """없는 도메인이면 빈 리스트를 반환한다."""
        onto = Ontology()
        onto.register_entity(_entity("MODEL"))
        assert onto.get_entities_by_domain("없는도메인") == []

    def test_get_modules_by_layer(self) -> None:
        """layer가 일치하는 모듈 목록을 반환한다."""
        onto = Ontology()
        onto.register_module(_module("Ctrl", "controller"))
        onto.register_module(_module("Svc", "biz"))
        onto.register_module(_module("Dao", "dao"))
        result = onto.get_modules_by_layer("dao")
        assert len(result) == 1
        assert result[0].name == "Dao"

    def test_get_modules_by_layer_no_match(self) -> None:
        """없는 layer면 빈 리스트를 반환한다."""
        onto = Ontology()
        assert onto.get_modules_by_layer("mapper") == []

    def test_get_entities_by_type(self) -> None:
        """entity_type이 일치하는 엔티티 목록을 반환한다."""
        onto = Ontology()
        onto.register_entity(_entity_typed("COMM_CD", "C"))
        onto.register_entity(_entity_typed("USER_CD", "C"))
        onto.register_entity(_entity_typed("MODEL", "M"))
        result = onto.get_entities_by_type("C")
        assert len(result) == 2
        assert {e.name for e in result} == {"COMM_CD", "USER_CD"}

    def test_get_entities_by_type_no_match(self) -> None:
        """없는 유형이면 빈 리스트를 반환한다."""
        onto = Ontology()
        onto.register_entity(_entity_typed("MODEL", "M"))
        assert onto.get_entities_by_type("R") == []
