"""schema.py 단위 테스트."""

import pytest
from ontology_core.schema import AttributeDef, DerivedConceptDef, EntityDef, RelationshipDef


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
