# Recipe 61: Rest Pocketing

Demonstrates two-tool rest pocketing: a large tool clears bulk material, then a smaller tool finishes corners and perimeter.

**Key concepts:**
- `rest_tool: 3.175mm` for simple form (default 0.5mm rough allowance)
- `rest: { tool: 3.175mm, rough_allowance: 0.3mm }` for explicit allowance control
- Rough pass uses the default pocket tool (6.35mm); rest pass uses the specified smaller tool
- Produces separate G-code files per tool
