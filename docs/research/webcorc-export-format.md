# The WebCorC export format

Research findings for [#2 — Inventory the WebCorC export format from the samples](https://github.com/madalime/cbc-to-tikz-converter/issues/2).

**Evidence base:** the five files in `samples/` — `SimpleAddition`, `LinearSearch`, `Transaction`, `MaxElement`, `Bubblesort` — and nothing else. The ticket fenced this deliberately: no WebCorC documentation, no source, no external material was consulted. Every claim below is either *observed* across those five files or explicitly marked as **not derivable**.

`samples/` is gitignored, so this document is the durable record of what those files contain.

**Corpus size:** 5 documents, 5 diagrams, 33 statement nodes, 117 condition strings (55 distinct), 15 variable declarations, 3 KeY include files.

Counts are stated as `k/n` throughout: *k* occurrences confirmed out of *n* opportunities. `5/5` means every sample; `33/33` means every statement node.

---

## 1. Envelope

The document is a small read-only filesystem: a tree of **inodes**.

```
root (directory, urn "")
├── <name>.diagram   (file, type "diagram")   ← the refinement tree
└── include/         (directory)              ← OPTIONAL, absent in 2/5
    └── *.key        (file, type "key")       ← KeY predicate definitions
```

Two inode shapes:

| | directory | file |
|---|---|---|
| keys | `urn`, `content`, `inodeType` | `urn`, `inodeType`, `type`, `content` |
| `inodeType` | `"directory"` | `"file"` |
| `content` | array of inodes | object (`diagram`) or string (`key`) |

**`content` is polymorphic across three shapes** — array, object, or string — discriminated by `inodeType` and then `type`. This is the format's main parser trap: never index `content` without checking `inodeType` first.

Observed facts:

- The root is always exactly `{"urn": "", "content": [...], "inodeType": "directory"}` — those three keys, `urn` always the empty string. 5/5.
- Maximum nesting depth observed is **2** (root → `include/` → `.key`). Samples without an `include/` directory are depth 1. Nothing observed constrains depth further; the structure is recursive.
- `urn` on a file is its path relative to the root: `bubblesort.diagram` at top level, `include/predicates.key` nested. The directory's own `urn` is the bare segment `include`. Consistent 5/5.
- Exactly **one** `.diagram` file per document, always at root level. 5/5.
- `type: "key"` files carry raw KeY source as a **single string** with embedded `\n`. Out of scope for the figure (map's Out-of-scope list), but they are where user-defined predicates like `appears`, `maxe`, `partSort` are actually defined.

**Not derivable from samples:** whether a document may contain more than one `.diagram`. The array structurally permits it and all five samples have exactly one. This is the open question behind the map's *"Whether one export containing multiple diagrams should produce multiple figures"* fog item — the samples cannot settle it.

### Diagram name vs. file name

| `urn` | `content.name` |
|---|---|
| `simpleAddition.diagram` | `SimpleAddition` |
| `linearSearch.diagram` | `LinearSearch` |
| `maxElement.diagram` | `MaxElement` |
| `transaction.diagram` | `Transaction` |
| `bubblesort.diagram` | `bubblesort` |

The urn stem is lowerCamel; `content.name` is usually UpperCamel but `bubblesort` is not. **Derive the figure title from `content.name`, never from the urn** — the casing relationship does not hold.

---

## 2. The diagram node

The `content` of the `.diagram` file. Ten keys, all present 5/5, in this order:

| field | type | observed |
|---|---|---|
| `name` | string | 5/5, non-empty |
| `preCondition` | `{condition: string}` | 5/5 |
| `postCondition` | `{condition: string}` | 5/5 |
| `verifierConditions` | **object** | `{}` in 5/5 |
| `javaVariables` | array of `{name, kind}` | 1–4 entries, 5/5 non-empty |
| `globalConditions` | array of `{condition}` | empty in 2/5, 4–5 entries in 3/5 |
| `renamings` | array | `[]` in 5/5 |
| `isProven` | bool | `false` in 5/5 |
| `position` | `{xinPx, yinPx}` | `{0, 0}` in 5/5 |
| `statement` | statement node | 5/5 |

**The diagram is not a statement node.** It has no `id`, no `nodeState`, and no `type` field of its own (its `type` lives on the enclosing file inode). Any IR that models "node" uniformly must treat the diagram as a distinct root kind, not as a sixth statement type.

**`javaVariables[].name` is an undivided declaration string** — `"int i"`, `"int[] A"`, `"int tmp"`. Type and identifier are *not* separate fields; splitting them means parsing the string, and `int[] A` shows the type may contain brackets. `kind` is `"LOCAL"` in 15/15 — no other value observed, so the enum's full range is **not derivable**.

---

## 3. Statement nodes

Nine fields common to all five types, present 33/33, in this order:

`name`, `type`, `preCondition`, `postCondition`, `position`, `isProven`, `verifierConditions`, `id`, `nodeState`

then type-specific fields:

| type | n | additional fields | children |
|---|---|---|---|
| `STATEMENT` | 14 | `programStatement` (string) | — |
| `SKIP` | 3 | *none* | — |
| `COMPOSITION` | 9 | `intermediateCondition`, `verifierIntermediateConditions`, `firstStatement`, `secondStatement` | exactly 2 |
| `REPETITION` | 4 | `variant`, `invariant`, `guard`, `isVariantProven`, `isPreProven`, `isPostProven`, `loopStatement` | exactly 1 |
| `SELECTION` | 3 | `guards` (array), `isPreProven`, `commands` (array) | *n*, index-aligned |

**Within a type, no field was ever absent.** Every field listed appears on every node of that type. There are no optional fields *inside* a statement node in this corpus — the only optionality observed anywhere in the format is the `include/` directory.

Note `SELECTION` carries `isPreProven` but **not** `isPostProven` or `isVariantProven`; `REPETITION` carries all three. The proof-flag set is type-specific, not uniform.

### Conditions are uniformly wrapped

Every condition-bearing slot in the format is the same single-key object `{"condition": "<string>"}` — never a bare string:

`preCondition`, `postCondition`, `intermediateCondition`, `guard`, `invariant`, `variant`, each element of `guards[]`, each element of `globalConditions[]`.

This holds even for `variant`, which is an *integer* expression (`"i"`, `"A.length - j"`, `"j+1"`), not a boolean. One `Condition` type covers the whole format; the boolean/integer distinction is not marked in the JSON and must be inferred from the field name.

All 117 condition strings are non-empty, single-line, and free of leading/trailing whitespace. The longest is 121 characters.

### `SKIP` placement

All 3 `SKIP` nodes appear as the *second* command of a `SELECTION` — never as a composition branch or a loop body. Whether the editor permits `SKIP` elsewhere is **not derivable**; a parser should accept it in any child slot regardless.

---

## 4. The condition-chaining invariants

These are the strongest results in the corpus, and the most useful to a renderer. All were checked mechanically, not by eye.

### 4.1 Non-repetition children match their slot exactly

For every child that is **not** a `REPETITION`, the child's `preCondition` and `postCondition` are **textually identical** to the contract of the slot it occupies:

| relationship | holds |
|---|---|
| `diagram.pre/post` == `diagram.statement.pre/post` | 5/5 |
| `composition.firstStatement.pre` == `composition.pre`, `.post` == `intermediateCondition` | 8/8 |
| `composition.secondStatement.pre` == `intermediateCondition`, `.post` == `composition.post` | 6/6 |
| `selection.commands[i].post` == `selection.post` | 6/6 |

Identical as strings, not merely equivalent as formulas. A renderer can therefore print each edge's condition once, at the parent, without risk of contradicting the child.

### 4.2 `SELECTION` guards and commands are index-aligned pairs

- `len(guards) == len(commands)` in 3/3 selections.
- All 3 selections are **binary** (`n = 2`). No selection with 1, 3, or more branches appears in the corpus — so the n-ary branching the map anticipates is real in the schema but **unexercised by the samples**.
- The pairing is confirmed by a textual derivation that holds in **6/6** pairs:

  ```
  commands[i].preCondition == selection.preCondition + " && " + guards[i].condition
  ```

  Exactly, including spacing. This is strong evidence the editor generates the command's precondition by conjoining the guard onto the selection's precondition.

**No implicit else.** In all 3 selections the two guards are explicit complements written by the author — `A[j] > A[i]` / `A[j] <= A[i]`, `newBalance >= limit` / `newBalance < limit`, `A[j] > A[j+1]` / `A[j] <= A[j+1]`. Totality is stated, never implied, and there is no fallback branch to synthesise.

Because nothing in the format *enforces* equal array lengths, a parser should **validate** `len(guards) == len(commands)` and fail loudly rather than `zip()` silently.

### 4.3 A `REPETITION` node's pre/post describe its body, not its slot

**This is the anomaly to design around.** For all 4 repetitions:

```
REPETITION.preCondition  == invariant && guard      (4/4, textually)
REPETITION.postCondition == invariant               (4/4, textually)
REPETITION.loopStatement.preCondition  == REPETITION.preCondition    (4/4)
REPETITION.loopStatement.postCondition == REPETITION.postCondition   (4/4)
```

And correspondingly, a `REPETITION` occupying a composition slot **never** matches that slot's contract — 4/4 deviating, in both the first and second slot, so it is the *node type* that deviates, not the position. For example, in `LinearSearch`:

```
Comp.intermediateCondition = "appears(A, x, 0, A.length) && i == A.length-1"   ← what the slot supplies
Comp.postCondition         = "A[i] == x"                                       ← what the slot demands
Comp.secondStatement (REPETITION) stores instead:
  preCondition  = "!appears(A, x, i+1, A.length) && (A[i] != x)"   = invariant && guard
  postCondition = "!appears(A, x, i+1, A.length)"                  = invariant
```

**Consequences for the converter:**

1. The loop's *external* contract exists **only in the parent** — it is not stored on the repetition node. Rendering a repetition in isolation loses it. Any subtree-selection feature (#5) that roots a figure at a `REPETITION` must decide what to show as that figure's contract, because the node itself does not know it.
2. A renderer that uniformly prints "this node's pre/post" produces a loop whose conditions **do not chain** with its parent — a silently wrong figure, not a crash.
3. The `loopStatement` restates the repetition's own pre/post verbatim, so printing both node and body doubles the same two formulas. The figure should show them once.

This belongs in the IR design (#6) and the node-to-visual mapping (#8).

---

## 5. Identity: `id` and `name`

Relevant to [#5 — Decide how a subtree is addressed](https://github.com/madalime/cbc-to-tikz-converter/issues/5).

### `id`

- Present on all 33 statement nodes; **absent on the diagram**.
- Unique within each document 5/5, and unique across all 33 nodes in the whole corpus.
- Shape is `\d+\.\d+` in 33/33 — e.g. `154698266724.14005`, `71435419048.67198`. Consistent with a JavaScript-generated random/timestamp value.
- **No ordering relationship to tree position.** Ids do not increase with depth or traversal order.
- **Stability across re-export is not derivable from samples.** A single snapshot cannot show whether an id survives a round-trip through the editor. Given the generated shape, assuming stability would be unwise, but the samples do not prove it either way.

### `name`

- Unique within each document 5/5 — but this is a **property of these samples, not an enforced invariant**.
- Names are plainly **user-editable**: `MaxElement` contains a hand-named `CompLoop` among auto-named siblings, and all 13 of `Bubblesort`'s nodes have been renamed to the plain integers `"0"` … `"12"`.
- Auto-numbering **leaves gaps**: `Transaction` has `Statement1`, `Statement3`, `Statement4` and no `Statement2`. So a name's numeric suffix does not index anything.
- Names may be **purely numeric** (`"0"`). Any addressing scheme that supports both names and positional indices must disambiguate these two, or they will collide.

**Bearing on #5:** `name` is the only human-typable handle in the format, and it is readable in practice — but a resolver must treat uniqueness as an assumption to *check*, not to rely on, and must define behaviour for collisions. `id` is unique and stable within a document but is unreadable and of unproven durability.

---

## 6. Condition and statement surface syntax

Relevant to [#4 — Establish the GCL rendering target](https://github.com/madalime/cbc-to-tikz-converter/issues/4).

Conditions are **JML-flavoured Java**, not plain Java expressions. Token counts across all 117 condition strings:

| construct | count | |
|---|---|---|
| `&&` | 80 | Java conjunction |
| `==>` | 27 | JML implication |
| `\old` | 22 | JML pre-state reference |
| `\forall` | 16 | JML universal quantifier |
| `==` | 60 | |
| `<=` / `>=` | 23 / 18 | |
| `!=` | 14 | |
| `!` (unary) | 5 | |
| `[…]` indexing | 51 | |
| `.length` | 68 | |
| `null` / `true` | 3 / 6 | |

**Absent from every sample:** `||`, `\exists`, `<==>`, `\sum`, `\result`, `\num_of`, `\bigint`, `instanceof`, and the ternary `?:`. Their absence bounds what the samples can justify — it does not prove WebCorC forbids them.

Quantifiers bind with an explicit type and a semicolon, and nest:

```
(\forall int m; (0 <= m && m < A.length ==> (\forall int n; (0 <= n && n < A.length ==> (m != n ==> A[m] != A[n])))))
```

Five call-shaped identifiers appear, all of them **user-defined predicates declared in the KeY include files**, never Java methods: `appears`, `maxe`, `partSort`, `sort`, `containsOldElements`. In `LinearSearch` the same predicate is written both `appears(A, x, 0, A.length)` and `appears(A,x,0,A.length)` — **spacing inside a call is not normalised**, so two textually different conditions may be the same formula. Any textual-comparison strategy has to reckon with this.

So the minimum grammar covering the corpus is: Java expressions (arithmetic, comparison, boolean, array indexing, field access) **plus** `\old(...)`, `\forall <type> <var>; (...)`, and `==>`. That is the floor for #4's substitution-vs-parsing decision.

### `programStatement`

All 14 values, verbatim:

```
i=0;                                      j=A.length-2;        j=j-1;
i=i+1;                                    i = A.length-1;      i = i-1;
i = 0;                                    j = 1;               i = j;
j = j + 1;                                i = i + 1;           balance = newBalance;
newBalance = balance + x;
tmp = A[j]; A[j] = A[j+1]; A[j+1] = tmp;
```

- **A `programStatement` is not necessarily one statement.** `Bubblesort` node `11` holds three assignments in a single field, on one line.
- All 14 end with `;`.
- Whitespace around `=` is author-typed and inconsistent (`i=0;` vs `i = 0;`, `j=j-1;` vs `j = j + 1;`). Not normalised by the editor.
- All are plain assignments. **No method or subroutine call appears in any `programStatement`** in the corpus.

**Bearing on #8:** a `STATEMENT` box may need to hold multiple statements and should not assume a single short line.

---

## 7. Always-empty fields

Three fields are present in every sample and empty in every sample. Their populated shape is therefore **not derivable**, and nothing in the corpus reveals what fills them.

| field | where | observed |
|---|---|---|
| `verifierConditions` | diagram + every statement node | `{}` — an **object**, 38/38 |
| `verifierIntermediateConditions` | every `COMPOSITION` | `{}` — an **object**, 9/9 |
| `renamings` | diagram only (never on statement nodes) | `[]` — an **array**, 5/5 |

Note the container kinds differ: the `verifier*` fields are objects, `renamings` is an array. A parser must not assume either is a list.

**Recommendation:** model all three as opaque (`dict` / `list`), ignore them, and do not let them influence the IR. If a future export populates them, that is a new ticket — the map already carries *"Handling of `renamings`, `verifierConditions`, …"* in **Not yet specified**, and this finding confirms the samples cannot graduate it.

## 8. Proof state

- `isProven` is `false` in 33/33 statement nodes and 5/5 diagrams.
- `nodeState` is `"unverified"` in 33/33 — the only value in the corpus.
- `isVariantProven`, `isPreProven`, `isPostProven` are `false` in every occurrence.

The corpus contains **no verified node at all**, so the value space of `nodeState` and its relationship to `isProven` are **not derivable**. This does not block the effort: rendering proof state is on the map's Out-of-scope list. Model `nodeState` as an opaque string and `isProven` as a bool, and let neither drive layout.

## 9. `position`

Present on the diagram and on all 33 statement nodes as `{xinPx: int, yinPx: int}`. The diagram's is always `{0, 0}`; node values range over both signs (`-450`, `-25`, `1650`, `2625`). The map already decided these are ignored in favour of computed layout — recorded here only so the decision is not silently re-litigated.

---

## 10. What a parser may rely on

Distilled for the IR ticket ([#6](https://github.com/madalime/cbc-to-tikz-converter/issues/6)):

1. Dispatch on `inodeType` before touching `content`; it is an array, an object, or a string depending on the inode.
2. The diagram root is **not** a statement node — no `id`, no `nodeState`, no own `type`.
3. Five statement types, closed set. Within a type, every documented field is always present.
4. Every condition slot is `{"condition": str}` — one type, everywhere, including the integer-valued `variant`.
5. Child counts are fixed by type: `COMPOSITION` 2, `REPETITION` 1, `SELECTION` *n*, `STATEMENT`/`SKIP` 0.
6. `SELECTION.guards` and `.commands` are index-aligned — **validate the lengths match**, do not assume.
7. Non-repetition children restate their slot's contract verbatim; **`REPETITION` does not** — it stores `invariant && guard` / `invariant` instead, and its external contract lives only in its parent.
8. `id` is unique per document but opaque and of unproven cross-export stability. `name` is readable and unique in every sample, but user-editable, gap-prone, sometimes purely numeric, and not guaranteed unique.
9. Conditions are JML-flavoured Java: Java operators plus `\old`, `\forall`, `==>`. Whitespace is author-typed and unnormalised.
10. `programStatement` may contain several `;`-separated statements.
11. `verifierConditions`, `verifierIntermediateConditions`, `renamings` are always empty — treat as opaque and ignore.

## 11. Residual gaps

Seven questions the fenced evidence cannot answer. Each requires WebCorC behaviour or documentation, both out of #2's scope:

1. Can one export contain more than one `.diagram`?
2. Do `id` values survive a re-export?
3. What values can `nodeState` take, and how does it relate to `isProven`?
4. What populates `verifierConditions` / `verifierIntermediateConditions`?
5. What is `renamings`, and what would fill it?
6. What `kind` values other than `LOCAL` can a `javaVariable` have?
7. Is there a statement type for method or subroutine calls that these five samples simply do not exercise?

None of them blocks the parser design: the recommended handling for all seven is "treat as opaque, validate rather than assume." They are recorded so a later ticket can pick them up deliberately rather than rediscover them.

---

## Reproducing

`verify_export_invariants.py` in this directory re-checks every `k/n` claim above against `samples/`. Run it from the repo root with the sample files present (they are gitignored, so a fresh clone will not have them):

```
python docs/research/verify_export_invariants.py
```

It prints the field census, the type counts, each invariant's hit count, and a violation list. At the time of writing it reports **zero violations** across the five samples.
