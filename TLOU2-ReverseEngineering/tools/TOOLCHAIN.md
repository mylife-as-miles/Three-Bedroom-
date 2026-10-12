# Toolchain provenance

- [dconstruct](https://github.com/DeepQuantum/dconstruct), commit `583b38d8b25b2f0b2cd079db70d8caac0a69f3a7`. Original source unchanged. Current CMake targets Windows. SID seed: test/fixtures/dc/sidbase_new_fixed.bin, 1,410,109 entries, SHA-256 c2d983bfb5afbfc51591a2d9c003e2e801abe841042768107dc0bd91ce5ceb94. Compiler/DCPL grammar, state parser, relocation and opcodes were inspected. No compiler output or round-trip modification is claimed.
- [t2r-dc-disasm](https://github.com/icemesh/t2r-dc-disasm), commit `bb37ab4f4af8ed5431d939cd1e5818a1641bd7f8`, MIT. Local private Linux copy uses fopen_s/memcpy_s/_bittest compatibility wrappers and fixes include-directory case. Five actual game modules were independently disassembled, yielding 4,095 comparable matching call targets. Full output remains private. This validates call labels/offsets, not native effects or every argument.
- [UnPSARC](https://github.com/rm-NoobInCoding/UnPSARC), MIT. DSAR/PSAR structure reference; our independently written extractor handles actual LZ4/zero-padding/raw DSAR and zlib/raw PSAR, validates lengths/paths and fails unsupported types.
- [icemesh/dc](https://github.com/icemesh/dc), public structure reference, inspected as supporting context.
- 7-Zip Linux 25.01 used to extract the RAR; Python 3.12 and lz4 4.4.5 used for analysis. 7-Zip/vendor assets are private dependencies, not repository payloads.

Place upstream clones under .private/vendor/. Avoid recursive git staging of vendor fixtures or game files. Prefer shallow clones to reduce storage. The full SID database is not republished; only corpus-used symbol metadata is retained publicly.

Sources in the original Three-Bedroom handoff contain a version discrepancy: architecture/README describe 1.6, SOURCE_NOTES describes 1.4. This run independently acquires the requested 1.6 archive and identifies every extracted file by hash. Prior artifacts are preserved and reconciled as leads, not silently substituted for primary evidence.
