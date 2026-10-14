from __future__ import annotations

# JoustingBot v0.5 balance configuration.
# These values are deliberately kept outside the combat engine so match tuning
# can be adjusted without rewriting the simulation flow.

PASSES_PER_MATCH = 5
WINNING_SCORE = 3

ALIGNMENT_TARGET = 18
MISS_TARGET = 10

REFUSAL_TARGET = 10
SLIP_TARGET = 9
BOLT_TARGET = 8

SLIP_POINT_AWARD = 1
REFUSAL_POINT_AWARD = 1

SLIP_ALIGNMENT_PENALTY = -4
BOLT_ALIGNMENT_PENALTY = -5
POOR_LINE_CHARGE_PENALTY = -3

# Final adjusted-margin thresholds. Higher margins are more decisive.
UNHORSING_MARGIN = 10
SADDLE_STAGGER_MARGIN = 7
HEAVY_SHIELD_HIT_MARGIN = 4
LANCE_BREAK_MARGIN = 2
SHIELD_SCRAPE_MARGIN = 1
