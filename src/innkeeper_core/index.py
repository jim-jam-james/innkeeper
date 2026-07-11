from dataclasses import dataclass, field
from pathlib import Path

from innkeeper_core.models import Entity
from innkeeper_core.vault import read_entity


@dataclass
class VaultIndex:
    entities: dict[str, Entity] = field(default_factory=dict)
    path_by_uid: dict[str, Path] = field(default_factory=dict)
    uid_by_title: dict[str, str] = field(default_factory=dict)
    uid_by_alias: dict[str, str] = field(default_factory=dict)

    def resolve(self, ref: str) -> Entity | None:
        if ref in self.entities:
            return self.entities[ref]
        uid = self.uid_by_title.get(ref) or self.uid_by_alias.get(ref)
        return self.entities.get(uid) if uid is not None else None


def scan_vault(vault_path: Path) -> VaultIndex:
    index = VaultIndex()
    for md_path in vault_path.rglob("*.md"):
        rel_parts = md_path.relative_to(vault_path).parts
        if ".innkeeper" in rel_parts or "_trash" in rel_parts or ".obsidian" in rel_parts:
            continue

        try:
            entity = read_entity(md_path)
        except Exception:
            continue

        index.entities[entity.uid] = entity
        index.path_by_uid[entity.uid] = md_path
        index.uid_by_title[entity.name] = entity.uid
        aliases = entity.frontmatter.get("aliases")

        if aliases is None:
            aliases = []
        if isinstance(aliases, str):
            aliases = [aliases]

        for alias in aliases:
            index.uid_by_alias[alias] = entity.uid

    return index
