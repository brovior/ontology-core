"""OWL/SKOS Turtle 내보내기 — 순수 문자열 생성, 외부 의존성 없음.

- to_owl(): EntityDef → owl:Class, AttributeDef → owl:DatatypeProperty,
  RelationshipDef → owl:ObjectProperty로 변환한 Turtle 문자열을 반환한다.
- to_skos(): CodeConceptDef를 scheme_name 단위 skos:ConceptScheme +
  skos:Concept으로 변환한 Turtle 문자열을 반환한다.
- SqlDef/ModuleDef/DerivedConceptDef는 export 대상이 아니다.

결정론 규약: 엔티티/관계/스킴(및 스킴 내 concept)은 이름(또는 code_value)
오름차순으로 정렬하고, 엔티티 내부의 속성은 attributes 튜플의 정의 순서를
그대로 유지한다. 동일한 Ontology 입력에 대해서는 항상 바이트 단위로 동일한
Turtle 문자열을 반환한다.
"""

from __future__ import annotations

import hashlib
import json
import re

from ontology_core.registry import Ontology
from ontology_core.schema import CodeConceptDef, EntityDef, RelationshipDef

_PRELUDE_TEMPLATE = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix : <{base_iri}> ."""

_SAFE_CHAR_RE = re.compile(r"[A-Za-z0-9_]")

_XSD_TYPE_MAP = {
    "str": "xsd:string",
    "int": "xsd:integer",
    "float": "xsd:decimal",
    "date": "xsd:date",
    "datetime": "xsd:dateTime",
    "bool": "xsd:boolean",
}

# EntityDef/RelationshipDef 주석(annotation) 술어의 고정 선언 순서.
_ANNOTATION_ORDER = ("domain", "entityType", "pslTag", "isa95Tag", "cardinality", "relationType")


def _safe_iri_fragment(name: str) -> str:
    """이름을 Turtle prefixed-name에 안전한 fragment로 변환한다.

    영문자/숫자/언더스코어는 그대로 통과시키고, 그 외 문자는 결정론적으로
    `_U{유니코드 코드포인트 16진 대문자}_` 로 치환한다(percent-encoding은 Turtle
    prefixed-name 파서와 호환되지 않아 사용하지 않는다).
    """
    parts: list[str] = []
    for ch in name:
        if _SAFE_CHAR_RE.match(ch):
            parts.append(ch)
        else:
            parts.append(f"_U{ord(ch):X}_")
    return "".join(parts)


def _claim_fragment(seen: dict[str, str], frag: str, original_identifier: str) -> None:
    """frag가 이미 다른 원본 식별자에 의해 사용되었는지 검사하고 등록한다."""
    if frag in seen and seen[frag] != original_identifier:
        raise ValueError(
            f"IRI fragment 충돌: '{seen[frag]}'와(과) '{original_identifier}'이(가) "
            f"모두 '{frag}'로 변환됩니다."
        )
    seen[frag] = original_identifier


def _fragment_for(seen: dict[str, str], name: str) -> str:
    """이름으로부터 안전한 fragment를 만들고 충돌을 검사한 뒤 반환한다."""
    frag = _safe_iri_fragment(name)
    _claim_fragment(seen, frag, name)
    return frag


def _escape_literal(text: str) -> str:
    """Turtle 문자열 리터럴 이스케이프 — 백슬래시를 가장 먼저 치환한다."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    return text


def _xsd_type(data_type: str) -> str:
    """AttributeDef.data_type을 xsd 타입으로 매핑한다. 알 수 없으면 xsd:string."""
    return _XSD_TYPE_MAP.get(data_type, "xsd:string")


