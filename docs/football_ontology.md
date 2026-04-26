# Football Ontology

## Purpose

This document defines the initial offensive football taxonomy for PL-AI-CALLING. Its job is to create a shared concept layer between custom playbook terminology and opponent tendency analysis.

The ontology is intentionally practical rather than exhaustive. It is designed to support play mapping, opponent matching, and recommendation logic in early project phases.

## A. Play Types

### Run

Designed to advance the ball primarily on the ground through a handoff, quarterback run, or run-action structure.

### Pass

Designed to attack through the air, whether by quick rhythm throws, full dropback concepts, movement passes, or run-pass conflict structures.

## B. Run Families

Run concepts are commonly grouped into `zone`, `gap`, and `man` blocking structures, with the exact play family shaped by the point of attack, back read, and blocking intent. This is a useful organizing model for the project's ontology and aligns with common coaching language described in the [GoRout run concepts overview](https://gorout.com/football-running-plays/).

### Inside Zone

Zone run aimed inside the tackle box. Linemen work area-based combinations while the runner reads interior leverage and vertical seams.

### Outside Zone

Zone run designed to stretch the defense horizontally before the runner chooses to bounce, bang, or bend the ball.

### Power

Gap-scheme run built around a defined point of attack, usually with a puller and lead blocker creating an extra gap.

### Counter

Gap-scheme run that uses backfield misdirection and a puller or pullers to influence linebackers and create a delayed point of attack.

### Duo

Physical downhill run often mistaken for inside zone, but built on double teams and linebacker displacement rather than classic zone tracks.

### Trap

Quick-hitting run that invites penetration from a defender who is then trapped by an unexpected blocker, often a pulling lineman or H-back.

### Draw

Delayed run designed to influence pass rush and coverage depth before handing the ball off into lighter interior spacing.

### Screen

Constraint run/pass family that uses misdirection, delayed release, and blockers in space to attack aggressive pursuit.

## C. Pass Families

### Quick Game

Fast-timing pass concepts built for rhythm, leverage reads, and efficient ball distribution.

### Dropback

Traditional pass game from the pocket with deeper route development and fuller field reads.

### Play Action

Pass concepts paired with run action to influence second-level defenders and create throwing windows behind them.

### RPO

Run-pass option structure that places a defender or coverage rule in conflict and lets the quarterback decide post-snap or pre-snap.

### Bootleg

Movement pass off run action, often changing the launch point and stressing edge defenders and underneath coverage.

### Screen

Perimeter or interior pass designed to get the ball out quickly with blockers in front and punish pressure or soft cushion.

## D. Core Pass Concepts

### Mesh

