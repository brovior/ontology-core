# ontology-core

시맨틱 데이터 레이어를 위한 범용 온톨로지 엔진입니다. 메타데이터 기반으로 데이터 소스를 추상화하여, 특정 SQL 스키마에 종속되지 않고 엔티티·관계·파생 개념·SQL 구문·모듈을 정의하고 균일한 인터페이스로 데이터를 조회할 수 있습니다.

## 특징

- **불변 메타데이터 정의** — `frozen=True` 데이터클래스로 런타임 변이 방지
- **중앙 레지스트리** — 엔티티·관계·파생 개념·SQL·모듈을 이름 기반으로 관리
- **교차 참조 검증** — `validate()`가 등록 누락·참조 오류를 한꺼번에 수집
- **프로토콜 기반 확장** — 상속 없이 4개 메서드 구현만으로 새 데이터 백엔드 추가 가능
- **쿼리 전 검증** — 미등록 엔티티·관계 조회 시 데이터 소스 호출 전에 즉시 `KeyError` 발생
- **의존성 없음** — 표준 라이브러리만 사용 (Python ≥ 3.10)

## 설치

```bash
pip install ontology-core
```

개발 환경 설치:

```bash
git clone https://github.com/brovior/ontology-core.git
cd ontology-core
pip install -e ".[dev]"
```

## 빠른 시작

```python
from ontology_core.schema import AttributeDef, EntityDef, SqlDef, ModuleDef
from ontology_core.registry import Ontology
from ontology_core.query import OntologyQuery

# 1. 메타데이터 정의
model_cd = AttributeDef(name="model_cd", column_name="MODEL_CD", description="모델 코드", data_type="str", unit="none")
model_nm = AttributeDef(name="model_nm", column_name="MODEL_NM", description="모델명",  data_type="str", unit="none")

model = EntityDef(
    name="MODEL",
    table_name="T_MODEL",
    description="모델 마스터",
    domain="제조",
    primary_key=("model_cd",),
    attributes=(model_cd, model_nm),
)

sql = SqlDef(
    name="GET_MODEL_BY_CD",
    sql="SELECT * FROM T_MODEL WHERE MODEL_CD = :model_cd",
    entity="MODEL",
    params=("model_cd",),
)

module = ModuleDef(
    name="ModelController",
    layer="controller",
    file_path="com/example/ModelController.java",
    related_entities=("MODEL",),
    related_sqls=("GET_MODEL_BY_CD",),
)

# 2. 레지스트리 등록 및 검증
ontology = Ontology()
ontology.register_entity(model)
ontology.register_sql(sql)
ontology.register_module(module)

errors = ontology.validate()
if errors:
    raise RuntimeError(errors)

# 3. DataSource 구현 및 쿼리 실행
class InMemoryDataSource:
    def fetch(self, entity_name, key):
        data = {"MODEL": [{"model_cd": "M001", "model_nm": "알파"}]}
        for row in data.get(entity_name, []):
            if all(row.get(k) == v for k, v in key.items()):
                return row
        return None
    def fetch_many(self, entity_name, filter): return []
    def fetch_all(self, entity_name): return []
    def join(self, rel_name, source_key): return []

query = OntologyQuery(ontology=ontology, data_source=InMemoryDataSource())
record = query.get("MODEL", {"model_cd": "M001"})
print(record)  # {'model_cd': 'M001', 'model_nm': '알파'}
```

### OWL/SKOS로 내보내기

`export.py`는 외부 의존성 없이(rdflib 등 미사용) 순수 문자열 생성만으로 Turtle을 만듭니다. `to_owl()`은 엔티티·속성·관계를, `to_skos()`는 코드 컨셉을 변환합니다.

