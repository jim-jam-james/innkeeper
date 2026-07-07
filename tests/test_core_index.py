from innkeeper_core.entities import mint_uid
from innkeeper_core.index import scan_vault
from innkeeper_core.models import Entity
from innkeeper_core.vault import init_vault, write_entity


def test_vault_index(tmp_path):
    init_vault(tmp_path)

    char1 = Entity(
        uid=mint_uid("Character", "Name"),
        type="Character",
        name="Name",
        frontmatter={"aliases": ["Alias"]},
        body="",
    )

    char2 = Entity(
        uid=mint_uid("Character", "Name2"),
        type="Character",
        name="Name2",
        frontmatter={"aliases": ["Alias2"]},
        body="",
    )

    faction = Entity(
        uid=mint_uid("Faction", "Faction"), type="Faction", name="Faction", frontmatter={}, body=""
    )
    write_entity(tmp_path / "Characters" / "Name.md", char1)
    write_entity(tmp_path / "Characters" / "Name2.md", char2)
    write_entity(tmp_path / "Factions" / "Faction.md", faction)

    index = scan_vault(tmp_path)

    assert char1 == index.resolve(char1.uid)
    assert char2 == index.resolve(char2.name)
    assert char1 == index.resolve("Alias")
    assert index.resolve("Nonexistent") is None


def test_resolve_survives_rename(tmp_path):
    init_vault(tmp_path)

    entity = Entity(
        uid=mint_uid("Character", "Character"),
        type="Character",
        name="Character",
        frontmatter={},
        body="",
    )

    write_entity(tmp_path / "Characters" / "Character.md", entity=entity)

    index = scan_vault(tmp_path)

    assert entity == index.resolve(entity.uid)
    assert entity == index.resolve("Character")

    (tmp_path / "Characters" / "Character.md").rename(tmp_path / "Characters" / "Renamed.md")

    index = scan_vault(tmp_path)

    assert entity.uid == index.resolve(entity.uid).uid
    assert entity.uid == index.resolve("Renamed").uid
    assert index.resolve("Character") is None
