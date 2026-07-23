"""Builds context for the LLM and periodically distills a long-term
'understanding of you' from recent entries, so prompts get more personal
and relevant over time without re-reading your whole journal every time."""

from llm_client import chat

MEMORY_UPDATE_PROMPT = """You maintain a private, evolving profile of a person based on their \
journal entries, so that future journaling sessions can ask them better, more relevant \
questions. This profile is for your own use as a journaling companion -- it is never shown \
verbatim to the person unless they ask.

Write in concise bullet points, organized under these headings if relevant:
- Recurring themes or stressors
- Values and what seems to matter to them
- Goals or things they're working toward
- Communication/emotional patterns (e.g. tends to minimize feelings, is hard on themself, etc.)
- Anything they've explicitly asked you to remember or watch for

Be specific but brief. Do not speculate wildly beyond what's actually in the entries. \
Do not include any clinical or diagnostic language. Merge new information with the existing \
profile below rather than starting over -- keep what's still true, update what's changed, drop \
what's stale.

EXISTING PROFILE:
{existing}

NEW JOURNAL ENTRIES SINCE LAST UPDATE:
{entries}

Return ONLY the updated profile in bullet points. No preamble."""


def format_conversation(conversation):
    lines = []
    for turn in conversation:
        speaker = "Companion" if turn["role"] == "assistant" else "You"
        lines.append(f"{speaker}: {turn['content']}")
    return "\n".join(lines)


def format_entries_for_prompt(entries):
    blocks = []
    for e in entries:
        blocks.append(f"--- Entry ({e['timestamp'][:10]}) ---\n{format_conversation(e['conversation'])}")
    return "\n\n".join(blocks)


def update_memory_summary(existing_summary, new_entries, model_id, trust_remote_code=False):
    if not new_entries:
        return existing_summary
    prompt = MEMORY_UPDATE_PROMPT.format(
        existing=existing_summary or "(none yet -- this is the first update)",
        entries=format_entries_for_prompt(new_entries),
    )
    updated = chat(
        messages=[{"role": "user", "content": prompt}],
        model_id=model_id,
        max_tokens=500,
        trust_remote_code=trust_remote_code,
    )
    return updated


TAG_PROMPT = """Read this journal entry and pick 2-5 short, lowercase thematic tags that \
capture what it's really about (e.g. "work stress", "family", "gratitude", "burnout", \
"creative block", "relationship", "health", "money worry", "small win"). Prefer tags that \
would be useful to spot patterns across many entries over time -- not overly specific one-offs.

ENTRY:
{entry}

Return ONLY a JSON object like: {{"tags": ["tag one", "tag two"]}}"""


def build_tag_prompt(conversation):
    return TAG_PROMPT.format(entry=format_conversation(conversation))


def build_system_prompt(persona, memory_summary):
    if memory_summary:
        return (
            f"{persona}\n\n"
            f"Here is what you've come to understand about this person from past entries "
            f"(use it to make your question more relevant and personal, but don't quote it "
            f"back at them or make them feel 'profiled'):\n{memory_summary}"
        )
    return f"{persona}\n\nYou don't have any history with this person yet -- this is their first entry."
