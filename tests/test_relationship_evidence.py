"""관계 근거 계약과 RDF 경계의 합성 회귀."""

from dataclasses import FrozenInstanceError, replace

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS

from ontology_core import (
    AttributeDef, EntityDef, EvidenceEndpointDef, EvidenceSourceDef, Ontology,
    RelationshipDef, RelationshipEvidenceDef, to_owl,
)
from ontology_core.schema import ALLOWED_UNMATERIALIZED_REASONS

NS = Namespace("http://example.org/mes-ontology#")


def entity(name: str, table: str | None = None) -> EntityDef:
    """물질화된 합성 엔티티를 만든다."""
    return EntityDef(name, table or name, "", "", ("id",), (
        AttributeDef("id", "ID", "", "str", "none"),
    ))


def evidence(**changes: object) -> RelationshipEvidenceDef:
    """두 컬럼쌍을 가진 기준 근거를 만든다."""
    values: dict[str, object] = dict(
        name="canonical", source_endpoint=EvidenceEndpointDef("A", "A"),
        target_endpoint=EvidenceEndpointDef("B", "B"),
        join_keys=(("id", "parent"), ("site", "area")), role="CANONICAL", group_id="g",
    )
    values.update(changes)
    return RelationshipEvidenceDef(**values)  # type: ignore[arg-type]


def ontology(*items: RelationshipEvidenceDef) -> Ontology:
    """정상 엔티티와 주어진 근거를 등록한다."""
    result = Ontology()
    result.register_entity(entity("A"))
    result.register_entity(entity("B"))
    for item in items:
        result.register_relationship_evidence(item)
    return result


