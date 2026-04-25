# Problem Definition

## Problem We Are Solving

Offensive playcalling in American football involves making fast, high-impact decisions under uncertainty. Coaches must balance field position, down and distance, clock context, score state, and broader strategic considerations. This project aims to create an AI assistant that helps organize those inputs and returns a ranked set of play recommendations.

The goal is not to automate coaching. The goal is to provide structured decision support that improves consistency, speeds up evaluation, and creates a foundation for data-driven play selection.

## Primary User

The primary user is the offensive coordinator.

This user needs:

- Fast recommendations for a specific game situation
- Clear outputs that can support human judgment
- A system narrow enough to trust and evaluate

## Expected System Output

For a given game situation, the system should output top play recommendations.

At a high level, that means:

- A ranked list of candidate plays or play categories
- A score, probability, or confidence-style signal for each option
- A format that is easy to inspect and compare

## What Is Not Included Yet

The current project foundation does not include:

- Reinforcement learning
- Real-time adaptation during live games
- Full opponent modeling
- Autonomous strategy control
- Multi-drive or full-game planning
- Special teams or defensive decision support
- Explainability guarantees beyond basic ranking output

## Design Principle

The first version should stay narrow: given a defined offensive situation, return a short list of useful play recommendations. Everything else can be layered on later.
