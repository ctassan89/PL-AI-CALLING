# Problem Definition

## The Real Problem

Offensive coaches do not need a generic football answer. They need actionable playcalling support that fits their own system.

Every offense has its own language, play names, tags, formations, and constraints. A recommendation such as "call a run" or "attack the flat" is too vague to be operational on game day. A useful system must be able to work from the actual playbook the coach carries and turn opponent information into a concrete list of callable plays.

The real problem, then, is this:

How do we help a coach select the best plays from their own playbook against the specific defensive tendencies of a given opponent?

## Why Generic AI Is Not Enough

A generic AI model can talk about football concepts, but that is not enough for serious playcalling support.

Generic outputs fail in several important ways:

- they do not understand the coach's custom terminology
- they do not know which plays are actually installed
- they cannot reliably distinguish between similar plays with different coaching intent
- they may recommend concepts that do not exist in the offense
- they often provide broad advice instead of executable playcalls

In football, usefulness depends on context and availability. The system must know both what the offense can call and what the defense tends to allow or take away.

## Why Playbook Modeling Matters

The playbook is the operational boundary of the offense. It defines the menu of realistic options.

To support playcalling, the system must ingest custom play names and map them to a standardized concept layer. That concept layer is necessary because different teams may use different names for the same idea, and the same family of concepts may appear in multiple forms across formations or personnel groupings.

Playbook modeling makes it possible to:

- preserve coach terminology
- compare plays using shared football concepts
- group similar calls into families
- reason about which concepts are available in the offense

Without this layer, the system cannot move from abstract football knowledge to practical recommendation.

## Why Opponent Modeling Matters

Playcalling is not only about what the offense likes. It is also about what the defense shows repeatedly.

Opponent modeling captures tendencies such as:

- coverage preferences
- front structure
- pressure frequency
- situational habits by down, distance, and field area
- overplays or weaknesses against specific concept families

These tendencies create the tactical context for recommendation. A concept is only valuable if it aligns with what the defense is likely to present or struggle against.

## Final System Behavior

The target system behavior is straightforward and coach-facing:

1. ingest a custom offensive playbook
2. map each play to a structured football ontology
3. ingest opponent defensive tendency data
4. compare available plays against those tendencies
5. return a ranked list of recommended plays from the coach's own playbook
6. explain each recommendation in football terms

The system is not intended to replace coaches. It is intended to give them a structured decision-support tool that is grounded in their terminology, their available calls, and the opponent they are preparing to attack.
