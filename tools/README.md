# Tooling — reproducible pipeline

Everything here is our own code. Game data and anything decompiled from it stay in `.private/`, which is gitignored.
Total run time on a 4-core container is about 2 minutes, plus a one-time dconstruct build.

```
Drive RAR ──unrar──▶ bin.psarc (DSAR) ──dsar_unpack──▶ PSARC ──psarc_extract──▶ dc1/*.bin (8,004)
                                                             └▶ dc1/startup-dc-files.psarc ──▶ +63 startup-only files
dc1 (8,021 .bin) ──scan_corpus──▶ corpus.jsonl.gz + strings.tsv.gz
                 ──build_sid_dict──▶ sid_full.tsv (1.53 M) + referenced-SID census
                 ──xref_index──▶ data-level SID cross-reference
                 ──build_databases──▶ databases/*.json
                 ──dconstruct (Linux)──▶ .private/dconstruct_out/**/*.asm|.dcpl
databases ──event_graph / ss_mermaid──▶ graphs
```

## 0. Prerequisites

```sh
apt-get install -y unrar          # or any RAR4 extractor (p7zip 16 / libarchive failed on this archive)
pip install lz4 numpy
```

## 1. Acquire and extract

```sh
mkdir -p .private/archives && cd .private/archives
# the user's own Drive file "bin_1.6-378-1-6-1759117728.rar" (44,817,442 bytes)
unrar x bin16.rar ../raw16/
cd ../..
python3 -I tools/extract/dsar_unpack.py .private/raw16/bin_1.6/bin.psarc .private/bin16.psarc
python3 -I tools/extract/psarc_extract.py .private/bin16.psarc .private/extracted16 --manifest .private/psarc_manifest16.json
python3 -I tools/extract/psarc_extract.py .private/extracted16/dc1/startup-dc-files.psarc .private/extracted16_startup
# copy the 63 startup-only files into extracted16/dc1 (same relative paths)
```

Observed formats:

* **DSAR** (PC wrapper): 32-byte block table entries. Codec 3 = raw LZ4 block, codec 254 = stored, or zero-fill
  when the compressed size is 0.
* **PSARC** v1.4 zlib, 64 KiB blocks, flags 12. Entry 0 is the NUL-separated path list. TOC entries are sorted by
  `MD5(path)`, **not** manifest order, so paths have to be matched by hash.
* **DC00** script binaries: see the `tools/analysis/dclib.py` docstring.

## 2. Analysis passes

```sh
python3 -I tools/analysis/scan_corpus.py .private/extracted16/dc1 .private/db -j 4        # ~14 s
python3 -I tools/sid/build_sid_dict.py .private/db \
        .private/ext/dconstruct/test/fixtures/dc/sidbase_new_fixed.bin .private/sid \
        --sid-addresses .private/ext/dconstruct/sid_addresses.tsv                          # ~2 min
python3 -I tools/analysis/xref_index.py .private/extracted16/dc1 .private/db .private/sid/sid_full.tsv  # ~11 s
python3 -I tools/analysis/build_databases.py .private/db .private/sid \
        .private/ext/dconstruct/sid_addresses.tsv databases .private/psarc_manifest16.json        # ~16 s
python3 -I tools/graph/event_graph.py [--filter REGEX --dot databases/graphs]
python3 -I tools/graph/ss_mermaid.py ss-openable-drawer
```

dconstruct (decompiler) on Linux: `tools/extract/dconstruct_linux/build.sh --install-deps`, then
`.private/build/dconstruct-linux/build/dconstruct -i .private/extracted16/dc1 -o .private/dconstruct_out/dc1`
(about 25 s for all 8,021 files). See `PATCHES.md` for why the patch files are local-only.

## 3. Query

```sh
python3 -I tools/analysis/q.py fn player-apply-pickup
python3 -I tools/analysis/q.py callers override-interact-def
python3 -I tools/analysis/q.py event player-requested-interact
python3 -I tools/analysis/q.py uses interact-openable-drawer     # data + code references of a SID
python3 -I tools/analysis/q.py ss ss-openable-cabinet
python3 -I tools/analysis/trace_ss.py .private/extracted16/dc1/ss-t2/ss-openable-drawer.bin --sids .private/sid/sid_full.tsv
```

## Components

| file | purpose |
|---|---|
| `extract/dsar_unpack.py` | DSAR → PSARC |
| `extract/psarc_extract.py` | PSARC → files (+ manifest) |
| `extract/dconstruct_linux/` | Linux build of the dconstruct CLI |
| `analysis/dclib.py` | DC00 parser: header, relocation bitmap, entries, StateScript / declarations / blocks / tracks, ScriptLambda discovery (0xDEADBEEF1337F00D marker), linear register tracer for call-target and argument recovery |
| `analysis/scan_corpus.py` | pass 1: raw facts for every file (parallel) |
| `sid/build_sid_dict.py` | FNV-1a 64 reverse dictionary from the sidbase, native names and every corpus string/token; resolution census |
| `analysis/xref_index.py` | pass 2: SIDs embedded in *data* (non-pointer aligned words) per file, plus the inverted index |
| `analysis/build_databases.py` | pass 3: committed databases |
| `analysis/q.py` | query tool |
| `analysis/trace_ss.py` | human-readable state-script call trace from raw bytecode (independent of dconstruct) |
| `graph/event_graph.py` | sender → event → handler graph and the native event vocabulary |
| `graph/ss_mermaid.py` | Mermaid state diagrams |

## Known limits

* The tracer simulates registers linearly. Arguments are reliable (they are marshalled right before each call), but
  branch conditions are not reconstructed. Use the dconstruct `.dcpl` for control flow.
* Event names computed at runtime (not literal SIDs) cannot be attributed.
* 383 referenced 64-bit values are unresolved. All of them are bitmask constants in melee move tables, not StringIDs.
