# Worldbuild MCP — Project Plan

> A schema-driven **Model Context Protocol (MCP) server** that turns an Obsidian vault into a
> queryable, self-validating worldbuilding database for TTRPGs (D&D), game settings, and novels.
> The MCP server is a thin protocol adapter over a standalone, independently-tested domain core.

This document is the single source of truth for the build. It records every locked design decision
(with rationale) and lays out a phased roadmap you can work through and check off. Build order is
deliberate: you implement the **entire world engine as plain Python first**, then learn and add the
**MCP layer last**, in isolation, as a near-trivial wrapper.

---

## 1. Goals & Non-Goals

**Primary goals (co-equal):**
- **Portfolio-grade.** Clean architecture, real tests, CI, a finished and documented public repo that
  demonstrates LLM/agentic engineering. Resume-legible.
- **Genuinely useful daily-driver.** A tool you actually use to build and maintain real worlds.

**Non-goals for v1 (deliberately deferred):**
- History / quest-line simulation (Phase 2 — seams reserved, no sim code in v1).
- Live Obsidian-app integration (REST/plugin) — filesystem-only for now.
- A CLI front-end, multi-vault-in-one-process, persistent on-disk cache, bulk operations.

**Target resume audience:** generic software / AI-engineering roles. (If you later target frontend
roles, revisit TypeScript + a companion Obsidian plugin.)

---

## 2. Locked Decision Record

Each row is a settled decision. The rationale is kept so the repo (and future-you) understands *why*.

