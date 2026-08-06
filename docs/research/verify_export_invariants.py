"""Re-check every claim in webcorc-export-format.md against the sample exports.

Research artifact for issue #2, not converter code. It exists so the findings in
webcorc-export-format.md can be re-verified against a new or changed sample set
rather than taken on trust.

Usage:  python docs/research/verify_export_invariants.py [samples_dir]

Exits non-zero if any documented invariant is violated.
"""

import collections
import glob
import json
import os
import re
import sys

CHILD_KEYS = {
    "COMPOSITION": ["firstStatement", "secondStatement"],
    "REPETITION": ["loopStatement"],
    "SELECTION": ["commands"],
    "STATEMENT": [],
    "SKIP": [],
}

COMMON_FIELDS = ["name", "type", "preCondition", "postCondition", "position",
                 "isProven", "verifierConditions", "id", "nodeState"]

DIAGRAM_FIELDS = ["name", "preCondition", "postCondition", "verifierConditions",
                  "javaVariables", "globalConditions", "renamings", "isProven",
                  "position", "statement"]


def inodes(node, depth=0):
    yield node, depth
    if node.get("inodeType") == "directory":
        for child in node["content"]:
            yield from inodes(child, depth + 1)


def walk(node):
    """Every statement node in the subtree, root first."""
    yield node
    for key in CHILD_KEYS[node["type"]]:
        value = node.get(key)
        if isinstance(value, list):
            for child in value:
                yield from walk(child)
        elif value is not None:
            yield from walk(value)