```python
from ontology_core.schema import CodeConceptDef
from ontology_core.export import to_owl, to_skos

# 코드 컨셉 등록 (위 model 온톨로지에 이어서)
ontology.register_code_concept(CodeConceptDef(
    scheme_name="WORK_TYPE",
    code_value="W",
    pref_label="작업",
    definition="생산 작업 지시 유형",
    source_ref="WorkTypeDao",
))

print(to_owl(ontology))
# @prefix owl: <http://www.w3.org/2002/07/owl#> .
# ...
# :MODEL a owl:Class .
# :MODEL rdfs:label "MODEL"@ko .
# :MODEL rdfs:comment "모델 마스터"@ko .
# :MODEL_model_cd a owl:DatatypeProperty .
# :MODEL_model_cd rdfs:domain :MODEL .
# :MODEL_model_cd rdfs:range xsd:string .
# ...

print(to_skos(ontology))
# @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
# ...
# :WORK_TYPE a skos:ConceptScheme .
# :WORK_TYPE rdfs:label "WORK_TYPE"@ko .
# :WORK_TYPE_W a skos:Concept .
# :WORK_TYPE_W skos:inScheme :WORK_TYPE .
# :WORK_TYPE_W skos:prefLabel "작업"@ko .
# :WORK_TYPE_W skos:definition "생산 작업 지시 유형"@ko .
# :WORK_TYPE_W dct:source "WorkTypeDao" .
```

동일한 `Ontology` 입력에 대해 항상 바이트 단위로 동일한 문자열을 반환합니다(엔티티/관계/scheme은 이름 오름차순 정렬). `SqlDef`/`ModuleDef`/`DerivedConceptDef`는 export 대상이 아닙니다.

## 아키텍처

레이어는 한 방향으로만 조합됩니다: `schema → registry → data_source → query`

```
┌─────────────────────────────────────────────────┐
│  query.py  ·  OntologyQuery                     │  데이터 조회 엔진
│    ├─ get / fetch_many / fetch_all              │
│    ├─ traverse (관계 탐색)                       │
│    └─ derive  (파생 개념 계산)                   │
├─────────────────────────────────────────────────┤
│  data_source.py  ·  DataSource (Protocol)       │  데이터 접근 추상화
│    ├─ fetch / fetch_many / fetch_all / join     │
│    └─ SqlDataSource (Phase F 구현 예정)          │
├─────────────────────────────────────────────────┤
│  registry.py  ·  Ontology                       │  중앙 메타데이터 스토어
│    ├─ register / get : entity, relationship,    │
│    │                   concept, sql, module,    │
│    │                   code_concept              │
│    └─ validate()                                │
├─────────────────────────────────────────────────┤
│  schema.py  ·  불변 메타데이터 정의              │  스키마 레이어
│    ├─ AttributeDef    (논리 컬럼)               │
│    ├─ EntityDef       (논리 테이블)             │
│    ├─ RelationshipDef (방향성 관계)             │
│    ├─ DerivedConceptDef (파생 공식)             │
│    ├─ SqlDef          (SQL 구문)                │
│    ├─ ModuleDef       (Java 모듈)              │
│    └─ CodeConceptDef  (코드값 의미)             │
├─────────────────────────────────────────────────┤
│  export.py  ·  OWL/SKOS Turtle 내보내기          │  부가 레이어(registry만 소비)
│    ├─ to_owl  (엔티티/속성/관계 → OWL)           │
│    └─ to_skos (코드 컨셉 → SKOS)                 │
└─────────────────────────────────────────────────┘
```

### schema.py — 불변 메타데이터 정의

열 가지 `frozen=True` 데이터클래스로 구성됩니다.