def to_owl(ontology: Ontology, base_iri: str = "http://example.org/mes-ontology#") -> str:
    """Ontology의 EntityDef/AttributeDef/RelationshipDef를 OWL Turtle 문자열로 변환한다.

    SqlDef/ModuleDef/DerivedConceptDef/CodeConceptDef는 변환 대상에서 제외된다.
    엔티티는 이름 오름차순, 엔티티 내 속성은 attributes 튜플의 정의 순서, 관계는
    이름 오름차순으로 출력되어 동일 입력에 대해 항상 동일한 문자열을 반환한다.
    서로 다른 두 원본 이름이 동일한 IRI fragment로 치환되면 ValueError를 발생시킨다.
    """
    if ontology.list_relationship_evidence():
        errors = ontology.validate()
        if errors:
            raise ValueError("근거 출력 전 validate() 실패: " + "; ".join(errors))
    fragments: dict[str, str] = {}
    used_annotations: set[str] = set()
    entity_lines: list[str] = []
    relationship_lines: list[str] = []

    entity_names = sorted(ontology.list_entities())
    entities: list[EntityDef] = [ontology.get_entity(n) for n in entity_names]

    for entity in entities:
        frag = _fragment_for(fragments, entity.name)
        lines = [f":{frag} a owl:Class ."]
        lines.append(f':{frag} rdfs:label "{_escape_literal(entity.name)}"@ko .')
        if entity.description:
            lines.append(f':{frag} rdfs:comment "{_escape_literal(entity.description)}"@ko .')
        if entity.domain:
            lines.append(f':{frag} :domain "{_escape_literal(entity.domain)}" .')
            used_annotations.add("domain")
        if entity.entity_type:
            lines.append(f':{frag} :entityType "{_escape_literal(entity.entity_type)}" .')
            used_annotations.add("entityType")
        if entity.psl_tag:
            lines.append(f':{frag} :pslTag "{_escape_literal(entity.psl_tag)}" .')
            used_annotations.add("pslTag")
        if entity.isa95_tag:
            lines.append(f':{frag} :isa95Tag "{_escape_literal(entity.isa95_tag)}" .')
            used_annotations.add("isa95Tag")

        for attr in entity.attributes:
            attr_frag = f"{frag}_{_safe_iri_fragment(attr.name)}"
            _claim_fragment(fragments, attr_frag, f"{entity.name}.{attr.name}")
            lines.append(f":{attr_frag} a owl:DatatypeProperty .")
            lines.append(f":{attr_frag} rdfs:domain :{frag} .")
            lines.append(f":{attr_frag} rdfs:range {_xsd_type(attr.data_type)} .")
            if attr.description:
                lines.append(f':{attr_frag} rdfs:comment "{_escape_literal(attr.description)}"@ko .')

        entity_lines.append("\n".join(lines))

    rel_names = sorted(ontology.list_relationships())
    relationships: list[RelationshipDef] = [ontology.get_relationship(n) for n in rel_names]

    for rel in relationships:
        frag = _fragment_for(fragments, rel.name)
        source_frag = _fragment_for(fragments, rel.source_entity)
        target_frag = _fragment_for(fragments, rel.target_entity)
        lines = [f":{frag} a owl:ObjectProperty ."]
        lines.append(f":{frag} rdfs:domain :{source_frag} .")
        lines.append(f":{frag} rdfs:range :{target_frag} .")
        if rel.cardinality:
            lines.append(f':{frag} :cardinality "{_escape_literal(rel.cardinality)}" .')
            used_annotations.add("cardinality")
        if rel.relation_type:
            # relation_type="hierarchy"여도 owl:partOf 등으로 자동 매핑하지 않는다 —
            # annotation으로만 기록한다.
            lines.append(f':{frag} :relationType "{_escape_literal(rel.relation_type)}" .')
            used_annotations.add("relationType")
        if rel.source_ref:
            # 관계의 출처(관측 DAO 메서드 등)는 Dublin Core `dct:source`로 기록한다 —
            # CodeConceptDef.source_ref(to_skos)와 동일 표준·패턴. 외부 term이라
            # AnnotationProperty 선언이 필요 없고, 언어태그 없는 순수 리터럴이다.
            lines.append(f':{frag} dct:source "{_escape_literal(rel.source_ref)}" .')
        if rel.description:
            lines.append(f':{frag} rdfs:comment "{_escape_metadata_literal(rel.description)}"@ko .')
        lines.extend(_join_key_lines(fragments, frag, rel.join_keys, used_annotations))
        relationship_lines.append("\n".join(lines))

    evidence_lines, metadata_classes = _evidence_lines(ontology, fragments, used_annotations)
    for name in sorted((used_annotations - set(_ANNOTATION_ORDER)) | metadata_classes):
        _claim_fragment(fragments, name, f"metadata vocabulary:{name}")
    blocks = [_PRELUDE_TEMPLATE.format(base_iri=base_iri)]

    annotation_order = (*_ANNOTATION_ORDER, *sorted(used_annotations - set(_ANNOTATION_ORDER)))
    annotation_decls = [
        f":{name} a owl:AnnotationProperty ." for name in annotation_order if name in used_annotations
    ]
    if annotation_decls:
        blocks.append("\n".join(annotation_decls))

    if metadata_classes:
        blocks.append("\n".join(f":{name} a owl:Class ." for name in sorted(metadata_classes)))
    blocks.extend(entity_lines)
    blocks.extend(relationship_lines)
    blocks.extend(evidence_lines)

    return "\n\n".join(blocks) + "\n"


