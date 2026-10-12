# dconstruct on Linux: build notes and patches

This is a Linux build of the `dconstruct` CLI (disassembler and decompiler for
Naughty Dog DC script `.bin` files). It is built from the upstream clone at
`.private/ext/dconstruct` (https://github.com/DeepQuantum/dconstruct, tested at
commit `583b38d`). The build never modifies that clone.

## Build

```sh
tools/extract/dconstruct_linux/build.sh --install-deps   # first time (apt: g++-14 cmake libtbb-dev curl patch)
tools/extract/dconstruct_linux/build.sh                  # incremental
tools/extract/dconstruct_linux/build.sh --clean          # from scratch
```

`build.sh` does the following:

1. Copies `include/`, `source/{disassembly,decompilation,compilation,ast,base}/`
   and `source/main_cli.cpp` into `.private/build/dconstruct-linux/src/`.
2. Applies `patches/*.patch` (`patch -p1`).
3. Puts our own `CMakeLists.txt` in place. It replaces upstream's, which is
   Windows-only.
4. Fetches the `ctre.hpp` single header (hanickadot/compile-time-regular-expressions
   v3.10.0, checked by sha256). Upstream gets it from the `qui` UI submodule.
5. Builds with g++-14 (C++23 with `<print>` and `std::println`; GCC 13 lacks them) in Release mode.
6. Copies `test/fixtures/dc/sidbase_new_fixed.bin` to `build/sidbase.bin`. The
   binary looks for `sidbase.bin` next to itself via `/proc/self/exe`.

The result is `.private/build/dconstruct-linux/build/dconstruct`.

The `compilation/` sources are built because `driver_functions.cpp` and the
decompiler depend on them. The following are not built: UI, debugger, hooking,
minhook, LLVM transpiler, LSP, tests (gtest) and `dcc`.

## Usage

```sh
DC=.private/build/dconstruct-linux/build/dconstruct
# single file -> foo.asm + foo.dcpl (decompile is the default)
$DC -i .private/extracted16/dc1/ss-t2/ss-openable-drawer.bin -o .private/dconstruct_out/ss-openable-drawer.asm
# whole tree (parallel via TBB); the output dir mirrors the input tree as <name>.bin.asm / <name>.bin.dcpl
$DC -i .private/extracted16/dc1 -o .private/dconstruct_out/dc1 [--show_warnings]
# disassembly only
$DC -i file.bin -o file.asm --no_decompile
```

Other flags: `--language C|Racket|Python`, `--pascal_case`, `--no_optimize`,
`-g t2r|t1x|uc4` (default `t2r`), `--graphs`.

When `-o` names a directory, that directory must already exist. Otherwise the
path is treated as a file name.

All output is derived from proprietary game code and must stay under
`.private/`.

## Patches (`patches/`)

| # | File(s) | Why |
|---|---------|-----|
| 0001 | `include/base.h` | The user-defined literal operators `_r`, `_imm` and `_b` take `u64`. On LP64 Linux `uint64_t` is `unsigned long`, which is not a valid literal-operator parameter type. Changed to `unsigned long long`. |
| 0002 | `source/base/base.cpp` | `executable_path()` used `GetModuleFileNameW` from `<windows.h>`. Wrapped in `#ifdef _WIN32`. The non-Windows path is `read_symlink("/proc/self/exe")`. |
| 0003 | `include/decompilation/control_flow_graph.h`, `source/decompilation/control_flow_graph.cpp` | Graphviz is optional, behind `DCONSTRUCT_NO_GRAPHVIZ`, which our CMakeLists defines. Upstream needs the bundled Graphviz-13 win64 libs. Ubuntu's Graphviz 2.42 headers are incompatible: they use non-const `char*` APIs, lack `agsafeset_html`, and define `TRUE`/`FALSE` macros that break `token_type::TRUE`. With the define set, `--graphs` writes an unrendered `.dot` file (same nodes, HTML labels and colours) in place of each `.svg`. Render it with `dot -Tsvg x.dot -o x.svg`. |
| 0004 | `source/ast/state_script/state_script.cpp`, `source/ast/program.cpp` | Missing `<cstring>` (`std::memcpy`) and `<cmath>` (`std::ceil`). MSVC pulls these in transitively. |

No other source changes were needed. The AVX-512 relocation path in
`binaryfile.cpp` is already behind `#ifdef AVX512`, which is not defined, so
the scalar fallback is used. `<immintrin.h>` compiles fine with GCC.
`std::execution::par_unseq` uses libstdc++'s TBB backend (`libtbb-dev`). If
TBB is missing, CMake skips it and the batch runs serially.

## Known limitations

- `--graphs` produces `.dot` files, not `.svg` files (see patch 0003).
- Upstream decompiler limitations remain. For example, `goto-shared-block-0x..()`
  is emitted for shared code blocks, and a small number of functions are reported
  by `--show_warnings` as inaccurate (147 of ~211k functions in dc1).
- Batch mode calls `std::terminate()` if a single file fails to load (upstream
  behaviour). No file in dc1 triggered this.

## Licensing note

Upstream dconstruct is licensed CC BY-NC-ND 4.0 (no derivatives). The four
`.patch` files are kept **locally only** (`patches/` is gitignored) because
they contain context lines from upstream sources. The changes are small and
fully described above, so they can be re-created by hand; alternatively ask the
dconstruct author before publishing them.
