"""
Notion API sync.

LIVE mode (NOTION_TOKEN + NOTION_DATABASE_ID set): creates one page per
interview in the target database, with themes/pain points/action items
rendered as toggle blocks, ready for a PM to open and triage.

MOCK mode: renders the exact same content to a local Markdown file under
output/notion_preview/ so you can see precisely what would land in
Notion without needing a workspace/token during the interview.
"""
from __future__ import annotations

from pathlib import Path

from .config import OUTPUT_DIR, get_settings
from .schema import ExtractionResult


def push_to_notion(result: ExtractionResult) -> str:
    """Returns either a Notion page URL (live) or a local file path (mock)."""
    settings = get_settings()
    if settings.mode == "live" and settings.notion_token and settings.notion_database_id:
        return _push_live(result, settings.notion_token, settings.notion_database_id)
    return _push_mock(result)


def render_notion_markdown(result: ExtractionResult) -> str:
    """Shared renderer used by both mock preview and the live page body."""
    lines = [f"# {result.interview_id}", ""]
    lines.append(f"*Source: `{result.source_file}` — prompt `{result.prompt_version}` "
                 f"— method `{result.extraction_method.value}` — confidence {result.confidence:.2f}*")
    lines.append("")

    lines.append("## 🧵 Themes")
    if not result.themes:
        lines.append("_None extracted._")
    for t in result.themes:
        lines.append(f"### {t.title}  _(mentioned {t.frequency}x)_")
        lines.append(t.summary)
        for q in t.supporting_quotes:
            lines.append(f"> {q}")
        lines.append("")

    lines.append("## 🔥 Pain Points")
    if not result.pain_points:
        lines.append("_None extracted._")
    for p in result.pain_points:
        badge = {"high": "🔴", "medium": "🟠", "low": "🟡"}[p.severity.value]
        lines.append(f"- {badge} **[{p.severity.value.upper()}]** ({p.affected_area}) {p.description}")
        if p.quote:
            lines.append(f"  > {p.quote}")
    lines.append("")

    lines.append("## ✅ Action Items")
    if not result.action_items:
        lines.append("_None extracted._")
    for a in result.action_items:
        owner = f" `@{a.owner_hint}`" if a.owner_hint else ""
        lines.append(f"- [ ] **[{a.priority.value.upper()}]**{owner} {a.action}")
        if a.rationale:
            lines.append(f"  _Why: {a.rationale}_")
    lines.append("")

    lines.append("## 🏷️ Entities")
    if not result.entities:
        lines.append("_None extracted._")
    for e in result.entities:
        lines.append(f"- `{e.type}` — **{e.name}** ({e.mentions}x)")

    return "\n".join(lines)


def _push_mock(result: ExtractionResult) -> str:
    out_dir = OUTPUT_DIR / "notion_preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.interview_id}.md"
    path.write_text(render_notion_markdown(result), encoding="utf-8")
    return str(path)


def _push_live(result: ExtractionResult, token: str, database_id: str) -> str:
    from notion_client import Client

    client = Client(auth=token)

    children = []
    for t in result.themes:
        children.append(_toggle_block(f"🧵 {t.title}", [t.summary, *[f"“{q}”" for q in t.supporting_quotes]]))
    for p in result.pain_points:
        children.append(_toggle_block(
            f"🔥 [{p.severity.value.upper()}] {p.description}",
            [f"Area: {p.affected_area}", p.quote or ""],
        ))
    for a in result.action_items:
        children.append(_toggle_block(
            f"✅ [{a.priority.value.upper()}] {a.action}",
            [a.rationale or ""],
        ))

    page = client.pages.create(
        parent={"database_id": database_id},
        properties={
            "Name": {"title": [{"text": {"content": result.interview_id}}]},
        },
        children=children,
    )
    return page.get("url", page.get("id", ""))


def _toggle_block(title: str, body_lines: list[str]) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
                }
                for line in body_lines if line
            ],
        },
    }
