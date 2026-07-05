# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 참고하는 지침 파일입니다.

## 프로젝트 개요

`ontology-core`는 시맨틱 데이터 레이어를 위한 범용 온톨로지 엔진입니다. 메타데이터 기반으로 데이터 소스를 추상화하여, 소비자가 엔티티·관계·파생 개념·SQL 구문·모듈을 정의하고 특정 SQL 스키마에 종속되지 않는 균일한 인터페이스로 데이터를 조회할 수 있습니다.

## 명령어

**개발 모드 설치:**
```bash
pip install -e ".[dev]"
```

**전체 테스트 실행:**
```bash
pytest
```

**단일 테스트 파일 실행:**
```bash
pytest tests/test_schema.py
```

**테스트 이름으로 단건 실행:**
```bash
pytest tests/test_registry.py::TestOntologyValidate::test_validate_clean
```

**배포판 빌드:**
```bash
pip install hatchling && python -m hatchling build
```

## 아키텍처

라이브러리는 한 방향으로만 조합되는 네 개의 레이어로 구성됩니다: `schema → registry → data_source → query`. `export.py`는 `registry`(`Ontology`)만 입력받아 Turtle 문자열을 만드는 부가 레이어로, 위 조합 방향에는 참여하지 않습니다.

### `schema.py` — 불변 메타데이터 정의
모든 스키마 타입은 `frozen=True` 데이터클래스입니다. `__post_init__`의 유효성 검증 외에는 별도 동작을 갖지 않습니다:
- `AttributeDef`: 논리 컬럼. `unit`은 `{"sec","pct","count","grade","weeks","none"}` 중 하나여야 합니다.
- `EntityDef`: 논리 테이블. `AttributeDef` 튜플과 속성 이름의 `primary_key` 튜플을 보유합니다. `primary_key`·`attributes`는 비어 있을 수 없고 속성명은 중복될 수 없습니다. 선택적 `entity_type`은 테이블 유형 코드로 `{"M","D","P","S","C","R"}`(마스터/디테일/피리어드/써머리/코드/임시) 중 하나 또는 빈 문자열(미분류)이며, 관계·카디널리티 추론의 사전 신호로 쓰입니다. 선택적 `psl_tag`/`isa95_tag`는 PSL(ISO 18629)/ISA-95 표준 어휘 정합 태그로, 값 검증 없는 열린 어휘입니다(기본값 `""`).
- `RelationshipDef`: 두 엔티티 간의 방향성 관계. `cardinality`는 `"1:1"`, `"1:N"`, `"M:N"` 중 하나. 선택적 `via_entity`로 M:N의 중간 엔티티를 지정합니다. 선택적 `relation_type`은 `ALLOWED_RELATION_TYPES`(`{"", "hierarchy", "reference", "code_reference"}`) 중 하나여야 합니다.
- `DerivedConceptDef`: 이름이 있는 공식. `formula_ref`는 plain callable; `inputs`로 키워드 인수명을 선언합니다.
- `SqlDef`: SQL 구문 단위 메타데이터. `name`, `sql`, `entity`는 빈 문자열 불가. `sql_type`은 `{"SELECT","INSERT","UPDATE","DELETE"}` 중 하나(기본 `"SELECT"`). `params`로 바인드 파라미터명을 선언합니다.
- `ModuleDef`: Java 소스 모듈 단위 메타데이터. `layer`는 `{"controller","biz","dao","mapper"}` 중 하나. `related_entities`와 `related_sqls`로 연관 메타데이터를 참조합니다.
- `CodeConceptDef`: 코드값(enum) 단위 의미 메타데이터(SKOS Concept에 대응). `scheme_name`(코드그룹명)·`code_value`·`pref_label`은 빈 문자열 불가. 선택적 `definition`(복원된 업무 의미)·`source_ref`(출처 식별자)를 가집니다.

모든 컬렉션 필드는 불변성 보장을 위해 `list` 대신 `tuple`을 사용합니다.

### `registry.py` — 중앙 메타데이터 스토어 (`Ontology`)
`Ontology`는 런타임 레지스트리입니다. 이름을 키로 하는 dict들을 보유합니다(엔티티/관계/파생 개념/SQL/모듈은 `name`, 코드 컨셉은 `(scheme_name, code_value)` 복합키). 핵심 메서드는 `validate()`로, 다음 교차 참조 검증을 수행합니다:
- 각 `EntityDef`의 `primary_key` 필드가 `attributes`에 존재하는지 확인
- `RelationshipDef`에서 참조하는 `source_entity`, `target_entity`, `via_entity`가 등록된 엔티티인지 확인
- `SqlDef.entity`가 등록된 엔티티인지 확인
- `ModuleDef.related_entities`의 각 항목이 등록된 엔티티인지 확인
- `ModuleDef.related_sqls`의 각 항목이 등록된 SQL인지 확인

`CodeConceptDef`는 `validate()`의 교차 참조 대상이 아닙니다 — `scheme_name`은 자유 문자열이라 참조할 등록 대상이 없고, 필수값은 생성 시점에, 유일성은 등록 시점에 이미 강제되기 때문입니다.

`validate()`는 반환 전에 모든 오류를 수집합니다. 호출자는 반환된 목록을 반드시 확인해야 합니다.

조회 편의 메서드도 제공합니다: `list_entities()`/`list_relationships()`/`list_derived_concepts()`/`list_sqls()`/`list_modules()`(등록 순서 이름 목록), `get_entities_by_domain(domain)`, `get_entities_by_type(entity_type)`, `get_modules_by_layer(layer)`.

