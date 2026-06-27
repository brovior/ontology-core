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

라이브러리는 한 방향으로만 조합되는 네 개의 레이어로 구성됩니다: `schema → registry → data_source → query`

### `schema.py` — 불변 메타데이터 정의
모든 스키마 타입은 `frozen=True` 데이터클래스입니다. `__post_init__`의 유효성 검증 외에는 별도 동작을 갖지 않습니다:
- `AttributeDef`: 논리 컬럼. `unit`은 `{"sec","pct","count","grade","weeks","none"}` 중 하나여야 합니다.
- `EntityDef`: 논리 테이블. `AttributeDef` 튜플과 속성 이름의 `primary_key` 튜플을 보유합니다. `primary_key`·`attributes`는 비어 있을 수 없고 속성명은 중복될 수 없습니다. 선택적 `entity_type`은 테이블 유형 코드로 `{"M","D","P","S","C","R"}`(마스터/디테일/피리어드/써머리/코드/임시) 중 하나 또는 빈 문자열(미분류)이며, 관계·카디널리티 추론의 사전 신호로 쓰입니다.
- `RelationshipDef`: 두 엔티티 간의 방향성 관계. `cardinality`는 `"1:1"`, `"1:N"`, `"M:N"` 중 하나. 선택적 `via_entity`로 M:N의 중간 엔티티를 지정합니다.
- `DerivedConceptDef`: 이름이 있는 공식. `formula_ref`는 plain callable; `inputs`로 키워드 인수명을 선언합니다.
- `SqlDef`: SQL 구문 단위 메타데이터. `name`, `sql`, `entity`는 빈 문자열 불가. `sql_type`은 `{"SELECT","INSERT","UPDATE","DELETE"}` 중 하나(기본 `"SELECT"`). `params`로 바인드 파라미터명을 선언합니다.
- `ModuleDef`: Java 소스 모듈 단위 메타데이터. `layer`는 `{"controller","biz","dao","mapper"}` 중 하나. `related_entities`와 `related_sqls`로 연관 메타데이터를 참조합니다.

모든 컬렉션 필드는 불변성 보장을 위해 `list` 대신 `tuple`을 사용합니다.

### `registry.py` — 중앙 메타데이터 스토어 (`Ontology`)
`Ontology`는 런타임 레지스트리입니다. 이름을 키로 하는 다섯 개의 dict를 보유합니다. 핵심 메서드는 `validate()`로, 다음 교차 참조 검증을 수행합니다:
- 각 `EntityDef`의 `primary_key` 필드가 `attributes`에 존재하는지 확인
- `RelationshipDef`에서 참조하는 `source_entity`, `target_entity`, `via_entity`가 등록된 엔티티인지 확인
- `SqlDef.entity`가 등록된 엔티티인지 확인
- `ModuleDef.related_entities`의 각 항목이 등록된 엔티티인지 확인
- `ModuleDef.related_sqls`의 각 항목이 등록된 SQL인지 확인

`validate()`는 반환 전에 모든 오류를 수집합니다. 호출자는 반환된 목록을 반드시 확인해야 합니다.

조회 편의 메서드도 제공합니다: `list_entities()`/`list_relationships()`/`list_derived_concepts()`/`list_sqls()`/`list_modules()`(등록 순서 이름 목록), `get_entities_by_domain(domain)`, `get_entities_by_type(entity_type)`, `get_modules_by_layer(layer)`.

### `data_source.py` — 데이터 접근 추상화
`DataSource`는 4개의 메서드를 가진 `runtime_checkable` `Protocol`입니다: `fetch`(PK로 단건 조회), `fetch_many`(필터 목록), `fetch_all`(전체 스캔), `join`(관계 탐색). 이 4개 메서드를 구현한 클래스는 상속 없이 프로토콜을 만족합니다.

`SqlDataSource`는 모든 메서드에서 `NotImplementedError`를 발생시키는 스텁으로, "Phase F"에서 구현 예정입니다.

### `query.py` — 쿼리 엔진 (`OntologyQuery`)
`OntologyQuery`는 `Ontology`와 `DataSource`로 생성됩니다. 모든 데이터 호출을 레지스트리 조회로 감싸서, 알 수 없는 엔티티나 관계에 대해 데이터 소스 호출 전에 `KeyError`를 발생시킵니다. 이를 통해 등록된 메타데이터만 쿼리되도록 강제합니다.

`derive()`는 이름으로 `DerivedConceptDef`를 해석하고 `**records` 키워드 인수를 그대로 `formula_ref`에 전달합니다.

## 핵심 관례

- **튜플 사용 원칙**: 컬렉션을 담는 스키마 필드(`attributes`, `primary_key`, `join_keys`, `inputs`, `enum_values`, `params`, `related_entities`, `related_sqls`)는 항상 `tuple`이며 `list`를 사용하지 않습니다. 테스트나 애플리케이션 코드에서 생성할 때는 `tuple(...)` 또는 `(item,)` 리터럴을 사용하세요.
- **이름 기반 레지스트리**: 엔티티·관계·파생 개념·SQL·모듈은 각각 `name` 필드로 등록되고 조회됩니다. 이름은 각 카테고리 내에서 고유해야 합니다.
- **분류 축은 검증된 enum 필드로**: 유한한 분류 값(`AttributeDef.unit`, `RelationshipDef.cardinality`, `ModuleDef.layer`, `SqlDef.sql_type`, `EntityDef.entity_type`)은 `description`/`domain`에 녹이지 않고 전용 필드 + `__post_init__` enum 검증으로 구조화합니다. `entity_type`(테이블 유형 코드)은 추출기가 채우며 코어는 분류값 저장·조회만 담당합니다(R 필터링·카디널리티 추론은 추출기 책임).
- **프로토콜 기반 확장성**: 새 데이터 백엔드를 추가하려면 임의 클래스에 4개의 `DataSource` 프로토콜 메서드를 구현하면 됩니다 — 기반 클래스 상속 불필요.
- **목록으로 반환되는 오류, 예외 없음**: `Ontology.validate()`는 `list[str]`을 반환합니다. 빈 목록은 정합성 통과를 의미합니다. 다운스트림 코드는 등록된 관계가 실제 엔티티를 참조한다고 신뢰하기 전에 반드시 이 목록을 확인해야 합니다.
- **`InMemoryDataSource`를 통한 테스트 더블**: `tests/test_query.py`에 완전히 동작하는 인메모리 `DataSource` 구현체가 있습니다. 테스트에서 데이터를 목킹할 때의 참조 패턴으로 활용하세요.
