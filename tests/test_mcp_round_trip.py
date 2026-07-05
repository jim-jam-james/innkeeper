import asyncio

from fastmcp import Client

from worldbuild_core.entities import create_entity
from worldbuild_core.vault import init_vault, load_schema
from worldbuild_mcp.server import mcp


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
        "worldbuild://schema",
        "worldbuild://types",
        "worldbuild://summary",
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
