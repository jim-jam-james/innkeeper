import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from innkeeper_core.entities import _add_link, _rewrite_links, parse_wikilinks
from innkeeper_core.index import scan_vault
from innkeeper_core.schema import Schema
from innkeeper_core.vault import write_entity


@dataclass
class Issue:
    severity: Literal["ERROR", "WARN", "INFO"]
    code: str
    ref: str
    message: str
    suggestion: str = ""


def validate(
    vault_path: Path, schema: Schema, fix: bool = False, scope: str | None = None
) -> list[Issue]:
    index = scan_vault(vault_path)

    issues = []

    if scope is None:
        targets = list(index.entities.values())
    elif schema.get_type(scope) is not None:
        targets = [e for e in index.entities.values() if e.type == scope]
    else:
        found = index.resolve(scope)
        targets = [found] if found is not None else []

    for entity in targets:
        spec = schema.get_type(entity.type)

        if spec is None:
            continue

        if entity.frontmatter.get("status") == "stub":
            issues.append(
                Issue(
                    severity="WARN",
                    code="stub",
                    ref=entity.name,
                    message=f"{entity.name} is a stub",
                    suggestion="Flesh out this entity",
                )
            )

        for req in spec.required:
            if req == "name":
                continue
            if not entity.frontmatter.get(req):
                issues.append(
                    Issue(
                        severity="WARN",
                        code="missing_required",
                        ref=entity.name,
                        message=f"{entity.name} missing required field '{req}'",
                        suggestion=f"Add '{req}' to frontmatter",
                    )
                )

        for rel_name, rel in spec.relationships.items():
            value = entity.frontmatter.get(rel_name)
            titles = parse_wikilinks(value)

            if rel.cardinality == "one" and len(titles) > 1:
                issues.append(
                    Issue(
                        severity="ERROR",
                        code="cardinality_violation",
                        ref=entity.name,
                        message=f"{entity.name}.{rel_name} has {len(titles)} links but \
                            cardinality is 'one'",
                        suggestion=f"Keep only one target in {rel_name}",
                    )
                )
            for title in titles:
                target = index.resolve(title)
                if target is None:
                    if fix:
                        candidates = [
                            e
                            for e in index.entities.values()
                            if e.type == rel.target and e.name.lower() == title.lower()
                        ]
                        if len(candidates) == 1:
                            pattern = re.compile(r"\[\[" + re.escape(title) + r"(\|[^\]]*)?\]\]")
                            entity.frontmatter[rel_name] = _rewrite_links(
                                value=value, pattern=pattern, new_name=candidates[0].name
                            )
                            write_entity(index.path_by_uid[entity.uid], entity)
                            continue
                    issues.append(
                        Issue(
                            severity="ERROR",
                            code="dangling_link",
                            ref=entity.name,
                            message=f"{entity.name}.{rel_name} -> '{title}' resolves to nothing",
                            suggestion=f"Create '{title}' or fix the link in {rel_name}",
                        )
                    )
                    continue
                if target.type != rel.target:
                    issues.append(
                        Issue(
                            severity="ERROR",
                            code="wrong_target_type",
                            ref=entity.name,
                            message=(
                                f"{entity.name}.{rel_name} -> '{title}' is a {target.type},"
                                f"  expected {rel.target}"
                            ),
                            suggestion=f"{rel_name} must point at a {rel.target}",
                        )
                    )
                    continue

                inverse = [
                    index.resolve(t) for t in parse_wikilinks(target.frontmatter.get(rel.inverse))
                ]
                inverse_uids = {e.uid for e in inverse if e is not None}

                if entity.uid not in inverse_uids:
                    if fix:
                        target_spec = schema.get_type(target.type)
                        if target_spec is not None:
                            inv = target_spec.relationships[rel.inverse]
                            _add_link(target, rel.inverse, entity.name, inv.cardinality)
                            write_entity(index.path_by_uid[target.uid], target)
                    else:
                        issues.append(
                            Issue(
                                severity="WARN",
                                code="missing_inverse",
                                ref=target.name,
                                message=(
                                    f"{target.name}.{rel.inverse} is missing a link back "
                                    f"to {entity.name}"
                                ),
                                suggestion=f"Add [[{entity.name}]] to {target.name}.{rel.inverse}",
                            )
                        )
    referenced: set[str] = set()
    has_outbound: set[str] = set()
    for entity in index.entities.values():
        spec = schema.get_type(entity.type)
        if spec is None:
            continue
        for rel_name in spec.relationships:
            for title in parse_wikilinks(entity.frontmatter.get(rel_name)):
                target = index.resolve(title)
                if target is not None:
                    referenced.add(target.uid)
                    has_outbound.add(entity.uid)

    for entity in targets:
        if entity.uid not in referenced and entity.uid not in has_outbound:
            issues.append(
                Issue(
                    severity="INFO",
                    code="orphan",
                    ref=entity.name,
                    message=f"{entity.name} has no typed relationships",
                    suggestion="Link it to another note, or leave it as standalone lore",
                )
            )
    return issues