| 클래스 | 역할 | 주요 제약 |
|--------|------|-----------|
| `AttributeDef` | 논리 컬럼 | `unit` ∈ `{sec, pct, count, grade, weeks, none}` |
| `EntityDef` | 논리 테이블 | `primary_key`·`attributes` 비어 있을 수 없음; `entity_type` ∈ `{M, D, P, S, C, R}` 또는 빈 문자열; 선택적 `psl_tag`/`isa95_tag`(값 검증 없는 열린 어휘, 예: `"activity"`/`"ProcessSegment"`) |
| `RelationshipDef` | 방향성 관계 | `cardinality` ∈ `{1:1, 1:N, M:N, UNKNOWN}`(`UNKNOWN` = 관측됐으나 미증명 카디널리티의 정직한 공백); 선택적 `relation_type` ∈ `{"", hierarchy, reference, code_reference}`; 선택적 `source_ref`(관계 출처, `dct:source`로 export) |
| `EvidenceEndpointDef` | 관측 테이블의 논리 끝점 | `table_ref` 필수; `entity_ref`와 미물질화 사유는 상호 배타적 |
| `EvidenceSourceDef` | 출처·문맥·입력 스냅샷 | `source_ref` 필수; 세 값의 대응을 보존 |
| `RelationshipEvidenceDef` | 전체 관계 관측·전문가 분류·평가 상태 | 비어 있지 않은 중복 없는 컬럼쌍 tuple; 역할·평가 상태 enum 및 그룹 검증 |
| `DerivedConceptDef` | 파생 공식 | `formula_ref`는 callable; `inputs`로 키워드 인수 선언 |
| `SqlDef` | SQL 구문 | `name`, `sql`, `entity` 모두 빈 문자열 불가; `sql_type` ∈ `{SELECT, INSERT, UPDATE, DELETE}` |
| `ModuleDef` | Java 소스 모듈 | `layer` ∈ `{controller, biz, dao, mapper}` |
| `CodeConceptDef` | 코드값(enum) 의미 | `scheme_name`·`code_value`·`pref_label` 모두 빈 문자열 불가; 선택적 `definition`·`source_ref` |

모든 컬렉션 필드는 불변성 보장을 위해 `list` 대신 `tuple`을 사용합니다.

#### EntityDef.entity_type — 테이블 유형 코드

엔티티의 구조적 역할을 나타내는 선택적 분류 축입니다(빈 문자열 = 미분류). 관계 추출·
카디널리티 추론·cross-module 허브 분석의 사전 신호로 활용됩니다.

| 코드 | 의미 | 비고 |
|------|------|------|
| `M` | 마스터(기준 정보) | 단일 PK 경향, 1:N의 1쪽 |
| `D` | 디테일(상세/명세) | 마스터 참조, 복합키 경향, 1:N의 N쪽 |
| `P` | 피리어드(기간성) | 날짜/기간 + 마스터키 복합 PK, 이력성 |
| `S` | 써머리(요약/집계) | 원본에서 파생, 집계 단위 키 |
| `C` | 코드(공통 코드) | 작은 룩업 테이블, 여러 모듈이 공유 참조 |
| `R` | 임시 | 추출 대상에서 제외 또는 별도 처리 |

### registry.py — 중앙 레지스트리 (`Ontology`)

```python
ontology = Ontology()
# 등록
ontology.register_entity(entity_def)
ontology.register_relationship(rel_def)
ontology.register_derived_concept(concept_def)
ontology.register_sql(sql_def)
ontology.register_module(module_def)
ontology.register_code_concept(code_concept_def)

# 교차 참조 검증 (오류 없으면 [])
errors = ontology.validate()
```

`validate()`가 검증하는 항목:
- `EntityDef.primary_key` 항목이 `attributes`에 존재하는지
- `RelationshipDef`의 `source_entity`, `target_entity`, `via_entity`가 등록된 엔티티인지
- `SqlDef.entity`가 등록된 엔티티인지
- `ModuleDef.related_entities`의 각 항목이 등록된 엔티티인지
- `ModuleDef.related_sqls`의 각 항목이 등록된 SQL인지

(`CodeConceptDef`는 `scheme_name`이 자유 문자열이라 교차 참조 대상이 없으며, 필수값·유일성은 생성/등록 시점에 이미 강제되므로 `validate()` 대상이 아닙니다.)

