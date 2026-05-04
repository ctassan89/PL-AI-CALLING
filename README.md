# PL-AI-CALLING

PL-AI-CALLING is a playbook-aware American football playcalling recommendation engine. It validates a versioned CSV playbook, scores plays against the current situation, optionally adjusts recommendations with opponent tendencies, and returns explainable suggestions from your own offensive inventory.

## Data Layout

- Main playbook: `data/playbook.csv`
- Opponent tendencies: `data/opponent_tendencies.csv`
- Taxonomy files: `data/taxonomy/`
- Pressure allowed values: `data/taxonomy/pressure.csv`

The repo is designed to work from a fresh clone with the versioned data that ships inside `data/`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Validate Data

```bash
python scripts/validate_data.py
```

Run the test suite:

```bash
python -m pytest
```

## Request Play Suggestions

```bash
python scripts/suggest_play.py \
  --down 2 \
  --distance 4 \
  --field-zone open_field \
  --front even \
  --coverage cover3 \
  --pressure-id sim_pressure \
  --box-count 6 \
  --personnel 10 \
  --top-n 3
```

Default output is compact and prints only the top recommendations with essential details.

## Show Detailed Reasons

```bash
python scripts/suggest_play.py \
  --down 2 \
  --distance 4 \
  --field-zone open_field \
  --front even \
  --coverage cover3 \
  --pressure-id nickel_blitz \
  --box-count 6 \
  --personnel 10 \
  --top-n 3 \
  --show-reasons
```

## Coverage Vs Pressure

- `beats_coverage` is reserved for coverage structure answers only: `none`, `zone`, `man`, `cover1`, `cover2`, `cover3`, `cover4`, `match`, `soft_zone`
- `beats_pressure` is reserved for blitz and pressure answers only
- Example pressure values:
  - `edge_blitz`: pressure from the edge
  - `nickel_blitz`: pressure brought by the nickel
  - `double_a_gap`: interior mug/double A-gap pressure
  - `sim_pressure`: simulated pressure without a full-out blitz
  - `creeper`: creeper pressure from a disguised front

Example:

```bash
python scripts/suggest_play.py \
  --down 3 \
  --distance 6 \
  --field-zone open_field \
  --front even \
  --coverage cover1 \
  --pressure-id nickel_blitz \
  --box-count 6 \
  --personnel 11 \
  --top-n 5 \
  --show-reasons
```

## Repository Layout

```text
data/
  allowed_values/
  playbook.csv
  opponent_tendencies.csv
  taxonomy/
scripts/
src/
tests/
docs/
```

## Notes

- `scripts/validate_data.py` exposes `validate_data(base_dir: Path | None = None) -> list[str]` for tests and temporary repo fixtures.
- `scripts/suggest_play.py` reads the versioned playbook directly from `data/playbook.csv` by default.
- The recommendation engine deduplicates repeated tactical concepts in the top results so the output is more varied and useful.