| # | Decision | Rationale (short) |
|---|----------|-------------------|
| 1 | Optimize for **portfolio-grade AND useful daily-driver** (co-equal). Sim → Phase 2. | A finished, legible repo + a tool you use beats a half-built simulator. |
| 2 | Target **real Obsidian** (heavy existing user). | Real-tool integration serves both goals; fits an existing workflow. |
| 3 | **Direct filesystem** access (primary); optional REST adapter later. | Headless, dependency-free, trivially testable in CI. Use atomic write-then-rename; don't live-edit the same note in Obsidian while the server writes it. |
| 4 | **Python + standalone FastMCP** (`pip install fastmcp`, 3.x line). | Lingua franca of the agentic ecosystem; cleanest decorators; de-facto MCP standard; in-memory client makes tests easy. FastMCP is built on the official `mcp` SDK, so you can drop down for protocol-level control if ever needed. |
| 5 | **Greenfield vault** (full overhaul). Plugins welcome (Templater, Dataview). Structured folders + frontmatter. | Server is free to define structure; no migration of an existing vault. |
| 6 | **Config-driven ontology** — one schema file is the single source of truth. | Schema drives validation, *generates* Templater templates, and is the target of Dataview queries — no drift across server/templates/queries. Extensible (add a type by editing the file). |
| 7 | Default **core-6 entity types**: `Character`, `Location` (hierarchical), `Faction`, `Event`, `Item`, `Lore` (catch-all). Tier-2 types documented, one-line config to enable. | Lean, opinionated default; covers ~90% across TTRPG/game/novel; never boxed in. |
| 8 | **Typed frontmatter link-properties** + **two-tier link model**. | Formal typed links (e.g. `member_of:`) are validated, rendered in graph view, Dataview-queryable, and machine-structured; the server **auto-maintains inverses**. Plain prose `[[mentions]]` remain soft associations a later tool can offer to promote. *Seam reserved:* `valid_from`/`valid_to` for time-bounded relationships (Phase 2). |
| 9 | **Hybrid identity** — wikilinks by **title** (human-readable, graph-native); every entity also carries a stable readable `uid` (e.g. `char_aldric_a1b2`) used as the server's internal primary key; `aliases` fold into the resolver. | Content stays human-authored; integrity enforced by a stable-ID index, rebuildable from a full scan. Survives renames, duplicate names, external edits. |
| 10 | **Scan-on-demand now**, incremental re-index later — both behind a stable `VaultIndex` interface. | Correct-by-construction in v1 (no stale-cache bug class). Swap to incremental re-index later without touching any tool. No persistent on-disk cache until proven necessary. |
| 11 | **Pure primitives** — the server never calls a model. Host LLM does all reasoning/generation by orchestrating tools + resources + prompts. | The agentic showcase *is* an agent chaining `read → reason → validate → write` over a well-designed surface. Sampling = documented Phase-1.5 upgrade. |
| 12 | **Parametrized generic tools** + schema-as-resource. | Flat, fixed tool surface regardless of type count; runtime validation against schema; avoids tool-schema token bloat; partners the config-driven ontology. |
| 13 | **10-tool v1 roster** (see §4). | Lean but complete enough to build & maintain a whole world end-to-end. |
| 14 | **Tiered strictness, tilted permissive.** Structural impossibilities hard-reject; incompleteness allowed-with-warning. Link to a nonexistent target **auto-creates a `status: stub`**. `type` + `name` are the only truly blocking fields. | Worldbuilding is out-of-order; forward-references become a worklist, not an error. |
| 15 | **Soft-delete default + explicit purge.** `delete_entity` → `_trash/` (reversible). `purge=true` strips inbound **typed** links + inverses *with a report of every note touched*, leaves inbound **prose** mentions as dangling links for `validate` to flag. | Deletion is the one irreversible op; never silently rewrite human narrative text. |
| 16 | **In-vault schema**, YAML, hidden: `.worldbuild/schema.yaml`. `init` writes the default. Per-vault ontology. | Vault is self-describing & portable; D&D world and novel can diverge on one install. Index excludes `.worldbuild/` and `_trash/`. |
| 17 | **`validate` = read-only default + opt-in mechanical `fix=true`.** Severity-grouped report (ERROR/WARN/INFO); each item carries refs + suggested fix; `scope` = vault\|type\|entity. `fix` only does unambiguous repairs (rebuild missing inverses; repoint a stale wikilink when exactly one target matches). | Mechanical repairs automated; semantic repairs surfaced, never guessed. The headline "worldbuilding intelligence" feature. Server **verifies**; LLM **creates**. |
| 18 | **Graph-aware prompts**, v1 set of 4: `flesh_out_entity`, `suggest_connections`, `consistency_review`, `brainstorm`. Each embeds `schema` + world context. | Host LLM is already great at blank-page invention; prompts earn their keep by injecting *your world's* structure/state. `consistency_review` (semantic) pairs with `validate` (structural). |
| 19 | **One vault per server instance.** Transport = **stdio**. Vault path via `OBSIDIAN_VAULT_PATH` env var or `--vault` CLI arg. | Idiomatic MCP deployment; total isolation; keeps all 10 tool signatures free of a `vault` param. |
| 20 | **Source-first → PyPI.** `uvx worldbuild-mcp --vault /path` one-liner; ship a copy-paste host-config snippet. | Develop runnable from source so packaging never blocks; publish as a finishing milestone. Wiring-in is the #1 MCP onboarding cliff. |
| 21 | **Standalone `worldbuild_core` + thin MCP adapter.** One-way rule: core never imports `mcp`; adapter holds no logic. No CLI in v1. | Ports-and-adapters / hexagonal. Clean tests, strongest design talking point, reuse for Phase 2 — and the gentlest on-ramp (build familiar Python first, learn MCP last). |
| 22 | **Unit tests + thin in-memory MCP layer + CI.** pytest with temp-vault fixtures carries coverage; in-memory client proves each tool registers & round-trips; GitHub Actions runs tests + **ruff** + **type-check** (mypy/pyright) over a fully type-hinted core. Ship a tiny **example vault** that doubles as fixtures + demo. | Where coverage belongs is the standalone core; the in-memory layer catches wiring bugs unit tests can't. Coverage gates / property tests deferred. |
| 23 | **Structured result envelope.** Every tool returns `status` (ok\|warning\|error) + `data` + `messages[]`; mutations include a what-changed summary. Expected outcomes return as readable data; only truly exceptional failures raise. | Backbone of the agentic loop — the agent must read what just happened to act next. One home for stub/touched-notes/fix reports. |
| 24 | **Seams reserved + documented roadmap; no sim code in v1.** | Clean v1 boundary; roadmap credibly says the architecture already reserves temporal + graph-traversal seams. |
| 25 | **README/presentation plan + MIT license.** GIF/graph visual + architecture diagram non-optional; in-repo example vault. | Most visitors judge in 60s; the visual + architecture section separate "finished product" from "class exercise." |

