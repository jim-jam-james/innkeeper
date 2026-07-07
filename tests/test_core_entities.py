import pytest

from innkeeper_core.entities import (
    EntityError,
    create_entity,
    delete_entity,
    get_entity,
    link,
    mint_uid,
    query_entities,
    rename_entity,
    search,
    slugify,
    unlink,
    update_entity,
)
from innkeeper_core.index import scan_vault
from innkeeper_core.models import Entity
from innkeeper_core.vault import (
    init_vault,
    load_schema,
    parse_entity,
    read_entity,
    serialize_entity,
)


def test_slugify():
    assert slugify("James") == "james"
    assert slugify("Aldric the Gray") == "aldric_the_gray"
    assert slugify("K'sh'tal") == "k_sh_tal"


def test_mint_uid():
    assert mint_uid("Character", "James").startswith("character_")
    assert mint_uid("Faction", "The Graybeards").startswith("faction_")
    assert mint_uid("Character", "Sauron") != mint_uid("Character", "Sauron")


def test_build_entity():
    entity = Entity(mint_uid("Character", "Mario"), "Character", "Mario", {}, "")

    assert entity.uid is not None
    assert entity.type == "Character"
    assert entity.name == "Mario"
    assert entity.frontmatter is not None
    assert entity.body is not None


def test_entity_round_trip():
    entity = Entity(
        uid=mint_uid("Character", "Name"),
        type="Character",
        name="Name",
        frontmatter={
            "aliases": "[An Alias]",
            "member_of": ["[[Faction]]"],
            "located_in": "[[Location]]",
        },
        body="Body",
    )

    serial = serialize_entity(entity)
    parsed = parse_entity(serial, "Name")

    assert entity.uid == parsed.uid
    assert entity.type == parsed.type
    assert entity.name == parsed.name
    assert entity.frontmatter == parsed.frontmatter
    assert entity.body == parsed.body


def test_get_entity_resolves_relationships(tmp_path):
    init_vault(tmp_path)

    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(
        vault_path=tmp_path,
        schema=schema,
        type="Character",
        name="Character",
        fields={"member_of": ["[[Faction]]"]},
    )

    view = get_entity(tmp_path, schema, "Character")

    assert view is not None
    assert view.entity.name == "Character"
    assert isinstance(view.relationships["member_of"], list)
    assert len(view.relationships["member_of"]) == 1
    assert view.relationships["member_of"][0].name == "Faction"


def test_get_entity_missing_returns_none(tmp_path):
    init_vault(tmp_path)

    schema = load_schema(tmp_path)

    assert get_entity(tmp_path, schema, "Unknown") is None


def test_get_entity_backlinks(tmp_path):
    init_vault(tmp_path)

    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(
        vault_path=tmp_path,
        schema=schema,
        type="Character",
        name="Character",
        fields={"member_of": ["[[Faction]]"]},
    )

    view = get_entity(tmp_path, schema, "Faction")

    assert len(view.backlinks) == 1
    assert view.backlinks[0].name == "Character"


