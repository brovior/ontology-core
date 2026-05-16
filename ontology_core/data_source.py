"""DataSource 프로토콜 및 SqlDataSource 스텁 — 외부 데이터 접근 추상화."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ontology_core.registry import Ontology


@runtime_checkable
class DataSource(Protocol):
    """온톨로지 엔티티/관계 데이터를 조회하는 인터페이스."""

    def fetch(self, entity_name: str, key: dict) -> dict | None:
        """단건 조회 — primary_key 값으로 레코드를 반환한다. 없으면 None."""
        ...

    def fetch_many(self, entity_name: str, filter: dict) -> list[dict]:
        """필터 조건에 맞는 레코드 목록을 반환한다."""
        ...

    def fetch_all(self, entity_name: str) -> list[dict]:
        """엔티티의 모든 레코드를 반환한다."""
        ...

    def join(self, rel_name: str, source_key: dict) -> list[dict]:
        """관계 이름과 소스 키로 연결된 타겟 레코드 목록을 반환한다."""
        ...


class SqlDataSource:
    """SQL 기반 DataSource 구현체 — Phase F에서 구현 예정."""

    def __init__(self, ontology: Ontology) -> None:
        """Ontology 레지스트리를 주입받아 초기화한다."""
        self._ontology = ontology

    def fetch(self, entity_name: str, key: dict) -> dict | None:
        """단건 조회 — SQL SELECT WHERE 구현 예정."""
        raise NotImplementedError("SqlDataSource 미구현: SQL 어댑터는 Phase F에서 구현")

    def fetch_many(self, entity_name: str, filter: dict) -> list[dict]:
        """필터 조건 다건 조회 — SQL SELECT WHERE 구현 예정."""
        raise NotImplementedError("SqlDataSource 미구현: SQL 어댑터는 Phase F에서 구현")

    def fetch_all(self, entity_name: str) -> list[dict]:
        """전체 조회 — SQL SELECT 구현 예정."""
        raise NotImplementedError("SqlDataSource 미구현: SQL 어댑터는 Phase F에서 구현")

    def join(self, rel_name: str, source_key: dict) -> list[dict]:
        """관계 기반 JOIN 조회 — SQL JOIN 구현 예정."""
        raise NotImplementedError("SqlDataSource 미구현: SQL 어댑터는 Phase F에서 구현")
