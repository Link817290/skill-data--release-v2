---
name: pkg-config-metadata-debugging
description: Use when a native library installs .pc metadata but pkg-config emits stale, missing, or non-relocatable compiler and linker paths for downstream builds.
---

# pkg-config Metadata Debugging

Treat a `.pc` file as an executable metadata contract. The file may exist and be discoverable
while its expanded flags still point to the wrong headers, archives, dependencies, or prefix.

## Inspect expansion in context

1. Use `pkg-config --debug`, module search diagnostics, or a queried file-location variable
   to identify the metadata file actually selected.
2. Capture `--cflags`, `--libs`, and `--static --libs` separately. The default link query and
   static link query can expose different dependency defects.
3. Read the selected `.pc` file and expand variables from their definitions. Distinguish a
   stale `prefix`, `libdir`, or `includedir` from a missing `Requires` or `Libs.private` edge.
4. Compile a minimal consumer with only the emitted flags. A successful query proves syntax
   and discovery, not that its paths or transitive link contract work.

## Relocation reasoning

For every stale path, trace three representations: the producer template, the installed
`.pc` assignment, and the final emitted flag. Determine whether the build configurator,
pkg-config variable expansion, or the invoking shell introduced it. Then change the earliest
owning representation and regenerate the installed file. Keep directory names supplied by
the build system rather than assuming one library layout on every platform.

Variable references may pass through more than one expansion layer. Inspect literal template
text, installed text, and query output rather than guessing which layer consumed a sigil or
escape. A repair is complete only when the installed file remains valid in a new location and
its emitted flags select files inside that location.

### Derive paths from actual destinations

For each path variable, record four fields: the producer option that selects the destination,
the installed metadata location, the runtime expansion anchor, and the file the emitted flag
must select. Then perturb library and include destination shapes independently. This exposes
constants that encode one observed layout without prescribing a particular template spelling.

Judge a template by the relationships its expansions maintain, not by one preferred spelling.
Document which producer input and runtime base determine each emitted path, then place the
perturbation result alongside the final query, compile, and run evidence.

## Validation and boundaries

Install to a fresh prefix, copy or move the complete tree, remove the original, and make only
the moved metadata directory discoverable. Confirm that `--cflags` and `--libs` contain no old
prefix, then compile and run a consumer. Test static flags when the package claims static
consumption.

Do not add ambient compiler search paths to make the test pass, and do not edit an installed
`.pc` file as the final repair. Fix the producer template or generation rule. Keep CMake package
exports and pkg-config metadata as separate contracts: repairing one does not establish the
other.