조회 편의 메서드:
- `list_entities()` · `list_relationships()` · `list_derived_concepts()` · `list_sqls()` · `list_modules()` — 등록된 이름 목록(등록 순서)
- `get_entities_by_domain(domain)` — 도메인별 엔티티 필터
- `get_entities_by_type(entity_type)` — 유형 코드별 엔티티 필터 (예: `"C"` → 공통 코드 테이블)
- `get_modules_by_layer(layer)` — 레이어별 모듈 필터
- `get_code_concept(scheme_name, code_value)` — 코드 컨셉 단건 조회 (없으면 `KeyError`)
- `get_concepts_by_scheme(scheme_name)` — scheme별 코드 컨셉 목록(등록 순서)
- `code_concepts` — 등록된 전체 `CodeConceptDef` 목록(등록 순서)
- `list_schemes()` — 등록된 고유 scheme 이름 목록(등록 순서)

`register_code_concept(concept_def)`는 동일한 `(scheme_name, code_value)`를, `register_relationship_evidence(evidence_def)`는 동일한 근거 이름을 `ValueError`로 거부합니다. 기존 `register_relationship()`의 같은 이름 덮어쓰기는 유지합니다.

### data_source.py — DataSource Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataSource(Protocol):
    def fetch(self, entity_name: str, key: dict) -> dict | None: ...
    def fetch_many(self, entity_name: str, filter: dict) -> list[dict]: ...
    def fetch_all(self, entity_name: str) -> list[dict]: ...
    def join(self, rel_name: str, source_key: dict) -> list[dict]: ...
```

이 4개 메서드를 구현한 클래스라면 `DataSource`를 상속하지 않아도 프로토콜을 만족합니다.

### query.py — 쿼리 엔진 (`OntologyQuery`)

| 메서드 | 설명 |
|--------|------|
| `get(entity, key)` | PK 검증 후 단건 조회 |
| `fetch_many(entity, filter)` | 필터 조건 다건 조회 |
| `fetch_all(entity)` | 전체 스캔 |
| `traverse(rel_name, source_key)` | 관계 탐색 |
| `derive(concept_name, **records)` | 파생 개념 계산 |

## 사용 예제

### SqlDef — SQL 구문 메타데이터 등록

```python
from ontology_core.schema import SqlDef

sql = SqlDef(
    name="GET_MODEL_BY_CD",
    sql="SELECT * FROM T_MODEL WHERE MODEL_CD = :model_cd",
    entity="MODEL",
    params=("model_cd",),
    description="모델 코드로 단건 조회",
)
ontology.register_sql(sql)

# 조회
retrieved = ontology.get_sql("GET_MODEL_BY_CD")
print(retrieved.entity)  # MODEL
```

### ModuleDef — Java 모듈 메타데이터 등록

```python
from ontology_core.schema import ModuleDef

module = ModuleDef(
    name="ModelDao",
    layer="dao",
    file_path="com/example/dao/ModelDao.java",
    related_entities=("MODEL",),
    related_sqls=("GET_MODEL_BY_CD",),
    description="모델 데이터 접근 객체",
)
ontology.register_module(module)
```

허용 layer 값: `controller` · `biz` · `dao` · `mapper`

### 관계 탐색

```python
from ontology_core.schema import RelationshipDef

ontology.register_relationship(RelationshipDef(
    name="MODEL_TO_PLANTS",
    source_entity="MODEL",
    target_entity="PLANT",
    cardinality="M:N",
    join_keys=(("model_cd", "model_cd"),),
    via_entity="MODEL_PLANT_MAP",
))

