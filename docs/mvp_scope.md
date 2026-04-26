# MVP Scope

## MVP Definition

The MVP is an offline, playbook-aware recommendation workflow.

It takes a coach's offensive playbook and a structured set of opponent defensive tendencies, then returns a ranked list of recommended plays from that same playbook. The MVP exists to validate the project structure, the football ontology, and the recommendation flow before any machine learning or product interfaces are introduced.

## Inputs

### 1. `playbook.csv`

The offensive playbook input should contain, at minimum:

- custom play name
- play type (`run` or `pass`)
- concept or family label
- optional tags such as formation, personnel, or notes

### 2. `opponent_tendencies.csv`

The opponent input should contain structured defensive tendencies, such as:

- coverage tendencies
- front or box tendencies
- pressure tendencies
- situational notes tied to down and distance

The exact column schema can evolve, but the MVP assumes the data is already available in CSV form.

## Outputs

The MVP output is a ranked list of recommended plays with brief explanations.

Each recommendation should include:

- rank
- play name from the coach's playbook
- concept/family
- score or priority value
- short explanation of why the play fits the opponent tendency

Example:

```text
1. Gun Doubles Rt 62 Mesh
   Concept: Mesh
   Score: 0.87
   Why: Strong answer versus heavy man coverage tendency on 3rd-and-medium.
```

## MVP Behavior

The MVP should be able to:

1. read the playbook CSV
2. read the opponent tendencies CSV
3. align play concepts to a shared ontology
4. apply simple recommendation logic
5. return ranked plays with explanation text

## Not Included

The MVP explicitly does not include:

- machine learning models
- reinforcement learning
- real-time or in-game decision support
- UI or dashboard work
- API development
- automated data collection pipelines
- advanced simulation or opponent forecasting

## Boundary

If the system can accept `playbook.csv` and `opponent_tendencies.csv` and produce a ranked, explainable list of plays from the coach's own playbook, the MVP is successful.
