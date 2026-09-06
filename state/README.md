# State slots (EICP AI Bridge transport)

One JSON file per slot. Encoding is collision-free (fix 2026-09-06):

- `a.b.c` → `state/a__d__b__d__c.json` (dot → `__d__`)
- `a_b` → `state/a__u__b.json` (underscore → `__u__`)
- `a/b` → `state/a__s__b.json` (slash → `__s__`)

This avoids the old collision where `project.eicp.status` and `project_eicp_status`
both mapped to `project_eicp_status.json`.

Written by agents or `eicp/helper.py` (`write_state_slot`). Last successful merge to `main` wins for that file.

Old files with `a_b_c.json` naming are legacy; new code uses the collision-free scheme.
If you find a legacy file, migrate its value to the new path or keep both for compat.