plants = query.traverse("MODEL_TO_PLANTS", {"model_cd": "M001"})
```

### 관계 근거 보존 (0.5.0)

활성 `RelationshipDef`가 없는 관측도 별도 레지스트리에 저장합니다. `CANONICAL`은 그룹 대표이며 기본/안전 조인을 뜻하지 않습니다. `SUPPORTING_OBSERVATION`의 추가 조건은 기준 관계에 합치지 않으며 `HOLD`/`EXCLUDED`는 활성 관계를 참조할 수 없습니다. core는 역할이나 평가 상태를 승격하거나 카디널리티를 추론하지 않습니다. `RelationshipDef.cardinality`의 `REVIEW` 비허용은 유지합니다.

```python
from ontology_core import EvidenceEndpointDef, EvidenceSourceDef, RelationshipEvidenceDef

ontology.register_relationship_evidence(RelationshipEvidenceDef(
    name="observed_mapping",
    source_endpoint=EvidenceEndpointDef("T_MODEL", entity_ref="MODEL"),
    target_endpoint=EvidenceEndpointDef("T_DETAIL", unmaterialized_reason="PK_UNKNOWN"),
    join_keys=(("MODEL_CD", "MODEL_CD"), ("SITE_CD", "SITE_CD")),
    role="CANONICAL",
    group_id="model_detail_group",
    sources=(EvidenceSourceDef("ModelDao.find", "CTX_1", "input_snapshot_hash"),),
    description="전문가 원문 검토 설명",
    assessment_status="UNRESOLVED",
))
assert ontology.validate() == []
assert ontology.list_relationship_evidence() == ["observed_mapping"]
assert ontology.get_relationship_evidence("observed_mapping").relationship_name == ""
```

- `EvidenceEndpointDef(table_ref, entity_ref="", unmaterialized_reason="")`: 실제 엔티티가 있으면 `entity_ref`와 `EntityDef.table_name`이 일치해야 합니다. 없으면 `OUT_OF_SCOPE`, `NOT_WHITELISTED`, `PK_UNKNOWN`, `DICT_MISSING`, `NO_COLUMNS`, `PK_COL_MISSING` 중 사유가 필수입니다. 가짜 PK/엔티티를 만들지 않습니다.
- `EvidenceSourceDef(source_ref, context_ref="", snapshot_ref="")`: 원출처·문맥·입력 스냅샷을 한 레코드로 보존하며 SQL 원문/업무행을 저장하는 용도가 아닙니다.
- `RelationshipEvidenceDef` 필수 인수는 `name`, `source_endpoint`, `target_endpoint`, `join_keys`, `role`입니다. 선택 필드는 `group_id`, `canonical_evidence_name`, `relationship_name`, `sources`, `review_status`, `reason_code`, `description`, `assessment_status`(기본 `UNASSESSED`), `assessment_method`입니다. `description`은 원래 전문가 설명이며 LLM 설명으로 덮어쓰지 않습니다.
- 역할은 `CANONICAL`, `SUPPORTING_OBSERVATION`, `HOLD`, `EXCLUDED`; 평가 상태는 `UNASSESSED`, `RESOLVED`, `UNRESOLVED`, `CONFLICT`입니다. 이 상태는 카디널리티가 아닙니다.
- `CANONICAL`/`SUPPORTING_OBSERVATION`은 그룹이 필수이고, 같은 논리 테이블쌍·그룹에는 기준이 정확히 하나 있어야 합니다. 보조는 같은 그룹·끝점의 실제 기준을 참조해야 합니다. 기준은 다른 기준을 참조하지 않습니다.
- `relationship_name`은 선택적 활성 관계 참조입니다. 기준 전체 컬럼쌍과 실제 관계를 비교하고, 관계 방향이 역이면 컬럼쌍 묶음 전체를 반전합니다. 보조의 참조는 기준 관계와 같아야 합니다. 미물질화 끝점이 있는 그룹에는 활성 관계 참조를 허용하지 않습니다.
- 등록 순서의 이름 목록은 `list_relationship_evidence()`, 단건 조회는 `get_relationship_evidence(name)`입니다. 일반 `OntologyQuery.traverse()`는 등록된 `RelationshipDef`만 탐색합니다.

`to_owl()`은 근거가 있으면 전체 `validate()` 결과가 빈 목록인지 검사하고 오류 시 `ValueError`를 냅니다. 출력은 `RelationshipEvidence`, `EvidenceEndpoint`, `EvidenceSource`, `JoinKeyPair` 메타데이터 클래스와 `owl:NamedIndividual`을 사용합니다. 실제 엔티티/관계 IRI는 `resolvesTo`/`relationshipRef` annotation으로만 참조합니다. 미물질화 끝점에는 테이블명과 사유만 보존하며 엔티티 클래스를 새로 만들지 않습니다. 근거 자체는 `owl:ObjectProperty`나 cardinality restriction이 되지 않습니다.

0.5.0부터 기존 관계의 `description`도 `rdfs:comment`로, 관계와 근거의 전체 `join_keys`도 소유자별 `JoinKeyPair`로 출력합니다. `joinKeyPair`, `pairIndex`(0부터 시작하는 정렬 순서), `sourceColumn`, `targetColumn`은 서로 다른 시그니처의 경계를 보존합니다. 출처는 `hasSource`로 연결하고 각 레코드에 `dct:source`/`contextRef`/`snapshotRef`를 대응시킵니다. 끝점·출처 IRI는 전체 값의 SHA-256, 근거 IRI는 이름의 SHA-256, 컬럼쌍 IRI는 소유 IRI+인덱스에 결속됩니다. 사용자 IRI와 새 어휘/생성 IRI 충돌은 오류입니다. 새 어휘는 사용 시에만 선언하며 근거가 없고 기존 관계의 컬럼쌍·설명도 비어 있으면 이전 바이트 출력을 유지합니다. RDF parser인 `rdflib`은 개발 테스트에만 사용하고 런타임 의존성은 없습니다.

### 파생 개념 계산

```python
from ontology_core.schema import DerivedConceptDef

