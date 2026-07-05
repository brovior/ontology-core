"""ontology-core 패키지 공개 API."""

from ontology_core.schema import (
    EntityDef,
    AttributeDef,
    RelationshipDef,
    DerivedConceptDef,
    SqlDef,
    ModuleDef,
    CodeConceptDef,
)
from ontology_core.registry import Ontology
from ontology_core.data_source import DataSource, SqlDataSource
from ontology_core.query import OntologyQuery
from ontology_core.export import to_owl, to_skos

__all__ = [
    "EntityDef",
    "AttributeDef",
    "RelationshipDef",
    "DerivedConceptDef",
    "SqlDef",
    "ModuleDef",
    "CodeConceptDef",
    "Ontology",
    "DataSource",
    "SqlDataSource",
    "OntologyQuery",
    "to_owl",
    "to_skos",
]
