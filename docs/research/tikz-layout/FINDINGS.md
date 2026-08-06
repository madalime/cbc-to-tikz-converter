# Choosing the TikZ tree-layout mechanism

Research for [#3 Choose the TikZ tree-layout mechanism](https://github.com/madalime/cbc-to-tikz-converter/issues/3),
under [Map: WebCorC JSON to TikZ converter spec](https://github.com/madalime/cbc-to-tikz-converter/issues/1).

## Recommendation

**Python computes absolute coordinates; TikZ only draws.** The emitted fragment uses nothing
but `\node[...] at (x,y)` and `\draw`, so the only LaTeX dependency is `tikz` itself.

Node text is set in a **monospace font**, which is what makes this exact rather than estimated
(see below). `forest`, `graphdrawing`, and `matrix` are all rejected for the primary path, but the
seam keeps them implementable.

## The decisive fact: monospace makes Python's size model exact

The usual objection to Python-side layout is that only LaTeX knows how big a node is. That
objection dissolves in a monospace font. Measured on this machine (`measurechar.tex`, 10pt
document, Computer Modern Typewriter):

| Sample | Width |
|---|---|
| `\ttfamily M` | 5.24995pt |
| `\ttfamily i` | 5.24995pt |
| `\ttfamily MMMMMMMMMM` | 52.49954pt (exactly 10x) |
| `\ttfamily\small` per char | 4.724945pt |
| `\ttfamily\footnotesize` per char | 4.250061pt |
| `\baselineskip` @10pt | 12.0pt |

Every glyph is the same width, so:

```
node_width  = max_line_length_in_chars * CHAR_WIDTH + 2 * inner_sep
node_height = line_count * BASELINESKIP     + 2 * inner_sep
```

Both are exact integers-times-a-constant, known before a single line of LaTeX runs. Crucially,
**Python also does the line wrapping** and emits explicit `\\` breaks, so LaTeX never re-wraps and
never surprises us.

Monospace is also the right look on the merits: node content is program statements and
JML-ish conditions — `A[j+1] = tmp;`, `(\old(balance) + x >= limit ==> ...)`. It is code.

### Verified end to end

Generated `Bubblesort.json` (13 nodes, depth 8 — the deepest sample) via `proto_layout.py`:

| | Width | Height |
|---|---|---|
| Python predicted | 934.0pt | 768.5pt |
| pdfLaTeX actual | 930.9pt | 764.6pt |
| LuaLaTeX actual | 930.9pt | 764.7pt |

Under 0.5% error — the residual is the `standalone` border and the 0.4pt stroke width, both of
which a real implementation accounts for explicitly. The two engines agree to within 0.1pt, so
**the output is engine-independent**: it compiles as-is under pdfLaTeX, LuaLaTeX or XeLaTeX.

See `bubblesort-render.png` for the result: no overlaps, no overflowing text, n-ary `SELECTION`
and the deep `REPETITION`/`COMPOSITION` chain both laid out correctly.

## Why not the alternatives

| Mechanism | Verdict |
|---|---|
| **`forest`** | Genuinely good at trees and node-size aware. But layout happens inside LaTeX, so *we* cannot know the figure's extent, cannot reason about page overflow, and cannot test layout without compiling. Adds a package dependency. Rejected as primary, kept viable via the seam. |
| **`graphdrawing`** | LuaLaTeX-only. Overleaf offers LuaLaTeX, so this is not fatal — but it forces the engine choice onto every document that includes the fragment, for no benefit over the recommended path. Rejected. |
| **`matrix` of nodes** | A rigid grid is a poor fit for a tree with wildly varying subtree widths; it wastes horizontal space badly, and these figures are already too wide. Rejected. |
| **Absolute coordinates** | **Recommended.** Zero LaTeX layout packages, engine-independent, fully testable in Python without invoking LaTeX at all. |

The trade normally paid for absolute coordinates — owning text measurement — is paid in full by
the monospace decision, and refundable via the measurement seam if a proportional font is ever
wanted.

## Dependencies

- **Python:** none beyond the standard library (`json`, `textwrap`, `dataclasses`). Nothing to add
  to `requirements.txt` for layout.
- **LaTeX (fragment):** `tikz` only.
- **LaTeX (`--standalone` preview):** `tikz` + `standalone`.

Both are in TeX Live and therefore present on Overleaf without installation.

## Layout algorithm

The prototype uses **bounding-box packing**: subtree width is
`max(own_width, sum(child_widths) + gaps)`, children are laid left to right, and the parent is
centred over its children. For trees of this size (samples run 1-13 nodes) this is sufficient and
easy to reason about.

The known upgrade, if figures ever need tightening, is the **Reingold-Tilford** tidy-tree
algorithm in the linear-time **Buchheim/Junger/Leipert** formulation, which uses left/right
contours instead of bounding boxes and packs sibling subtrees more tightly. It handles variable
node sizes and n-ary branching natively. This is an internal change to one strategy, invisible
through the seam.

## The layout-strategy seam

The seam must not leak "Python computes coordinates", or `forest` becomes unimplementable behind
it. The trick is that a layout strategy returns a **result union**, not a coordinate list:

```python
@dataclass(frozen=True)
class Box:            # what a measurer produces per node
    lines: tuple[str, ...]
    width: float      # pt
    height: float     # pt

@dataclass(frozen=True)
class Placed:         # Python-computed geometry
    positions: dict[NodeId, tuple[float, float]]   # centre, pt
    boxes: dict[NodeId, Box]
    bbox: tuple[float, float, float, float]

@dataclass(frozen=True)
class Deferred:       # LaTeX-computed geometry (forest, graphdrawing)
    body: str                       # e.g. a forest bracket expression
    requires: tuple[str, ...]       # extra \usepackage lines
    engine: str | None              # e.g. "lualatex", or None for any

LayoutResult = Placed | Deferred

class Measurer(Protocol):
    def measure(self, lines: Sequence[str]) -> Box: ...

class LayoutStrategy(Protocol):
    name: str
    def layout(self, tree: RenderTree, measurer: Measurer, opts: LayoutOpts) -> LayoutResult: ...
```

Three things this buys:

1. **`Measurer` is its own seam.** `MonospaceMeasurer` is exact today; a future
   `LaTeXProbeMeasurer` (two-pass: compile, read box dimensions from the log, re-emit) would allow
   proportional fonts without touching any layout strategy.
2. **`Deferred` keeps `forest` honest.** A `ForestStrategy` returns the bracket expression and
   declares `requires=("forest",)`. The output backend handles both variants; nothing else changes.
3. **`bbox` on `Placed` is why the recommended path is worth having.** Knowing the figure's extent
   in Python is what makes page-overflow handling possible at all — a `Deferred` layout simply
   cannot answer "will this fit".

`LayoutOpts` carries orientation (`top-down` default, per the map's decision), gaps, and the font
size — each a CLI flag with a config default, per the map's standing constraint.

## Finding that affects the map

The 13-node `Bubblesort` figure is **32.7cm x 26.9cm** — wider than an A4 page is tall. Overflow is
not an edge case for large inputs; it is the normal case for the samples we already have. This
sharpens the map's "tree overflows the page" fog into a real, ticketable question.