---

## 3. Architecture

### 3.1 Data flow (ports & adapters)

```
┌─────────────────┐   MCP (stdio)   ┌──────────────────┐   plain calls   ┌──────────────────┐   files   ┌─────────────┐
│  Host LLM        │ ◄────────────► │  MCP adapter      │ ◄────────────► │  worldbuild_core  │ ◄──────► │ Obsidian vault│
│ (Claude Desktop) │   tools /       │  (server.py)      │   (no mcp       │  (no mcp imports) │  read/    │  .md + .yaml │
│  orchestrates    │   resources /   │  thin wrappers    │    imports)     │  schema, index,   │  write    │              │
│  the workflow    │   prompts       │  + result envelope│                 │  links, validate  │           │              │
└─────────────────┘                 └──────────────────┘                 └──────────────────┘           └─────────────┘
        the agent             ◄── the new thing you learn LAST ──►        ◄── familiar Python you build FIRST ──►
```

**The one-way rule:** `worldbuild_core` never imports `mcp`. The adapter never contains logic.

### 3.2 Repo layout

```
worldbuild-mcp/
├── src/
│   ├── worldbuild_core/          # the domain engine — ZERO mcp imports
│   │   ├── __init__.py
│   │   ├── schema.py             # load/validate .worldbuild/schema.yaml
│   │   ├── vault.py              # init_vault(), paths, atomic write-then-rename
│   │   ├── index.py              # VaultIndex: scan → path↔uid↔aliases, link resolver
│   │   ├── entities.py           # create/get/update/rename/delete + uid minting
│   │   ├── links.py              # link/unlink, inverse maintenance, auto-stub
│   │   ├── validate.py           # the consistency engine + fix
│   │   ├── query.py              # query_entities, search
│   │   └── models.py             # Entity, ValidationReport, Result envelope, etc.
│   └── worldbuild_mcp/           # the thin MCP adapter
│       ├── __init__.py
│       └── server.py             # @mcp.tool / @mcp.resource / @mcp.prompt wrappers
├── tests/
│   ├── conftest.py               # tmp-vault fixtures
│   ├── test_core_*.py            # unit tests against worldbuild_core
│   └── test_mcp_roundtrip.py     # in-memory FastMCP client: registration + round-trip
├── examples/
│   └── sample_vault/             # tiny demo world (doubles as test fixtures)
├── .github/workflows/ci.yml      # tests + ruff + type-check
├── pyproject.toml
├── README.md
├── LICENSE                       # MIT
└── PROJECT_PLAN.md               # this file
```

### 3.3 Schema file — north-star shape

`.worldbuild/schema.yaml` (illustrative; the real default ships the core-6):

```yaml
version: 1
types:
  Character:
    folder: Characters
    fields:
      required: [name]
      optional: [aliases, status, summary]
    relationships:
      member_of:   { target: Faction,   cardinality: many, inverse: members }
      located_in:  { target: Location,  cardinality: one,  inverse: occupants }
  Faction:
    folder: Factions
    fields:
      required: [name]
      optional: [summary]
    # 'members' is the auto-maintained inverse of Character.member_of — no need to redeclare
  Location:
    folder: Locations
    hierarchical: true          # supports continent → region → city → site
    relationships:
      located_in:  { target: Location, cardinality: one, inverse: contains }
  Event:
    folder: Events
    fields:
      optional: [date, valid_from, valid_to]   # temporal anchors — seams for Phase 2 sim
  Item:    { folder: Items }
  Lore:    { folder: Lore }                     # deliberate catch-all
# Tier-2 types (Species, Culture, Creature, Deity, Quest, SessionLog) live here when enabled.
```

---

## 4. The v1 Tool Surface

**Tools (10)** — all return the structured result envelope (`status` / `data` / `messages[]`):

