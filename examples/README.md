# Example vault

[`sample_vault/`](./sample_vault) is a small, fully-linked world you can point Innkeeper at to try it out — a waystation town (**Thornwick**) built around its inn, **The Gilded Antler**. It exercises all six default types and every kind of typed relationship, with inverses auto-maintained.

Point a host at it, or explore from the shell:

```bash
uv run innkeeper --vault examples/sample_vault    # serve it to an MCP host
```

The world at a glance:

- **Thornwick** (Location) — contains **The Gilded Antler** (hierarchical link).
- **Marta Bellweather** (Character) — the innkeeper; `located_in` the Antler, carries **Bellweather's Ledger** (Item).
- **Captain Orin Vale** (Character) — `member_of` **The Roadwardens** (Faction).
- **The Salt Road Fair** (Event) — Marta and Orin are `participant_in` it.
- **The Founding of Thornwick** (Lore) — standalone lore (deliberately unlinked; `validate` flags it as an `INFO` orphan, which is expected for the catch-all `Lore` type).

## Regenerating

The vault is generated from [`build_sample_vault.py`](./build_sample_vault.py), which drives `innkeeper_core` directly so every link, inverse, and `uid` is valid by construction. To rebuild it from scratch:

```bash
uv run python examples/build_sample_vault.py
```
