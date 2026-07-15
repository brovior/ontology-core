"""schema.py 단위 테스트."""

import pytest
from ontology_core.schema import (
    AttributeDef,
    CodeConceptDef,
    DerivedConceptDef,
    EntityDef,
    ModuleDef,
    RelationshipDef,
    SqlDef,
)


def _make_attr(name: str = "id", unit: str = "none") -> AttributeDef:
    """테스트용 AttributeDef 생성 헬퍼."""
    return AttributeDef(
        name=name,
        column_name=name.upper(),
        description=f"{name} 설명",
        data_type="str",
        unit=unit,
    )


class TestAttributeDef:
    def test_create_basic(self) -> None:
        """기본 AttributeDef 생성."""
        attr = _make_attr("plant_cd", "none")
        assert attr.name == "plant_cd"
        assert attr.column_name == "PLANT_CD"
        assert attr.nullable is True
        assert attr.enum_values == ()

    def test_invalid_unit_raises(self) -> None:
        """허용되지 않는 unit이면 ValueError."""
        with pytest.raises(ValueError, match="허용되지 않는 unit"):
            AttributeDef(name="x", column_name="X", description="", data_type="str", unit="invalid")

    def test_all_valid_units(self) -> None:
        """모든 허용 unit이 정상 생성."""
        for unit in ("sec", "pct", "count", "grade", "weeks", "none"):
            attr = _make_attr("x", unit)
            assert attr.unit == unit

    def test_frozen(self) -> None:
        """frozen=True — 속성 변경 불가."""
        attr = _make_attr()
        with pytest.raises((AttributeError, TypeError)):
            attr.name = "changed"  # type: ignore[misc]


