# TLOU2 gameplay interaction research — PC 1.6

This repository analyzes the user's actual `bin_1.6-378-1-6-1759117728.rar`, not public example scripts. The initial workspace had no existing checkout. After the user supplied https://github.com/mylife-as-miles/Three-Bedroom-, its existing handoff/state exports were inspected and preserved; this project is integrated as a subdirectory. There is no AGENTS.md in that repository. No remote publication, game modification or mod deployment was performed.

**Verified corpus:** 8,004 files under dc1: 7,958 DC00 binaries, 44 JSON files, one text file and one nested PSARC. All 7,958 DC files were structurally indexed. The nested startup PSARC contains 1,714 files, all SHA-256-identical to already indexed files; they are not counted twice. They contain 5,431 state scripts, 29,251 states, 178,581 validated lambda structures and 644,423 statically reachable call sites. Parser errors: zero. These counts do not establish semantic completeness or runtime correctness.

Start with [Interaction architecture](INTERACTION_ARCHITECTURE.md), [engine boundaries](ENGINE_BOUNDARIES.md), [modding surface](modding/MODDABLE_SURFACE.md), and [research checkpoint](PROGRESS.md). Each interaction directory contains interpreted `README.md`, generated `evidence.md`, machine-readable evidence and explicit-transition Mermaid graphs.

## Evidence rules

- **CONFIRMED:** a source structure, call instruction, constant argument or declared dependency exists at the cited file/offset.
- **HIGH CONFIDENCE:** several observations support the interpretation, but native implementation or runtime binding has not been checked.
- **INFERRED:** a plausible interpretation or candidate link; not established behavior.
- **UNKNOWN / NEEDS NATIVE RESEARCH:** the available corpus cannot answer the question.

Names alone do not prove behavior. Static `go` edges include conditional alternatives. Event-name matches do not prove receiver identity. A function with no DC definition is not automatically proven native; `CallFf` plus a missing definition supports that boundary interpretation. Runtime variables and facts are not automatically saved flags.

## Reproduce

Use Python 3.12+ and `python3 -m pip install -r requirements.txt`. Tool sources are pinned in `tools/TOOLCHAIN.md`; `bash tools/setup.sh` fetches the required public clones into private storage. Obtain the exact RAR from the user's Drive folder, or put it in `.private/input/bin_1.6-378-1-6-1759117728.rar`. Extract the RAR locally with 7-Zip into `.private/game`, for example `7zz x -y -o.private/game .private/input/bin_1.6-378-1-6-1759117728.rar`. Then:

```bash
python3 tools/extract/extract_archive.py .private/game/bin_1.6/bin.psarc .private/extracted --manifest databases/file_manifest.json
python3 tools/analysis/corpus.py
python3 tools/analysis/build_reports.py
python3 tools/analysis/augment.py
python3 tools/analysis/scan_auxiliary.py
python3 tools/graph/build_graphs.py
python3 tools/analysis/build_reference.py
python3 tools/analysis/validate.py
python3 tools/analysis/package_metadata.py
python3 tools/analysis/query.py calls player-apply-pickup
python3 tools/analysis/query.py states ss-openable-drawer
```

`dconstruct`'s current CLI targets Windows. Its SID database and structure/opcode definitions were studied and used, but **dconstruct itself was not executed** in this Linux session. The original tool was not modified. `tools/analysis/decompile_windows.ps1` supplies a private-output batch path for a Windows run. An MIT-licensed Linux compatibility build of `t2r-dc-disasm` was run on five actual core modules for independent validation.

## Storage and integrity

Original RAR/PSARC/DC files, third-party fixtures, full readable strings, merged SID dictionary, reference listings and our raw bytecode listings live only under ignored `.private/`. Public datasets contain derived symbols, states, dependency relationships and call metadata. Large datasets use gzip JSON with small `.json` descriptors; `tools/analysis/data.py` transparently reads both. Descriptive string literals are redacted from public metadata; identifiers and asset paths are retained. Only documentation, independently authored tools and derived metadata are intended for version control.

The PSARC SHA-256 is `fb49971e0a8aed47d75803d1600b6f28aa993b79524bd88167de89be2538f210`. Per-file hashes and archive positions are in [file manifest](databases/file_manifest.json). Coverage and verification are in [coverage](databases/coverage.json), [reference validation](databases/reference_validation.json), and [prior reconciliation](databases/prior_reconciliation.json).

All 621 prior exported state scripts agree with known names and counts; 402 previously unnamed states are now resolved. All published SID labels recompute to their exact FNV-1a 64 value; 556,351 originate from DC word matches, with additional labels from JSON/TXT resource metadata. The merged private dictionary also hashes 126,055 unique readable game strings and 97,951 derived token candidates. Token candidates become evidence only when their hashes match binary values.

## Limits

The supplied archive contains script/data, not the complete game executable, animations, geometry, models, sound banks or save files. Native inventory mutations, interaction scoring, animation solver math, AI decisions and resource residency cannot be reconstructed completely from it. No live game trace, save/reload experiment or new mod compilation was performed. The analysis does not bypass DRM or anti-cheat and includes no redistributed original game assets.

## Subsequent mod experiment

[Mod Experiment 01 — Drawer Diagnostics](modding/experiments/01-drawer-diagnostics/README.md) builds an isolated, filtered observer using the pinned dconstruct core. Its authored smoke round-trip and static preservation checks pass. Original assets stay private; Windows/game behavior tests have not run. The limits above describe the original corpus-analysis phase; the experiment's evidence records the subsequent compilation separately.