| Tool | Behavior notes |
|------|----------------|
| `create_entity(type, name, fields?, body?)` | Folder placement, mint `uid`, apply frontmatter + generated template. |
| `get_entity(ref)` | `ref` = uid \| title \| alias. Returns frontmatter, body, **resolved one-hop relationships**, backlinks. |
| `update_entity(ref, ...)` | Patch frontmatter / append or replace body. |
| `rename_entity(ref, new_name)` | Retitle + repair inbound wikilinks. |
| `delete_entity(ref, purge?)` | Soft-delete → `_trash/` by default; `purge=true` removes + strips typed inverses (with touched-notes report), leaves prose mentions dangling for `validate`. |
| `link(source, relation, target)` | Validate types/cardinality vs schema; auto-write inverse; auto-create `status: stub` if target missing. |
| `unlink(source, relation, target)` | Remove + inverse. |
| `query_entities(type?, field_filters?, tags?)` | Structured query. |
| `search(text)` | Full-text / fuzzy find. |
| `validate(scope?, fix?)` | Severity-grouped report; `fix=true` does only unambiguous mechanical repairs. |

**Resources (3):** `schema`, `world_summary`, `list_types`.

**Prompts (4, graph-aware):** `flesh_out_entity(ref)`, `suggest_connections(ref)`, `consistency_review(scope?)`, `brainstorm(seed, type?)`.

**Deferred:** multi-hop `traverse`, mention-promotion tool, bulk ops, explicit `reindex`.

---

## 5. Implementation Roadmap

Work top-to-bottom. **Phases 1–5 are plain Python you already know.** You don't touch MCP until Phase 6.
Each phase ends at a real, testable milestone. Write tests *as you go*, not after.

### Phase 0 — Scaffold
- [x] `git init`; create repo structure (§3.2); MIT `LICENSE`; README stub.
- [x] `pyproject.toml` with `fastmcp`, `pyyaml`, `pytest`, `ruff`, `mypy` (or `pyright`).
- [x] Set up `uv` for the project (`uv venv`, `uv sync`).
- [x] `ruff` + type-checker config; minimal GitHub Actions `ci.yml` (lint + type-check + pytest).
- [x] First green CI run on an empty test. **Done when:** CI badge is green.

### Phase 1 — Schema & vault bootstrap (core)
- [x] Define the `schema.yaml` format (types, folders, required/optional fields, relationship specs with `target`/`cardinality`/`inverse`).
- [x] `schema.py`: load + **validate the schema itself** (catch malformed ontologies early).
- [x] `vault.py`: `init_vault(path)` writes the default core-6 schema into `.worldbuild/schema.yaml` and creates the folder skeleton.
- [x] Tests: schema loads, defaults are written, a malformed schema is rejected.
- [x] **Done when:** `init_vault(tmp)` produces a valid, self-describing vault.

### Phase 2 — Entity model, identity, index (core)
- [x] `models.py`: `Entity` (frontmatter + body), the `Result` envelope, `ValidationReport`.
- [x] Readable `uid` minting (e.g. `char_aldric_a1b2`).
- [x] Markdown read/write: frontmatter parse/serialize, **atomic write-then-rename**.
- [x] `index.py`: `VaultIndex` (scan-on-demand) builds `path ↔ uid ↔ aliases`; excludes `.worldbuild/` and `_trash/`.
- [x] Link resolver: resolve a `ref` by uid, title, or alias; report unresolved.
- [x] Tests with temp vaults: round-trip a note, resolve by all three ref kinds, detect a broken link.
- [x] **Done when:** you can scan a vault and resolve links reliably after a rename.

### Phase 3 — CRUD (core)
- [x] `create_entity` (folder placement, uid, template/frontmatter from schema).
- [x] `get_entity` (frontmatter + body + **resolved one-hop links** + backlinks).
- [x] `update_entity` (patch frontmatter / append or replace body).
- [x] `rename_entity` (retitle + repair inbound wikilinks).
- [x] `delete_entity` (soft → `_trash/`) and the `purge=true` path (strip typed inverses, touched-notes report, leave prose dangling).
- [x] Tests for each, including soft-delete reversibility and the purge report.
- [x] **Done when:** full lifecycle of an entity works end-to-end on files.

