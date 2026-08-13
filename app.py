"""
Transcript Intelligence Pipeline — Streamlit demo app.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st

from tip.config import SAMPLE_TRANSCRIPTS_DIR, get_settings
from tip.notion_sync import render_notion_markdown
from tip.pipeline import run_pipeline

st.set_page_config(page_title="Transcript Intelligence Pipeline", page_icon="🎙️", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

settings = get_settings()

with st.sidebar:
    st.title("🎙️ Transcript Intelligence Pipeline")
    st.caption("Python · Whisper · GPT-4 · Notion API · Prompt Engineering")

    if settings.mode == "live":
        st.success("Mode: **LIVE** — real Whisper + GPT-4 + Notion calls")
    else:
        st.warning("Mode: **MOCK** — cached demo responses, zero API calls")
        with st.expander("Why mock mode?"):
            st.write(
                "No `OPENAI_API_KEY` was found. The pipeline still runs the "
                "full architecture end-to-end using hand-verified cached "
                "GPT-4 responses for the bundled sample interviews (and a "
                "deterministic rule-based fallback for anything else), so "
                "you can demo it with zero setup. Add API keys to `.env` to "
                "flip to live mode — see the README."
            )

    st.divider()
    st.subheader("1. Choose input")

    sample_files = sorted(SAMPLE_TRANSCRIPTS_DIR.glob("*.txt"))
    sample_labels = {p.stem: p for p in sample_files}

    input_mode = st.radio("Source", ["Sample interview", "Paste / upload your own"], label_visibility="collapsed")

    selected_path: Path | None = None
    custom_text: str | None = None
    custom_id: str | None = None

    if input_mode == "Sample interview":
        chosen = st.selectbox("Pick a sample", list(sample_labels.keys()))
        selected_path = sample_labels[chosen]
        st.caption(f"`{selected_path.relative_to(SAMPLE_TRANSCRIPTS_DIR.parent.parent)}`")
    else:
        uploaded = st.file_uploader("Upload a .txt transcript", type=["txt"])
        pasted = st.text_area("...or paste transcript text", height=150)
        custom_id = st.text_input("Interview ID", value="custom_interview")
        if uploaded is not None:
            custom_text = uploaded.read().decode("utf-8")
        elif pasted.strip():
            custom_text = pasted
        st.caption(
            "Custom input won't match the demo cache, so it will run "
            "through the deterministic heuristic fallback in MOCK mode "
            "(or live GPT-4 if you've set an API key)."
        )

    push_notion = st.checkbox("Push to Notion after extraction", value=True)
    run_clicked = st.button("▶ Run pipeline", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.markdown(
    "### From raw research recording to PM-ready Notion handoff\n"
    "Whisper transcription → 3-stage GPT-4 prompt chain "
    "(candidates → structure/classify → entities) → schema validation "
    "with automatic repair + heuristic fallback → Notion sync."
)

if "output" not in st.session_state:
    st.session_state.output = None

if run_clicked:
    if input_mode == "Sample interview":
        run_input = selected_path
        run_id = None
    else:
        if not custom_text:
            st.error("Please upload or paste a transcript first.")
            st.stop()
        tmp_path = Path("/tmp") / f"{custom_id or 'custom_interview'}.txt"
        tmp_path.write_text(custom_text, encoding="utf-8")
        run_input = tmp_path
        run_id = custom_id or "custom_interview"

    progress_box = st.status("Running pipeline…", expanded=True)
    log_lines = []

    def on_progress(stage: str, message: str):
        log_lines.append(f"**[{stage}]** {message}")
        progress_box.update(label=f"Running pipeline — {stage}…")
        progress_box.write(f"[{stage}] {message}")
        time.sleep(0.15)  # tiny pacing so the demo reads as "live" work happening

    output = run_pipeline(run_input, interview_id=run_id, push_notion=push_notion, on_progress=on_progress)
    progress_box.update(label="Pipeline complete ✅", state="complete", expanded=False)
    st.session_state.output = output

output = st.session_state.output

if output is None:
    st.info("Pick a sample interview (or paste your own) in the sidebar, then click **Run pipeline**.")
    st.stop()

r = output.extraction

st.divider()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Themes", len(r.themes))
m2.metric("Pain points", len(r.pain_points))
m3.metric("Action items", len(r.action_items))
m4.metric("Entities", len(r.entities))
m5.metric("Confidence", f"{r.confidence:.0%}")

method_label = {
    "llm": "🟢 GPT-4 prompt chain",
    "llm_repaired": "🟡 GPT-4 (repaired after schema validation failure)",
    "heuristic_fallback": "🔴 Rule-based fallback (no LLM available)",
}[r.extraction_method.value]
st.caption(f"Extraction method: {method_label} · Prompt version: `{r.prompt_version}` · Interview: `{r.interview_id}`")

tab_themes, tab_pain, tab_actions, tab_entities, tab_notion, tab_transcript = st.tabs(
    ["🧵 Themes", "🔥 Pain Points", "✅ Action Items", "🏷️ Entities", "📓 Notion Preview", "📄 Transcript"]
)

with tab_themes:
    if not r.themes:
        st.write("No themes extracted.")
    for t in r.themes:
        with st.container(border=True):
            st.markdown(f"**{t.title}**  \n_mentioned {t.frequency}x_")
            st.write(t.summary)
            for q in t.supporting_quotes:
                st.markdown(f"> {q}")

with tab_pain:
    if not r.pain_points:
        st.write("No pain points extracted.")
    sev_color = {"high": "🔴", "medium": "🟠", "low": "🟡"}
    for p in r.pain_points:
        with st.container(border=True):
            st.markdown(f"{sev_color[p.severity.value]} **[{p.severity.value.upper()}]** `{p.affected_area}`")
            st.write(p.description)
            if p.quote:
                st.markdown(f"> {p.quote}")

with tab_actions:
    if not r.action_items:
        st.write("No action items extracted.")
    pr_color = {"high": "🔴", "medium": "🟠", "low": "🟡"}
    for a in r.action_items:
        with st.container(border=True):
            owner = f" · `@{a.owner_hint}`" if a.owner_hint else ""
            st.markdown(f"{pr_color[a.priority.value]} **[{a.priority.value.upper()}]**{owner} {a.action}")
            if a.rationale:
                st.caption(f"Why: {a.rationale}")

with tab_entities:
    if not r.entities:
        st.write("No entities extracted.")
    else:
        st.dataframe(
            [{"Entity": e.name, "Type": e.type, "Mentions": e.mentions} for e in r.entities],
            use_container_width=True,
            hide_index=True,
        )

with tab_notion:
    st.caption(f"Written to: `{output.notion_destination or output.notion_markdown_path}`")
    st.markdown(render_notion_markdown(r))

with tab_transcript:
    st.text(output.transcription.text)

st.divider()
st.caption(
    f"JSON output: `{output.json_path}`  ·  "
    f"Notion markdown: `{output.notion_markdown_path}`"
)
