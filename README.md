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
│    │                   concept, sql, module     │
│    └─ validate()                                │
├─────────────────────────────────────────────────┤
│  schema.py  ·  불변 메타데이터 정의              │  스키마 레이어
│    ├─ AttributeDef    (논리 컬럼)               │
│    ├─ EntityDef       (논리 테이블)             │
│    ├─ RelationshipDef (방향성 관계)             │
│    ├─ DerivedConceptDef (파생 공식)             │
│    ├─ SqlDef          (SQL 구문)                │
│    └─ ModuleDef       (Java 모듈)              │
└─────────────────────────────────────────────────┘
```

### schema.py — 불변 메타데이터 정의

여섯 가지 `frozen=True` 데이터클래스로 구성됩니다.

| 클래스 | 역할 | 주요 제약 |
|--------|------|-----------|
| `AttributeDef` | 논리 컬럼 | `unit` ∈ `{sec, pct, count, grade, weeks, none}` |
| `EntityDef` | 논리 테이블 | `primary_key`·`attributes` 비어 있을 수 없음; `entity_type` ∈ `{M, D, P, S, C, R}` 또는 빈 문자열 |
| `RelationshipDef` | 방향성 관계 | `cardinality` ∈ `{1:1, 1:N, M:N}` |
| `DerivedConceptDef` | 파생 공식 | `formula_ref`는 callable; `inputs`로 키워드 인수 선언 |
| `SqlDef` | SQL 구문 | `name`, `sql`, `entity` 모두 빈 문자열 불가; `sql_type` ∈ `{SELECT, INSERT, UPDATE, DELETE}` |
| `ModuleDef` | Java 소스 모듈 | `layer` ∈ `{controller, biz, dao, mapper}` |

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

# 교차 참조 검증 (오류 없으면 [])
errors = ontology.validate()
```

`validate()`가 검증하는 항목:
- `EntityDef.primary_key` 항목이 `attributes`에 존재하는지
- `RelationshipDef`의 `source_entity`, `target_entity`, `via_entity`가 등록된 엔티티인지
- `SqlDef.entity`가 등록된 엔티티인지
- `ModuleDef.related_entities`의 각 항목이 등록된 엔티티인지
- `ModuleDef.related_sqls`의 각 항목이 등록된 SQL인지

조회 편의 메서드:
- `list_entities()` · `list_relationships()` · `list_derived_concepts()` · `list_sqls()` · `list_modules()` — 등록된 이름 목록(등록 순서)
- `get_entities_by_domain(domain)` — 도메인별 엔티티 필터
- `get_entities_by_type(entity_type)` — 유형 코드별 엔티티 필터 (예: `"C"` → 공통 코드 테이블)
- `get_modules_by_layer(layer)` — 레이어별 모듈 필터

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
│   ├── schema.py       # 불변 메타데이터 정의 (6개 클래스)
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