### Phase 4 — Relationships (core)
- [x] `link` (validate types/cardinality vs schema; **auto-write inverse**; **auto-stub** nonexistent target).
- [x] `unlink` (+ inverse removal with report).
- [x] Enforce the two-tier model: typed links are managed; prose `[[mentions]]` are left untouched.
- [x] Tests: inverse appears on the target, cardinality is enforced, a forward-reference creates a `status: stub`.
- [x] **Done when:** the typed-relationship graph is self-consistent by construction.

### Phase 5 — Validate & query (core)  ← core feature-complete
- [x] `validate` engine: ERROR (illegal relationship type, busted cardinality, link resolving to nothing), WARN (missing required field, stubs, missing inverse, ref to trashed entity), INFO (orphans, recurring promotable mentions). Severity-grouped report with refs + suggested fixes; `scope` = vault\|type\|entity.
- [x] `validate(fix=true)`: rebuild missing inverses; repoint a stale wikilink when exactly one target matches. Never guess semantics.
- [x] `query_entities` (type/field/tag filters); `search` (full-text).
- [x] Tests covering each severity and each mechanical fix.
- [x] **Done when:** `worldbuild_core` can build, query, and self-heal a whole world with **no MCP at all**. *(Tag a `v0.1-core` git tag here.)*

### Phase 6 — MCP adapter (learn this layer now, in isolation)
- [ ] `server.py`: create the FastMCP server; read vault path from `OBSIDIAN_VAULT_PATH` / `--vault`.
- [ ] Wrap the 10 core functions as `@mcp.tool`, each returning the structured envelope.
- [ ] Expose `schema`, `world_summary`, `list_types` as `@mcp.resource`.
- [ ] `test_mcp_roundtrip.py`: FastMCP **in-memory client** asserts each tool is registered and round-trips (catches "not registered / won't serialize" bugs).
- [ ] Manually wire into Claude Desktop and drive it once by hand.
- [ ] **Done when:** an agent in the host can create linked entities and run `validate`.

### Phase 7 — Prompts
- [x] `flesh_out_entity`, `suggest_connections`, `consistency_review`, `brainstorm` as `@mcp.prompt`, each embedding `schema` + relevant world context.
- [x] **Done when:** the host can do graph-aware generation that respects existing structure.

### Phase 8 — Packaging, docs, polish  ← ship
- [ ] Build & publish to PyPI; verify `uvx worldbuild-mcp --vault /path`.
- [ ] README: hook → **GIF/graph visual** → quickstart + **copy-paste host-config snippet** → concepts (ontology, two-tier links, validate) → **architecture diagram** (ports & adapters) → tool/resource/prompt reference → roadmap.
- [ ] Polish `examples/sample_vault/` as both demo and fixtures.
- [ ] Final CI green + badge. *(Tag `v1.0.0`.)*
- [ ] **Done when:** a stranger can install, wire in, and use it from the README alone.

### Phase 9 — Future (Phase 2 vision — documented only, no v1 code)
- [ ] Activate temporal seams: `valid_from`/`valid_to` time-bounded relationships.
- [ ] Multi-hop `traverse` for real graph-walking.
- [ ] `develop_history(seed)` / `generate_quest` — internally-consistent history & quest-line generation.
- [ ] MCP `sampling` upgrade (Phase-1.5) for in-server generation without a server-side key.

---

## 6. Definition of Done (v1)

- [ ] `worldbuild_core` is standalone, fully type-hinted, and tested (no `mcp` import anywhere in it).
- [ ] All 10 tools + 3 resources + 4 prompts work through the MCP adapter.
- [ ] CI is green: pytest + ruff + type-check.
- [ ] Published on PyPI; README leads with a working `uvx` one-liner and a host-config snippet.
- [ ] README has the GIF/graph visual and the architecture diagram.
- [ ] Example vault present; MIT licensed; clean commit history.
- [ ] Roadmap section names the reserved Phase-2 seams.

---

*Guiding invariants to keep returning to:* **Server verifies, LLM creates.** **Core never imports the protocol.**
**Non-destructive by default; `validate` is the safety net.** **The schema is the single source of truth.**
