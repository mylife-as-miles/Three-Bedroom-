// Independently authored offline driver for the pinned dconstruct compiler core.
// No packaging, registry mutation, game install access, or deployment.
#include "compilation/compiler_funcs.h"
int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: compile_core source.dcpl output.bin\n"; return 2; }
    std::ifstream input(argv[1]);
    if (!input) return 2;
    std::string source((std::istreambuf_iterator<char>(input)), {});
    dconstruct::compilation::global_state global;
    auto elements = dconstruct::compilation::run_compilation(source, global);
    if (!elements) return 3;
    auto binary = dconstruct::ast::program::make_binary(std::move(*elements), global);
    if (!binary) { std::cerr << binary.error() << '\n'; return 4; }
    std::ofstream output(argv[2], std::ios::binary);
    output.write(reinterpret_cast<const char*>(binary->first.get()), binary->second);
    return output ? 0 : 5;
}
