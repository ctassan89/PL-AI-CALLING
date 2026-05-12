# Manual Drive Smoke Tests

These are coach-facing manual QA scenarios for the sequential playcaller. They are not unit tests. The goal is to inspect whether recommendations stay football-coherent across a full drive while defensive context and personnel change.

Base command:

```bash
python3 scripts/playcaller_session.py \
  --opponent Rhinos \
  --opponent-tendencies-path data/opponent_tendencies.csv \
  --top-n 5
```

General checks for every scenario:

- Recommendation blocks should match the situation tag.
- Displayed recommendation numbers should be global across blocks.
- Called-play input should use `call ... gain ...`, not numeric-only yards.
- Personnel entered by the user should hard-filter the recommendations.
- Opponent tendency usage should print clearly, including fallback messaging when exact buckets are missing.
- Screens should only rise when pressure/aggression supports them.
- Play-action / bootleg should not dominate a generic 1st & 10 menu.

## 1. Normal open-field drive

Command: base command above

Inputs:

```text
first and 10 own 25 cover3 even box 6 personnel 11
call 1 gain 4
call 3 gain 3
call Stick TREY gain 6
q
```

Look for:

- 1st & 10 shows `Run options`, `RPO options`, and `Pass options`.
- 2nd medium still looks balanced.
- 3rd short shows physical run and quick conversion answers.

Common failure signs:

- No run block on 1st & 10.
- Bubble/now access RPOs show as primary 3rd-and-medium answers.
- The defense context resets after numeric inputs.

## 2. 10 personnel spread drive

Command: base command above

Inputs:

```text
first and 10 own 30 cover3 even box 6 personnel 10
call 1 gain 5
call 3 gain 2
call 4 gain 4
q
```

Look for:

- Recommendations stay in 10 personnel only.
- 2nd short shows `Shot play`, `Safe conversion`, and `RPO conflict` blocks.
- Spread quick game and conflict answers appear naturally.

Common failure signs:

- 11 or 12 personnel plays appear.
- 2nd short looks like generic 2nd-and-medium output.

## 3. 11 personnel balanced drive

Command: base command above

Inputs:

```text
first and 10 own 35 cover3 even box 6 personnel 11
call 1 gain 4
cover1 box 6
call Stick TREY gain 5
q
```

Look for:

- 11 personnel hard-filter stays intact after the defense update.
- Balanced 11 personnel answers include run, RPO, and pass families.
- Man-coverage answers rise after the `cover1` update.

Common failure signs:

- Personnel filter gets lost after the text update.
- The next recommendation still looks like pure zone answers versus Cover 1.

## 4. 12 personnel heavy / short-yardage drive

Command: base command above

Inputs:

```text
second and 2 own 42 odd_tite cover1 box 8 personnel 12
call 2 gain 1
third and 1 own 43 odd_tite cover1 box 8 personnel 12
q
```

Look for:

- 2nd short shows shot/safe/RPO structure, but safe answers should feel physical.
- 3rd short should strongly surface downhill runs and quick man-beaters.
- Recommendations remain 12 personnel only.

Common failure signs:

- Perimeter fluff dominates short-yardage.
- Soft spread answers appear despite 12 personnel and a loaded box.

## 5. Cover 1 / man-heavy defense drive

Command: base command above

Inputs:

```text
first and 10 own 28 cover1 even box 6 personnel 11
call 3 gain 4
call Stick TREY gain 3
q
```

Look for:

- Quick man-beaters show up on money downs.
- 3rd short or 3rd medium should emphasize conversion concepts that beat man.
- Redundant zone-only answers should not crowd out man answers.

Common failure signs:

- No `Man / pressure` or `Quick / man-beater` style block on later downs.
- Slow-developing concepts dominate obvious man situations.

## 6. Cover 3 zone-heavy defense drive

Command: base command above

Inputs:

```text
first and 10 own 25 cover3 even box 6 personnel 10
call 1 gain 5
call 3 gain 2
call 5 gain 7
q
```

Look for:

- Open-field output stays balanced on 1st down.
- 3rd medium favors intermediate conversion concepts.
- Cover 3 answers can appear without becoming only deep shots.

Common failure signs:

- PA/Boot dominates generic 1st & 10.
- 3rd medium lacks intermediate move-the-sticks answers.

## 7. Heavy pressure defense drive

Command: base command above

Inputs:

```text
second and 8 own 33 cover1 nickel blitz box 6 personnel 10
call 2 gain 0
q
```

Look for:

- Pressure answers and true screens can rise.
- Any screen block should be tied to pressure context, not generic.
- The pressure snapshot should print if tendencies are used.

Common failure signs:

- Screens jump to the top with no pressure support.
- Slow-developing downfield concepts crowd out hot answers.

## 8. Odd front / bear / heavy box drive

Command: base command above

Inputs:

```text
first and 10 own 40 bear cover1 box 8 personnel 11
call 1 gain 2
call 2 gain 2
q
```

Look for:

- Physical run and conflict answers should feel appropriate against the heavy box.
- Screens should not rise unless pressure is also present.
- The engine should still produce useful answers instead of collapsing to one concept family.

Common failure signs:

- Screen-heavy output versus a static heavy box with no pressure.
- Weak perimeter run recommendations dominate versus bear looks.

## 9. Red-zone drive

Command: base command above

Inputs:

```text
first and 10 opp 18 cover1 odd_tite box 7 personnel 11
call 2 gain 6
call 4 gain 3
q
```

Look for:

- Red-zone output shows `Quick / safe answers`, `Man-beater answers`, and `Run / physical answers`.
- Quick answers and man-beaters should be favored over wide-open-field concepts.
- Tendency fallback should print clearly if the exact bucket is thin.

Common failure signs:

- Deep open-field concepts dominate in the red zone.
- No man-beater emphasis against Cover 1.

## 10. Goal-line / short-yardage stress drive

Command: base command above

Inputs:

```text
second and 1 opp 3 cover1 bear box 8 personnel 12
call 1 gain 1
third and 1 opp 2 cover1 bear box 8 personnel 12
q
```

Look for:

- Goal line should show `Physical run options` and `Goal-line pass answers`.
- No RPO-specific goal-line block should appear.
- Physical run options should be credible first answers.

Common failure signs:

- Goal-line output includes an RPO goal-line block.
- Perimeter finesse concepts outrank downhill calls.

## 11. 3rd-down stress drive

Command: base command above

Inputs:

```text
third and 3 own 44 cover1 even box 6 personnel 11
call 1 gain 0
third and 8 own 44 cover3 nickel blitz box 6 personnel 11
q
```

Look for:

- 3rd short shows physical run, quick-man, and tendency-answer structure.
- 3rd long should not show bubble/now RPOs as the screen/constraint answer.
- Pressure answers can rise on the 3rd-and-8 update, but not at the expense of all real conversion concepts.

Common failure signs:

- Bubble/now access RPOs appear as primary 3rd-long screen answers.
- 3rd short lacks a physical run lane entirely.
