import asyncio

import pytest
from fastmcp import Client

from innkeeper.server import mcp
from innkeeper_core.entities import create_entity
from innkeeper_core.vault import init_vault, load_schema


def test_create_entity_tool_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool(
                "create_entity", {"type": "Character", "name": "Character"}
            )

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    print(result.data)
    assert result.data["entity"]["name"] == "Character"


def test_get_entity_tool_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character")

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("get_entity", {"ref": "Character"})

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    assert result.data["entity_view"]["entity"]["name"] == "Character"


def test_all_tools_and_resources_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)

    async def scenario():
        async with Client(mcp) as client:
            tools = {t.name for t in await client.list_tools()}
            resources = {str(r.uri) for r in await client.list_resources()}
            return tools, resources

    tools, resources = asyncio.run(scenario())
    assert {
        "create_entity",
        "get_entity",
        "update_entity",
        "rename_entity",
        "delete_entity",
        "link",
        "unlink",
        "query_entities",
        "search",
        "validate",
    } <= tools
    assert {
        "innkeeper://schema",
        "innkeeper://types",
        "innkeeper://summary",
    } <= resources


def test_delete_tool_returns_touched_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    create_entity(tmp_path, schema, "Character", "Doomed")

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("delete_entity", {"ref": "Doomed"})

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    assert isinstance(result.data["touched"], list)  # Path list serialized to strings


