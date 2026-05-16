"""ontology-core 패키지 공개 API."""

from ontology_core.schema import EntityDef, AttributeDef, RelationshipDef, DerivedConceptDef
from ontology_core.registry import Ontology
from ontology_core.data_source import DataSource, SqlDataSource
from ontology_core.query import OntologyQuery

__all__ = [
    "EntityDef",
    "AttributeDef",
    "RelationshipDef",
    "DerivedConceptDef",
    "Ontology",
    "DataSource",
    "SqlDataSource",
    "OntologyQuery",
]
