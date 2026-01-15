# mill_ui MCP Server

MCP (Model Context Protocol) server exposing the mill_ui CAM pipeline to Claude.

## Tools

| Tool | Description |
|------|-------------|
| `compile_pml` | Compile PML to G-code + SVG + STL |
| `compile_nest` | Compile .nest file to multi-sheet outputs |
| `list_templates` | List available templates and parameters |
| `validate_pml` | Validate PML without generating outputs |
| `get_syntax_spec` | Get PML/.nest syntax documentation |

## Setup

### 1. Install MCP dependency

```bash
cd /home/squinlan/Code/mill_ui
source venv/bin/activate
pip install "mcp[cli]"
```

### 2. Configure Claude Code

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "mill_ui": {
      "command": "/home/squinlan/Code/mill_ui/venv/bin/python",
      "args": ["-m", "mill_mcp.server"],
      "cwd": "/home/squinlan/Code/mill_ui",
      "env": {
        "PYTHONPATH": "/home/squinlan/Code/mill_ui",
        "MILL_UI_OUTPUT_DIR": "/home/squinlan/cliff_ai/memories/cam_projects/mill_ui"
      }
    }
  }
}
```

## Output Directory

By default, outputs go to:
```
/home/squinlan/cliff_ai/memories/cam_projects/mill_ui/
```

Override with `MILL_UI_OUTPUT_DIR` environment variable.

Each job creates a timestamped subdirectory containing:
- `{job_name}.pml` - PML record
- `{job_name}.svg` - Blueprint visualization
- `{job_name}.stl` - 3D model
- `{job_name}-{pass}.nc` - G-code files
- `metrics.json` - Job metrics

## Usage Examples

### Compile PML

```
compile_pml("sheet 450mm 650mm 19mm\n\nrect door at 225mm,325mm size 400mm,600mm profile through outside")
```

### Compile Nest Job

```
compile_nest("""
nest maxrects
    sheet 1220mm 2440mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        door 400mm 600mm x10
            template Shaker
                stile_w 50mm
                rail_h 50mm
                panel_recess 6mm
""")
```

### Get Syntax Help

```
get_syntax_spec("pml")   # PML syntax
get_syntax_spec("nest")  # .nest syntax
get_syntax_spec("all")   # Both
```

### Validate Before Compile

```
validate_pml("sheet 450mm 650mm 19mm\n\nrect test at 0mm,0mm size 100mm,100mm pocket 5mm")
```

## Development

Run locally for testing:

```bash
cd /home/squinlan/Code/mill_ui
source venv/bin/activate
python -m mill_mcp.server
```

The server uses stdio transport - it reads JSON-RPC from stdin and writes to stdout.
