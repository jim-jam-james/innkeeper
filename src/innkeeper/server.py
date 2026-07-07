import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from innkeeper_core import entities
from innkeeper_core import validate as validate_core
from innkeeper_core.index import scan_vault
from innkeeper_core.vault import load_schema

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


@mcp.resource("innkeeper://schema")
def schema_resource() -> str:
    """The active vault schema as YAML: types, fields, relationships"""
    return (_vault() / ".innkeeper" / "schema.yaml").read_text(encoding="utf-8")


@mcp.resource("innkeeper://types")
def list_types() -> list[str]:
    """All entity type names defined by the schema."""
    return sorted(load_schema(_vault()).types.keys())


@mcp.resource("innkeeper://summary")
def world_summary() -> dict[str, Any]:
    """A count of entities in the vault, total and broken down by type."""
    index = scan_vault(_vault())
    by_type: dict[str, int] = {}
    for entity in index.entities.values():
        by_type[entity.type] = by_type.get(entity.type, 0) + 1
    return {"total": len(index.entities), "by_type": by_type}


@mcp.prompt
def flesh_out_entity(ref: str) -> str:
    """Expand a stub or thin entity into rich detail, respecting the schema."""
    vault = _vault()
    schema = load_schema(vault)
    view = entities.get_entity(vault, schema, ref)

    if view is None:
        return f"No entity named '{ref}' exists yet. Create it first then try again."

    entity = view.entity
    type_spec = schema.get_type(entity.type)
    rels = ", ".join(type_spec.relationships) if type_spec else ""

    return (
        f"Flesh out the {entity.type} '{entity.name}' in my worldbuilding vault.\n\n"
        f"Current frontmatter: {entity.frontmatter}\n"
        f"Current body: {entity.body or '(empty)'}\n\n"
        f"Available typed relationships for a {entity.type}: {rels}\n\n"
        "Write an evocative body associated with the entity type, and use the Innkeeper "
        "tools to add fitting frontmatter fields and typed relationships. Only use "
        "relationships from the list above and respect the existing schema and world."
    )


@mcp.prompt
def brainstorm(type: str) -> str:
    """Brainstorm new entities of a given type that fill gaps in the existing world."""
    vault = _vault()
    schema = load_schema(vault)

    type_spec = schema.get_type(type)

    if type_spec is None:
        return f"Entity type '{type}' doesn't exist. Create it or change entity type."

    return (
        f"{type} schema:\n{type_spec.__dict__}\n\n"
        f"Based on the entity type counts:\n{world_summary()}\n\n"
        f"Brainstorm new {type} entities to fill in any gaps of that type found within the "
        "user's world."
    )


@mcp.prompt
def suggest_connections(ref: str) -> str:
    """Propose new typed relationships from an entity to others in the world."""
    vault = _vault()
    schema = load_schema(vault)

    view = entities.get_entity(vault, schema, ref)

    if view is None:
        return f"No entity named '{ref}' exists yet. Create it first then try again."

    entity = view.entity
    type_spec = schema.get_type(entity.type)
    rels = ", ".join(type_spec.relationships) if type_spec else ""
    all_entities = {e.name: e.type for e in entities.query_entities(vault) if e.uid != entity.uid}

    return (
        f"Entity Information:\n{entity}\n\n"
        f"Entity Relationship Types: {rels}\n\n"
        f"Other Entities:\n{all_entities}\n\n"
        "Given the supplied entity, propose *new* relationships to other"
        " entities, where a relationship is not already formed."
    )


@mcp.prompt
def consistency_review(scope: str | None = None) -> str:
    """Review the world's validation issues and suggest narrative fixes."""
    vault = _vault()
    schema = load_schema(vault)

    issues = validate_core.validate(vault, schema, fix=False, scope=scope)

    if len(issues) == 0:
        return "No issues found."

    issue_dicts = [issue.__dict__ for issue in issues]

    return (
        f"List of Issues:\n{issue_dicts}\n\n"
        "Given the list of issues in the world, provide narrative"
        " fixes that go beyond the basic suggestion. For each issue, "
        "respond sequentially, each issue being addresed seperately unless"
        " directly tied together."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
