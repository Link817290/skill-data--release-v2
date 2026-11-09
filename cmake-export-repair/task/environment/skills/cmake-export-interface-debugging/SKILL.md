---
name: cmake-export-interface-debugging
description: Use when a CMake producer builds locally but an installed package cannot be configured or linked by a downstream project, especially with shared/static variants or multiple export sets.
---

# CMake Export Interface Debugging

Treat the producer build and the consumer build as different states. A local target can
compile while the installed package exposes different target names, files, include paths,
or transitive links.

## Establish both contracts

1. Record the producer options, generator, install prefix, and build directory. Keep the
   prefix outside the source tree so stale files cannot satisfy a later check.
2. Inspect the generated package configuration, export files, per-configuration imports,
   and installed archive/header paths. Do not infer generated metadata from a source
   declaration.
3. Build a minimal consumer through the package's public configuration entry point. It
   should include a public header, link a public target, and produce a runnable binary when
   that is meaningful. Configure-only checks miss link-interface defects.
4. Compare the requested consumer target with the exported target set. For every imported
   target, follow `INTERFACE_LINK_LIBRARIES`, include directories, compile definitions, and
   imported file locations. Every referenced imported target must be provided by the same
   package or by an explicitly documented dependency.

## Export-set reasoning

Build a four-column inventory for each consumer-visible variant: build-tree target,
installed artifact, generated imported target, and downstream link item. Populate it from
the actual build and install outputs. Any blank or renamed transition identifies a narrower
owner than the final linker message alone.

Inspect each configured variant separately. Variants may intentionally share an output name
while using distinct CMake target names and dependencies. Trace the actual dependency graph
from the consumer request through every imported target and archive; a package is incomplete
when an imported target refers to an item the prefix does not provide. A plain name in
`target_link_libraries` can be interpreted differently from an imported target, so read the
generated link command and import metadata before deciding whether the failure is naming,
search-path, or export-set related.

## Repair discipline

Bind the diagnosis to the first failing command, the missing target or file, the owning
declaration, and the generated import artifact. Select the smallest correction at the owner
boundary established by that evidence. Preserve public target identifiers, output names,
include layout, and unrelated destinations unless the evidence requires a change. A
consumer-only include path or raw archive flag is a workaround, not proof that the package
contract is repaired.

## Relocatable install metadata

An isolated prefix is not automatically a relocatable prefix. After installation, copy or
move the complete prefix, remove the original, and configure the consumer against only the
new location. When this fails, compare the moved import/config files with their producer
templates and install declarations. Record which layer first introduces the old path and
whether it describes an artifact, include interface, dependency, or legacy variable.

Change the declaration that owns the earliest incorrect expansion, regenerate the package,
and repeat the move. Do not patch generated import files as a final repair because the next
install replaces them. Distinguish imported targets from legacy variables and other metadata
formats; a check of one interface cannot establish the others.

### Non-default destination geometry

Audit destination geometry as data rather than as incidental strings. Make a matrix whose rows
are generated imports, compatibility variables, headers, and libraries, and whose columns are
the producer-selected destination, runtime anchor, generated value, and consuming check. Change
the shapes of at least two destinations independently and rerun the matrix. A repair is general
only when its relationships survive that perturbation without consumer-side overrides.

Imported targets and compatibility variables can take different generation paths, so exercise
both even if they initially agree. In the diagnosis, name the producer input and runtime anchor
for each generated value and distinguish a relationship maintained by the producer from a magic
constant that merely fits the first layout.

## Stop conditions

Stop and report an environment or dependency problem when a clean producer build fails before
the suspected interface is generated. Stop when the requested target is intentionally private
and no public package contract promises it. Otherwise, accept a repair only after a fresh
prefix, any promised prefix move, and an independent consumer all pass.
