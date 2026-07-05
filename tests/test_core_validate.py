from worldbuild_core.entities import create_entity, link
from worldbuild_core.validate import validate
from worldbuild_core.vault import build_schema, init_vault, load_schema, read_entity


def test_validate_clean_vault_no_error(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character")

    link(tmp_path, schema, "Character", "member_of", "Faction")

    assert len(validate(tmp_path, schema)) == 0


def test_validate_detects_dangling_link(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character", {"member_of": ["[[Unfound]]"]})

    assert any(i.code == "dangling_link" for i in validate(tmp_path, schema))


def test_validate_detects_wrong_target_type(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Location", "Location")
    create_entity(tmp_path, schema, "Character", "Character", {"member_of": ["[[Location]]"]})

    assert any(i.code == "wrong_target_type" for i in validate(tmp_path, schema))


def test_validate_detects_cardinality_violation(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Location", "A")
    create_entity(tmp_path, schema, "Location", "B")
    create_entity(tmp_path, schema, "Character", "Character", {"located_in": ["[[A]]", "[[B]]"]})

    assert any(i.code == "cardinality_violation" for i in validate(tmp_path, schema))


def test_validate_warns_stub(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character", {"status": "stub"})

    assert any(i.code == "stub" for i in validate(tmp_path, schema))


def test_validate_warns_missing_required(tmp_path):
    raw_schema = {
        "version": 1,
        "types": {"Character": {"folder": "Characters", "fields": {"required": ["summary"]}}},
    }

    schema = build_schema(raw_schema)

    create_entity(tmp_path, schema, "Character", "NoSummary")

    assert any(i.code == "missing_required" for i in validate(tmp_path, schema))


def test_validate_warns_missing_inverse(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character", {"member_of": ["[[Faction]]"]})

    assert any(i.code == "missing_inverse" for i in validate(tmp_path, schema))


def test_validate_fix_rebuilds_missing_inverse(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character", {"member_of": ["[[Faction]]"]})

    assert any(i.code == "missing_inverse" for i in validate(tmp_path, schema))

    validate(tmp_path, schema, fix=True)

    faction = read_entity(tmp_path / "Factions" / "Faction.md")
    assert faction.frontmatter["members"] == ["[[Character]]"]

    assert len(validate(tmp_path, schema)) == 0


def test_validate_flags_orphan(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")

    assert any(i.code == "orphan" for i in validate(tmp_path, schema))


def test_validate_fix_repoints_stale_link(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Faction")
    create_entity(tmp_path, schema, "Character", "Character", {"member_of": ["[[faction]]"]})

    assert any(i.code == "dangling_link" for i in validate(tmp_path, schema))

    validate(tmp_path, schema, fix=True)

    character = read_entity(tmp_path / "Characters" / "Character.md")

    assert character.frontmatter["member_of"] == ["[[Faction]]"]

    assert not any(i.code == "dangling_link" for i in validate(tmp_path, schema))


def test_validate_scope_by_type(tmp_path):
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "C", {"member_of": ["[[Ghost]]"]})

    assert any(i.code == "dangling_link" for i in validate(tmp_path, schema))
    assert len(validate(tmp_path, schema, scope="Faction")) == 0
    assert any(i.code == "dangling_link" for i in validate(tmp_path, schema, scope="Character"))
    assert any(i.code == "dangling_link" for i in validate(tmp_path, schema, scope="C"))
