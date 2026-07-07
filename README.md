# Innkeeper

[![CI](https://github.com/jim-jam-james/innkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/jim-jam-james/innkeeper/actions/workflows/ci.yml)

A schema-driven [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that turns an
Obsidian vault into a queryable, self-validating worldbuilding database for TTRPGs (D&D), game
settings, and novels.

The MCP server is a thin protocol adapter over a standalone, independently-tested domain core
(`innkeeper_core`). Core invariants: **the server verifies, the LLM creates; the core never imports
the protocol; non-destructive by default; the schema is the single source of truth.**

> 🚧 **Status:** early development. See [`PROJECT_PLAN.md`](./PROJECT_PLAN.md) for the full design and
> phased roadmap.

## License

MIT
