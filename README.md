# inkscape-mcp — Claude Code skill

🌐 **English** · [Русский](README.ru.md)

A [Claude Code](https://claude.com/claude-code) skill for working with
[inkscape-mcp](https://github.com/sandraschi/inkscape-mcp) — an MCP server that lets
AI agents create, edit, animate and export SVG vector graphics through Inkscape.

The skill packages everything an agent needs to be productive with the server:

- **Idempotent installer** (`scripts/setup.ps1`) — clone → environment check → install →
  `claude mcp add` → healthcheck. Safe to re-run; also the way to move the setup to another
  Windows machine.
- **Working scripts** (`scripts/`) — reusable raster→clean-vector toolkit built during a real
  logo-remaster session: `font2svg.py` (glyph outlines straight from TTF via fontTools — no
  system font registry involved), `fitgeom3.py` (turns staircase-traced lettering into minimal
  L/A/C primitives: line/arc coverage competition + axis snapping), `smoothmin.py` (vtracer
  smoothing/minify recipe), `build_final.py` (reference implementation of manual-vectorization
  finishing: polygon corner fillets, capsule dash construction, full pen-state relative-subpath
  parser, per-glyph split and reference alignment), `setup.ps1` (idempotent installer).
- **Battle-tested operating guide** (`SKILL.md`) — install steps, gotchas found in practice
  (cmd path mangling from Git-Bash, slow first `uv sync`, session restart needed to load
  MCP tools), recipes for the draw → render → inspect vision loop, and a direct stdio test
  harness for when the tools are not yet loaded in the current session.
- **Honesty audit** of the server's tools — verified end-to-end which operations actually
  produce real results and which silently fake success:

  | Tool / operation | Verdict |
  |---|---|
  | `create_object`, `export_preview`, `inkscape_file convert/info/validate`, `generate_heraldry`, layers, SMIL animations | ✅ works |
  | `trace_image` | ❌ returns `success: true` without creating any file (calls a non-existent Inkscape action) |
  | `generate_barcode_qr` | ❌ renders the data as monospace text, not an actual QR matrix |
  | `create_object` (repeated calls) | ⚠️ each call overwrites the whole document |

## Install

Clone this repository directly into your Claude Code skills folder:

```bash
git clone https://github.com/Jonecuper/inkscape-mcp ~/.claude/skills/inkscape-mcp
```

Restart Claude Code. The skill activates automatically when you ask for something
vector-graphics-related, or invoke it by name.

To actually connect the MCP server on a Windows 10/11 machine (Inkscape 1.2+ and `uv`
required), run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ~/.claude/skills/inkscape-mcp/scripts/setup.ps1 -TargetDir C:\dev\tools\inkscape-mcp
```

…or just ask Claude: *"set up inkscape-mcp on this machine"* — the skill will walk it
through the same script.

## Notes

- `scripts/setup.ps1` must stay **UTF-8 with BOM** — Windows PowerShell 5.1 misparses
  Cyrillic comments otherwise. A `.gitattributes` rule protects it.
- The skill is written for Claude Code but `SKILL.md` is plain Markdown: the operational
  notes and the tool audit are useful reading for anyone automating inkscape-mcp.

Upstream project: https://github.com/sandraschi/inkscape-mcp (server tested here: v3.4.5, Inkscape 1.4.4, 2026-11).

## License

Released under the [MIT License](LICENSE).
