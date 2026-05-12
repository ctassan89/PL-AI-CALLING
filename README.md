# PL-AI-CALLING

PL-AI-CALLING is a football play-calling recommendation system. It maps a structured offensive playbook against game situation, defensive structure, and optional opponent tendencies, then returns ranked recommendations from the plays you actually carry.

## Current MVP

- CSV-first playbook in `data/playbook.csv`
- Taxonomy and allowed-values validation through `scripts/validate_data.py`
- Standard CLI suggester driven by the shared recommendation engine
- Pressure-aware scoring with explainable reasons
- Sequential playcalling session that reuses the same engine path
- Basic human-readable initial situation parsing such as `primo e 10 own 25 cover3 even box 6 personnel 10`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest
python3 scripts/validate_data.py
```

## Main Commands

```bash
python3 scripts/validate_data.py
python3 -m pytest
python3 scripts/suggest_play.py --help
python3 scripts/playcaller_session.py --top-n 5
```

## Standard Suggester

Example:

```bash
python3 scripts/suggest_play.py \
  --down 3 \
  --distance 6 \
  --field-zone open_field \
  --front-id even \
  --coverage-id cover3_buzz_field \
  --pressure-id nickel_blitz \
  --box-count 6 \
  --personnel 11 \
  --top-n 5 \
  --show-reasons
```

The standard suggester builds a normalized situation with `build_situation(...)` and ranks plays through `recommend_plays(...)`.

Ranking happens in three passes:

- The engine computes base football-fit scores from down/distance, field zone, defensive structure, pressure, and risk/reward.
- It then applies lightweight contextual reranking adjustments, such as preferring play-action only in good play-action spots and de-emphasizing screens when pressure is not present.
- It finishes with diversity penalties so the top recommendations are less likely to be filled with near-duplicate concepts across play-action variants or very similar formations.

Coverage handling stays intentionally split:

- `data/taxonomy/coverages.csv` is the full defensive coverage taxonomy, including specific variants like `cover3_buzz_field` and `cover7_stubbie_trips`.
- `beats_coverage` in `data/playbook.csv` is the playbook-facing answer list and should stay mostly generic, such as `cover3`, `zone`, or `match`.
- `data/taxonomy/coverage_values/coverage_id.csv` is the allowed input list for defensive `coverage_id` values.
- The engine maps `coverage_id -> base_coverage -> coverage_family`, so a play tagged with `beats_coverage=cover3` can still match an input of `cover3_buzz_field`.

## Sequential Session

Start a drive:

```bash
python3 scripts/playcaller_session.py --top-n 5
```

Example flow:

```text
Initial situation:
primo e 10 own 25 cover3 even box 6 personnel 10

Then:
call 1 gain 7
cover1 nickel blitz box 6
call Stick TREY gain 5
q
```

Session behavior:

- Called-play input uses `call ... gain ...`, for example `call 3 gain 8` or `call IZ Insert DOT gain 6`.
- Displayed recommendation numbers are global across all shown blocks.
- Exact play names are allowed if they exist in the playbook.
- Numeric-only yard input is rejected.
- Non-numeric input updates defensive context only.
- Defensive context persists until changed.
- The session uses the same `build_situation(...)` and `recommend_plays(...)` functions as `scripts/suggest_play.py`.

## Manual QA And Logging

Manual sequential-drive smoke tests live in [tests/manual_drive_tests.md](/home/carlo/PL-AI-CALLING/PL-AI-CALLING/tests/manual_drive_tests.md).

Run the tendency coverage audit:

```bash
python3 scripts/audit_tendencies.py --opponent Rhinos
```

Run the sequential session with an optional CSV log:

```bash
python3 scripts/playcaller_session.py \
  --opponent Rhinos \
  --opponent-tendencies-path data/opponent_tendencies.csv \
  --top-n 5 \
  --save-log logs/rhinos_drive_01.csv
```

Session log review still works through `scripts/view_session_log.py`, including called-play details from newer logs.

## Viewing Session Logs

```bash
python3 scripts/view_session_log.py logs/test_drive_01.csv
python3 scripts/view_session_log.py logs/test_drive_01.csv --compact
python3 scripts/view_session_log.py logs/test_drive_01.csv --snap 3
```

## Data Files

- `data/playbook.csv`: structured offensive inventory used for recommendations
- `data/opponent_tendencies.csv`: optional opponent lookup table for tendency adjustments
- `data/taxonomy/coverages.csv`: full defensive coverage taxonomy, including specific variants
- `data/taxonomy/playbook_values/*`: playbook-facing allowed values used to validate `data/playbook.csv`
- `data/taxonomy/coverage_values/*`: allowed values used to validate columns inside `data/taxonomy/coverages.csv`

## Repository Layout

```text
data/
docs/
scripts/
src/
tests/
```

## Development Notes

- Keep the playbook CSV schema stable.
- Run `python3 scripts/validate_data.py` before trusting recommendation output.
- Run `python3 -m pytest` after code or data changes.
- Prefer updating taxonomy values in `data/taxonomy/` rather than introducing ad hoc strings in code.