ontology.register_derived_concept(DerivedConceptDef(
    name="efficiency",
    formula_ref=lambda real_ct, st: round(st / real_ct, 4) if real_ct else 0.0,
    inputs=("real_ct", "st"),
    formula_text="st / real_ct",
))

result = query.derive("efficiency", real_ct=10.0, st=8.0)
# 0.8
```

### 새 DataSource 백엔드 추가

```python
class MyDatabaseSource:
    def fetch(self, entity_name: str, key: dict) -> dict | None: ...
    def fetch_many(self, entity_name: str, filter: dict) -> list[dict]: ...
    def fetch_all(self, entity_name: str) -> list[dict]: ...
    def join(self, rel_name: str, source_key: dict) -> list[dict]: ...

# DataSource를 상속하지 않아도 프로토콜 충족
assert isinstance(MyDatabaseSource(), DataSource)
```

## 테스트

```bash
# 전체 테스트
pytest

# 특정 파일
pytest tests/test_schema.py

# 특정 테스트
pytest tests/test_registry.py::TestOntologySqlModule::test_validate_clean_with_sql_and_module
```

테스트에서 데이터 소스를 목킹할 때는 `tests/test_query.py`의 `InMemoryDataSource` 구현을 참고하세요.

## 빌드

```bash
pip install hatchling
python -m hatchling build
```

## 프로젝트 구조

```
ontology-core/
├── ontology_core/
│   ├── __init__.py
│   ├── schema.py       # 불변 메타데이터 정의 (10개 클래스)
│   ├── registry.py     # 중앙 레지스트리 (Ontology)
│   ├── data_source.py  # DataSource 프로토콜 + SqlDataSource 스텁
│   └── query.py        # 쿼리 엔진 (OntologyQuery)
├── tests/
│   ├── test_schema.py
│   ├── test_registry.py
│   └── test_query.py   # InMemoryDataSource 참조 구현 포함
├── pyproject.toml
└── README.md
```

## 로드맵

- **Phase F**: `SqlDataSource` 구현 — SQLAlchemy 기반 SQL 어댑터

## 라이선스

MIT
