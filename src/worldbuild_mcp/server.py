import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from worldbuild_core import entities
from worldbuild_core import validate as validate_core
from worldbuild_core.index import scan_vault
from worldbuild_core.vault import load_schema

mcp = FastMCP("innkeeper")


def _vault() -> Path:
    return Path(os.environ["OBSIDIAN_VAULT_PATH"])


def _err(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": str(exc)}


@mcp.tool
def create_entity(
    type: str, name: str, fields: dict[str, Any] | None = None, body: str = ""
) -> dict[str, Any]:
    """Create a new entity (Character, Faction, Location, ...) and return it."""
    vault = _vault()
    schema = load_schema(vault)
    entity = entities.create_entity(vault, schema, type, name, fields, body)
    return {"ok": True, "entity": asdict(entity)}


@mcp.tool
def get_entity(ref: str) -> dict[str, Any]:
    """Get information about an entity (uid, type, name, frontmatter, body) and returns it."""
    vault = _vault()
    schema = load_schema(vault)
    entity_view = entities.get_entity(vault, schema, ref)

    if entity_view is None:
        return {"ok": False, "error": f"No entity found for '{ref}'"}

    return {"ok": True, "entity_view": asdict(entity_view)}


@mcp.tool
def update_entity(
    ref: str,
    fields: dict[str, Any] | None = None,
    body: str | None = None,
    append_body: bool = False,
) -> dict[str, Any]:
    """Patch an entity's frontmatter fields and/or replace or append its body."""
    vault = _vault()
    schema = load_schema(vault)
    try:
        entity = entities.update_entity(vault, schema, ref, fields, body, append_body)
    except entities.EntityError as exc:
        return _err(exc)
    return {"ok": True, "entity": asdict(entity)}


@mcp.tool
def rename_entity(ref: str, new_name: str) -> dict[str, Any]:
    """Rename an entity and repair inbound wikilinks across the vault."""
    vault = _vault()
    schema = load_schema(vault)
    try:
        entity = entities.rename_entity(vault, schema, ref, new_name)
    except entities.EntityError as exc:
        return _err(exc)
    return {"ok": True, "entity": asdict(entity)}


@mcp.tool
def delete_entity(ref: str, purge: bool = False) -> dict[str, Any]:
    """Delete an entity: soft-delete to _trash (default), or purge=True to strip typed refs."""
    vault = _vault()
    schema = load_schema(vault)
    try:
        touched = entities.delete_entity(vault, schema, ref, purge)
    except entities.EntityError as exc:
        return _err(exc)
    return {"ok": True, "touched": [str(p) for p in touched]}


@mcp.tool
def link(source_ref: str, rel_name: str, target_ref: str) -> dict[str, Any]:
    """Create a typed relationship (writes the inverse; auto-stubs a missing target)."""
    vault = _vault()
    schema = load_schema(vault)
    try:
        entities.link(vault, schema, source_ref, rel_name, target_ref)
    except entities.EntityError as exc:
        return _err(exc)
    return {"ok": True}


@mcp.tool
def unlink(source_ref: str, rel_name: str, target_ref: str) -> dict[str, Any]:
    """Remove a typed relationship from both sides; returns the notes that were touched."""
    vault = _vault()
    schema = load_schema(vault)
    try:
        touched = entities.unlink(vault, schema, source_ref, rel_name, target_ref)
    except entities.EntityError as exc:
        return _err(exc)
    return {"ok": True, "touched": [str(p) for p in touched]}


@mcp.tool
def query_entities(
    type: str | None = None,
    fields: dict[str, Any] | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Query entities by type, exact frontmatter field values, and/or tag."""
    results = entities.query_entities(_vault(), type, fields, tag)
    return {"ok": True, "entities": [asdict(e) for e in results]}


@mcp.tool
def search(query: str) -> dict[str, Any]:
    """Full-text (case-insensitive) search over entity names and bodies."""
    results = entities.search(_vault(), query)
    return {"ok": True, "entities": [asdict(e) for e in results]}


@mcp.tool
def validate(fix: bool = False, scope: str | None = None) -> dict[str, Any]:
    """Validate the vault. fix=True auto-heals safe issues; scope narrows to a type or entity."""
    vault = _vault()
    schema = load_schema(vault)
    issues = validate_core.validate(vault, schema, fix, scope)
    return {"ok": True, "issues": [asdict(i) for i in issues]}


@mcp.resource("worldbuild://schema")
def schema_resource() -> str:
    """The active vault schema as YAML: types, fields, relationships"""
    return (_vault() / ".worldbuild" / "schema.yaml").read_text(encoding="utf-8")


@mcp.resource("worldbuild://types")
def list_types() -> list[str]:
    """All entity type names defined by the schema."""
    return sorted(load_schema(_vault()).types.keys())


@mcp.resource("worldbuild://summary")
def world_summary() -> dict[str, Any]:
    """A count of entities in the vault, total and broken down by type."""
    index = scan_vault(_vault())
    by_type: dict[str, int] = {}
    for entity in index.entities.values():
        by_type[entity.type] = by_type.get(entity.type, 0) + 1
    return {"total": len(index.entities), "by_type": by_type}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
