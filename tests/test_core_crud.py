import pytest

from worldbuild_core.entities import EntityError, create_entity
from worldbuild_core.vault import init_vault, load_schema, read_entity


def test_create_entity(tmp_path):
    init_vault(tmp_path)

    schema = load_schema(tmp_path)

    create_entity(
        vault_path=tmp_path,
        schema=schema,
        type="Character",
        name="Character",
        fields={"status": "active"},
        body="Example body.",
    )

    assert (tmp_path / "Characters" / "Character.md").exists()

    entity = read_entity(tmp_path / "Characters" / "Character.md")

    assert entity.type == "Character"
    assert entity.name == "Character"
    assert entity.frontmatter["status"] == "active"
    assert entity.uid.startswith("character_")


def test_create_unknown_type_rejected(tmp_path):
    init_vault(tmp_path)

    schema = load_schema(tmp_path)

    with pytest.raises(EntityError):
        create_entity(
            vault_path=tmp_path,
            schema=schema,
            type="Religion",
            name="Religion",
            fields={},
            body="Body",
        )


def test_create_no_clobber(tmp_path):
    init_vault(tmp_path)

    schema = load_schema(tmp_path)

    create_entity(
        vault_path=tmp_path,
        schema=schema,
        type="Character",
        name="Character",
        fields={},
        body="Body",
    )

    with pytest.raises(EntityError):
        create_entity(
            vault_path=tmp_path,
            schema=schema,
            type="Character",
            name="Character",
            fields={},
            body="Different body",
        )
