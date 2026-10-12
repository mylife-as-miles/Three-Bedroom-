# Format and analysis notes

Reference implementations: DeepQuantum/dconstruct at 583b38d8b25b2f0b2cd079db70d8caac0a69f3a7, include/DCHeader.h, include/DCScript.h, source/base/binaryfile.cpp, include/disassembly/opcodes.h and source/disassembly/disassembler.cpp; icemesh/t2r-dc-disasm at bb37ab4f4af8ed5431d939cd1e5818a1641bd7f8, DC/state-script structures and script-manager-eval. Our Python parser is independently authored and read-only; dconstruct is unmodified.

DC header magic is stored as little-endian integer 0x44433030 (bytes 30 30 43 44). Header text size identifies the relocation bit table; strings offset identifies the string area. Relocated pointer words are recognized via the bit table and retained as file offsets, never guessed by integer range. StateScript, state, on-block, track and lambda structure sizes are validated. Lambda flag is 0xDEADBEEF1337F00D; instructions are eight-byte records; register arguments begin at 49. Branch targets use dst + (operand2 << 8).

LookupInt/Float/Pointer load a GLOBAL REFERENCE, not a literal SID or numeric constant. A called lookup symbol resolves to a named call target; when used as an argument it remains global-ref. LoadStaticU64Imm is a literal SID/value. Result identities preserve caller/PC, not native return values. Joins retain only constants identical on all incoming paths; unknown loads/arithmetic lose value knowledge. Native side effects are not simulated. This avoids linear-tracer contamination across conditional branches.

All call sites found by CFG reachability are a static may-call superset; conditions are not executed. Definitions with the same symbol are candidate bindings until import/object context resolves them. Event name equality is not delivery proof. Structural scan also finds valid embedded lambdas, even in animation/data modules.

Full readable string extraction and token hashing are private. Public symbol matches include untyped aligned words, with exact FNV verification and resolution provenance. Matching an aligned word is weaker evidence than a typed state/event/declaration or an executed call opcode. Full decompilation and all numeric data field schemas remain outside the indexer's coverage.

Game-interactable records have 512-byte payloads at exported addresses; the next record's type tag is at +0x200. Unknown field semantics are retained as offsets rather than invented property names. Original raw bytecode, string literals and full SID seed are excluded from publishable outputs.

Public JSON encodes nonfinite IEEE-754 constants with explicit tagged objects (NaN/Infinity/-Infinity), preserving their meaning without invalid JSON numeric tokens. Descriptive literal strings are hash-redacted; complete originals remain private.