class TestEntityDef:
    def _make_entity(self) -> EntityDef:
        """테스트용 EntityDef 생성 헬퍼."""
        return EntityDef(
            name="MODEL",
            table_name="T_MODEL",
            description="모델 마스터",
            domain="제조",
            primary_key=("model_cd",),
            attributes=(
                _make_attr("model_cd"),
                _make_attr("model_nm"),
            ),
        )

    def test_create(self) -> None:
        """EntityDef 정상 생성."""
        entity = self._make_entity()
        assert entity.name == "MODEL"
        assert "model_cd" in entity.attribute_names

    def test_get_attribute(self) -> None:
        """get_attribute로 AttributeDef 조회."""
        entity = self._make_entity()
        attr = entity.get_attribute("model_cd")
        assert attr.name == "model_cd"

    def test_get_attribute_not_found(self) -> None:
        """없는 속성 조회 시 KeyError."""
        entity = self._make_entity()
        with pytest.raises(KeyError, match="속성"):
            entity.get_attribute("nonexistent")

    def test_frozen(self) -> None:
        """frozen=True — 속성 변경 불가."""
        entity = self._make_entity()
        with pytest.raises((AttributeError, TypeError)):
            entity.name = "changed"  # type: ignore[misc]

    def test_empty_primary_key_raises(self) -> None:
        """primary_key가 빈 tuple이면 ValueError."""
        with pytest.raises(ValueError, match="primary_key는 비어 있을 수 없습니다"):
            EntityDef(
                name="E", table_name="T_E", description="", domain="test",
                primary_key=(),
                attributes=(_make_attr("id"),),
            )

    def test_empty_attributes_raises(self) -> None:
        """attributes가 빈 tuple이면 ValueError."""
        with pytest.raises(ValueError, match="attributes는 비어 있을 수 없습니다"):
            EntityDef(
                name="E", table_name="T_E", description="", domain="test",
                primary_key=("id",),
                attributes=(),
            )

    def test_duplicate_attribute_names_raises(self) -> None:
        """attributes에 중복 name이 있으면 ValueError."""
        with pytest.raises(ValueError, match="중복된 name"):
            EntityDef(
                name="E", table_name="T_E", description="", domain="test",
                primary_key=("id",),
                attributes=(_make_attr("id"), _make_attr("id")),
            )

    def test_entity_type_default_empty(self) -> None:
        """entity_type 기본값은 빈 문자열(미분류)."""
        entity = self._make_entity()
        assert entity.entity_type == ""

    def test_all_valid_entity_types(self) -> None:
        """모든 허용 entity_type이 정상 생성."""
        for et in ("M", "D", "P", "S", "C", "R"):
            entity = EntityDef(
                name="E", table_name="T_E", description="", domain="test",
                primary_key=("id",), attributes=(_make_attr("id"),),
                entity_type=et,
            )
            assert entity.entity_type == et

    def test_invalid_entity_type_raises(self) -> None:
        """허용되지 않는 entity_type이면 ValueError."""
        with pytest.raises(ValueError, match="허용되지 않는 entity_type"):
            EntityDef(
                name="E", table_name="T_E", description="", domain="test",
                primary_key=("id",), attributes=(_make_attr("id"),),
                entity_type="X",
            )

    def test_psl_isa95_tag_defaults_empty(self) -> None:
        """psl_tag/isa95_tag 기본값은 빈 문자열."""
        entity = self._make_entity()
        assert entity.psl_tag == ""
        assert entity.isa95_tag == ""

    def test_psl_isa95_tag_arbitrary_value(self) -> None:
        """psl_tag/isa95_tag는 임의 값을 자유롭게 설정할 수 있다(열린 어휘)."""
        entity = EntityDef(
            name="E", table_name="T_E", description="", domain="test",
            primary_key=("id",), attributes=(_make_attr("id"),),
            psl_tag="activity", isa95_tag="ProcessSegment",
        )
        assert entity.psl_tag == "activity"
        assert entity.isa95_tag == "ProcessSegment"

    def test_positional_args_backward_compatible(self) -> None:
        """신규 필드 없이 위치 인자만으로 생성해도 동작한다(하위 호환)."""
        entity = EntityDef(
            "E", "T_E", "설명", "test",
            ("id",),
            (_make_attr("id"),),
        )
        assert entity.name == "E"
        assert entity.entity_type == ""
        assert entity.psl_tag == ""
        assert entity.isa95_tag == ""


class TestRelationshipDef:
    def test_create(self) -> None:
        """RelationshipDef 정상 생성."""
        rel = RelationshipDef(
            name="MODEL_PLANT",
            source_entity="MODEL",
            target_entity="PLANT",
            cardinality="M:N",
            join_keys=(("model_cd", "model_cd"),),
            via_entity="MODEL_PLANT_MAP",
        )
        assert rel.cardinality == "M:N"
        assert rel.via_entity == "MODEL_PLANT_MAP"

    def test_invalid_cardinality(self) -> None:
        """허용되지 않는 cardinality이면 ValueError."""
        with pytest.raises(ValueError, match="허용되지 않는 cardinality"):
            RelationshipDef(
                name="R",
                source_entity="A",
                target_entity="B",
                cardinality="N:M",
                join_keys=(("id", "id"),),
            )

    def test_all_valid_cardinalities(self) -> None:
        """허용되는 cardinality 값 4개 전부 정상 생성(UNKNOWN 포함)."""
        for card in ("1:1", "1:N", "M:N", "UNKNOWN"):
            rel = RelationshipDef(
                name="R", source_entity="A", target_entity="B",
                cardinality=card, join_keys=(("id", "id"),),
            )
            assert rel.cardinality == card

    def test_review_cardinality_raises(self) -> None:
        """파이프라인 일시 상태("REVIEW")는 관계 속성이 아니므로 거부된다."""
        with pytest.raises(ValueError, match="허용되지 않는 cardinality"):
            RelationshipDef(
                name="R", source_entity="A", target_entity="B",
                cardinality="REVIEW", join_keys=(("id", "id"),),
            )

    def test_relation_type_default_empty(self) -> None:
        """relation_type 기본값은 빈 문자열(미분류)."""
        rel = RelationshipDef(
            name="R", source_entity="A", target_entity="B",
            cardinality="1:N", join_keys=(("id", "id"),),
        )
        assert rel.relation_type == ""

    def test_all_valid_relation_types(self) -> None:
        """허용되는 relation_type 값 4개 전부 정상 생성."""
        for rt in ("", "hierarchy", "reference", "code_reference"):
            rel = RelationshipDef(
                name="R", source_entity="A", target_entity="B",
                cardinality="1:N", join_keys=(("id", "id"),),
                relation_type=rt,
            )
            assert rel.relation_type == rt

    def test_invalid_relation_type_raises(self) -> None:
        """허용되지 않는 relation_type이면 ValueError."""
        with pytest.raises(ValueError, match="허용되지 않는 relation_type"):
            RelationshipDef(
                name="R", source_entity="A", target_entity="B",
                cardinality="1:N", join_keys=(("id", "id"),),
                relation_type="partof",
            )

    def test_positional_args_backward_compatible(self) -> None:
        """신규 필드 없이 위치 인자만으로 생성해도 동작한다(하위 호환)."""
        rel = RelationshipDef(
            "R", "A", "B", "1:N", (("id", "id"),),
        )
        assert rel.name == "R"
        assert rel.via_entity == ""
        assert rel.description == ""
        assert rel.relation_type == ""
        assert rel.source_ref == ""


