# MVP Scope

## MVP Definition

The MVP is an offline play recommendation system for offensive football situations.

It accepts a structured description of a game situation and returns a ranked list of recommended plays or play types. The MVP is intended for early experimentation, evaluation, and iteration. It is not a live game system and it is not a complete football intelligence platform.

## Core Inputs

The MVP should be designed around game-situation variables such as:

- Down
- Distance to first down
- Field position
- Yard line direction
- Quarter
- Time remaining
- Score differential
- Offensive personnel grouping
- Hash or field-side context

These variables define the initial feature space for recommendation logic. The exact schema can be refined later.

## Output Format

The MVP output should be a ranked set of play suggestions.

Example structure:

```text
1. Play: Inside Zone | Score: 0.81
2. Play: Slant/Flat     | Score: 0.74
3. Play: Play Action    | Score: 0.68
```

At minimum, each recommendation should include:

- Rank
- Play name or play family
- Associated score or confidence value

## Assumptions

- The user is evaluating one offensive decision at a time
- Inputs are available in structured form
- Early play outputs may be broad play families rather than full playbook-specific calls
- Initial model quality will depend heavily on data design and labeling consistency

## Limitations

- No reinforcement learning
- No live in-game adaptation
- No opponent-specific tactical engine
- No direct integration with headset, sideline, or broadcast systems
- No full playbook installation logic
- No guarantee that recommendations are optimal in all contexts

## MVP Boundary

If the system can take a game situation and return a short, ranked set of offensive play suggestions in a repeatable way, it satisfies the MVP definition.
