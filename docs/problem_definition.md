# Problem Definition

## Problem

Offensive play-callers need to choose real plays from their own inventory based on down, distance, field position, defensive front, coverage, pressure, box count, personnel, and optional opponent tendencies. Generic football advice is not enough if it cannot be converted into an actual callable play from the installed system.

## Inputs

- Structured playbook
- Game situation
- Defensive context
- Optional opponent tendencies

## Output

- Ranked list of recommended plays
- Score for each recommendation
- Short reasons when requested

## Core Design Idea

The system separates football concepts into structured dimensions instead of relying on a single free-text description:

- Coverage
- Pressure
- Front
- Box
- Down and distance
- Field zone
- Personnel
- Tactical tags

This makes the scoring deterministic, inspectable, and easy to validate from CSV data.

## Why Pressure Is Separate From Coverage

`cover1` with no pressure and `cover1` with a `nickel_blitz` should not be treated as the same situation. Coverage describes the shell or match structure behind the call. Pressure describes how the defense is attacking the pocket. The recommendation engine keeps those dimensions separate so hot answers, screens, quick game, and slower-developing concepts can be scored more honestly.

## Constraints

- Deterministic and inspectable scoring for the MVP
- CSV-first data model
- The validator must catch bad taxonomy values before recommendations are trusted
- Recommendations should remain explainable

## Success Criteria

- Correct plays rise in realistic situations
- Pressure beaters rise against pressure
- Slow-developing plays are penalized under pressure
- Sequential mode stays consistent across a drive
- Documentation is clear enough for a new developer to install, validate, test, and run the project