def relationship(**changes: object) -> RelationshipDef:
    """기준 근거와 일치하는 활성 관계를 만든다."""
    values: dict[str, object] = dict(name="active", source_entity="A", target_entity="B",
                                    cardinality="1:N", join_keys=evidence().join_keys)
    values.update(changes)
    return RelationshipDef(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("cls,values", [
    (EvidenceEndpointDef, {"table_ref": ""}),
    (EvidenceEndpointDef, {"table_ref": "A", "entity_ref": "A", "unmaterialized_reason": "PK_UNKNOWN"}),
    (EvidenceEndpointDef, {"table_ref": "A", "unmaterialized_reason": "UNKNOWN"}),
    (EvidenceEndpointDef, {"table_ref": "A"}),
    (EvidenceSourceDef, {"source_ref": " "}),
])
def test_endpoint_source_invalid(cls: type, values: dict[str, object]) -> None:
    """끝점 상태와 필수 출처를 거부한다."""
    with pytest.raises(ValueError):
        cls(**values)


@pytest.mark.parametrize("changes,error", [
    ({"name": " "}, ValueError), ({"name": 1}, TypeError),
    ({"role": "REVIEW"}, ValueError), ({"assessment_status": "REVIEW"}, ValueError),
    ({"group_id": ""}, ValueError), ({"canonical_evidence_name": "canonical"}, ValueError),
    ({"role": "SUPPORTING_OBSERVATION"}, ValueError),
    ({"role": "HOLD", "relationship_name": "active"}, ValueError),
    ({"role": "EXCLUDED", "relationship_name": "active"}, ValueError),
    ({"source_endpoint": {"table_ref": "A"}}, TypeError),
    ({"target_endpoint": "B"}, TypeError), ({"sources": []}, TypeError),
    ({"sources": ("DAO",)}, TypeError), ({"join_keys": []}, TypeError),
    ({"join_keys": ()}, ValueError), ({"join_keys": (["id", "id"],)}, TypeError),
    ({"join_keys": (("id",),)}, TypeError), ({"join_keys": (("id", 1),)}, TypeError),
    ({"join_keys": (("id", " "),)}, ValueError),
    ({"join_keys": (("id", "id"), ("id", "id"))}, ValueError),
])
def test_evidence_constructor_invalid(changes: dict[str, object], error: type[Exception]) -> None:
    """새 필드의 enum·타입·전체 컬럼쌍 제약을 검사한다."""
    with pytest.raises(error):
        evidence(**changes)


def test_frozen_and_registry_compatibility() -> None:
    """세 타입은 불변이고 새 근거만 중복 거부하며 기존 관계 덮어쓰기는 유지한다."""
    for item in (evidence(), EvidenceEndpointDef("A", "A"), EvidenceSourceDef("DAO")):
        with pytest.raises(FrozenInstanceError):
            item.name = "changed"  # type: ignore[attr-defined,misc]
    item = evidence()
    result = ontology(item)
    assert result.get_relationship_evidence("canonical") is item
    assert result.list_relationship_evidence() == ["canonical"]
    with pytest.raises(ValueError):
        result.register_relationship_evidence(item)
    with pytest.raises(KeyError):
        result.get_relationship_evidence("missing")
    with pytest.raises(TypeError):
        result.register_relationship_evidence("bad")  # type: ignore[arg-type]
    result.register_relationship(relationship())
    result.register_relationship(relationship(cardinality="UNKNOWN"))
    assert result.get_relationship("active").cardinality == "UNKNOWN"
    with pytest.raises(ValueError):
        relationship(cardinality="REVIEW")


@pytest.mark.parametrize("reason", sorted(ALLOWED_UNMATERIALIZED_REASONS))
def test_unmaterialized_reason_preserved_without_entity_or_active_relation(reason: str) -> None:
    """가짜 엔티티 없이 기준·보조·보류를 전종 사유로 보존한다."""
    endpoint = EvidenceEndpointDef("MISSING", unmaterialized_reason=reason)
    canonical = evidence(source_endpoint=endpoint, assessment_status="UNRESOLVED")
    supporting = replace(canonical, name="support", role="SUPPORTING_OBSERVATION",
                         canonical_evidence_name="canonical", join_keys=(("extra", "condition"),))
    hold = replace(canonical, name="hold", role="HOLD", group_id="")
    result = Ontology()
    result.register_entity(entity("B"))
    for item in (canonical, supporting, hold):
        result.register_relationship_evidence(item)
    assert result.validate() == []
    assert result.list_relationships() == []
    graph = Graph().parse(data=to_owl(result), format="turtle")
    assert len(set(graph.subjects(RDF.type, NS.RelationshipEvidence))) == 3
    assert len(set(graph.subjects(RDF.type, OWL.ObjectProperty))) == 0
    assert set(graph.objects(None, NS.unmaterializedReason)) == {Literal(reason)}
    assert NS.MISSING not in set(graph.subjects(RDF.type, OWL.Class))
    assert len(set(graph.subjects(RDF.type, OWL.Class)) - {NS.EvidenceEndpoint, NS.JoinKeyPair, NS.RelationshipEvidence}) == 1


def test_multiple_canonical_groups_and_support_extra_conditions() -> None:
    """독립 기준 둘을 활성화하고 보조의 추가조건은 기준 비교에 합치지 않는다."""
    first = evidence(relationship_name="active")
    second = evidence(name="other", group_id="g2", join_keys=(("other", "key"),), relationship_name="active2")
    support = evidence(name="support", role="SUPPORTING_OBSERVATION", canonical_evidence_name="canonical",
                       join_keys=(("id", "parent"), ("extra", "filter")), relationship_name="active")
    result = ontology(first, second, support, evidence(name="hold", role="HOLD", group_id=""),
                      evidence(name="excluded", role="EXCLUDED", group_id=""))
    result.register_relationship(relationship())
    result.register_relationship(relationship(name="active2", join_keys=second.join_keys))
    assert result.validate() == []
    graph = Graph().parse(data=to_owl(result), format="turtle")
    assert len(set(graph.subjects(RDF.type, OWL.ObjectProperty))) == 2
    assert len(set(graph.subjects(RDF.type, NS.RelationshipEvidence))) == 5
    assert len(list(graph.triples((None, NS.supportsMapping, None)))) == 1


@pytest.mark.parametrize("items,expected", [
    ((evidence(source_endpoint=EvidenceEndpointDef("A", "missing")),), "entity_ref"),
    ((evidence(source_endpoint=EvidenceEndpointDef("wrong", "A")),), "table_ref"),
    ((evidence(), evidence(name="other")), "정확히 1개"),
    ((evidence(name="support", role="SUPPORTING_OBSERVATION", canonical_evidence_name="absent"),), "CANONICAL"),
    ((evidence(name="support", role="SUPPORTING_OBSERVATION", canonical_evidence_name="support"),), "CANONICAL"),
    ((evidence(), evidence(name="support", role="SUPPORTING_OBSERVATION", group_id="other", canonical_evidence_name="canonical")), "같은 그룹"),
    ((evidence(), evidence(name="support", role="SUPPORTING_OBSERVATION", canonical_evidence_name="canonical", target_endpoint=EvidenceEndpointDef("A", "A"))), "논리 끝점"),
    ((evidence(relationship_name="absent"),), "relationship_name"),
    ((evidence(), evidence(name="support", role="SUPPORTING_OBSERVATION", canonical_evidence_name="canonical", relationship_name="active")), "CANONICAL의 관계"),
    ((evidence(name="s1", role="SUPPORTING_OBSERVATION", canonical_evidence_name="s2"), evidence(name="s2", role="SUPPORTING_OBSERVATION", canonical_evidence_name="s1")), "CANONICAL"),
])
def test_cross_reference_errors(items: tuple[RelationshipEvidenceDef, ...], expected: str) -> None:
    """오등록·그룹 위반·자기참조·순환을 검증 오류로 보존한다."""
    result = ontology(*items)
    assert any(expected in error for error in result.validate())
    with pytest.raises(ValueError, match=r"validate\(\)"):
        to_owl(result)


def test_unmaterialized_group_cannot_reference_active_relationship() -> None:
    """미물질화 그룹은 관계가 따로 등록되어도 참조할 수 없다."""
    result = ontology(evidence(source_endpoint=EvidenceEndpointDef("A", unmaterialized_reason="PK_UNKNOWN"),
                               relationship_name="active"))
    result.register_relationship(relationship())
    assert any("미물질화" in error for error in result.validate())


@pytest.mark.parametrize("self_join", [False, True])
def test_whole_signature_reversal_and_partial_reversal(self_join: bool) -> None:
    """방향 반전은 묶음 전체만 동치이며 self join에서도 부분 반전은 거부한다."""
    canonical = evidence(relationship_name="active")
    if self_join:
        canonical = replace(canonical, target_endpoint=canonical.source_endpoint)
    result = ontology(canonical)
    result.register_relationship(relationship(source_entity=canonical.target_endpoint.entity_ref,
                                             target_entity=canonical.source_endpoint.entity_ref,
                                             join_keys=tuple((r, l) for l, r in reversed(canonical.join_keys))))
    assert result.validate() == []
    result.register_relationship(relationship(source_entity=canonical.target_endpoint.entity_ref,
                                             target_entity=canonical.source_endpoint.entity_ref,
                                             join_keys=(("parent", "id"), ("site", "area"))))
    assert any("join_keys" in error for error in result.validate())


def test_rdf_pair_ownership_source_triples_escaping_and_determinism() -> None:
    """파서로 좌우·소유자·출처 삼중항·원문 설명을 손실 없이 확인한다."""
    note = '사람 "검토"\\설명\n다음\r줄\x00'
    sources = (EvidenceSourceDef('DAO"\\', "ctx1", "snap1"), EvidenceSourceDef('DAO"\\', "ctx2", "snap2"))
    canonical = evidence(relationship_name="active", sources=sources + sources[:1], description=note,
                         review_status="VALID", reason_code="EXPERT", assessment_status="RESOLVED", assessment_method="RULE_v1")
    support = evidence(name="support", role="SUPPORTING_OBSERVATION", canonical_evidence_name="canonical",
                       join_keys=(("extra", "filter"),), sources=(sources[0],))
    result = ontology(canonical, support)
    result.register_relationship(relationship(description=note))
    graph = Graph().parse(data=to_owl(result), format="turtle")
    canonical_iri = next(graph.subjects(RDFS.label, Literal("canonical")))
    support_iri = next(graph.subjects(RDFS.label, Literal("support")))
    assert (canonical_iri, RDFS.comment, Literal(note, lang="ko")) in graph
    assert (NS.active, RDFS.comment, Literal(note, lang="ko")) in graph
    assert set(graph.objects(canonical_iri, NS.assessmentStatus)) == {Literal("RESOLVED")}
    for owner, expected in ((canonical_iri, canonical.join_keys), (support_iri, support.join_keys), (NS.active, canonical.join_keys)):
        pairs = list(graph.objects(owner, NS.joinKeyPair))
        actual = sorted((int(graph.value(pair, NS.pairIndex)), str(graph.value(pair, NS.sourceColumn)), str(graph.value(pair, NS.targetColumn))) for pair in pairs)
        assert actual == [(i, left, right) for i, (left, right) in enumerate(sorted(expected))]
        assert all((pair, RDF.type, OWL.NamedIndividual) in graph for pair in pairs)
    triples = {(str(graph.value(src, DCTERMS.source)), str(graph.value(src, NS.contextRef)), str(graph.value(src, NS.snapshotRef))) for src in graph.objects(canonical_iri, NS.hasSource)}
    assert triples == {(s.source_ref, s.context_ref, s.snapshot_ref) for s in sources}
    assert len(list(graph.subjects(RDF.type, NS.EvidenceSource))) == 2
    assert (canonical_iri, NS.relationshipRef, NS.active) in graph
    assert (support_iri, NS.supportsMapping, canonical_iri) in graph
    assert not list(graph.subjects(RDF.type, OWL.Restriction))
    alternate = ontology(replace(support, join_keys=tuple(reversed(support.join_keys))),
                         replace(canonical, sources=tuple(reversed(sources)), join_keys=tuple(reversed(canonical.join_keys))))
    alternate.register_relationship(relationship(description=note, join_keys=tuple(reversed(canonical.join_keys))))
    assert to_owl(result) == to_owl(alternate)


def test_self_join_keeps_source_target_edges() -> None:
    """같은 끝점 노드여도 SOURCE/TARGET 술어는 각각 유지한다."""
    result = ontology(evidence(target_endpoint=EvidenceEndpointDef("A", "A")))
    graph = Graph().parse(data=to_owl(result), format="turtle")
    subject = next(graph.subjects(RDF.type, NS.RelationshipEvidence))
    assert graph.value(subject, NS.evidenceSource) == graph.value(subject, NS.evidenceTarget)
    assert len(list(graph.objects(subject, NS.evidenceSource))) == 1
    assert len(list(graph.objects(subject, NS.evidenceTarget))) == 1


def test_new_vocabulary_iri_collision_rejected() -> None:
    """새 어휘·생성 페어 IRI와 사용자 엔티티가 충돌하면 조용히 합치지 않는다."""
    result = ontology(evidence())
    result.register_entity(entity("RelationshipEvidence"))
    with pytest.raises(ValueError, match="IRI fragment 충돌"):
        to_owl(result)
    result = ontology()
    result.register_entity(entity("active_join_0"))
    result.register_relationship(relationship())
    with pytest.raises(ValueError, match="IRI fragment 충돌"):
        to_owl(result)


def test_legacy_empty_annotations_bytes() -> None:
    """근거·관계 컬럼쌍·설명이 공란이면 0.4.0 바이트 출력을 유지한다."""
    result = Ontology()
    result.register_entity(entity("A"))
    result.register_relationship(relationship(source_entity="A", target_entity="A", join_keys=()))
    assert to_owl(result) == '''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix : <http://example.org/mes-ontology#> .

:cardinality a owl:AnnotationProperty .

:A a owl:Class .
:A rdfs:label "A"@ko .
:A_id a owl:DatatypeProperty .
:A_id rdfs:domain :A .
:A_id rdfs:range xsd:string .

:active a owl:ObjectProperty .
:active rdfs:domain :A .
:active rdfs:range :A .
:active :cardinality "1:N" .
'''
