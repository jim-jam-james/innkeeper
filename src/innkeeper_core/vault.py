from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from innkeeper_core.models import Entity
from innkeeper_core.schema import Schema, build_schema


def default_schema_text() -> str:
    return files("innkeeper_core").joinpath("default_schema.yaml").read_text(encoding="utf-8")


def init_vault(path: Path) -> None:
    schema_text = default_schema_text()
    schema = build_schema(yaml.safe_load(schema_text))

    innkeeper_dir = path / ".innkeeper"
    schema_file = innkeeper_dir / "schema.yaml"
    if schema_file.exists():
        raise FileExistsError(f"Vault already initialized: {schema_file}")

    innkeeper_dir.mkdir(parents=True, exist_ok=True)
    schema_file.write_text(schema_text, encoding="utf-8")

    for type_spec in schema.types.values():
        (path / type_spec.folder).mkdir(parents=True, exist_ok=True)


def serialize_entity(entity: Entity) -> str:
    fm = {"type": entity.type, "uid": entity.uid, **entity.frontmatter}
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    return f"---\n{fm_text}---\n\n{entity.body}".rstrip() + "\n"


def parse_entity(text: str, name: str) -> Entity:
    _, fm_text, body = text.split("---", 2)
    fm: dict[str, Any] = yaml.safe_load(fm_text) or {}
    type_ = fm.pop("type")
    uid = fm.pop("uid")
    return Entity(uid=uid, type=type_, name=name, frontmatter=fm, body=body.strip("\n"))


def read_entity(path: Path) -> Entity:
    text = path.read_text(encoding="utf-8")
    return parse_entity(text, name=path.stem)


def write_entity(path: Path, entity: Entity) -> None:
    text = serialize_entity(entity)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_schema(vault_path: Path) -> Schema:
    text = (vault_path / ".innkeeper" / "schema.yaml").read_text(encoding="utf-8")
    return build_schema(yaml.safe_load(text))


def load_body_template(vault_path: Path, type_name: str) -> str:
    path = vault_path / ".innkeeper" / "templates" / f"{type_name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""