def _escape_metadata_literal(text: str) -> str:
    """새 메타데이터의 제어문자도 이스케이프하며 기존 출력은 유지한다."""
    return re.sub(r"[\x00-\x1f]", lambda m: f"\\u{ord(m.group()):04X}", _escape_literal(text))


def _metadata_fragment(fragments: dict[str, str], prefix: str, values: tuple[str, ...]) -> str:
    """종류와 전체 값에 결속된 메타데이터 IRI를 만들고 충돌을 검사한다."""
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    frag = prefix + "_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    _claim_fragment(fragments, frag, f"metadata {prefix}:{payload}")
    return frag


def _join_key_lines(
    fragments: dict[str, str], owner: str, join_keys: tuple[tuple[str, str], ...],
    used_annotations: set[str],
) -> list[str]:
    """소유자별 전체 컬럼쌍을 정렬하고 좌우·인덱스를 별도 레코드로 기록한다."""
    lines: list[str] = []
    for index, (left, right) in enumerate(sorted(join_keys)):
        pair_frag = f"{owner}_join_{index}"
        _claim_fragment(fragments, pair_frag, f"metadata join:{owner}:{index}")
        lines.extend([
            f":{owner} :joinKeyPair :{pair_frag} .",
            f":{pair_frag} a owl:NamedIndividual, :JoinKeyPair .",
            f":{pair_frag} :pairIndex {index} .",
            f':{pair_frag} :sourceColumn "{_escape_metadata_literal(left)}" .',
            f':{pair_frag} :targetColumn "{_escape_metadata_literal(right)}" .',
        ])
    if lines:
        used_annotations.update({"joinKeyPair", "pairIndex", "sourceColumn", "targetColumn"})
    return lines


def _evidence_lines(
    ontology: Ontology, fragments: dict[str, str], used_annotations: set[str],
) -> tuple[list[str], set[str]]:
    """근거·논리 끝점·대응된 출처를 활성 관계와 분리해 출력한다."""
    blocks: list[str] = []
    classes: set[str] = set()
    if "joinKeyPair" in used_annotations:
        classes.add("JoinKeyPair")
    endpoint_blocks: dict[str, str] = {}
    source_blocks: dict[str, str] = {}
    evidence_names = sorted(ontology.list_relationship_evidence())
    evidence_fragments = {
        name: _metadata_fragment(fragments, "evidence", (name,)) for name in evidence_names
    }
    for name in evidence_names:
        evidence = ontology.get_relationship_evidence(name)
        frag = evidence_fragments[name]
        classes.update({"RelationshipEvidence", "EvidenceEndpoint", "JoinKeyPair"})
        lines = [f":{frag} a owl:NamedIndividual, :RelationshipEvidence .",
                 f':{frag} rdfs:label "{_escape_metadata_literal(name)}" .']
        for field, predicate in (
            ("role", "role"), ("group_id", "groupId"), ("review_status", "reviewStatus"),
            ("reason_code", "reasonCode"), ("assessment_status", "assessmentStatus"),
            ("assessment_method", "assessmentMethod"), ("relationship_name", "relationshipName"),
            ("canonical_evidence_name", "canonicalEvidenceName"),
        ):
            value = getattr(evidence, field)
            if value:
                lines.append(f':{frag} :{predicate} "{_escape_metadata_literal(value)}" .')
                used_annotations.add(predicate)
        if evidence.description:
            lines.append(f':{frag} rdfs:comment "{_escape_metadata_literal(evidence.description)}"@ko .')
        for endpoint, predicate in ((evidence.source_endpoint, "evidenceSource"),
                                    (evidence.target_endpoint, "evidenceTarget")):
            endpoint_frag = _metadata_fragment(fragments, "endpoint", (
                endpoint.table_ref, endpoint.entity_ref, endpoint.unmaterialized_reason,
            ))
            lines.append(f":{frag} :{predicate} :{endpoint_frag} .")
            used_annotations.update({predicate, "tableRef"})
            endpoint_lines = [f":{endpoint_frag} a owl:NamedIndividual, :EvidenceEndpoint .",
                              f':{endpoint_frag} :tableRef "{_escape_metadata_literal(endpoint.table_ref)}" .']
            if endpoint.entity_ref:
                entity_frag = _fragment_for(fragments, endpoint.entity_ref)
                endpoint_lines.append(f":{endpoint_frag} :resolvesTo :{entity_frag} .")
                used_annotations.add("resolvesTo")
            else:
                endpoint_lines.append(f':{endpoint_frag} :unmaterializedReason "{endpoint.unmaterialized_reason}" .')
                used_annotations.add("unmaterializedReason")
            endpoint_blocks[endpoint_frag] = "\n".join(endpoint_lines)
        if evidence.role == "SUPPORTING_OBSERVATION":
            lines.append(f":{frag} :supportsMapping :{evidence_fragments[evidence.canonical_evidence_name]} .")
            used_annotations.add("supportsMapping")
        if evidence.relationship_name:
            rel_frag = _fragment_for(fragments, evidence.relationship_name)
            lines.append(f":{frag} :relationshipRef :{rel_frag} .")
            used_annotations.add("relationshipRef")
        for source in sorted(set(evidence.sources), key=lambda s: (s.source_ref, s.context_ref, s.snapshot_ref)):
            classes.add("EvidenceSource")
            source_frag = _metadata_fragment(fragments, "source", (
                source.source_ref, source.context_ref, source.snapshot_ref,
            ))
            lines.append(f":{frag} :hasSource :{source_frag} .")
            used_annotations.add("hasSource")
            source_lines = [f":{source_frag} a owl:NamedIndividual, :EvidenceSource .",
                            f':{source_frag} dct:source "{_escape_metadata_literal(source.source_ref)}" .']
            for predicate, value in (("contextRef", source.context_ref), ("snapshotRef", source.snapshot_ref)):
                if value:
                    source_lines.append(f':{source_frag} :{predicate} "{_escape_metadata_literal(value)}" .')
                    used_annotations.add(predicate)
            source_blocks[source_frag] = "\n".join(source_lines)
        lines.extend(_join_key_lines(fragments, frag, evidence.join_keys, used_annotations))
        blocks.append("\n".join(lines))
    blocks.extend(endpoint_blocks[key] for key in sorted(endpoint_blocks))
    blocks.extend(source_blocks[key] for key in sorted(source_blocks))
    return blocks, classes


