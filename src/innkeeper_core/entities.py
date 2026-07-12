import re
import secrets
from pathlib import Path
from typing import Any

from innkeeper_core.index import VaultIndex, scan_vault
from innkeeper_core.models import Entity, EntityView
from innkeeper_core.schema import Schema
from innkeeper_core.vault import load_body_template, read_entity, write_entity


class EntityError(Exception):
    pass


class EntityExistsError(EntityError):
    def __init__(self, entity: Entity):
        self.entity = entity
        super().__init__(
            f"Entity '{entity.name}' already exists (uid: {entity.uid}). Cannot overwrite."
        )


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def mint_uid(type_name: str, name: str) -> str:
    return f"{type_name.lower()}_{slugify(name)}_{secrets.token_hex(2)}"


def create_entity(
    vault_path: Path,
    schema: Schema,
    type: str,
    name: str,
    fields: dict[str, Any] | None = None,
    body: str = "",
) -> Entity:
    type_spec = schema.get_type(type)

    if type_spec is None:
        raise EntityError(f"You can't create an entity of type {type}: Undefined")

    note_path = vault_path / type_spec.folder / f"{name}.md"

    if note_path.exists():
        raise EntityExistsError(read_entity(note_path))

    uid = mint_uid(type, name)

    body = body or load_body_template(vault_path, type)

    entity = Entity(uid=uid, type=type, name=name, frontmatter=dict(fields or {}), body=body)

    note_path.parent.mkdir(parents=True, exist_ok=True)
    write_entity(note_path, entity)

    return entity


