"""data_source.py 단위 테스트."""

import pytest
from ontology_core.data_source import DataSource, SqlDataSource
from ontology_core.registry import Ontology


class TestSqlDataSource:
    def _make(self) -> SqlDataSource:
        return SqlDataSource(ontology=Ontology())

    def test_fetch_raises_not_implemented(self) -> None:
        """fetch()는 NotImplementedError를 발생시킨다."""
        with pytest.raises(NotImplementedError):
            self._make().fetch("MODEL", {"id": "1"})

    def test_fetch_many_raises_not_implemented(self) -> None:
        """fetch_many()는 NotImplementedError를 발생시킨다."""
        with pytest.raises(NotImplementedError):
            self._make().fetch_many("MODEL", {})

    def test_fetch_all_raises_not_implemented(self) -> None:
        """fetch_all()는 NotImplementedError를 발생시킨다."""
        with pytest.raises(NotImplementedError):
            self._make().fetch_all("MODEL")

    def test_join_raises_not_implemented(self) -> None:
        """join()은 NotImplementedError를 발생시킨다."""
        with pytest.raises(NotImplementedError):
            self._make().join("REL", {"id": "1"})


class TestDataSourceProtocol:
    def test_sql_data_source_satisfies_protocol(self) -> None:
        """SqlDataSource는 DataSource 프로토콜을 만족한다."""
        assert isinstance(SqlDataSource(ontology=Ontology()), DataSource)

    def test_custom_class_satisfies_protocol(self) -> None:
        """4개 메서드를 구현한 임의 클래스는 상속 없이 프로토콜을 만족한다."""
        class MySource:
            def fetch(self, entity_name: str, key: dict) -> dict | None:
                return None

            def fetch_many(self, entity_name: str, filter: dict) -> list[dict]:
                return []

            def fetch_all(self, entity_name: str) -> list[dict]:
                return []

            def join(self, rel_name: str, source_key: dict) -> list[dict]:
                return []

        assert isinstance(MySource(), DataSource)

    def test_incomplete_class_does_not_satisfy_protocol(self) -> None:
        """메서드가 부족한 클래스는 프로토콜을 만족하지 않는다."""
        class Incomplete:
            def fetch(self, entity_name: str, key: dict) -> dict | None:
                return None

        assert not isinstance(Incomplete(), DataSource)
