# Example vault

[`sample_vault/`](./sample_vault) is a small, fully-linked world you can point Innkeeper at to try it out — a waystation town (**Thornwick**) built around its inn, **The Gilded Antler**. It exercises all seven default types and every kind of typed relationship, with inverses auto-maintained, and demonstrates per-type body templates.

Point a host at it, or explore from the shell:

```bash
uv run innkeeper --vault examples/sample_vault    # serve it to an MCP host
```

The world at a glance:

- **Thornwick** (Location) — contains **The Gilded Antler** (hierarchical link).
- **Marta Bellweather** (Character) — the innkeeper; `located_in` the Antler, carries **Bellweather's Ledger** (Item).
- **Captain Orin Vale** (Character) — `member_of` **The Roadwardens** (Faction).
- **The Salt Road Fair** (Event) — Marta and Orin are `participant_in` it.
- **Bellweather's Ledger** (Item) — `equipped_by` Marta.
- **Session 1 — The Salt Road Fair** (Session) — a play-session recap that `covers` the Fair, `mentions` Marta and Orin, and is `located_in` Thornwick.
- **The Founding of Thornwick** (Lore) — standalone lore (deliberately unlinked; `validate` flags it as an `INFO` orphan, which is expected for the catch-all `Lore` type).

## Body templates

`init_vault` scaffolds an empty `.innkeeper/templates/<Type>.md` for every type. Fill one in and new entities of that type inherit it as their starting body — an explicit body always wins. This vault ships a filled-in [`templates/Session.md`](./sample_vault/.innkeeper/templates/Session.md) recap scaffold, which is why the Session note already has `## Recap` / `## Loose Threads` sections without anyone typing them.

## Regenerating

The vault is generated from [`build_sample_vault.py`](./build_sample_vault.py), which drives `innkeeper_core` directly so every link, inverse, and `uid` is valid by construction. To rebuild it from scratch:

```bash
uv run python examples/build_sample_vault.py
```
