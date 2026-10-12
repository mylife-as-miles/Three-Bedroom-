# Resources

CONFIRMED: modules.bin has 7,096 registry records with names, sizes, imports and exports. These support exact declared module dependency edges. The manifest contains 7,958 actual DC files, so the registry and corpus counts should not be conflated. Exports can be declarations or data, not necessarily a code implementation.

Level-set, part-module, actor-state, animation, sfx/VO and render-setting structures provide resource references. The nested startup-dc-files.psarc was extracted separately: all 1,714 entries are SHA-256 duplicates of files in the primary manifest, so no additional unique script corpus was omitted. Workbench texture-priority calls demonstrate residency requests and dynamic checkpoint calls demonstrate separate gameplay bookkeeping.

HIGH CONFIDENCE: scripts/data describe what is needed and can request supported loading behavior. UNKNOWN: memory budgets, cache eviction, runtime reference counting, native stream priority and all texture/model/bank contents. Resource IDs alone cannot reconstruct proprietary assets. Streaming availability and saved world state are independent concerns.

[Generated corpus evidence](evidence.md).

CONFIRMED resource manifests: 44 JSON files (two empty) decode as concatenated JSON documents, yielding 3,348 named resource groups. Derived owner-to-reference edges distinguish levels, looks, level-sets, actors and their PC variants. `databases/level_resources.json` records these declarations; `auxiliary_coverage.json` covers JSON/TXT readable-string hashing. These are resource identities, not the geometry/model/texture contents.
