"""Throwaway prototype for wayfinder ticket #3.

Verifies: Python-computed absolute coordinates + monospace text => exact node
boxes, no layout package needed, compiles on any engine with only `tikz`.
"""
import json, os, sys, textwrap

# --- measured from LaTeX (measurechar.tex), 10pt document ------------------
PT_PER_CHAR = {"normalsize": 5.24995, "small": 4.724945, "footnotesize": 4.250061}
BASELINESKIP = {"normalsize": 12.0, "small": 11.0, "footnotesize": 9.5}
SIZE = "footnotesize"
CHAR_W = PT_PER_CHAR[SIZE]
LINE_H = BASELINESKIP[SIZE]

WRAP_COLS = 40        # config: max characters per line inside a node
INNER_SEP = 4.0       # pt padding inside the node box
H_GAP = 14.0          # pt between sibling subtrees
V_GAP = 26.0          # pt between levels


# --- model ----------------------------------------------------------------
class Node:
    def __init__(self, kind, name, lines):
        self.kind, self.name, self.lines = kind, name, lines
        self.children = []          # list of (edge_label, Node)
        self.w = self.h = 0.0
        self.x = self.y = 0.0
        self.subtree_w = 0.0


def cond(v):
    if isinstance(v, dict):
        return v.get("condition") or ""
    return v or ""


def wrap(prefix, text):
    if not text.strip():
        return []
    return textwrap.wrap(prefix + text, WRAP_COLS, break_long_words=True,
                         subsequent_indent="  ") or [prefix + text]


def build(n):
    kind = n.get("type")
    lines = []
    lines += wrap("", "%s  %s" % (kind, n.get("name", "")))
    lines += wrap("pre: ", cond(n.get("preCondition")))
    if n.get("programStatement"):
        lines += wrap("", n["programStatement"])
    if kind == "COMPOSITION":
        lines += wrap("mid: ", cond(n.get("intermediateCondition")))
    if kind == "REPETITION":
        lines += wrap("inv: ", cond(n.get("invariant")))
        lines += wrap("var: ", cond(n.get("variant")))
    lines += wrap("post: ", cond(n.get("postCondition")))

    node = Node(kind, n.get("name", ""), lines)
    if kind == "COMPOSITION":
        for k, lbl in (("firstStatement", "1"), ("secondStatement", "2")):
            if isinstance(n.get(k), dict):
                node.children.append((lbl, build(n[k])))
    elif kind == "REPETITION":
        if isinstance(n.get("loopStatement"), dict):
            node.children.append((cond(n.get("guard")) or "loop", build(n["loopStatement"])))
    elif kind == "SELECTION":
        guards = n.get("guards") or []
        for i, c in enumerate(n.get("commands") or []):
            g = cond(guards[i]) if i < len(guards) else ""
            node.children.append((g, build(c)))
    return node


# --- sizing (exact, because monospace) ------------------------------------
def size(node):
    cols = max((len(l) for l in node.lines), default=1)
    node.w = cols * CHAR_W + 2 * INNER_SEP
    node.h = len(node.lines) * LINE_H + 2 * INNER_SEP
    for _, c in node.children:
        size(c)


# --- layout: bounding-box packing, parent centred over children -----------
def measure(node):
    if not node.children:
        node.subtree_w = node.w
        return node.subtree_w
    tot = sum(measure(c) for _, c in node.children) + H_GAP * (len(node.children) - 1)
    node.subtree_w = max(node.w, tot)
    return node.subtree_w


def place(node, left, top):
    """left = left edge of this subtree band; top = y of this node's top edge."""
    node.y = top
    if not node.children:
        node.x = left + node.subtree_w / 2.0
        return
    kids_w = sum(c.subtree_w for _, c in node.children) + H_GAP * (len(node.children) - 1)
    cur = left + (node.subtree_w - kids_w) / 2.0
    child_top = top - node.h - V_GAP
    for _, c in node.children:
        place(c, cur, child_top)
        cur += c.subtree_w + H_GAP
    first, last = node.children[0][1], node.children[-1][1]
    node.x = (first.x + last.x) / 2.0


# --- emit ------------------------------------------------------------------
def pt(v):
    return "%.3f" % v


def emit(node, out):
    out.append(
        "  \\node[cbcnode, text width={w}pt] (n{i}) at ({x}pt,{y}pt) "
        "{{\\{sz}\\ttfamily {body}}};".format(
            w=pt(node.w - 2 * INNER_SEP), i=id(node) % 100000,
            x=pt(node.x), y=pt(node.y - node.h / 2.0), sz=SIZE,
            body="\\\\".join(escape(l) for l in node.lines)))
    for lbl, c in node.children:
        emit(c, out)
        out.append("  \\draw[cbcedge] (n%d.south) -- (n%d.north)%s;"
                   % (id(node) % 100000, id(c) % 100000,
                      (" node[cbclabel,midway]{%s}" % escape(lbl[:22])) if lbl else ""))


def escape(s):
    for a, b in (("\\", "\\textbackslash "), ("&", "\\&"), ("%", "\\%"), ("_", "\\_"),
                 ("#", "\\#"), ("$", "\\$"), ("{", "\\{"), ("}", "\\}"), ("^", "\\^{}"),
                 ("~", "\\~{}")):
        s = s.replace(a, b)
    return s


PREAMBLE = r"""\documentclass{standalone}
\usepackage{tikz}
\begin{document}
\begin{tikzpicture}[
  cbcnode/.style={draw, rounded corners=2pt, align=left, inner sep=%(sep)spt,
                  fill=black!3, line width=0.4pt},
  cbcedge/.style={draw, -latex, line width=0.4pt},
  cbclabel/.style={font=\tiny\ttfamily, fill=white, inner sep=1pt},
]
""" % {"sep": INNER_SEP}


def main(path, outtex):
    d = json.load(open(path, encoding="utf-8"))
    diagram = None
    for e in d.get("content", []):
        if e.get("type") == "diagram":
            diagram = e["content"]
            break
    root = build(diagram["statement"])
    size(root)
    measure(root)
    place(root, 0.0, 0.0)

    body = []
    emit(root, body)
    with open(outtex, "w", encoding="utf-8") as f:
        f.write(PREAMBLE)
        f.write("\n".join(body))
        f.write("\n\\end{tikzpicture}\n\\end{document}\n")

    # report predicted extents
    def ext(n, acc):
        acc.append((n.x - n.w / 2, n.x + n.w / 2, n.y, n.y - n.h))
        for _, c in n.children:
            ext(c, acc)
    acc = []
    ext(root, acc)
    print("nodes=%d  predicted width=%.1fpt (%.1fcm)  height=%.1fpt (%.1fcm)"
          % (len(acc),
             max(a[1] for a in acc) - min(a[0] for a in acc),
             (max(a[1] for a in acc) - min(a[0] for a in acc)) / 28.45,
             max(a[2] for a in acc) - min(a[3] for a in acc),
             (max(a[2] for a in acc) - min(a[3] for a in acc)) / 28.45))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
