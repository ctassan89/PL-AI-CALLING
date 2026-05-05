# MVP Scope

PL-AI-CALLING is currently an offline, deterministic playbook recommendation workflow. The MVP is intentionally narrow: it should validate the data model, keep scoring explainable, and make it easy to test football assumptions against a structured playbook.

## What The MVP Does

- Validates the CSV playbook and taxonomy values
- Recommends plays from a structured situation
- Applies pressure-aware scoring in the shared engine
- Supports sequential down, distance, and field-position updates across a drive
- Supports basic human-readable session inputs for the initial situation and defensive updates

## What The MVP Does Not Do Yet

- No full natural-language understanding
- No automatic opponent scouting from film
- No automatic play design generation
- No clock, score, or broader game-management logic yet
- No hash, formation strength, motion sequencing, or sequencing memory yet
- No penalty, incompletion, turnover, or special result handling in session mode beyond the currently implemented gain/loss and touchdown or turnover-on-downs updates
- No probabilistic model trained on game outcomes yet

## Near-Term Roadmap

1. Improve sequential defensive-context parsing
2. Add coach terminology aliases
3. Improve playbook coverage and pressure tagging quality
4. Add opponent tendency integration tests
5. Add richer game state such as hash, score, clock, and quarter
6. Add a simple UI later

## Definition Of Done For The MVP

- `python3 scripts/validate_data.py` passes
- `python3 -m pytest` passes
- `scripts/suggest_play.py` works
- `scripts/playcaller_session.py` works
- The docs explain how to use both recommendation entry points