class TestDerivedConceptDef:
    def test_create_and_callable(self) -> None:
        """DerivedConceptDef 생성 및 formula_ref 호출 가능."""
        def efficiency(real_ct: float, st: float) -> float:
            return st / real_ct if real_ct else 0.0

        concept = DerivedConceptDef(
            name="efficiency",
            formula_ref=efficiency,
            inputs=("real_ct", "st"),
            formula_text="st / real_ct",
        )
        assert concept.formula_ref(real_ct=10.0, st=8.0) == pytest.approx(0.8)


class TestSqlDef:
    def _make_sql(self, name: str = "GET_MODEL", sql: str = "SELECT * FROM T_MODEL", entity: str = "MODEL") -> SqlDef:
        return SqlDef(name=name, sql=sql, entity=entity)

    def test_create_basic(self) -> None:
        """기본 SqlDef 생성."""
        s = self._make_sql()
        assert s.name == "GET_MODEL"
        assert s.entity == "MODEL"
        assert s.params == ()
        assert s.description == ""
        assert s.sql_type == "SELECT"

    def test_sql_type_default_is_select(self) -> None:
        """sql_type 기본값은 SELECT."""
        s = self._make_sql()
        assert s.sql_type == "SELECT"

    def test_all_valid_sql_types(self) -> None:
        """모든 허용 sql_type이 정상 생성."""
        for sql_type in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            s = SqlDef(name="Q", sql="SELECT 1", entity="MODEL", sql_type=sql_type)
            assert s.sql_type == sql_type

    def test_invalid_sql_type_raises(self) -> None:
        """허용되지 않는 sql_type이면 ValueError."""
        with pytest.raises(ValueError, match="허용되지 않는 sql_type"):
            SqlDef(name="Q", sql="SELECT 1", entity="MODEL", sql_type="MERGE")

    def test_empty_name_raises(self) -> None:
        """name이 빈 문자열이면 ValueError."""
        with pytest.raises(ValueError, match="name은 빈 문자열일 수 없습니다"):
            SqlDef(name="", sql="SELECT 1", entity="MODEL")

    def test_empty_sql_raises(self) -> None:
        """sql이 빈 문자열이면 ValueError."""
        with pytest.raises(ValueError, match="sql은 빈 문자열일 수 없습니다"):
            SqlDef(name="Q", sql="", entity="MODEL")

    def test_empty_entity_raises(self) -> None:
        """entity가 빈 문자열이면 ValueError."""
        with pytest.raises(ValueError, match="entity는 빈 문자열일 수 없습니다"):
            SqlDef(name="Q", sql="SELECT 1", entity="")

    def test_default_params_empty_tuple(self) -> None:
        """params 기본값은 빈 tuple."""
        s = self._make_sql()
        assert s.params == ()
        assert isinstance(s.params, tuple)

    def test_frozen(self) -> None:
        """frozen=True — 속성 변경 불가."""
        s = self._make_sql()
        with pytest.raises((AttributeError, TypeError)):
            s.name = "changed"  # type: ignore[misc]


