# The GCL rendering target

Findings for [#4 — Establish the GCL rendering target](https://github.com/madalime/cbc-to-tikz-converter/issues/4).

This document defines the notation the `gcl` condition renderer emits, the grammar it parses,
and its failure behaviour. It is written to be implementable without further research.

## 1. Source of truth

The notation is **not invented here**. It is taken from the CorC authors' own typesetting of
CbC derivations:

- **Primary.** Tobias Runge, Loek Cleophas, Ina Schaefer, Bruce W. Watson,
  *The Correctness-by-Construction Approach to Programming Using CorC*, CbC Tutorial,
  IEEE SecDev 2021, 18 October 2021.
  [PDF](https://secdev.ieee.org/wp-content/uploads/2021/10/tutorial-A1-schaefer.pdf)
  — slide 9 (the six GCL commands), slides 14–24 (the refinement rules),
  slides 27–33 (a fully worked linear search).
- **Background.** Derrick G. Kourie, Bruce W. Watson,
  *The Correctness-by-Construction Approach to Programming*, Springer, 2012 — the book the
  tutorial's rules are drawn from.
- **Origin.** E. W. Dijkstra, *A Discipline of Programming*, Prentice-Hall, 1976 — GCL itself.

### The tutorial renders our own sample

The tutorial's worked example is the same program as `samples/LinearSearch.json`. Slide 34 even
shows it loaded in WebCorC. This gives us a **ground-truth rendering** to match rather than a
notation we have to guess at.

Slide 33, the final version, typeset by the authors:

```
{ app(A, x, 0, A.len) }
i := A.len − 1;
{ inv ≜ ¬app(A, x, i + 1, A.len) }
do (A_i ≠ x) →
    i := i − 1
od
{ inv ∧ (A_i = x) }
```

The corresponding strings in `samples/LinearSearch.json`:

| JSON | Slide 33 |
| --- | --- |
| `appears(A, x, 0, A.length)` | `app(A, x, 0, A.len)` |
| `!appears(A, x, i+1, A.length)` | `¬app(A, x, i + 1, A.len)` |
| `(A[i] != x)` | `(A_i ≠ x)` |
| `A[i] == x` | `A_i = x` |
| `i = A.length-1;` | `i := A.len − 1` |

Two of those transformations — `appears → app` and `length → len` — are **author-chosen
abbreviations**, not properties of GCL. They are exactly what the configurable symbol table
(§5) exists to express. The rest are mechanical.

## 2. Decisions

Settled with the human before researching, per the map's "research tickets interview first"
constraint:

| Decision | Choice |
| --- | --- |
| Scope | **Conditions only.** `programStatement` stays verbatim Java. |
| Approach | **Full expression parser** — AST, then a GCL pretty-printer. |
| Predicates | **Configurable symbol table**, verbatim fallback for unmapped names. |
| Unparseable input | **Fall back to the verbatim renderer** for that one expression, warn naming the node, keep building. |
| Symbols | **LaTeX macros** (`\land`, `\neq`, …), not Unicode. pdflatex-compatible. |

### Which JSON fields this renderer touches

Every field that holds a predicate or an expression, per the format inventory from
[#2](https://github.com/madalime/cbc-to-tikz-converter/issues/2):

`preCondition`, `postCondition`, `condition`, `intermediateCondition`, `invariant`, `variant`,
each entry of `guards[]`, and each entry of `globalConditions`.

It does **not** touch `programStatement`, `name`, or `javaVariables`.

## 3. Operator and token mapping

Every macro below is plain LaTeX unless the Package column says otherwise.

| Java / JML | GCL | LaTeX emitted | Package |
| --- | --- | --- | --- |
| `&&` | ∧ | `\land` | kernel |
| `\|\|` | ∨ | `\lor` | kernel |
| `!` | ¬ | `\lnot` | kernel |
| `==` | = | `=` | kernel |
| `!=` | ≠ | `\neq` | kernel |
| `<=` | ≤ | `\leq` | kernel |
| `>=` | ≥ | `\geq` | kernel |
| `<` `>` | < > | `<` `>` | kernel |
| `==>` | ⇒ | `\Rightarrow` | kernel |
| `<==>` | ⇔ | `\Leftrightarrow` | kernel |
| `+` | + | `+` | kernel |
| `-` (binary) | − | `-` | kernel |
| `-` (unary) | − | `-` | kernel |
| `*` | · | `\cdot` | kernel |
| `/` | / | `/` | kernel |
| `%` | mod | `\bmod` | kernel |
| `\forall T v; B` | ∀ v : T • B | `\forall v : T \bullet B` | kernel |
| `\exists T v; B` | ∃ v : T • B | `\exists v : T \bullet B` | kernel |
| `true` / `false` | true / false | `\mathrm{true}` / `\mathrm{false}` | kernel |
| `null` | null | `\mathrm{null}` | kernel |

Use `\Rightarrow`, **not** amsmath's `\implies`: `\implies` inserts `\;` padding on both sides,
which is right for a display formula and wrong inside a compact TikZ node label.

### Preamble requirement

Strictly, the mapping above needs **no packages at all** — every macro is in the LaTeX kernel.
`amsmath` + `amssymb` are still the documented requirement, because:

- `\triangleq` (≜, §4) is **amssymb**;
- a user-supplied symbol-table template may reasonably use anything from either package.

So the documented preamble line is:

```latex
\usepackage{amsmath,amssymb}
```

and the renderer must not emit anything requiring more than that without saying so.

## 4. Structural rendering rules

These are AST-shaped rewrites — they cannot be expressed as name lookups, so they are built in
rather than living in the symbol table.

**Identifiers.** A single-character identifier is emitted bare (`i` → `i`, math italic). A
multi-character identifier **must** be wrapped: `newBalance` → `\mathit{newBalance}`. Emitting
it bare makes TeX typeset ten separate italic variables with inter-variable spacing —
`𝑛𝑒𝑤𝐵𝑎𝑙𝑎𝑛𝑐𝑒`. This is the single easiest thing to get wrong here.

**Underscores.** `_` inside an identifier must be escaped as `\_` even inside `\mathit{}`.

**Function and predicate names.** Upright: `\mathrm{app}`, matching the tutorial. Arguments are
recursively GCL-rendered.

**Field access.** `A.length` → `A.\mathrm{length}`, subject to the `identifiers` symbol table
(§5), which is how the tutorial's `A.len` is obtained.

**Array indexing.** Config `gcl.array-notation`, values `subscript` (default) or `bracket`:

| Input | `subscript` | `bracket` |
| --- | --- | --- |
| `A[i]` | `A_i` | `A[i]` |
| `A[j+1]` | `A_{j+1}` | `A[j+1]` |

`subscript` is the default because matching the published notation is the whole reason the GCL
renderer exists — the verbatim renderer is already there for anyone who wants input fidelity.
Caveat worth documenting: nested indexing (`A[A[i]]` → `A_{A_i}`) gets hard to read. No sample
does this, and `bracket` is the escape hatch if it ever shows up.

**Parenthesisation.** Emit only the parentheses precedence requires. Redundant parens in the
input are dropped — `(A[i] != x)` → `A_i \neq x` standing alone, and the slide-33 rendering
keeps them only where the surrounding `∧` makes them useful. Rule: a child is parenthesised iff
its precedence is lower than its parent's, or it is a right operand of equal precedence under a
left-associative operator.

**`\old`.** `\old(E)` → `E_0` by default — consistent with the tutorial's `V_0`/`i_0` for
"value at the start". Overridable through the symbol table. Note that JML's `\old` means "at
method entry" while the tutorial's subscript-0 means "at loop-iteration start"; they coincide
for our purposes but the default is a config key, not a hard-coded truth.

**Definitional equality.** `≜` (`\triangleq`, amssymb) is used by the tutorial for
`inv ≜ ¬app(...)`. Nothing in the JSON produces it — no sample has a named-definition field —
so the renderer never emits it today. It is listed only because it is why `amssymb` is required.

## 5. The predicate symbol table

Three maps, all optional, all with the same precedence as any other setting
(CLI > config > built-in default):

```yaml
gcl:
  array-notation: subscript

  # call sites: name -> LaTeX template, {n} = 0-indexed, recursively rendered argument
  predicates:
    appears: "\\mathrm{app}({0}, {1}, {2}, {3})"
    maxe:    "\\mathrm{max}({0}, {1}, {2}, {3})"
    partSort: "\\mathrm{sorted}({0}[0..{1}))"

  # bare identifiers and field names: name -> LaTeX
  identifiers:
    length: "\\mathrm{len}"

  # override any entry in the §3 table
  operators:
    "==>": "\\longrightarrow"
```

With just the `appears` and `length` entries above, `samples/LinearSearch.json` renders exactly
as slide 33. That is the acceptance test for this renderer.

**Semantics.**

- Key is the name **as written in the source**, before any rendering.
- `{n}` interpolates argument *n*, itself GCL-rendered. Out-of-range `{n}`, or a template whose
  highest index does not match the call's arity, is an **arity mismatch**: warn, and fall back
  to the default rendering for that call (not to verbatim for the whole expression).
- An unmapped name gets the default rendering — `\mathrm{name}(arg, arg, …)`.
- Built-in seed entries: `\old` (§4), `\result` → `\mathit{result}`.
- Templates are emitted **verbatim into math mode** and are not validated. A malformed template
  breaks the LaTeX compile, not the converter. This is deliberate — the templates are an
  escape hatch and should not be second-guessed — but it needs saying in the user docs.

## 6. Grammar

The minimum grammar covering the corpus, lowest precedence first.

**Verified, not asserted.** A throwaway recursive-descent parser implementing exactly this
grammar was run over every condition-bearing field in all five samples:
**55 distinct condition strings, 55 parsed, 0 failures.** The check is reproducible —
see [§11](#11-reproducing-the-grammar-check).

```
expr           := equivalence
equivalence    := implication ( '<==>' implication )*          // left-assoc
implication    := disjunction ( '==>' implication )?           // RIGHT-assoc
disjunction    := conjunction ( '||' conjunction )*
conjunction    := equality ( '&&' equality )*
equality       := relational ( ('==' | '!=') relational )*
relational     := additive ( ('<' | '>' | '<=' | '>=') additive )*
additive       := multiplicative ( ('+' | '-') multiplicative )*
multiplicative := unary ( ('*' | '/' | '%') unary )*
unary          := ('!' | '-' | '+') unary | postfix
postfix        := primary ( '[' expr ']' | '.' IDENT | '(' arglist ')' )*
primary        := INT | 'true' | 'false' | 'null' | IDENT
                | '(' expr ')'
                | quantifier
quantifier     := '(' ('\forall' | '\exists') type IDENT ';' expr ( ';' expr )? ')'
type           := IDENT ( '[' ']' )*
arglist        := ( expr ( ',' expr )* )?

IDENT          := '\\'? [A-Za-z_] [A-Za-z0-9_]*
INT            := [0-9]+
```

Three points that are easy to get wrong:

- **`IDENT` allows a leading backslash.** That is what makes `\old`, `\forall`, `\exists`,
  `\result` fall out of the lexer as ordinary identifiers instead of needing special cases.
- **`==>` is right-associative** and binds looser than `||`. This is JML, not Java.
- **The quantifier has an optional third part.** JML's `(\forall T x; R; P)` means
  `∀x : T • R ⇒ P`. The corpus only uses the two-part form, but the three-part form is standard
  and costs one optional group to support. Render it as `\forall x : T \bullet R \Rightarrow P`.

Whitespace is insignificant and is normalised away — which incidentally fixes the unnormalised
whitespace [#2](https://github.com/madalime/cbc-to-tikz-converter/issues/2) found
(`appears(A, x, 0, A.length)` and `appears(A,x,0,A.length)` both appear in the corpus and render
identically here).

### Deliberately not in the grammar

- **Bounded-quantifier idiom recognition.** The tutorial writes
  `app(A,x,k,ℓ) ≜ ∃i ∈ [k,ℓ) : (A_i = x)`, extracting a range from
  `0 <= m && m < A.length ==> …`. Pattern-matching that shape and rewriting it to
  `∃ i ∈ [k, ℓ)` would be prettier but is a semantic transformation, not a notational one, and
  it silently restructures the user's formula. Render faithfully:
  `\forall m : int \bullet 0 \leq m \land m < A.\mathrm{length} \Rightarrow \dots`.
  Anyone wanting the compact form has the symbol table.
- **Casts, `instanceof`, ternary `?:`, string literals, floats, method chains on literals.**
  None appear in the corpus. They fail to parse and take the §7 fallback, which is the correct
  outcome — better a visibly-verbatim cell than a guessed rendering.

## 7. Failure behaviour

Per-expression, never per-figure:

1. Parse the expression. On success, render it.
2. On a lex or parse error, emit the expression through the **verbatim** renderer instead.
3. Emit one warning per failed expression, naming: the node's `id`, its `name`, the field
   (`preCondition`, `guards[1]`, …), the offending text, and the parser's position and reason.
4. Keep going. The figure is produced; the process exit code is unaffected.

```
warning: node 8fa2c1 'Statement3': could not parse postCondition as GCL
         (unexpected '?' at offset 14), falling back to verbatim
           balance > 0 ? x : y
                       ^
```

Ticket [#11](https://github.com/madalime/cbc-to-tikz-converter/issues/11) owns the global
validation and error-reporting policy, including whether a `--strict` mode promotes these
warnings to errors. This section is only the local default.

## 8. Consequence to eyeball: mixed notation

Scope is conditions-only, so in GCL mode a node shows GCL-rendered conditions **beside**
verbatim Java statements:

```
                 ┌─────────────────────────────────────┐
   pre           │  ¬app(A, x, i+1, A.len)             │   ← GCL
   statement     │  i = i-1;                           │   ← Java, untouched
   post          │  ¬app(A, x, i+1, A.len) ∧ A_i ≠ x   │   ← GCL
                 └─────────────────────────────────────┘
```

Contrast slide 33, where the authors write `i := i − 1`.

This is a known and accepted consequence of the chosen scope, not an oversight — rendering
statements was offered and declined. It is called out here because
[#7 (Prototype the target figure by hand)](https://github.com/madalime/cbc-to-tikz-converter/issues/7)
is where it first becomes visible. If it jars on the page, the cheap remedy is a narrow
addition — assignment-only statement rewriting, `=` → `:=` — rather than reopening the whole
scope decision.

## 9. Interaction with other tickets

- **[#6 IR](https://github.com/madalime/cbc-to-tikz-converter/issues/6)** (blocked by this one).
  The IR must carry conditions as *unrendered source strings*, not pre-rendered LaTeX — renderer
  choice is a backend concern and the same IR has to serve both verbatim and GCL. Whether the
  IR caches a parsed AST is an IR-internal decision.
- **[#8 Node visual form](https://github.com/madalime/cbc-to-tikz-converter/issues/8).**
  GCL structural keywords (`do … od`, `if … [] … fi`, `skip`) belong to #8's node templates, not
  to this renderer. Slide 24 of the tutorial is the reference for how a refinement step is laid
  out; slide 17 uses `elseif` as the selection separator while slide 24 uses Dijkstra's `[]` —
  #8 gets to pick.
- **[#9 CLI/config surface](https://github.com/madalime/cbc-to-tikz-converter/issues/9).**
  New keys from this ticket: `gcl.array-notation`, `gcl.predicates`, `gcl.identifiers`,
  `gcl.operators`. Each needs a CLI equivalent per the map's standing constraint.
- **[#11 Validation policy](https://github.com/madalime/cbc-to-tikz-converter/issues/11).**
  Owns whether §7's warnings can be promoted to errors.

## 10. Acceptance test

`samples/LinearSearch.json`, rendered with

```yaml
gcl:
  predicates: { appears: "\\mathrm{app}({0}, {1}, {2}, {3})" }
  identifiers: { length: "\\mathrm{len}" }
```

must reproduce the conditions of slide 33 exactly:

| Field | Expected LaTeX |
| --- | --- |
| diagram pre | `\mathrm{app}(A, x, 0, A.\mathrm{len})` |
| invariant | `\lnot\mathrm{app}(A, x, i + 1, A.\mathrm{len})` |
| guard | `A_i \neq x` |
| diagram post | `A_i = x` |

The remaining four samples must render without a single §7 fallback warning. That pair — one
exact match against published notation, four clean parses — is the bar.

## 11. Reproducing the grammar check

[`docs/research/gcl-grammar-check.py`](gcl-grammar-check.py) implements §6's grammar as a bare
acceptor — no AST, no rendering — and runs it over every condition-bearing field in `samples/`:

```console
$ python docs/research/gcl-grammar-check.py .

distinct condition strings: 55
parsed OK: 55    failed: 0
```

It is a **research artifact, not production code**. Its only job is to keep §6 honest; the real
parser belongs wherever [#6](https://github.com/madalime/cbc-to-tikz-converter/issues/6) puts it.
`samples/` is gitignored, so the check needs a local copy of the corpus to run.

Re-run it if the grammar in §6 is edited, or if a new sample joins the corpus — a change that
makes the count drop below 55/55 is the signal that §7's fallback path is about to get exercised
in anger.