def to_skos(ontology: Ontology, base_iri: str = "http://example.org/mes-ontology#") -> str:
    """Ontology의 CodeConceptDef를 SKOS Turtle 문자열로 변환한다.

    scheme_name별로 skos:ConceptScheme 1개를 만들고, 그 안의 CodeConceptDef들을
    skos:Concept으로 변환한다. scheme은 이름 오름차순, scheme 내 concept은
    code_value 오름차순으로 출력되어 동일 입력에 대해 항상 동일한 문자열을 반환한다.
    서로 다른 두 원본 식별자가 동일한 IRI fragment로 치환되면 ValueError를 발생시킨다.
    """
    fragments: dict[str, str] = {}
    scheme_blocks: list[str] = []

    scheme_names = sorted(ontology.list_schemes())

    for scheme_name in scheme_names:
        scheme_frag = _fragment_for(fragments, scheme_name)
        lines = [f":{scheme_frag} a skos:ConceptScheme ."]
        lines.append(f':{scheme_frag} rdfs:label "{_escape_literal(scheme_name)}"@ko .')

        concepts: list[CodeConceptDef] = sorted(
            ontology.get_concepts_by_scheme(scheme_name), key=lambda c: c.code_value
        )
        for concept in concepts:
            concept_frag = f"{scheme_frag}_{_safe_iri_fragment(concept.code_value)}"
            _claim_fragment(fragments, concept_frag, f"{scheme_name}:{concept.code_value}")
            lines.append(f":{concept_frag} a skos:Concept .")
            lines.append(f":{concept_frag} skos:inScheme :{scheme_frag} .")
            lines.append(f':{concept_frag} skos:prefLabel "{_escape_literal(concept.pref_label)}"@ko .')
            if concept.definition:
                lines.append(
                    f':{concept_frag} skos:definition "{_escape_literal(concept.definition)}"@ko .'
                )
            if concept.source_ref:
                lines.append(f':{concept_frag} dct:source "{_escape_literal(concept.source_ref)}" .')

        scheme_blocks.append("\n".join(lines))

    blocks = [_PRELUDE_TEMPLATE.format(base_iri=base_iri)]
    blocks.extend(scheme_blocks)

    return "\n\n".join(blocks) + "\n"