class TestModuleDef:
    def _make_module(self, layer: str = "controller") -> ModuleDef:
        return ModuleDef(name="ModelController", layer=layer, file_path="com/example/ModelController.java")

    def test_create_basic(self) -> None:
        """기본 ModuleDef 생성."""
        m = self._make_module("controller")
        assert m.name == "ModelController"
        assert m.layer == "controller"
        assert m.related_entities == ()
        assert m.related_sqls == ()

    def test_all_valid_layers(self) -> None:
        """모든 허용 layer가 정상 생성."""
        for layer in ("controller", "biz", "dao", "mapper"):
            m = self._make_module(layer)
            assert m.layer == layer

    def test_invalid_layer_raises(self) -> None:
        """허용되지 않는 layer이면 ValueError."""
        with pytest.raises(ValueError, match="허용되지 않는 layer"):
            ModuleDef(name="X", layer="service", file_path="X.java")

    def test_default_collections_empty_tuple(self) -> None:
        """related_entities, related_sqls 기본값은 빈 tuple."""
        m = self._make_module()
        assert m.related_entities == ()
        assert m.related_sqls == ()

    def test_frozen(self) -> None:
        """frozen=True — 속성 변경 불가."""
        m = self._make_module()
        with pytest.raises((AttributeError, TypeError)):
            m.name = "changed"  # type: ignore[misc]


class TestCodeConceptDef:
    def _make_concept(self, **overrides: object) -> CodeConceptDef:
        """테스트용 CodeConceptDef 생성 헬퍼."""
        kwargs: dict[str, object] = dict(
            scheme_name="WORK_TYPE",
            code_value="W",
            pref_label="작업",
        )
        kwargs.update(overrides)
        return CodeConceptDef(**kwargs)  # type: ignore[arg-type]

    def test_create_basic(self) -> None:
        """기본 CodeConceptDef 생성."""
        concept = self._make_concept()
        assert concept.scheme_name == "WORK_TYPE"
        assert concept.code_value == "W"
        assert concept.pref_label == "작업"

    def test_defaults(self) -> None:
        """definition/source_ref 기본값은 빈 문자열."""
        concept = self._make_concept()
        assert concept.definition == ""
        assert concept.source_ref == ""

    def test_empty_scheme_name_raises(self) -> None:
        """scheme_name이 빈 문자열이면 ValueError."""
        with pytest.raises(ValueError, match="scheme_name은 빈 문자열일 수 없습니다"):
            self._make_concept(scheme_name="")

    def test_empty_code_value_raises(self) -> None:
        """code_value가 빈 문자열이면 ValueError."""
        with pytest.raises(ValueError, match="code_value는 빈 문자열일 수 없습니다"):
            self._make_concept(code_value="")

    def test_empty_pref_label_raises(self) -> None:
        """pref_label이 빈 문자열이면 ValueError."""
        with pytest.raises(ValueError, match="pref_label은 빈 문자열일 수 없습니다"):
            self._make_concept(pref_label="")

    def test_frozen(self) -> None:
        """frozen=True — 속성 변경 불가."""
        concept = self._make_concept()
        with pytest.raises((AttributeError, TypeError)):
            concept.code_value = "changed"  # type: ignore[misc]
