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