def test_update_patches_fields_and_appends_body(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    entity = create_entity(
        vault_path=tmp_path,
        schema=schema,
        type="Character",
        name="Character",
        fields={"status": "active"},
        body="First.",
    )

    updated = update_entity(
        vault_path=tmp_path,
        schema=schema,
        ref="Character",
        fields={"status": "dead", "alignment": "LG"},
        body="Second.",
        append_body=True,
    )

    assert entity.frontmatter["status"] == "active" and updated.frontmatter["status"] == "dead"
    assert updated.frontmatter["alignment"] == "LG"
    assert "First." in updated.body and "Second." in updated.body


def test_update_replaces_body(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    entity = create_entity(
        vault_path=tmp_path,
        schema=schema,
        type="Character",
        name="Character",
        fields={},
        body="First.",
    )

    updated = update_entity(
        vault_path=tmp_path, schema=schema, ref="Character", fields={}, body="Second."
    )

    assert "First." in entity.body and "Second." in updated.body and "First." not in updated.body


def test_update_missing_raises(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    with pytest.raises(EntityError):
        update_entity(vault_path=tmp_path, schema=schema, ref="Unfound", fields={}, body="")


def test_rename_repairs_link(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Old")
    create_entity(tmp_path, schema, "Character", "Member", {"member_of": ["[[Old]]"]})

    rename_entity(tmp_path, schema, "Old", "New")

    member = read_entity(tmp_path / "Characters" / "Member.md")
    assert member.frontmatter["member_of"] == ["[[New]]"]


def test_rename_preserves_display(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Old")
    create_entity(tmp_path, schema, "Character", "Member", {"member_of": ["[[Old|Name of Old]]"]})

    rename_entity(tmp_path, schema, "Old", "New")

    member = read_entity(tmp_path / "Characters" / "Member.md")
    assert member.frontmatter["member_of"] == ["[[New|Name of Old]]"]


def test_rename_no_clobber(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Old")
    create_entity(tmp_path, schema, "Character", "New")

    with pytest.raises(EntityError):
        rename_entity(tmp_path, schema, "Old", "New")


def test_rename_missing_raises(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    with pytest.raises(EntityError):
        rename_entity(tmp_path, schema, "Unfound", "New")


def test_delete_soft_moves_to_trash(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    entity = create_entity(tmp_path, schema, "Character", "Name")

    delete_entity(tmp_path, schema, "Name")

    assert (tmp_path / "Characters" / f"{entity.name}.md").exists() is False
    assert (tmp_path / "_trash" / f"{entity.uid}.md").exists()
    assert scan_vault(tmp_path).resolve("Name") is None


def test_delete_missing_raises(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    with pytest.raises(EntityError):
        delete_entity(tmp_path, schema, "Unfound")


def test_purge_strips_typed_reference(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    entity = create_entity(tmp_path, schema, "Faction", "Old")
    create_entity(tmp_path, schema, "Character", "Member", {"member_of": ["[[Old]]"]})

    touched = delete_entity(tmp_path, schema, "Old", purge=True)

    assert (tmp_path / "Factions" / f"{entity.name}.md").exists() is False

    member = read_entity(tmp_path / "Characters" / "Member.md")

    assert "member_of" not in member.frontmatter
    assert (tmp_path / "Characters" / "Member.md") in touched


def test_purge_removes_one_of_many(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Old")
    create_entity(tmp_path, schema, "Faction", "Keep")
    create_entity(tmp_path, schema, "Character", "Member", {"member_of": ["[[Old]]", "[[Keep]]"]})

    touched = delete_entity(tmp_path, schema, "Old", purge=True)

    member = read_entity(tmp_path / "Characters" / "Member.md")

    assert "member_of" in member.frontmatter
    assert member.frontmatter["member_of"] == ["[[Keep]]"]
    assert (tmp_path / "Characters" / "Member.md") in touched


def test_purge_leaves_body_dangling(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Old")
    create_entity(tmp_path, schema, "Character", "Member", {}, "Member of [[Old]].")

    delete_entity(tmp_path, schema, "Old", purge=True)

    member = read_entity(tmp_path / "Characters" / "Member.md")

    assert "[[Old]]" in member.body


def test_link_writes_both_sides(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character")

    link(tmp_path, schema, "Character", "member_of", "Faction")

    character = read_entity(tmp_path / "Characters" / "Character.md")
    faction = read_entity(tmp_path / "Factions" / "Faction.md")

    assert character.frontmatter["member_of"] == ["[[Faction]]"]
    assert faction.frontmatter["members"] == ["[[Character]]"]


def test_link_is_idempotent(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character")

    link(tmp_path, schema, "Character", "member_of", "Faction")
    link(tmp_path, schema, "Character", "member_of", "Faction")

    character = read_entity(tmp_path / "Characters" / "Character.md")
    faction = read_entity(tmp_path / "Factions" / "Faction.md")

    assert character.frontmatter["member_of"] == ["[[Faction]]"]
    assert faction.frontmatter["members"] == ["[[Character]]"]


def test_link_unknown_relationship_raises(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character")

    with pytest.raises(EntityError):
        link(tmp_path, schema, "Character", "leader_of", "Faction")


def test_link_wrong_target_type_raises(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Event", "Event")
    create_entity(tmp_path, schema, "Character", "Character")

    with pytest.raises(EntityError):
        link(tmp_path, schema, "Character", "member_of", "Event")


def test_link_auto_stubs_missing_target(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character")

    link(tmp_path, schema, "Character", "member_of", "Faction")

    assert (tmp_path / "Factions" / "Faction.md").exists()

    faction = read_entity(tmp_path / "Factions" / "Faction.md")

    assert faction.frontmatter["status"] == "stub"
    assert faction.type == "Faction"

    character = read_entity(tmp_path / "Characters" / "Character.md")

    assert character.frontmatter["member_of"] == ["[[Faction]]"]
    assert faction.frontmatter["members"] == ["[[Character]]"]


def test_unlink_removes_both_sides(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character")

    link(tmp_path, schema, "Character", "member_of", "Faction")
    report = unlink(tmp_path, schema, "Character", "member_of", "Faction")

    character = read_entity(tmp_path / "Characters" / "Character.md")
    faction = read_entity(tmp_path / "Factions" / "Faction.md")

    assert "members_of" not in character.frontmatter
    assert "members" not in faction.frontmatter

    assert (tmp_path / "Characters" / "Character.md") in report
    assert (tmp_path / "Factions" / "Faction.md") in report


def test_unlink_leaves_other_links(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "A")
    create_entity(tmp_path, schema, "Faction", "B")
    create_entity(tmp_path, schema, "Character", "Character")

    link(tmp_path, schema, "Character", "member_of", "A")
    link(tmp_path, schema, "Character", "member_of", "B")

    unlink(tmp_path, schema, "Character", "member_of", "B")

    character = read_entity(tmp_path / "Characters" / "Character.md")
    assert character.frontmatter["member_of"] == ["[[A]]"]


def test_unlink_unknown_relationship_raises(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character")

    with pytest.raises(EntityError):
        link(tmp_path, schema, "Character", "leader_of", "Faction")


def test_query_by_type(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character1")
    create_entity(tmp_path, schema, "Character", "Character2")
    create_entity(tmp_path, schema, "Faction", "Faction")

    assert len(query_entities(tmp_path, "Character")) == 2


def test_query_by_field(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character1", {"status": "active"})
    create_entity(tmp_path, schema, "Character", "Character2", {"status": "dead"})

    assert len(query_entities(tmp_path, None, {"status": "active"})) == 1


def test_query_by_tag(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character1", {"tags": ["villain"]})
    create_entity(tmp_path, schema, "Character", "Character2")

    assert len(query_entities(tmp_path, None, None, "villain")) == 1


def test_query_no_filter_returns_all(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character1")
    create_entity(tmp_path, schema, "Character", "Character2")

    assert len(query_entities(tmp_path)) == 2


def test_search_matches_body_case_insensitive(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character1", {}, "Puff the Magic Dragon.")
    create_entity(tmp_path, schema, "Character", "Character2")

    assert len(search(tmp_path, "dragon")) == 1


def test_Search_no_match_returns_empty(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character1")
    create_entity(tmp_path, schema, "Character", "Character2")

    assert len(search(tmp_path, "dragon")) == 0