Crossing-route concept built around shallow drags that create traffic and separation underneath. It is widely regarded as a strong man-coverage answer, including in coaching discussions such as this [Mesh concept breakdown](https://coachkoufootball.substack.com/p/top-3rd-down-passing-concepts-in).

### Stick

Quick-game concept built around a stick or option route paired with a flat control route, often used to isolate curl-flat defenders.

### Flood

Three-level stretch concept that overloads one sideline or zone structure with deep, intermediate, and short options.

### Curl/Flat

Quick-game high-low concept that reads a flat defender by pairing a curl or hitch element with an immediate route to the flat.

### Four Verticals

Vertical spacing concept designed to stress deep coverage integrity, seams, and safety leverage.

### Smash

Classic corner-flat stretch with a short route underneath and a corner route over the top, often used against Cover 2 structures.

### Y-Cross

Intermediate/deep crossing concept that creates a horizontal and vertical stress point through an over route from a featured receiver, often the tight end or inside receiver.

## E. Concept Definitions

### Inside Zone

- type: run
- description: Interior zone run with combination blocks and a one-cut read by the back.
- beats: light boxes, overaggressive interior flow, fronts vulnerable to vertical displacement
- weak_against: heavy interior penetration, overloaded boxes, dominant interior defensive tackles

### Outside Zone

- type: run
- description: Perimeter-oriented zone run that stretches the defense horizontally before the runner makes a cut.
- beats: static fronts, slow edge setting, linebackers that overfit inside
- weak_against: fast-flow defenses, hard edge setters, heavy backside pursuit

### Power

- type: run
- description: Gap run with a designed point of attack and a puller creating an extra blocker at the hole.
- beats: even fronts, soft edge support, defenses that struggle with downhill gap fits
- weak_against: heavy penetration, wrong-arm techniques, overloaded run blitzes into the point of attack

### Counter

- type: run
- description: Misdirection gap run that influences linebackers before hitting a delayed lane with pull support.
- beats: fast-flow linebackers, aggressive second-level trigger, defenses that overreact to initial backfield action
- weak_against: disciplined box defenders, edge disruption, penetration that blows up timing

### Duo

- type: run
- description: Downhill run based on double teams and linebacker reads, often attacking interior structure with physical displacement.
- beats: two-high structures, lighter boxes, linebackers slow to fit downhill
- weak_against: interior run blitzes, stacked boxes, quick penetration in the A and B gaps

### Trap

- type: run
- description: Quick interior run that uses a trapping blocker against an upfield defensive lineman.
- beats: penetrating defensive tackles, aggressive interior fronts, slant-heavy movement
- weak_against: disciplined read defenders, backfield disruption, muddy interior traffic

### Draw

- type: run
- description: Delayed handoff that uses pass look and pass rush behavior to open interior running lanes.
- beats: aggressive pass rush, light boxes in passing situations, defenders bailing into coverage depth
- weak_against: disciplined spy or green-dog defenders, interior penetration, obvious draw tendency

### Screen

- type: run/pass
- description: Perimeter or interior constraint play that gets the ball to a runner or receiver behind blockers in space.
- beats: heavy pressure, overaggressive pursuit, defenders playing with soft tackling angles
- weak_against: disciplined retrace, well-triggered perimeter support, defenders reading screen cues early

### Quick Game

- type: pass
- description: Rhythm-based pass family using short timing routes and leverage-based reads.
- beats: off coverage, soft cushions, pressure looks that require fast answers
- weak_against: tight press with disruption, passing-lane defenders, condensed throwing windows

### Dropback

- type: pass
- description: Traditional pocket pass family with fuller route development and progression structure.
- beats: predictable coverage rotations, defenses that cannot pressure with four, favorable matchup isolations
- weak_against: fast pressure, protection breakdowns, disguised post-snap rotation

### Play Action

- type: pass
- description: Pass family using run action to move linebackers and create intermediate or deep windows.
- beats: downhill linebackers, aggressive run defenders, coverage units that overfit the run
- weak_against: disciplined second-level defenders, heavy pressure that disrupts the fake, long-yardage situations where run action has less effect

### RPO

- type: pass
- description: Conflict-based family pairing run action with a quick passing answer keyed to a specific defender or leverage cue.
- beats: overfit box defenders, conflict players in the curl-flat or hook zones, numbers disadvantages in the box or perimeter
- weak_against: muddy post-snap pictures, disguised rotations, defenders coached to exchange responsibilities cleanly

### Bootleg

- type: pass
- description: Movement pass that changes the launch point and typically works off outside zone or similar run action.
- beats: aggressive backside pursuit, static underneath coverage, edge defenders crashing hard on run action
- weak_against: disciplined contain players, fast pursuit to the launch point, pressure off naked edges

### Mesh

- type: pass
- description: Shallow-cross concept that creates traffic and separation underneath.
- beats: man coverage, Cover 1, Cover 0, defenders chasing across the field
- weak_against: disciplined zone drops, robber help inside, pressure that hits before routes develop

### Stick

- type: pass
- description: Quick-game concept pairing a stick route with a flat route to stress curl-flat leverage.
- beats: soft zone, off coverage, linebackers slow to widen
- weak_against: tight man leverage, reroutes on the inside receiver, fast downhill flat defenders

### Flood

- type: pass
- description: Three-level stretch concept that overloads one side of the field.
- beats: Cover 3, spot-drop zone, corner-flat defenders forced to defend multiple levels
- weak_against: pressure to the rollout side, match coverage passing routes cleanly, tight sideline spacing

### Curl/Flat

- type: pass
- description: Simple high-low on the flat defender using a short outside settle route and a route to the flat.
- beats: Cover 2, Cover 3, soft underneath zone leverage
- weak_against: tight man coverage, trap corners, defenders jumping the flat quickly

### Four Verticals

- type: pass
- description: Vertical spacing concept that attacks seams and deep safety leverage with four upfield threats.
- beats: single-high seam stress, Cover 3 voids, safeties late to widen or carry vertical routes
- weak_against: quick pressure, deep two-high structures with disciplined landmark play, protection issues

### Smash

- type: pass
- description: Corner-flat stretch concept using a short hitch or sit route underneath a corner route.
- beats: Cover 2, squat corners, flat defenders forced to choose between short and deep threats
- weak_against: man coverage with strong corner leverage, pressure disrupting timing, defenses matching the corner route well

### Y-Cross

- type: pass
- description: Intermediate/deep crossing concept that stretches linebackers and safeties across the field.
- beats: middle-of-field-open structures, linebackers slow to carry crossers, zone coverage with weak backside help
- weak_against: heavy pressure, bracket treatment on the featured crosser, robbers driving underneath
