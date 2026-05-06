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
3
cover1 nickel blitz box 6
5
q
```

Session behavior:

- Numeric input updates down, distance, and field position.
- Non-numeric input updates defensive context only.
- Defensive context persists until changed.
- The session uses the same `build_situation(...)` and `recommend_plays(...)` functions as `scripts/suggest_play.py`.

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
