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
        relationship_lines.append("\n".join(lines))

    blocks = [_PRELUDE_TEMPLATE.format(base_iri=base_iri)]

    annotation_decls = [
        f":{name} a owl:AnnotationProperty ." for name in _ANNOTATION_ORDER if name in used_annotations
    ]
    if annotation_decls:
        blocks.append("\n".join(annotation_decls))

    blocks.extend(entity_lines)
    blocks.extend(relationship_lines)

    return "\n\n".join(blocks) + "\n"


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
