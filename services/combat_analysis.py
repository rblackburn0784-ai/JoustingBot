"""v2.9.6 — read-only post-joust analysis from completed saved match records.

No rerolls, score changes, journal writes or access to uncompleted challenges.
Only one of the match's real participants may fetch its private breakdown.
"""
from __future__ import annotations

from services.records import load_history

PASS_LABELS = {
    "clean_miss": "Missed lines",
    "shield_scrape": "Glancing shield scrape",
    "lance_break": "Broken lance",
    "heavy_shield_hit": "Heavy shield impact",
    "saddle_stagger": "Rider staggered",
    "unhorsing": "Unhorsing",
    "horse_slip": "Horse lost footing",
    "horse_refusal": "Horse refused the charge",
    "double_clash": "Even collision",
}


def owned_match(guild_id: int, user_id: int, match_id: str | None = None,
                history: dict | None = None) -> dict | None:
    if guild_id is None or user_id <= 0:
        return None
    journal = history if history is not None else load_history()
    matches = journal.get("matches", [])
    if not isinstance(matches, list):
        return None
    for match in reversed(matches):
        if not isinstance(match, dict) or match.get("guild_id") != guild_id:
            continue
        if match_id and str(match.get("id", "")) != match_id:
            continue
        if not any(isinstance(match.get(side), dict)
                   and match[side].get("user_id") == user_id for side in ("a", "b")):
            continue
        if not isinstance(match.get("passes"), list):
            continue
        return match
    return None


def breakdown(match: dict, user_id: int) -> dict:
    """Constrain every response field to Discord's 1024-char field maximum."""
    mine = "a" if (match.get("a") or {}).get("user_id") == user_id else "b"
    if (match.get(mine) or {}).get("user_id") != user_id:
        raise ValueError("This is not one of your completed jousts.")
    other = "b" if mine == "a" else "a"
    own = match[mine]
    foe = match[other]
    score = f"{own.get('score', 0)}–{foe.get('score', 0)}"
    winner = ("Draw" if own.get("score") == foe.get("score")
              else "Victory" if own.get("score", 0) > foe.get("score", 0)
              else "Defeat")
    gear = own.get("gear") or {}
    tactics = own.get("tactics") or {}
    summary = [
        f"**You:** {own.get('knight', 'Rider')} · **Opponent:** {foe.get('knight', 'Rider')}",
        f"**Result:** {winner} · {score} · **Arena:** {match.get('arena_name', match.get('arena_key','?'))}",
        f"**Mode:** {match.get('mode', 'joust')} · **Seed:** {match.get('seed', 'unknown')}",
        f"**Gear:** {', '.join(f'{key}={value}' for key, value in gear.items() if value)[:400] or 'Unknown'}",
        f"**Plan:** {', '.join(f'{key}={value}' for key, value in tactics.items())[:400] or 'Balanced'}",
    ]
    passes = []
    for event in match.get("passes", [])[:8]:
        if not isinstance(event, dict):
            continue
        ix = event.get("pass_no", "?")
        cat = str(event.get("category", "unknown"))
        pts_for = event.get("points_" + mine, 0)
        pts_against = event.get("points_" + other, 0)
        own_fx = event.get("tactics_" + mine) or {}
        foe_fx = event.get("tactics_" + other) or {}
        notes = event.get("notes") or []
        note = next((str(n) for n in notes
                     if any(k in str(n).lower() for k in (
                         "shield", "stagger", "horse", "charge", "line", "slips", "guard",
                     ))), "")
        text = (f"**Pass {ix}:** {PASS_LABELS.get(cat, cat.replace('_', ' ').title())} "
                f"· **{pts_for}–{pts_against} points** · Margin: {event.get('margin',0)}\n"
                f"Your fatigue: {own_fx.get('fatigue', '?')} · "
                f"Alignment mod: {own_fx.get('alignment', '?')} · "
                f"Charge mod: {own_fx.get('charge', '?')}\n"
                f"Opponent fatigue: {foe_fx.get('fatigue', '?')}\n")
        if note:
            text += f"**Key moment:** {note[:240]}\n"
        passes.append(text[:900])
    return {
        "title": f"🧾 Joust Analysis — {str(match.get('id', '?'))[:35]}",
        "summary": "\n".join(summary)[:4000],
        "passes": passes,
        "count": len(passes),
    }
