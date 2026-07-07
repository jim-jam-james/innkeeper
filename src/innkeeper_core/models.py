from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    uid: str
    type: str
    name: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""


@dataclass
class EntityView:
    entity: Entity
    relationships: dict[str, list[Entity]]
    backlinks: list[Entity] = field(default_factory=list)
