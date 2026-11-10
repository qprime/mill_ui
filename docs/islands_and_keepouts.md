# Islands and fixture keepouts

An Island is material a pocket preserves. A Keepout is a fixture zone a cutting tool must not enter. They have separate meanings and separate paths through the compiler.

## Island

An Island must be a direct child of a Rect with a pocket feature. Its geometry becomes bounds subtracted from that pocket's removal region. Unsupported placements fail explicitly.

```yaml
- Rect:
    feature: {type: pocket, depth: 6mm}
    children:
      - Island:
          id: boss
          children:
            - Inset:
                distance: 50mm
                children:
                  - Rect: {}
```

The resolver collects geometry-only bounds, the AST-to-IR adapter produces existing Island constraints, and the pocket planner subtracts those bounds. An island is not a separate machining item. Existing layouts that used Keepout for this purpose must rename it to Island; the pocket's machining output stays the same.

## Keepout

A Keepout declares clamps, screws, or other fixtures in working-area coordinates. Its children produce non-machining Items. The AST-to-IR adapter attaches their bounds as KeepoutRegion constraints to every front-face removal intent. The back setup has independent fixtures and does not inherit front keepouts.

```yaml
- Keepout:
    id: clamp_left
    children:
      - Rect: {at: {x: 20mm, y: 200mm, width: 40mm, height: 60mm}}
```

Fixture geometry is drawn in the blueprint's Keepout Zones layer with its label. Verification uses conservative bounding boxes even for circular zones, expanded by the tool radius. A zone can extend outside the sheet; that does not relax cutting bounds.

One verifier tracks modal XY coordinates across complete cutting segments and plunges, including X-only and Y-only moves. It runs against each program's passes before G-code emission. Unknown cutting positions fail explicitly. A cutting intersection is an error and blocks all G-code for that setup, while diagnostic geometry remains available. The system does not clip profiles or reroute operations around clamps: change the layout to clear them.

Rapid crossings produce warnings naming the zone and safe Z. The operator confirms the fixture is below that height; clamp height is not modeled.

## Zone rules

Both nodes require nonempty geometry-only children. Neither may contain either zone type. Geometry carrying a machining feature is rejected. A Keepout directly under a pocket shape is rejected with guidance to use Island for preserved material.

The sheet margin protects the perimeter; fixture keepouts protect declared zones within or beyond that perimeter. Preserved material islands affect only their pocket.

## Examples

- `docs/recipes/panels/pocket_with_island/`: preserved material.
- `docs/recipes/shop/clamp_keepouts/`: fixture zones around two plates and a disc, with a pocket island on one plate.

Pocket fills do not yet show preserved islands correctly; blueprint hole rendering is tracked separately in #222. Keepout verification and pocket machining do not depend on that rendering fix.