코드 컨셉 전용 메서드: `register_code_concept(concept_def)`는 다른 `register_*`와 달리 **동일 `(scheme_name, code_value)`가 이미 등록되어 있으면 덮어쓰지 않고 `ValueError`를 발생**시킵니다(등록 시점 유일성 강제). `get_code_concept(scheme_name, code_value)`(없으면 `KeyError`), `get_concepts_by_scheme(scheme_name)`(등록 순서 보존), `code_concepts` 프로퍼티(전체 등록 순서), `list_schemes()`(등록 순서의 고유 scheme 이름 목록)를 제공합니다.

### `data_source.py` — 데이터 접근 추상화
`DataSource`는 4개의 메서드를 가진 `runtime_checkable` `Protocol`입니다: `fetch`(PK로 단건 조회), `fetch_many`(필터 목록), `fetch_all`(전체 스캔), `join`(관계 탐색). 이 4개 메서드를 구현한 클래스는 상속 없이 프로토콜을 만족합니다.

`SqlDataSource`는 모든 메서드에서 `NotImplementedError`를 발생시키는 스텁으로, "Phase F"에서 구현 예정입니다.

### `query.py` — 쿼리 엔진 (`OntologyQuery`)
`OntologyQuery`는 `Ontology`와 `DataSource`로 생성됩니다. 모든 데이터 호출을 레지스트리 조회로 감싸서, 알 수 없는 엔티티나 관계에 대해 데이터 소스 호출 전에 `KeyError`를 발생시킵니다. 이를 통해 등록된 메타데이터만 쿼리되도록 강제합니다.

`derive()`는 이름으로 `DerivedConceptDef`를 해석하고 `**records` 키워드 인수를 그대로 `formula_ref`에 전달합니다.

### `export.py` — OWL/SKOS Turtle 내보내기
`to_owl(ontology, base_iri=...)`와 `to_skos(ontology, base_iri=...)`는 순수 문자열 생성만으로 Turtle을 만듭니다(파일 쓰기·rdflib 등 외부 의존성 없음, zero-dependency 유지). `to_owl`은 `EntityDef`→`owl:Class`, `AttributeDef`→`owl:DatatypeProperty`, `RelationshipDef`→`owl:ObjectProperty`로 변환하고, `to_skos`는 `CodeConceptDef`를 `scheme_name` 단위 `skos:ConceptScheme` + `skos:Concept`으로 변환합니다. `SqlDef`/`ModuleDef`/`DerivedConceptDef`는 export 대상이 아닙니다.

- **관계형 어휘는 단일 상수로 관리**: `RelationshipDef.relation_type`이 허용하는 값 집합은 `schema.py`의 `ALLOWED_RELATION_TYPES` 하나로만 정의되며, `export.py`는 이를 그대로 annotation(`:relationType`)으로 기록할 뿐 `"hierarchy"` 등을 `owl:partOf` 같은 의미로 자동 매핑하지 않습니다.
- **결정론 출력 규약**: 엔티티/관계/scheme(및 scheme 내 concept)은 이름(또는 `code_value`) 오름차순, 엔티티 내 속성은 `attributes` 튜플의 정의 순서를 유지합니다. 동일 입력은 항상 바이트 단위로 동일한 문자열을 반환합니다.
- **IRI 안전화**: `_safe_iri_fragment()`가 영문자/숫자/언더스코어 외 문자를 `_U{코드포인트 16진}_`로 치환합니다(percent-encoding 미사용). 서로 다른 원본 이름이 같은 fragment로 치환되면 `ValueError`를 발생시킵니다.

## 핵심 관례

- **튜플 사용 원칙**: 컬렉션을 담는 스키마 필드(`attributes`, `primary_key`, `join_keys`, `inputs`, `enum_values`, `params`, `related_entities`, `related_sqls`)는 항상 `tuple`이며 `list`를 사용하지 않습니다. 테스트나 애플리케이션 코드에서 생성할 때는 `tuple(...)` 또는 `(item,)` 리터럴을 사용하세요.
- **이름 기반 레지스트리**: 엔티티·관계·파생 개념·SQL·모듈은 각각 `name` 필드로 등록되고 조회됩니다. 이름은 각 카테고리 내에서 고유해야 합니다.
- **분류 축은 검증된 enum 필드로**: 유한한 분류 값(`AttributeDef.unit`, `RelationshipDef.cardinality`, `ModuleDef.layer`, `SqlDef.sql_type`, `EntityDef.entity_type`)은 `description`/`domain`에 녹이지 않고 전용 필드 + `__post_init__` enum 검증으로 구조화합니다. `entity_type`(테이블 유형 코드)은 추출기가 채우며 코어는 분류값 저장·조회만 담당합니다(R 필터링·카디널리티 추론은 추출기 책임).
- **프로토콜 기반 확장성**: 새 데이터 백엔드를 추가하려면 임의 클래스에 4개의 `DataSource` 프로토콜 메서드를 구현하면 됩니다 — 기반 클래스 상속 불필요.
- **목록으로 반환되는 오류, 예외 없음**: `Ontology.validate()`는 `list[str]`을 반환합니다. 빈 목록은 정합성 통과를 의미합니다. 다운스트림 코드는 등록된 관계가 실제 엔티티를 참조한다고 신뢰하기 전에 반드시 이 목록을 확인해야 합니다.
- **`InMemoryDataSource`를 통한 테스트 더블**: `tests/test_query.py`에 완전히 동작하는 인메모리 `DataSource` 구현체가 있습니다. 테스트에서 데이터를 목킹할 때의 참조 패턴으로 활용하세요.
