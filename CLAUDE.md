# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ontology-core` is a generic ontology engine for semantic data layers. It provides a metadata-driven abstraction over data sources, allowing consumers to define entities, relationships, and derived concepts and query data through a uniform interface without coupling to specific SQL schemas.

## Commands

**Install (dev mode):**
```bash
pip install -e ".[dev]"
```

**Run all tests:**
```bash
pytest
```

**Run a single test file:**
```bash
pytest tests/test_schema.py
```

**Run a single test by name:**
```bash
pytest tests/test_registry.py::TestOntologyValidate::test_validate_clean
```

**Build distribution:**
```bash
pip install hatchling && python -m hatchling build
```

## Architecture

The library has four layers that compose in one direction: `schema → registry → data_source → query`.

### `schema.py` — Immutable metadata definitions
All four schema types are `frozen=True` dataclasses. They carry no behavior beyond validation in `__post_init__`:
- `AttributeDef`: a logical column. `unit` must be one of `{"sec","pct","count","grade","weeks","none"}`.
- `EntityDef`: a logical table. Holds a tuple of `AttributeDef`s and a `primary_key` tuple of attribute names.
- `RelationshipDef`: a directed edge between two entities. `cardinality` must be `"1:1"`, `"1:N"`, or `"M:N"`. Optional `via_entity` names an intermediate entity for M:N.
- `DerivedConceptDef`: a named formula. `formula_ref` is a plain callable; `inputs` lists its expected keyword argument names.

All collection fields use `tuple`, not `list`, to preserve immutability.

### `registry.py` — Central metadata store (`Ontology`)
`Ontology` is the runtime registry. It holds three plain dicts keyed by name. The key method is `validate()`, which performs cross-reference checks:
- Every `primary_key` field in each `EntityDef` must appear in its `attributes`.
- Every `source_entity`, `target_entity`, and `via_entity` referenced in a `RelationshipDef` must already be registered.

`validate()` collects all errors before returning; callers must check the returned list.

### `data_source.py` — Data access abstraction
`DataSource` is a `runtime_checkable` `Protocol` with four methods: `fetch` (single record by PK), `fetch_many` (filtered list), `fetch_all` (full scan), and `join` (relationship traversal). Any class implementing these four methods satisfies the protocol without inheriting from it.

`SqlDataSource` is a placeholder that raises `NotImplementedError` on all methods; it is scheduled for implementation in "Phase F".

### `query.py` — Query engine (`OntologyQuery`)
`OntologyQuery` is constructed with an `Ontology` and a `DataSource`. It wraps every data call with a registry lookup that raises `KeyError` for unknown entities or relationships before the call reaches the data source. This enforces that only registered metadata is ever queried.

`derive()` resolves a `DerivedConceptDef` by name and forwards `**records` keyword arguments directly to its `formula_ref`.

## Key Conventions

- **Tuples everywhere**: schema fields that hold collections (`attributes`, `primary_key`, `join_keys`, `inputs`, `enum_values`) are always `tuple`, never `list`. When constructing these in tests or application code, wrap lists in `tuple(...)` or use `(item,)` literals.
- **Name-keyed registries**: entities, relationships, and derived concepts are each registered and looked up by their `name` field. Names must be unique within each category.
- **Protocol-based extensibility**: to add a new data backend, implement the four `DataSource` protocol methods on any class — no base class inheritance needed.
- **Errors as lists, not exceptions**: `Ontology.validate()` returns a `list[str]`; an empty list means valid. Downstream code must check this before trusting registered relationships reference real entities.
- **Test doubles via `InMemoryDataSource`**: `tests/test_query.py` contains a fully functional in-memory `DataSource` implementation that is the reference pattern for mocking data in tests.
