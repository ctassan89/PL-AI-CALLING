# PL-AI-CALLING

PL-AI-CALLING is a long-term AI project focused on supporting offensive playcalling in American football. The objective is to build an assistant that helps an offensive coordinator evaluate a game situation and receive a small set of strong play recommendations.

## Goal

The system is intended to act as an AI assistant for offensive playcalling, not as a replacement for coaching judgment. It should take structured game-context inputs and return ranked play suggestions that can support faster and more consistent decision-making.

## Version 0.1 Scope

Version 0.1 is focused only on play recommendation.

Included in scope:

- Structured representation of game situation inputs
- A pipeline for generating ranked play recommendations
- Offline experimentation and evaluation
- Clear interfaces for future model and API integration

Not included in scope:

- Full game intelligence
- Real-time in-game adaptation
- Reinforcement learning
- Opponent simulation
- Autonomous game management

## High-Level Roadmap

### Phase 0: Foundation

- Define project structure
- Document the problem and MVP boundaries
- Establish a scalable development workflow

### Phase 1: Data and Representation

- Define core football situation variables
- Design play label taxonomy
- Prepare datasets and data-processing conventions

### Phase 2: Baseline Recommendation System

- Build a first recommendation pipeline
- Create simple evaluation metrics
- Compare baseline model approaches

### Phase 3: Internal Tools

- Add experiment tracking and model versioning
- Introduce APIs for local usage
- Improve testing and reproducibility

### Phase 4: Product Layer

- Build a web application or dashboard
- Expose recommendations through a usable interface
- Prepare for broader decision-support workflows

## Tech Stack Placeholder

- Python for core development
- Machine learning models for recommendation
- Jupyter notebooks for exploration
- API layer for future integration
- Web app to be added later

## Repository Layout

```text
src/        Core application code
data/       Datasets and data artifacts
notebooks/  Research and exploration notebooks
models/     Saved models and model-related assets
api/        Future service layer and endpoints
docs/       Project documentation
tests/      Automated tests
```
