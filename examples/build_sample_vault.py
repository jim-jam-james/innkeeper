"""Generate the example vault by driving innkeeper_core directly.

Building through the API (rather than hand-writing Markdown) guarantees every
typed relationship, its auto-maintained inverse, and every uid is valid. Re-run
to regenerate from scratch:

    uv run python examples/build_sample_vault.py
"""

import shutil
from pathlib import Path

from innkeeper_core import entities
from innkeeper_core.vault import init_vault, load_schema

VAULT = Path(__file__).parent / "sample_vault"


def build() -> None:
    if VAULT.exists():
        shutil.rmtree(VAULT)
    init_vault(VAULT)
    schema = load_schema(VAULT)

    def new(type: str, name: str, fields: dict | None = None, body: str = "") -> None:
        entities.create_entity(VAULT, schema, type, name, fields, body)

    def link(source: str, rel: str, target: str) -> None:
        entities.link(VAULT, schema, source, rel, target)

    # --- Locations (hierarchical: the inn sits inside the town) ---
    new(
        "Location",
        "Thornwick",
        {"biome": "temperate river valley", "governance": "elected moot"},
        "A waystation town where the Salt Road meets the river ford. Traders, "
        "pilgrims, and trouble all pass through eventually.",
    )
    new(
        "Location",
        "The Gilded Antler",
        {"summary": "The town's largest inn and de-facto common house."},
        "Three storeys of timber and lamplight. If something is happening in "
        "[[Thornwick]], someone at the Antler knows about it first.",
    )
    link("The Gilded Antler", "located_in", "Thornwick")

    # --- Characters ---
    new(
        "Character",
        "Marta Bellweather",
        {"status": "active", "summary": "Proprietor of the Gilded Antler."},
        "Sharp-eyed and unflappable, Marta has kept the Antler for thirty years "
        "and forgotten more secrets than most people ever learn.",
    )
    link("Marta Bellweather", "located_in", "The Gilded Antler")

    new(
        "Character",
        "Captain Orin Vale",
        {"status": "active", "class": "fighter", "alignment": "lawful neutral"},
        "Commander of the Roadwardens. Trusts Marta's read on strangers more than his own patrols.",
    )
    link("Captain Orin Vale", "located_in", "Thornwick")

    # --- Faction ---
    new(
        "Faction",
        "The Roadwardens",
        {"summary": "The volunteer militia that keeps the Salt Road safe."},
        "Neither soldiers nor sheriffs, the Roadwardens answer to the Thornwick "
        "moot and little else.",
    )
    link("The Roadwardens", "located_in", "Thornwick")
    link("Captain Orin Vale", "member_of", "The Roadwardens")

    # --- Event ---
    new(
        "Event",
        "The Salt Road Fair",
        {"date": "midsummer", "summary": "Thornwick's annual trade fair."},
        "For three days the town triples in size. The Antler never closes and "
        "the Roadwardens never sleep.",
    )
    link("The Salt Road Fair", "located_in", "Thornwick")
    link("Marta Bellweather", "participant_in", "The Salt Road Fair")
    link("Captain Orin Vale", "participant_in", "The Salt Road Fair")

    # --- Item ---
    new(
        "Item",
        "Bellweather's Ledger",
        {"item_type": "book", "summary": "A worn book of debts, favours, and rumours."},
        "Marta's ledger tracks more than coin. Half of Thornwick would pay to "
        "read it; the other half would pay to burn it.",
    )
    link("Bellweather's Ledger", "equipped_by", "Marta Bellweather")

    # --- Lore ---
    new(
        "Lore",
        "The Founding of Thornwick",
        {"lore_type": "history"},
        "They say the first inn on this ford was a single tent and a barrel of "
        "ale. Everything since has just been expansion.",
    )

    # --- Session (demonstrates a body template) ---
    # init_vault() scaffolds an empty templates/Session.md. Overwrite it with a real
    # recap scaffold, then create the Session with no body so it inherits the template.
    session_template = "## Recap\n\n## Notable NPCs\n\n## Loose Threads\n\n## Rewards & XP\n"
    (VAULT / ".innkeeper" / "templates" / "Session.md").write_text(
        session_template, encoding="utf-8"
    )

    new(
        "Session",
        "Session 1 - The Salt Road Fair",
        {
            "session_number": 1,
            "played_on": "2026-01-10",
            "summary": "The party arrives in Thornwick as the fair opens.",
        },
    )
    link("Session 1 - The Salt Road Fair", "covers", "The Salt Road Fair")
    link("Session 1 - The Salt Road Fair", "mentions", "Marta Bellweather")
    link("Session 1 - The Salt Road Fair", "mentions", "Captain Orin Vale")
    link("Session 1 - The Salt Road Fair", "located_in", "Thornwick")

    print(f"Sample vault built at {VAULT}")


if __name__ == "__main__":
    build()
