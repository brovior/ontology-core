"""export.py 단위 테스트 — to_owl/to_skos Turtle 문자열 생성."""

import pytest
from ontology_core.export import _safe_iri_fragment, to_owl, to_skos
from ontology_core.registry import Ontology
from ontology_core.schema import AttributeDef, CodeConceptDef, EntityDef, RelationshipDef


def _attr(name: str, description: str = "", data_type: str = "str") -> AttributeDef:
    """테스트용 AttributeDef 생성 헬퍼."""
    return AttributeDef(
        name=name, column_name=name.upper(), description=description, data_type=data_type, unit="none"
    )


@pytest.fixture
def sample_ontology() -> Ontology:
    """엔티티 2개(특수문자 포함 description) + 관계 1개 + 코드컨셉 2개로 구성된 합성 온톨로지."""
    onto = Ontology()
    onto.register_entity(
        EntityDef(
            name="MODEL",
            table_name="T_MODEL",
            description='모델 마스터 — "특수문자"\n둘째 줄',
            domain="제조",
            primary_key=("model_cd",),
            attributes=(
                _attr("model_cd", description="모델 코드"),
                _attr("model_nm"),
            ),
            entity_type="M",
        )
    )
    onto.register_entity(
        EntityDef(
            name="PLANT",
            table_name="T_PLANT",
            description="공장 마스터",
            domain="제조",
            primary_key=("plant_cd",),
            attributes=(_attr("plant_cd"),),
            entity_type="M",
        )
    )
    onto.register_relationship(
        RelationshipDef(
            name="MODEL_PLANT",
            source_entity="MODEL",
            target_entity="PLANT",
            cardinality="1:N",
            join_keys=(("plant_cd", "plant_cd"),),
            relation_type="hierarchy",
            source_ref="ModelPlantDao.listByPlant",
        )
    )
    onto.register_code_concept(
        CodeConceptDef(
            scheme_name="WORK_TYPE",
            code_value="W",
            pref_label="작업",
            definition="작업 지시 유형",
            source_ref="WorkTypeDao",
        )
    )
    onto.register_code_concept(
        CodeConceptDef(scheme_name="WORK_TYPE", code_value="R", pref_label="휴식")
    )
    return onto


class TestSafeIriFragment:
    def test_ascii_alnum_passthrough(self) -> None:
        """영문자/숫자/언더스코어는 그대로 통과한다."""
        assert _safe_iri_fragment("Model_1") == "Model_1"

    def test_non_ascii_replaced(self) -> None:
        """비허용 문자는 _U{hex}_로 치환된다."""
        assert _safe_iri_fragment("-") == "_U2D_"

    def test_collision_pair(self) -> None:
        """치환 규칙상 서로 다른 두 이름이 같은 fragment가 될 수 있다."""
        assert _safe_iri_fragment("A-B") == _safe_iri_fragment("A_U2D_B") == "A_U2D_B"

    def test_deterministic(self) -> None:
        """같은 입력은 항상 같은 fragment를 반환한다."""
        assert _safe_iri_fragment("모델명") == _safe_iri_fragment("모델명")


class TestToOwl:
    def test_contains_expected_triples(self, sample_ontology: Ontology) -> None:
        """to_owl 출력에 기대되는 트리플이 포함된다."""
        ttl = to_owl(sample_ontology)
        assert "a owl:Class ." in ttl
        assert 'rdfs:label "MODEL"@ko .' in ttl
        assert "a owl:DatatypeProperty ." in ttl
        assert "a owl:ObjectProperty ." in ttl
        assert ':relationType "hierarchy" .' in ttl
        # 관계 출처는 Dublin Core dct:source로 기록된다(CodeConceptDef와 동일 표준).
        assert 'dct:source "ModelPlantDao.listByPlant" .' in ttl

    def test_escapes_quotes_and_newlines(self, sample_ontology: Ontology) -> None:
        """description의 큰따옴표/개행이 이스케이프되어 출력된다."""
        ttl = to_owl(sample_ontology)
        assert '\\"특수문자\\"' in ttl
        assert "\\n둘째 줄" in ttl
        # 이스케이프된 리터럴 라인 안에 원시 개행이 없어야 한다.
        for line in ttl.splitlines():
            if "특수문자" in line:
                assert "\n" not in line

    def test_deterministic_output(self, sample_ontology: Ontology) -> None:
        """동일 온톨로지에 대해 두 번 호출한 결과가 완전히 동일하다."""
        assert to_owl(sample_ontology) == to_owl(sample_ontology)

    def test_escapes_carriage_return(self) -> None:
        """description의 캐리지 리턴(\\r)이 이스케이프되어 출력된다."""
        onto = Ontology()
        onto.register_entity(
            EntityDef(
                name="CR", table_name="T_CR", description="첫 줄\r\n둘째 줄", domain="d",
                primary_key=("id",), attributes=(_attr("id"),),
            )
        )
        ttl = to_owl(onto)
        assert "\\r\\n둘째 줄" in ttl
        assert "\r" not in ttl

    def test_empty_ontology_returns_prelude_only(self) -> None:
        """빈 Ontology는 prelude만 포함한 문자열을 반환한다."""
        ttl = to_owl(Ontology())
        assert "@prefix owl:" in ttl
        assert "@prefix : <http://example.org/mes-ontology#>" in ttl
        assert "owl:Class" not in ttl

    def test_iri_collision_raises(self) -> None:
        """치환 후 동일 fragment가 되는 두 엔티티가 있으면 ValueError."""
        onto = Ontology()
        onto.register_entity(
            EntityDef(
                name="A-B", table_name="T_A", description="", domain="d",
                primary_key=("id",), attributes=(_attr("id"),),
            )
        )
        onto.register_entity(
            EntityDef(
                name="A_U2D_B", table_name="T_B", description="", domain="d",
                primary_key=("id",), attributes=(_attr("id"),),
            )
        )
        with pytest.raises(ValueError, match="IRI fragment 충돌"):
            to_owl(onto)


class TestToSkos:
    def test_contains_expected_triples(self, sample_ontology: Ontology) -> None:
        """to_skos 출력에 ConceptScheme/Concept/inScheme/prefLabel/definition이 포함된다."""
        ttl = to_skos(sample_ontology)
        assert "a skos:ConceptScheme ." in ttl
        assert "a skos:Concept ." in ttl
        assert "skos:inScheme" in ttl
        assert 'skos:prefLabel "작업"@ko .' in ttl
        assert 'skos:definition "작업 지시 유형"@ko .' in ttl
        assert 'dct:source "WorkTypeDao" .' in ttl

    def test_empty_ontology_returns_prelude_only(self) -> None:
        """빈 Ontology는 prelude만 포함한 문자열을 반환한다."""
        ttl = to_skos(Ontology())
        assert "@prefix skos:" in ttl
        assert "skos:Concept" not in ttl

    def test_deterministic_output(self, sample_ontology: Ontology) -> None:
        """동일 온톨로지에 대해 두 번 호출한 결과가 완전히 동일하다."""
        assert to_skos(sample_ontology) == to_skos(sample_ontology)