def parse_wikilinks(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    titles: list[str] = []
    for item in value:
        titles.extend(re.findall(r"\[\[([^\]|]+)", item))
    return titles


def get_entity(vault_path: Path, schema: Schema, ref: str) -> EntityView | None:
    index = scan_vault(vault_path)
    entity = index.resolve(ref)

    if entity is None:
        return None

    type_spec = schema.get_type(entity.type)
    if type_spec is None:
        return None

    relationships: dict[str, list[Entity]] = {}
    for rel_name in type_spec.relationships:
        value = entity.frontmatter.get(rel_name)
        titles = parse_wikilinks(value)
        linked = [index.resolve(t) for t in titles]
        relationships[rel_name] = [e for e in linked if e is not None]

    backlinks = [
        other
        for other in index.entities.values()
        if other.uid != entity.uid and _links_to(index, schema, other, entity.uid)
    ]
    return EntityView(entity=entity, relationships=relationships, backlinks=backlinks)


def _links_to(index: VaultIndex, schema: Schema, source: Entity, target_uid: str) -> bool:
    spec = schema.get_type(source.type)
    if spec is None:
        return False
    for rel_name in spec.relationships:
        for title in parse_wikilinks(source.frontmatter.get(rel_name)):
            linked = index.resolve(title)
            if linked is not None and linked.uid == target_uid:
                return True
    return False


def update_entity(
    vault_path: Path,
    schema: Schema,
    ref: str,
    fields: dict[str, Any] | None = None,
    body: str | None = None,
    append_body: bool = False,
) -> Entity:
    index = scan_vault(vault_path)
    entity = index.resolve(ref)

    if entity is None:
        raise EntityError("Entity not found.")

    note_path = index.path_by_uid[entity.uid]

    if fields:
        entity.frontmatter.update(fields)

    if body is not None:
        if append_body:
            entity.body = f"{entity.body}\n\n{body}".strip("\n")
        else:
            entity.body = body.strip("\n")

    write_entity(note_path, entity)

    return entity


def rename_entity(vault_path: Path, schema: Schema, ref: str, new_name: str) -> Entity:
    def repl(m: re.Match[str]) -> str:
        return f"[[{new_name}{m.group(1) or ''}]]"

    index = scan_vault(vault_path)

    entity = index.resolve(ref)

    if entity is None:
        raise EntityError(f"Entity {ref} not found.")

    old_name = entity.name
    old_path = index.path_by_uid[entity.uid]

    new_path = old_path.with_name(f"{new_name}.md")

    if new_path.exists():
        raise EntityError(f"Path already exists: {new_path}")

    pattern = re.compile(r"\[\[" + re.escape(old_name) + r"(\|[^\]]*)?\]\]")

    for other in index.entities.values():
        new_fm = {k: _rewrite_links(v, pattern, new_name) for k, v in other.frontmatter.items()}
        new_body = pattern.sub(repl, other.body)

        if new_fm != other.frontmatter or new_body != other.body:
            other.frontmatter = new_fm
            other.body = new_body
            write_entity(index.path_by_uid[other.uid], other)

    old_path.rename(new_path)
    entity.name = new_name

    return entity


def _rewrite_links(value: Any, pattern: re.Pattern[str], new_name: str) -> Any:
    def repl(m: re.Match[str]) -> str:
        return f"[[{new_name}{m.group(1) or ''}]]"

    if isinstance(value, str):
        return pattern.sub(repl, value)
    if isinstance(value, list):
        return [pattern.sub(repl, v) if isinstance(v, str) else v for v in value]
    return value


def delete_entity(vault_path: Path, schema: Schema, ref: str, purge: bool = False) -> list[Path]:
    index = scan_vault(vault_path)

    entity = index.resolve(ref)

    if entity is None:
        raise EntityError(f"Entity {ref} not found.")

    note_path = index.path_by_uid[entity.uid]

    if not purge:
        trash = vault_path / "_trash"
        trash.mkdir(parents=True, exist_ok=True)

        note_path.rename(trash / f"{entity.uid}.md")

        return []
    else:
        touched: list[Path] = []
        pattern = re.compile(r"\[\[" + re.escape(entity.name) + r"(\|[^\]]*)?\]\]")

        for other in index.entities.values():
            if other.uid == entity.uid:
                continue
            spec = schema.get_type(other.type)
            if spec is None:
                continue

            changed = False
            for rel_name in spec.relationships:
                value = other.frontmatter.get(rel_name)
                if value is None:
                    continue
                if isinstance(value, str):
                    if pattern.search(value):
                        del other.frontmatter[rel_name]
                        changed = True
                if isinstance(value, list):
                    kept = [sub_value for sub_value in value if not pattern.search(sub_value)]
                    if len(kept) < len(value):
                        if kept:
                            other.frontmatter[rel_name] = kept
                        else:
                            del other.frontmatter[rel_name]
                        changed = True
            if changed:
                path = index.path_by_uid[other.uid]
                write_entity(path, other)
                touched.append(path)

        note_path.unlink()
        return touched


def _add_link(entity: Entity, slot: str, target_title: str, cardinality: str) -> None:
    token = f"[[{target_title}]]"
    if cardinality == "one":
        entity.frontmatter[slot] = token
    else:
        existing = entity.frontmatter.get(slot)
        items = existing if isinstance(existing, list) else ([existing] if existing else [])
        if token not in items:
            items.append(token)
        entity.frontmatter[slot] = items


def link(vault_path: Path, schema: Schema, source_ref: str, rel_name: str, target_ref: str) -> None:
    index = scan_vault(vault_path)

    source = index.resolve(source_ref)

    if source is None:
        raise EntityError(f"Source '{source_ref}' not found")

    source_spec = schema.get_type(source.type)
    if source_spec is None:
        raise EntityError(f"'{source.type}' isn't known for '{source_ref}'")

    rel = source_spec.relationships.get(rel_name)

    if rel is None:
        raise EntityError(
            f"'{source_ref}' has no relationship '{rel_name}'. {source.type} has "
            f"the following relationships: {list(source_spec.relationships.keys())}"
        )

    target = index.resolve(target_ref)

    if target is None:
        create_entity(vault_path, schema, rel.target, target_ref, {"status": "stub"})
        index = scan_vault(vault_path)
        source = index.resolve(source_ref)
        target = index.resolve(target_ref)

    if source is None or target is None:
        raise EntityError(f"Could not resolve after stubbing '{target_ref}'")

    if target.type != rel.target:
        raise EntityError(f"'{rel_name}' not associated with target type '{target.type}'")

    _add_link(source, rel_name, target.name, rel.cardinality)

    target_spec = schema.get_type(target.type)
    if target_spec is None:
        raise EntityError(f"'{target.type}' isn't known for '{target_ref}'")

    inv = target_spec.relationships[rel.inverse]
    _add_link(target, rel.inverse, source.name, inv.cardinality)

    write_entity(index.path_by_uid[source.uid], source)
    write_entity(index.path_by_uid[target.uid], target)


def _remove_link(entity: Entity, slot: str, target_title: str) -> bool:
    token = f"[[{target_title}]]"
    value = entity.frontmatter.get(slot)
    if value is None:
        return False
    if isinstance(value, list):
        kept = [v for v in value if v != token]
        if len(kept) == len(value):
            return False
        if kept:
            entity.frontmatter[slot] = kept
        else:
            del entity.frontmatter[slot]
        return True
    if value == token:
        del entity.frontmatter[slot]
        return True
    return False


def unlink(
    vault_path: Path, schema: Schema, source_ref: str, rel_name: str, target_ref: str
) -> list[Path]:
    index = scan_vault(vault_path)

    source = index.resolve(source_ref)

    if source is None:
        raise EntityError(f"Source '{source_ref}' not found")

    source_spec = schema.get_type(source.type)
    if source_spec is None:
        raise EntityError(f"'{source.type}' isn't known for '{source_ref}'")

    rel = source_spec.relationships.get(rel_name)

    if rel is None:
        raise EntityError(f"'{source_ref}' has no relationship '{rel_name}'")

    target = index.resolve(target_ref)

    if target is None:
        raise EntityError(f"Target '{target_ref}' not found")

    touched: list[Path] = []

    if _remove_link(source, rel_name, target.name):
        write_entity(index.path_by_uid[source.uid], source)
        touched.append(index.path_by_uid[source.uid])

    if _remove_link(target, rel.inverse, source.name):
        write_entity(index.path_by_uid[target.uid], target)
        touched.append(index.path_by_uid[target.uid])

    return touched


def query_entities(
    vault_path: Path,
    type: str | None = None,
    fields: dict[str, Any] | None = None,
    tag: str | None = None,
) -> list[Entity]:
    index = scan_vault(vault_path)

    keep = []
    for entity in index.entities.values():
        if type is not None and entity.type != type:
            continue
        if fields is not None and not all(
            entity.frontmatter.get(k) == v for k, v in fields.items()
        ):
            continue
        if tag is not None:
            tags = entity.frontmatter.get("tags") or []

            if isinstance(tags, str):
                tags = [tags]
            if tag not in tags:
                continue
        keep.append(entity)

    return sorted(keep, key=lambda e: e.name)


def search(vault_path: Path, query: str) -> list[Entity]:
    index = scan_vault(vault_path)

    q = query.lower()

    keep = [e for e in index.entities.values() if q in e.name.lower() or q in e.body.lower()]

    return sorted(keep, key=lambda e: e.name)
