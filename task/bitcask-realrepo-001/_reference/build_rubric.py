#!/usr/bin/env python3
"""Generate rubric.json for the bitcask-realrepo-001 unit/system packet.

Case schema (a superset of the reference family schema, adapted for a
process-per-command KV CLI):

  id, layer ("unit"|"system"), category, requirement_refs, description, weight
  system_dimension          (system cases only)
  env                       optional {ENV: value} applied to every command
  setup_files               optional {filename: contents} written to workspace
  commands                  list; each item is either ["DBDIR", "cmd", ...] or
                            {"args": [...], "expect_error": true}
  checks                    {kind: {command_index(str): expected}}
     kinds: stdout_equals | stdout_json | stdout_contains | stdout_json_contains
"""
import json
import os

DB = "store"
cases = []


# ---------------------------------------------------------------- UNIT (16) ---
cases += [
    {
        "id": "KVU001", "layer": "unit", "category": "put",
        "requirement_refs": ["REQ-put"],
        "description": "put then get returns the stored value.",
        "weight": 4,
        "commands": [[DB, "put", "a", "alpha"], [DB, "get", "a"]],
        "checks": {"stdout_equals": {"1": "alpha"}},
    },
    {
        "id": "KVU002", "layer": "unit", "category": "put",
        "requirement_refs": ["REQ-put"],
        "description": "Re-putting a key overwrites it; latest value wins.",
        "weight": 4,
        "commands": [[DB, "put", "a", "one"], [DB, "put", "a", "two"],
                     [DB, "get", "a"]],
        "checks": {"stdout_equals": {"2": "two"}},
    },
    {
        "id": "KVU003", "layer": "unit", "category": "get",
        "requirement_refs": ["REQ-get"],
        "description": "get on a missing key fails nonzero.",
        "weight": 4,
        "commands": [{"args": [DB, "get", "x"], "expect_error": True}],
        "checks": {},
    },
    {
        "id": "KVU004", "layer": "unit", "category": "update",
        "requirement_refs": ["REQ-update"],
        "description": "update on an existing key writes the new value.",
        "weight": 4,
        "commands": [[DB, "put", "a", "old"], [DB, "update", "a", "new"],
                     [DB, "get", "a"]],
        "checks": {"stdout_equals": {"2": "new"}},
    },
    {
        "id": "KVU005", "layer": "unit", "category": "update",
        "requirement_refs": ["REQ-update", "REQ-atomic"],
        "description": "update on a missing key fails and preserves existing state.",
        "weight": 4,
        "commands": [[DB, "put", "a", "keep"],
                     {"args": [DB, "update", "b", "x"], "expect_error": True},
                     [DB, "list"]],
        "checks": {"stdout_json": {"2": {"a": "keep"}}},
    },
    {
        "id": "KVU006", "layer": "unit", "category": "delete",
        "requirement_refs": ["REQ-delete"],
        "description": "delete removes a key from the live set.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "delete", "a"], [DB, "keys"]],
        "checks": {"stdout_json": {"3": ["b"]}},
    },
    {
        "id": "KVU007", "layer": "unit", "category": "delete",
        "requirement_refs": ["REQ-delete", "REQ-atomic"],
        "description": "delete on a missing key fails and preserves state.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"],
                     {"args": [DB, "delete", "z"], "expect_error": True},
                     [DB, "count"]],
        "checks": {"stdout_equals": {"2": "1"}},
    },
    {
        "id": "KVU008", "layer": "unit", "category": "metadata",
        "requirement_refs": ["REQ-metadata"],
        "description": "keys returns live keys sorted lexicographically.",
        "weight": 4,
        "commands": [[DB, "put", "c", "3"], [DB, "put", "a", "1"],
                     [DB, "put", "b", "2"], [DB, "keys"]],
        "checks": {"stdout_json": {"3": ["a", "b", "c"]}},
    },
    {
        "id": "KVU009", "layer": "unit", "category": "metadata",
        "requirement_refs": ["REQ-metadata"],
        "description": "count returns the number of live keys.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "put", "c", "3"], [DB, "count"]],
        "checks": {"stdout_equals": {"3": "3"}},
    },
    {
        "id": "KVU010", "layer": "unit", "category": "metadata",
        "requirement_refs": ["REQ-metadata"],
        "description": "list returns the full live key/value map.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "list"]],
        "checks": {"stdout_json": {"2": {"a": "1", "b": "2"}}},
    },
    {
        "id": "KVU011", "layer": "unit", "category": "get",
        "requirement_refs": ["REQ-get"],
        "description": "mget returns found keys and omits missing ones.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "mget", "a", "b", "zzz"]],
        "checks": {"stdout_json": {"2": {"a": "1", "b": "2"}}},
    },
    {
        "id": "KVU012", "layer": "unit", "category": "metadata",
        "requirement_refs": ["REQ-metadata"],
        "description": "stats reports live_keys and on-disk log_entries.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "stats"]],
        "checks": {"stdout_json": {"2": {"live_keys": 2, "log_entries": 2}}},
    },
    {
        "id": "KVU013", "layer": "unit", "category": "compact",
        "requirement_refs": ["REQ-compact"],
        "description": "compact drops superseded records and keeps latest values.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "a", "2"],
                     [DB, "put", "b", "9"], [DB, "compact"],
                     [DB, "stats"], [DB, "get", "a"]],
        "checks": {"stdout_json": {"4": {"live_keys": 2, "log_entries": 2}},
                   "stdout_equals": {"5": "2"}},
    },
    {
        "id": "KVU014", "layer": "unit", "category": "durability",
        "requirement_refs": ["REQ-durability"],
        "description": "a value written by one invocation is readable by a later one.",
        "weight": 4,
        "commands": [[DB, "put", "k", "v"], [DB, "put", "k2", "v2"],
                     [DB, "get", "k"]],
        "checks": {"stdout_equals": {"2": "v"}},
    },
    {
        "id": "KVU015", "layer": "unit", "category": "compact",
        "requirement_refs": ["REQ-compact"],
        "description": "compact removes tombstoned keys entirely.",
        "weight": 4,
        "commands": [[DB, "put", "a", "1"], [DB, "delete", "a"],
                     [DB, "compact"], [DB, "count"], [DB, "keys"]],
        "checks": {"stdout_equals": {"3": "0"}, "stdout_json": {"4": []}},
    },
    {
        "id": "KVU016", "layer": "unit", "category": "metadata",
        "requirement_refs": ["REQ-metadata"],
        "description": "metadata on an empty store is consistent and empty.",
        "weight": 4,
        "commands": [[DB, "keys"], [DB, "count"], [DB, "list"], [DB, "stats"]],
        "checks": {"stdout_json": {"0": [], "2": {},
                                   "3": {"live_keys": 0, "log_entries": 0}},
                   "stdout_equals": {"1": "0"}},
    },
]

