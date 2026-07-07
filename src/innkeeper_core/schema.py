from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class RelationshipSpec:
    name: str
    target: str
    cardinality: Literal["one", "many"]
    inverse: str
    derived: bool = False


@dataclass
class TypeSpec:
    name: str
    folder: str
    hierarchical: bool = False
    required: set[str] = field(default_factory=set)
    optional: set[str] = field(default_factory=set)
    relationships: dict[str, RelationshipSpec] = field(default_factory=dict)


@dataclass
class Schema:
    version: int
    types: dict[str, TypeSpec] = field(default_factory=dict)

    def get_type(self, name: str) -> TypeSpec | None:
        return self.types.get(name)


class SchemaError(Exception):
    pass


def build_schema(raw: dict[str, Any]) -> Schema:
    if "version" not in raw or not isinstance(raw["version"], int):
        raise SchemaError("Version is missing or a non-int.")

    version = raw["version"]

    if "types" not in raw or not isinstance(raw["types"], dict):
        raise SchemaError("Types missing or non-dict.")

    types: dict[str, TypeSpec] = {}
    for type_name, type_def in raw["types"].items():
        folder = type_def.get("folder", type_name)
        hierarchical = type_def.get("hierarchical", False)

        fields = type_def.get("fields", {})
        required_list = fields.get("required", [])
        optional_list = fields.get("optional", [])

        required = {"name"} | set(required_list)
        optional = set(optional_list)

        relationships: dict[str, RelationshipSpec] = {}
        rel_defs = type_def.get("relationships", {})
        for rel_name, rel_def in rel_defs.items():
            relationships[rel_name] = RelationshipSpec(
                name=rel_name,
                inverse=rel_def["inverse"],
                target=rel_def["target"],
                cardinality=rel_def["cardinality"],
                derived=False,
            )

        types[type_name] = TypeSpec(
            name=type_name,
            folder=folder,
            hierarchical=hierarchical,
            required=required,
            optional=optional,
            relationships=relationships,
        )

    for source_name, source_spec in types.items():
        for rel in list(source_spec.relationships.values()):
            if rel.derived:
                continue
            target_spec = types.get(rel.target)
            if target_spec is None:
                raise SchemaError(f"{source_name}.{rel.name} targets unknown type '{rel.target}'")
            inverse_spec = RelationshipSpec(
                name=rel.inverse,
                target=source_name,
                inverse=rel.name,
                cardinality="many",
                derived=True,
            )

            if rel.inverse in target_spec.relationships:
                raise SchemaError(f"Name is already used on {target_spec.name}")
            target_spec.relationships[rel.inverse] = inverse_spec

    return Schema(version=version, types=types)
