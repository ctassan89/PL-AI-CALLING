# PL-AI-CALLING

PL-AI-CALLING is a playbook-aware American football playcalling recommendation engine. It validates a custom playbook stored in CSV files, scores plays against game situation and defensive structure, optionally adjusts recommendations using opponent tendencies, and returns explainable play suggestions.

## Current Status

This project is currently an offline MVP. It includes:

- CSV-based playbook representation
- data validation scripts
- rule-based play scoring
- opponent tendency adjustment
- CLI play suggestion
- explainable scoring output

It is not production-ready yet and does not use machine learning for recommendation scoring.

## Quickstart

```bash
git clone https://github.com/ctassan89/PL-AI-CALLING.git
cd PL-AI-CALLING

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python scripts/validate_data.py
```

## Running the Project

Validate the CSV data:

```bash
python scripts/validate_data.py
```

Run the test suite:

```bash
python -m pytest
```

Generate play suggestions from the CLI:

```bash
python scripts/suggest_play.py \
  --down 3 \
  --distance 5 \
  --field-zone open_field \
  --front-id even \
  --coverage-id cover1 \
  --box-count 6 \
  --personnel 10 \
  --top-n 10
```

## Repository Layout

```text
src/        Recommendation engine and opponent tendency logic
scripts/    CLI and validation scripts
data/       Playbook, taxonomy, and sample tendency CSV files
tests/      Automated tests
docs/       Deeper project and design documentation
```

## Data Overview

The main input files are:

- `data/playbook.csv`: validated offensive playbook entries and metadata
- `data/opponent_tendencies.csv`: sample opponent tendency input for the analyzer
- `data/taxonomy/`: allowed football vocabulary used by validation and scoring

Before scoring recommendations, validate the data to catch schema or vocabulary issues.

## Documentation

For deeper background and design notes, see:

- [docs/problem_definition.md](docs/problem_definition.md)
- [docs/mvp_scope.md](docs/mvp_scope.md)
- [docs/football_ontology.md](docs/football_ontology.md)

## Example Output

The recommender returns ranked plays with component-based reasons, for example:

- down-and-distance fit
- field-zone fit
- coverage/front/box fit
- tactical bonuses and penalties
- risk/reward context

## Roadmap

Near-term priorities are:

- continue refining the rule-based scoring model
- improve recommendation quality and explainability
- expand evaluation scenarios and tests
- prepare the codebase for future service and UI layers