# -------------------------------------------------------------- SYSTEM (12) ---
cases += [
    {
        "id": "KVS001", "layer": "system",
        "system_dimension": "cross_feature_dataflow",
        "category": "put_compact_query",
        "requirement_refs": ["REQ-put", "REQ-compact", "REQ-metadata",
                             "REQ-global-invariants"],
        "description": "Overwritten values flow through compaction into list/stats.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "a", "2"],
                     [DB, "put", "b", "9"], [DB, "compact"],
                     [DB, "list"], [DB, "stats"]],
        "checks": {"stdout_json": {"4": {"a": "2", "b": "9"},
                                   "5": {"live_keys": 2, "log_entries": 2}}},
    },
    {
        "id": "KVS002", "layer": "system",
        "system_dimension": "state_accumulation",
        "category": "mixed_mutation_lifecycle",
        "requirement_refs": ["REQ-put", "REQ-update", "REQ-delete",
                             "REQ-metadata", "REQ-global-invariants"],
        "description": "Interleaved put/update/delete accumulate to latest live state.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "update", "a", "2"],
                     [DB, "put", "b", "1"], [DB, "delete", "b"],
                     [DB, "put", "c", "7"], [DB, "list"], [DB, "count"]],
        "checks": {"stdout_json": {"5": {"a": "2", "c": "7"}},
                   "stdout_equals": {"6": "2"}},
    },
    {
        "id": "KVS003", "layer": "system",
        "system_dimension": "global_invariant",
        "category": "metadata_consistency",
        "requirement_refs": ["REQ-put", "REQ-delete", "REQ-get",
                             "REQ-metadata", "REQ-global-invariants"],
        "description": "keys, count and get stay mutually consistent after a delete.",
        "weight": 8,
        "commands": [[DB, "put", "x", "10"], [DB, "put", "y", "20"],
                     [DB, "put", "z", "30"], [DB, "delete", "y"],
                     [DB, "keys"], [DB, "count"], [DB, "get", "x"],
                     [DB, "get", "z"]],
        "checks": {"stdout_json": {"4": ["x", "z"]},
                   "stdout_equals": {"5": "2", "6": "10", "7": "30"}},
    },
    {
        "id": "KVS004", "layer": "system",
        "system_dimension": "error_atomicity",
        "category": "failed_update_preserves_state",
        "requirement_refs": ["REQ-update", "REQ-atomic", "REQ-metadata",
                             "REQ-global-invariants"],
        "description": "A failed update leaves prior rows and count unchanged.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     {"args": [DB, "update", "c", "9"], "expect_error": True},
                     [DB, "list"], [DB, "count"]],
        "checks": {"stdout_json": {"3": {"a": "1", "b": "2"}},
                   "stdout_equals": {"4": "2"}},
    },
    {
        "id": "KVS005", "layer": "system",
        "system_dimension": "error_atomicity",
        "category": "failed_delete_no_append",
        "requirement_refs": ["REQ-delete", "REQ-atomic", "REQ-metadata"],
        "description": "A failed delete appends no record; log and value are intact.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "stats"],
                     {"args": [DB, "delete", "z"], "expect_error": True},
                     [DB, "stats"], [DB, "get", "a"]],
        "checks": {"stdout_json": {"1": {"live_keys": 1, "log_entries": 1},
                                   "3": {"live_keys": 1, "log_entries": 1}},
                   "stdout_equals": {"4": "1"}},
    },
    {
        "id": "KVS006", "layer": "system",
        "system_dimension": "operation_order_sensitivity",
        "category": "delete_then_put_resurrection",
        "requirement_refs": ["REQ-put", "REQ-delete", "REQ-get",
                             "REQ-metadata"],
        "description": "put after delete resurrects the key with the new value.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "delete", "a"],
                     [DB, "put", "a", "2"], [DB, "get", "a"], [DB, "keys"]],
        "checks": {"stdout_equals": {"3": "2"}, "stdout_json": {"4": ["a"]}},
    },
    {
        "id": "KVS007", "layer": "system",
        "system_dimension": "operation_order_sensitivity",
        "category": "writes_after_compaction",
        "requirement_refs": ["REQ-compact", "REQ-update", "REQ-put",
                             "REQ-metadata", "REQ-global-invariants"],
        "description": "Writes after a compaction append cleanly and latest wins.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "1"],
                     [DB, "compact"], [DB, "update", "a", "2"],
                     [DB, "put", "c", "3"], [DB, "list"], [DB, "stats"]],
        "checks": {"stdout_json": {"5": {"a": "2", "b": "1", "c": "3"},
                                   "6": {"live_keys": 3, "log_entries": 4}}},
    },
    {
        "id": "KVS008", "layer": "system",
        "system_dimension": "durability_reload",
        "category": "persist_across_invocations",
        "requirement_refs": ["REQ-durability", "REQ-compact", "REQ-get",
                             "REQ-metadata"],
        "description": "Values persist across separate invocations, including post-compact.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "compact"], [DB, "get", "a"], [DB, "get", "b"],
                     [DB, "list"]],
        "checks": {"stdout_equals": {"3": "1", "4": "2"},
                   "stdout_json": {"5": {"a": "1", "b": "2"}}},
    },
    {
        "id": "KVS009", "layer": "system",
        "system_dimension": "boundary_crossing",
        "category": "overwrite_delete_compact",
        "requirement_refs": ["REQ-put", "REQ-delete", "REQ-compact",
                             "REQ-metadata", "REQ-global-invariants"],
        "description": "Overwrite, delete and compaction compose to a clean final state.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "a", "2"],
                     [DB, "put", "b", "5"], [DB, "delete", "b"],
                     [DB, "compact"], [DB, "list"], [DB, "count"],
                     [DB, "stats"]],
        "checks": {"stdout_json": {"5": {"a": "2"},
                                   "7": {"live_keys": 1, "log_entries": 1}},
                   "stdout_equals": {"6": "1"}},
    },
    {
        "id": "KVS010", "layer": "system",
        "system_dimension": "global_invariant",
        "category": "compaction_no_resurrection",
        "requirement_refs": ["REQ-compact", "REQ-delete", "REQ-put",
                             "REQ-get", "REQ-global-invariants"],
        "description": "Compaction never resurrects deleted keys or reverts values.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "1"],
                     [DB, "delete", "b"], [DB, "put", "a", "9"],
                     [DB, "compact"], [DB, "keys"], [DB, "get", "a"],
                     {"args": [DB, "get", "b"], "expect_error": True}],
        "checks": {"stdout_json": {"5": ["a"]}, "stdout_equals": {"6": "9"}},
    },
    {
        "id": "KVS011", "layer": "system",
        "system_dimension": "state_accumulation",
        "category": "cross_segment_compaction",
        "requirement_refs": ["REQ-put", "REQ-compact", "REQ-metadata",
                             "REQ-durability"],
        "description": "Correctness holds when writes span multiple rolled segments.",
        "weight": 8,
        "env": {"KVMINI_MAX_SEGMENT_BYTES": "48"},
        "commands": [[DB, "put", "k1", "v1"], [DB, "put", "k2", "v2"],
                     [DB, "put", "k3", "v3"], [DB, "put", "k1", "v1new"],
                     [DB, "stats"], [DB, "compact"], [DB, "stats"],
                     [DB, "list"]],
        "checks": {"stdout_json": {
            "4": {"live_keys": 3, "log_entries": 4},
            "6": {"live_keys": 3, "log_entries": 3},
            "7": {"k1": "v1new", "k2": "v2", "k3": "v3"}}},
    },
    {
        "id": "KVS012", "layer": "system",
        "system_dimension": "boundary_crossing",
        "category": "mget_across_mutations",
        "requirement_refs": ["REQ-get", "REQ-update", "REQ-delete",
                             "REQ-metadata", "REQ-global-invariants"],
        "description": "mget reflects updates and deletions and matches list.",
        "weight": 8,
        "commands": [[DB, "put", "a", "1"], [DB, "put", "b", "2"],
                     [DB, "put", "c", "3"], [DB, "update", "b", "22"],
                     [DB, "delete", "c"], [DB, "mget", "a", "b", "c"],
                     [DB, "list"]],
        "checks": {"stdout_json": {"5": {"a": "1", "b": "22"},
                                   "6": {"a": "1", "b": "22"}}},
    },
]

out = os.path.join(os.path.dirname(__file__), "..", "rubric.json")
out = os.path.abspath(out)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(cases, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

units = [c for c in cases if c["layer"] == "unit"]
systems = [c for c in cases if c["layer"] == "system"]
print(f"wrote {out}")
print(f"  unit cases:   {len(units)} (weight {sum(c['weight'] for c in units)})")
print(f"  system cases: {len(systems)} (weight {sum(c['weight'] for c in systems)})")
dims = {}
for c in systems:
    dims.setdefault(c["system_dimension"], []).append(c["id"])
for d, ids in sorted(dims.items()):
    print(f"  dim {d}: {ids}")
