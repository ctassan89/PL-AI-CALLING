# Football Ontology

This document describes the structured football schema used by PL-AI-CALLING. The goal is to keep playbook data inspectable, validate it against stable taxonomies, and let the recommendation engine reason across consistent football dimensions.

## Playbook Schema

`data/playbook.csv` uses this column order:

- `play_id`: stable internal identifier
- `play_name`: coach-facing display name
- `play_family`: broad tactical family such as `dropback`, `run`, `rpo`, or `screen`
- `play_type`: primary type such as `run`, `pass`, or `rpo`
- `run_scheme`: canonical run concept
- `run_modifier`: variation on the run concept
- `pass_concept`: canonical pass concept
- `pass_modifier`: variation on the pass concept
- `protection`: protection family used by the pass concept
- `rpo_tag`: quick answer paired with an RPO when applicable
- `play_action`: `true` or `false`
- `formation_id`: formation taxonomy key
- `personnel`: offensive personnel grouping
- `beats_front`: fronts or front families the play answers
- `beats_coverage`: coverages or coverage families the play answers
- `beats_pressure`: pressures the play answers
- `beats_box`: box structures the play answers
- `preferred_down_distance`: situational down-and-distance tags
- `preferred_field_zone`: situational field-zone tags
- `tags`: tactical descriptors for explainability and tie-breaking

## Coverage Ontology

`beats_coverage` is only for coverage answers. Pressure is modeled separately.

Supported values in the repo and engine:

- `none`
- `zone`
- `man`
- `cover1`
- `cover2`
- `cover3`
- `cover4`
- `match`
- `soft_zone`

Use coverage values when the play is designed to answer structure, leverage, or rotation rules in coverage.

## Pressure Ontology

Pressure is separate from coverage. A call that handles `cover1` with no pressure is not automatically the same answer versus `cover1` plus blitz.

Supported values:

- `none`
- `any_pressure`
- `edge_blitz`
- `field_blitz`
- `boundary_blitz`
- `nickel_blitz`
- `inside_blitz`
- `double_a_gap`
- `zero_pressure`
- `sim_pressure`
- `creeper`

Use `beats_pressure` when the play is a hot answer, screen, protection-friendly concept, or another specific blitz answer.

## Front Ontology

`front_id` describes the defensive structure in the current situation. `beats_front` lists which fronts a play is intended to answer.

Current playbook-facing values in the repo:

- `none`
- `any`
- `even`
- `over`
- `under`
- `odd`
- `odd_tite`
- `bear`

The front taxonomy file in `data/taxonomy/fronts.csv` also maps higher-detail IDs such as `even_4`, `even_over`, `even_under`, `odd_3`, and `odd_mint` to broader structure families. For playbook tagging, stay with currently supported playbook values unless the validator and recommendation layer are extended together.

## Box Ontology

`box_count` is the numeric game-state input. The engine converts it into box labels used by `beats_box`.

Current playbook values:

- `none`
- `light_box`
- `normal_box`
- `heavy_box`
- `loaded_box`

Current engine mapping:

- `5` or fewer -> `light_box`
- `6` -> `normal_box`
- `7` -> `heavy_box`
- `8` or more -> `loaded_box`

## Protection Ontology

`protection` describes the high-level pass protection family used by the play.

Supported values:

- `none`
- `quick`
- `5man`
- `6man`
- `boot`
- `screen`

## Down/Distance Ontology

`preferred_down_distance` is a playbook-side situational tag, not raw yardage input. The engine builds a tag from `down` plus a normalized distance bucket, then rewards exact or related matches.

Current values:

- `early_down`
- `second_short`
- `second_medium`
- `second_long`
- `third_short`
- `third_medium`
- `third_long`
- `fourth_short`
- `fourth_medium`
- `fourth_long`

## Field Zone Ontology

The engine accepts normalized field-zone tags. The sequential session computes them from `field_position`.

Session-friendly mapping:

- `0-40` -> `own_territory`
- `41-60` -> `midfield`
- `61-80` -> `opp_territory`
- `81-95` -> `red_zone`
- `96-100` -> `goal_line`

Engine-side normalization then maps those aliases into its scoring vocabulary, including `open_field`, `high_redzone`, `redzone`, and `goal_line`.

## Tags

`tags` are tactical descriptors. They help explain and separate plays, but they do not replace structured fields such as coverage, pressure, front, box, personnel, or field zone.

Examples already used or supported by the repo include:

- `quick_game`
- `hot_answer`
- `screen`
- `pressure_beater`
- `man_beater`
- `zone_beater`
- `match_beater`
- `deep_shot`
- `intermediate_pass`
- `constraint`

## Nomenclature Rule

The playbook should store canonical football concepts. Coach-specific names can stay in `play_name`, and future alias or display layers can handle local terminology without weakening the shared schema.
