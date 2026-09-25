# Recipe 92: String Art

**Status:** Draft
**Difficulty:** Beginner
**Demonstrates:** The `StringArt` node with the `multiply` and `skip` rules on circular and square parents

## Overview

Three 200mm panels on a 700x260mm sheet, each cut out with a through
profile. Each panel places evenly spaced anchors along its outline and
engraves a straight chord from each anchor to a partner chosen by the
rule, 0.3mm deep.

- `cardioid`: a 200mm disc with 120 anchors and `rule: multiply`,
  `factor: 2`. Anchor `i` connects to anchor `2i`; the chords outline a
  cardioid with its cusp a third of the radius left of center.
- `nephroid`: the same disc with `factor: 3`. The chords outline a
  nephroid with cusps above and below the center.
- `star_square`: a 200mm square with 80 anchors and `rule: skip`,
  `step: 23`. Each anchor connects to the one 23 places further round.
  With 20 anchors per edge, no chord lies on the outline, so all 80 are
  engraved.

Change `factor` to get other envelopes on the discs. On the square, keep
both `step` and `80 − step` above 20, or chords between anchors on the
same edge are left out.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `92_string_art.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/92_string_art
```
