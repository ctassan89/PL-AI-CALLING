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
