# PL-AI-CALLING

PL-AI-CALLING is a long-term decision-support project for American football offensive playcalling. The system is designed to ingest a coach's custom offensive playbook, translate those play names into a shared football concept layer, analyze opponent defensive tendencies, and recommend the best plays from that specific playbook for the situation at hand.

This project is not a generic play prediction tool. It is a playbook-aware opponent tendency recommendation system built to help coaches make faster, more structured, and more explainable playcalling decisions.

## Project Description

The core problem is not simply predicting what play might work in the abstract. Coaches call from their own terminology, formations, tags, and constraints. A useful system must understand:

- what plays exist in the coach's playbook
- what those plays mean in football terms
- how an opponent tends to defend different situations
- which available plays best attack those tendencies

The output is a ranked list of recommended plays from the coach's own playbook, along with brief reasoning tied to concept matchups and opponent behavior.

## System Architecture

The project is organized around three primary components.

### 1. Playbook Layer

Responsible for ingesting and structuring the offensive playbook.

- reads playbook data from coach-defined inputs
- preserves custom naming and internal terminology
- maps each play to a standardized football ontology
- stores concept metadata such as play family, type, and tactical profile

### 2. Opponent Modeling Layer

Responsible for representing how a defense behaves.

- ingests opponent tendency data
- summarizes fronts, coverages, pressure habits, and situational patterns
- normalizes defensive tendency inputs into a format the recommendation engine can use

### 3. Recommendation Engine

Responsible for connecting the playbook to the opponent.

- compares play concepts against defensive tendencies
- scores candidate plays from the available playbook
- returns a ranked list of recommended plays with explanations

## MVP

The MVP is intentionally narrow and offline.

### Input

- `playbook.csv`: coach-defined offensive plays with concept labels
- `opponent_tendencies.csv`: summarized defensive tendencies by situation or coverage tendency

### Output

- ranked recommended plays from the coach's playbook
- short explanation for each recommendation, such as why the concept fits the opponent tendency

### MVP Objective

Demonstrate a clean end-to-end workflow:

1. load a playbook
2. load opponent tendency data
3. score available plays against those tendencies
4. return ranked recommendations

## Data Model

The football data model is split into taxonomy files and raw football data files.

- taxonomy CSV files in `data/taxonomy/` define the allowed football vocabulary
- `data/raw/defensive_tendencies.csv` stores opponent tendencies
- `data/raw/playbook.csv` stores our offensive plays
- `data/opponent_tendencies.csv` is a sample situation-based opponent tendency file for the analyzer
- `front_id`, `coverage_id`, `defensive_personnel_id`, and `formation_id` should reference taxonomy files
- RT/LT should be represented by the `strength` column, not by creating separate formation IDs
- `playbook.csv` uses semicolon-separated values for fields such as `beats_front` and `beats_coverage`
- run validation with `python scripts/validate_data.py`

Key taxonomy references:

- `front_id` describes the defensive box/front structure
- `coverage_id` describes the pass coverage
- `defensive_personnel_id` describes who is on the field for the defense
- `formation_id` describes the offensive formation context

## Development Roadmap

### Phase 0. Foundation

- finalize documentation and repo structure
- define ontology and naming conventions
- create clean package boundaries for future implementation

### Phase 1. Playbook Modeling

- define the playbook CSV schema
- build play-to-concept mapping rules
- validate custom naming against the internal ontology

### Phase 2. Opponent Modeling

- define the opponent tendencies CSV schema
- encode coverage, front, pressure, and situational tendencies
- build normalization and validation utilities

### Phase 3. Baseline Recommendation Engine

- implement rule-based scoring
- rank plays from the available playbook
- generate human-readable explanations for recommendations

### Phase 4. Evaluation and Expansion

- test recommendation quality against real scenarios
- refine concept weights and matchup logic
- prepare for future ML-assisted scoring and product interfaces

## Repository Layout

```text
src/        Core application packages
data/       Input datasets and derived data artifacts
docs/       Project documentation and design notes
models/     Future model artifacts
notebooks/  Exploration and research notebooks
tests/      Automated tests
api/        Future service layer, if needed later
```

## Scoring Philosophy

The recommendation engine is now situation-first.

- down and distance are the strongest scoring inputs
- territory is the next major football constraint
- defensive matchup data such as coverage, front, and box count are secondary adjustments
- opponent tendencies are applied after the base situation score
- explicit guardrail penalties prevent obviously bad top calls such as a pure run on `3rd/4th & very long` when viable pass answers exist

In practice this means:

- a light box can help Inside Zone on `1st & 10` or `2nd & medium`
- that same light box cannot rescue Inside Zone on `3rd & 15`
- pressure can move screens, quick game, and RPOs upward
- likely coverage can separate two otherwise sensible pass calls

## Down And Distance Buckets

The engine accepts either legacy bucket strings or numeric yards-to-go and normalizes them into:

- down buckets: `early_down`, `money_down`
- distance buckets: `short` (`1-2`), `medium` (`3-6`), `long` (`7-10`), `very_long` (`11+`)

Combined situation buckets:

- `1st & 10`
- `2nd & short`
- `2nd & medium`
- `2nd & long`
- `2nd & very long`
- `3rd/4th & short`
- `3rd/4th & medium`
- `3rd/4th & long`
- `3rd/4th & very long`

Situational examples:

- `3rd/4th & long` and `3rd/4th & very long` strongly favor concepts that attack the sticks, screens, and other credible conversion answers
- pure runs receive strong penalties in those situations unless they are specially tagged such as `draw` or `safe_call`
- `2nd & short` allows more aggressive play-action and shot behavior
- `3rd/4th & short` boosts short-yardage runs, quick game, and RPOs

## Field Position Buckets

The current CLI still accepts the project field-zone strings, but the scoring logic maps them into explicit territory buckets:

- `own_redzone` -> `backed_up`
- `own_territory` -> `own_side`
- `midfield` -> `midfield`
- `opp_territory` -> `plus_territory`
- `redzone` -> `red_zone`
- `goal_line` -> `goal_line`

Territory behavior:

- `backed_up` boosts safe calls, quick game, screens, and field-position-safe runs
- `plus_territory` allows somewhat more aggression
- `red_zone` boosts condensed-space calls and penalizes concepts that need deep vertical spacing
- `goal_line` strongly favors goal-line tags, inside runs, quick hitters, and condensed play-action

## Play Tags

The sample `playbook.csv` now includes a backward-compatible optional `tags` column.

Example tags:

- `pure_run`
- `inside_run`
- `short_yardage`
- `draw`
- `safe_call`
- `screen`
- `quick_game`
- `rpo`
- `play_action`
- `boot`
- `shot`
- `vertical`
- `attacks_sticks`
- `slow_developing`
- `pressure_answer`
- `red_zone`
- `goal_line`

Example rows:

```csv
inside_zone_trips,...,tags
inside_zone_trips,...,"pure_run;inside_run;safe_call"
slant_flat,...,"quick_game;pressure_answer;safe_call;red_zone;goal_line"
four_verts_switch,...,"shot;vertical;slow_developing;attacks_sticks"
```

These tags let the engine distinguish between:

- a pure run and a draw
- a quick answer and a slow-developing dropback
- a general pass and a concept that attacks the sticks
- a normal field call and a red-zone or goal-line-specific call

## Opponent Tendency CSV Format

The sample tendency analyzer expects `data/opponent_tendencies.csv` to include these columns:

- `opponent`
- `down`
- `distance_bucket`
- `field_zone`
- `personnel`
- `def_front`
- `box_count`
- `coverage`
- `pressure`
- `play_result`

Example row:

```csv
opponent,down,distance_bucket,field_zone,personnel,def_front,box_count,coverage,pressure,play_result
rhinos,2,short,midfield,11,odd_tite,8,cover3,yes,screen_allowed
```

Notes:

- `coverage` should use the same coverage IDs as `data/taxonomy/coverages.csv`
- `def_front` should use the same front IDs as `data/taxonomy/fronts.csv`
- `box_count` stays numeric in the CSV and is translated into `light_box`, `neutral_box`, `heavy_box`, or `loaded_box` inside the recommendation engine
- `pressure` is expected as `yes` or `no`

## Tendency Analyzer Usage

The analyzer groups rows by the most specific available situation bucket and returns defensive frequencies as probabilities.

```python
from opponent.tendencies import OpponentTendencyAnalyzer

analyzer = OpponentTendencyAnalyzer.from_csv("data/opponent_tendencies.csv")
tendencies = analyzer.lookup(
    {
        "opponent": "rhinos",
        "down": 2,
        "distance_bucket": "short",
        "field_zone": "midfield",
        "personnel": "11",
    }
)
```

Example output:

```python
{
    "coverage": {"cover3": 0.67, "cover1": 0.33},
    "pressure": {"yes": 1.0},
    "box_count": {"8": 0.67, "7": 0.33},
    "def_front": {"odd_tite": 1.0},
}
```

## Tendency-Adjusted Recommendations

The engine now layers scoring in this order:

1. situation score from down, distance, and territory
2. secondary matchup score from coverage, front, box, formation, and playbook preferences
3. tendency adjustments from likely coverage, pressure, and box count
4. explicit guardrail penalties for unrealistic top-call candidates

Representative scoring behavior:

- `3rd/4th & very long` gives large positive value to `attacks_sticks`, `screen`, and credible conversion answers
- pure runs on `3rd/4th & very long` take a near-disqualifying penalty before any tendency adjustments are applied
- high pressure boosts `pressure_answer` tags and penalizes `slow_developing` passes
- high light-box probability can help a viable run, but not enough to erase the money-down run penalty
- high heavy-box probability slightly reduces pure runs and slightly boosts pass/RPO answers

The CLI can now use the optional tendency file when an opponent is supplied:

```bash
python scripts/suggest_play.py \
  --down 2 \
  --distance short \
  --field-zone midfield \
  --formation-id gun_1rb_3x1_spread_no_te \
  --front-id odd_tite \
  --coverage-id cover3 \
  --box-count 7 \
  --personnel 11 \
  --opponent rhinos
```

CLI output includes:

- final score
- an explainable score breakdown with signed reasons
- whether opponent tendencies were used

Example recommendation reasoning:

```text
1. Flood — score 8.5
   Reasons:
   +5.5 situation fit: 3rd/4th & very long favors pass concepts attacking the sticks
   +2.5 coverage fit: strong versus cover3
   -1.8 pressure risk: long-developing concept against likely pressure
```

Example bad recommendation explanation:

```text
Inside Zone — score -7.0
Reasons:
-13.0 situation penalty: pure run on 3rd/4th & very long is near-disqualifying
+1.5 box fit: favorable into light_box
+1.0 formation fit: call is available from the formation
```