def test_link_then_get_shows_relationship(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    create_entity(tmp_path, schema, "Faction", "Guild")
    create_entity(tmp_path, schema, "Character", "Member")

    async def scenario():
        async with Client(mcp) as client:
            await client.call_tool(
                "link", {"source_ref": "Member", "rel_name": "member_of", "target_ref": "Guild"}
            )
            return await client.call_tool("get_entity", {"ref": "Member"})

    result = asyncio.run(scenario())
    members = result.data["entity_view"]["relationships"]["member_of"]
    assert members[0]["name"] == "Guild"


def test_validate_tool_returns_issues(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    create_entity(tmp_path, schema, "Character", "C", {"member_of": ["[[Ghost]]"]})

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("validate", {})

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    assert any(i["code"] == "dangling_link" for i in result.data["issues"])


def test_query_tool_filters_by_type(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    create_entity(tmp_path, schema, "Character", "A")
    create_entity(tmp_path, schema, "Faction", "B")

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("query_entities", {"type": "Character"})

    result = asyncio.run(scenario())
    names = {e["name"] for e in result.data["entities"]}
    assert names == {"A"}


def test_query_omits_body_by_default_and_expands(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    create_entity(tmp_path, schema, "Character", "Aldric", body="A long and costly body.")

    async def scenario():
        async with Client(mcp) as client:
            summary = await client.call_tool("query_entities", {"type": "Character"})
            expanded = await client.call_tool(
                "query_entities", {"type": "Character", "expand": True}
            )
            return summary, expanded

    summary, expanded = asyncio.run(scenario())

    summary_entity = summary.data["entities"][0]
    assert "body" not in summary_entity  # default trims the expensive field
    assert summary_entity["name"] == "Aldric"  # cheap fields still present

    expanded_entity = expanded.data["entities"][0]
    assert expanded_entity["body"] == "A long and costly body."  # expand restores it


def test_get_entity_thins_neighbors_by_default_and_expands(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    create_entity(tmp_path, schema, "Character", "Member")
    create_entity(tmp_path, schema, "Faction", "Guild", body="The guild's storied history.")

    async def scenario():
        async with Client(mcp) as client:
            await client.call_tool(
                "link", {"source_ref": "Member", "rel_name": "member_of", "target_ref": "Guild"}
            )
            summary = await client.call_tool("get_entity", {"ref": "Member"})
            expanded = await client.call_tool("get_entity", {"ref": "Member", "expand": True})
            return summary, expanded

    summary, expanded = asyncio.run(scenario())

    # Focal entity is always full; its neighbors are thinned by default.
    summary_guild = summary.data["entity_view"]["relationships"]["member_of"][0]
    assert summary_guild["name"] == "Guild"
    assert "body" not in summary_guild

    expanded_guild = expanded.data["entity_view"]["relationships"]["member_of"][0]
    assert expanded_guild["body"] == "The guild's storied history."


def test_create_duplicate_without_flag_reports_uid(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    original = create_entity(tmp_path, schema, "Character", "Aldric")

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("create_entity", {"type": "Character", "name": "Aldric"})

    result = asyncio.run(scenario())
    assert result.data["ok"] is False
    assert result.data["uid"] == original.uid  # agent can confirm the earlier write landed


def test_create_if_not_exists_returns_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    original = create_entity(tmp_path, schema, "Character", "Aldric")

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool(
                "create_entity",
                {"type": "Character", "name": "Aldric", "if_not_exists": True},
            )

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    assert result.data["created"] is False  # found the existing one, didn't write
    assert result.data["entity"]["uid"] == original.uid


def test_create_fresh_reports_created_true(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("create_entity", {"type": "Character", "name": "Aldric"})

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    assert result.data["created"] is True


def test_create_entities_bulk_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)

    items = [
        {"type": "Character", "name": "Aldric"},
        {"type": "Faction", "name": "Ravens"},
        {"type": "Location", "name": "Thornwick"},
    ]

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("create_entities", {"entities_in": items})

    result = asyncio.run(scenario())
    assert result.data["ok"] is True
    assert result.data["created_count"] == 3
    assert result.data["total"] == 3
    assert all(r["ok"] and r["created"] for r in result.data["results"])
    # All three were actually written to disk, not just reported.
    assert (tmp_path / "Characters" / "Aldric.md").exists()
    assert (tmp_path / "Factions" / "Ravens.md").exists()
    assert (tmp_path / "Locations" / "Thornwick.md").exists()


def test_create_entities_partial_failure_is_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)
    existing = create_entity(tmp_path, schema, "Character", "Aldric")  # pre-exists -> dup

    items = [
        {"type": "Character", "name": "Aldric"},  # duplicate, no flag -> fails
        {"type": "Faction", "name": "Ravens"},  # valid -> should still land
    ]

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("create_entities", {"entities_in": items})

    result = asyncio.run(scenario())
    assert result.data["ok"] is True  # the batch ran
    by_name = {r["name"]: r for r in result.data["results"]}
    assert by_name["Aldric"]["ok"] is False
    assert by_name["Aldric"]["uid"] == existing.uid  # dup surfaces the existing uid
    assert by_name["Ravens"]["ok"] is True  # one bad item didn't sink the rest
    assert (tmp_path / "Factions" / "Ravens.md").exists()


def test_create_entities_idempotent_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)

    items = [
        {"type": "Character", "name": "Aldric"},
        {"type": "Faction", "name": "Ravens"},
    ]

    async def scenario():
        async with Client(mcp) as client:
            first = await client.call_tool(
                "create_entities", {"entities_in": items, "if_not_exists": True}
            )
            second = await client.call_tool(
                "create_entities", {"entities_in": items, "if_not_exists": True}
            )
            return first, second

    first, second = asyncio.run(scenario())
    assert all(r["created"] for r in first.data["results"])  # first run wrote them
    assert all(not r["created"] for r in second.data["results"])  # retry created nothing
    assert all(r["ok"] for r in second.data["results"])  # and reported no errors
    # uids are stable across the retry
    first_uids = {r["name"]: r["uid"] for r in first.data["results"]}
    second_uids = {r["name"]: r["uid"] for r in second.data["results"]}
    assert first_uids == second_uids


def test_get_schema_loads_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)

    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("get_schema")

    result = asyncio.run(scenario())
    assert result.data == (tmp_path / ".innkeeper" / "schema.yaml").read_text(encoding="utf-8")


def test_flesh_out_entity_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Aldric", {"status": "stub"})

    async def scenario():
        async with Client(mcp) as client:
            return await client.get_prompt("flesh_out_entity", {"ref": "Aldric"})

    result = asyncio.run(scenario())
    text = result.messages[0].content.text
    assert "Aldric" in text
    assert "member_of" in text


def test_brainstorm_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Faction", "Nightwatch")
    create_entity(tmp_path, schema, "Faction", "The Guard")
    create_entity(tmp_path, schema, "Faction", "Red Barons")
    create_entity(tmp_path, schema, "Character", "Ulric")

    async def scenario():
        async with Client(mcp) as client:
            return await client.get_prompt("brainstorm", {"type": "Character"})

    result = asyncio.run(scenario())
    text = result.messages[0].content.text
    assert "Faction" in text


def test_suggest_connections_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Aldric")
    create_entity(tmp_path, schema, "Faction", "Ravens")

    async def scenario():
        async with Client(mcp) as client:
            return await client.get_prompt("suggest_connections", {"ref": "Aldric"})

    result = asyncio.run(scenario())
    text = result.messages[0].content.text
    assert "Aldric" in text
    assert "Ravens" in text
    assert "member_of" in text


def test_consistency_review(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    init_vault(tmp_path)
    schema = load_schema(tmp_path)

    create_entity(tmp_path, schema, "Character", "Character", {"member_of": ["[[Unfound]]"]})

    async def scenario():
        async with Client(mcp) as client:
            return await client.get_prompt("consistency_review", {"scope": None})

    result = asyncio.run(scenario())
    text = result.messages[0].content.text
    assert "Unfound" in text
    assert "dangling_link" in text


def test_init_command_scaffolds_vault(tmp_path):
    from innkeeper.server import main

    main(["init", "--vault", str(tmp_path)])
    assert (tmp_path / ".innkeeper" / "schema.yaml").exists()


def test_init_command_refuses_existing_vault(tmp_path):
    from innkeeper.server import main

    main(["init", "--vault", str(tmp_path)])  # first init succeeds
    with pytest.raises(SystemExit):
        main(["init", "--vault", str(tmp_path)])  # second must exit, not run the server