def main(samples_dir="samples"):
    paths = sorted(glob.glob(os.path.join(samples_dir, "*.json")))
    if not paths:
        print(f"no samples found in {samples_dir!r} "
              f"(samples/ is gitignored — a fresh clone will not have them)")
        return 1

    checks = collections.Counter()
    types = collections.Counter()
    fields = collections.defaultdict(collections.Counter)
    node_states = collections.Counter()
    var_kinds = collections.Counter()
    conditions = []
    program_statements = []
    all_ids = []
    violations = []

    def check(name, ok, detail=""):
        checks[name + "_total"] += 1
        if ok:
            checks[name + "_ok"] += 1
        else:
            violations.append(f"{name}: {detail}")

    for path in paths:
        doc = json.load(open(path, encoding="utf-8"))
        fn = os.path.basename(path)

        check("envelope_root_keys", list(doc) == ["urn", "content", "inodeType"], f"{fn}: {list(doc)}")
        check("envelope_root_urn_empty", doc["urn"] == "", fn)
        check("envelope_root_is_dir", doc["inodeType"] == "directory", fn)

        diagram_files = [n for n, _ in inodes(doc) if n.get("type") == "diagram"]
        check("envelope_single_diagram", len(diagram_files) == 1, f"{fn}: {len(diagram_files)}")

        for f in diagram_files:
            diagram = f["content"]
            check("diagram_fields", list(diagram) == DIAGRAM_FIELDS, f"{fn}: {list(diagram)}")
            check("diagram_verifierConditions_empty", diagram["verifierConditions"] == {}, fn)
            check("diagram_renamings_empty", diagram["renamings"] == [], fn)
            check("diagram_no_id", "id" not in diagram and "nodeState" not in diagram, fn)

            conditions += [diagram["preCondition"]["condition"], diagram["postCondition"]["condition"]]
            conditions += [g["condition"] for g in diagram["globalConditions"]]
            for var in diagram["javaVariables"]:
                var_kinds[var["kind"]] += 1
                check("var_keys", set(var) == {"name", "kind"}, f"{fn}: {list(var)}")

            root = diagram["statement"]
            check("diagram_contract_is_root_contract",
                  root["preCondition"] == diagram["preCondition"]
                  and root["postCondition"] == diagram["postCondition"], fn)

            ids, names = [], []
            for node in walk(root):
                t = node["type"]
                types[t] += 1
                for k in node:
                    fields[t][k] += 1
                node_states[node["nodeState"]] += 1
                ids.append(node["id"])
                names.append(node["name"])
                all_ids.append(node["id"])
                label = f"{fn}/{node['name']}"

                check("common_fields_present",
                      all(k in node for k in COMMON_FIELDS), label)
                check("verifierConditions_empty_object", node["verifierConditions"] == {}, label)
                check("id_shape", bool(re.fullmatch(r"\d+\.\d+", node["id"])), f"{label}: {node['id']}")

                conditions += [node["preCondition"]["condition"], node["postCondition"]["condition"]]

                if t == "STATEMENT":
                    program_statements.append(node["programStatement"])

                if t == "COMPOSITION":
                    conditions.append(node["intermediateCondition"]["condition"])
                    check("comp_verifierIntermediate_empty",
                          node["verifierIntermediateConditions"] == {}, label)
                    mid = node["intermediateCondition"]
                    slots = ((node["firstStatement"], node["preCondition"], mid, "first"),
                             (node["secondStatement"], mid, node["postCondition"], "second"))
                    for child, want_pre, want_post, slot in slots:
                        matches = (child["preCondition"] == want_pre
                                   and child["postCondition"] == want_post)
                        if child["type"] == "REPETITION":
                            # documented anomaly: a repetition stores its BODY's contract,
                            # never the contract of the slot it occupies
                            check("repetition_child_deviates_from_slot", not matches,
                                  f"{label}.{slot}: repetition unexpectedly matched its slot")
                        else:
                            check("nonrepetition_child_matches_slot", matches,
                                  f"{label}.{slot} ({child['type']})")

                if t == "REPETITION":
                    inv = node["invariant"]["condition"]
                    guard = node["guard"]["condition"]
                    conditions += [node["variant"]["condition"], inv, guard]
                    check("repetition_pre_is_invariant_and_guard",
                          node["preCondition"]["condition"] == f"{inv} && {guard}",
                          f"{label}: {node['preCondition']['condition']!r}")
                    check("repetition_post_is_invariant",
                          node["postCondition"]["condition"] == inv, label)
                    body = node["loopStatement"]
                    check("repetition_body_inherits_contract",
                          body["preCondition"] == node["preCondition"]
                          and body["postCondition"] == node["postCondition"], label)

                if t == "SELECTION":
                    guards, commands = node["guards"], node["commands"]
                    conditions += [g["condition"] for g in guards]
                    check("selection_guards_commands_same_length",
                          len(guards) == len(commands),
                          f"{label}: {len(guards)} vs {len(commands)}")
                    for i, (guard, command) in enumerate(zip(guards, commands)):
                        want = node["preCondition"]["condition"] + " && " + guard["condition"]
                        check("selection_command_pre_is_selpre_and_guard",
                              command["preCondition"]["condition"] == want,
                              f"{label}[{i}]: {command['preCondition']['condition']!r} != {want!r}")
                        check("selection_command_post_is_selection_post",
                              command["postCondition"] == node["postCondition"], f"{label}[{i}]")

            check("ids_unique_per_document", len(set(ids)) == len(ids), fn)
            check("names_unique_per_document", len(set(names)) == len(names), fn)

    print(f"documents: {len(paths)}   statement nodes: {sum(types.values())}   "
          f"conditions: {len(conditions)} ({len(set(conditions))} distinct)")
    print(f"node types: {dict(types)}")
    print(f"nodeState values: {dict(node_states)}")
    print(f"javaVariable kinds: {dict(var_kinds)}")
    print(f"ids globally unique: {len(set(all_ids)) == len(all_ids)}")
    print(f"programStatements with >1 ';': "
          f"{sum(1 for p in program_statements if p.count(';') > 1)}/{len(program_statements)}")

    absent = [t for t in ("||", r"\exists", "<==>", r"\result", "instanceof")
              if not any(t in c for c in conditions)]
    print(f"tokens absent from every condition: {absent}")

    print("\nfield census (occurrences / nodes of that type):")
    for t in sorted(fields):
        extras = [k for k in fields[t] if k not in COMMON_FIELDS]
        optional = [k for k, v in fields[t].items() if v != types[t]]
        print(f"  {t:<12} n={types[t]:<3} extra={extras} "
              f"{'OPTIONAL=' + str(optional) if optional else '(no optional fields)'}")

    print("\ninvariants:")
    for name in sorted(k[:-6] for k in checks if k.endswith("_total")):
        ok, total = checks[name + "_ok"], checks[name + "_total"]
        print(f"  {'OK ' if ok == total else 'FAIL'} {name}: {ok}/{total}")

    print(f"\nviolations: {len(violations)}")
    for v in violations:
        print("  " + v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
