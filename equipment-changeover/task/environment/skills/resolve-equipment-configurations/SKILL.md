---
name: resolve-equipment-configurations
description: Resolve device configuration and consumable compatibility across manuals, installed options and planned jobs before preparing setup instructions.
---

Separate the physical unit, installed option, consumable and requested output.
A family name is not a complete configuration. A material fitting through a
machine does not establish that the requested result fits its working envelope.

Read [configuration layers](references/configuration-layers.md) when a manual has
model or option branches. Read [units and bounds](references/units-and-bounds.md)
when converting physical requests to controller parameters. Use
`scripts/convert_units.py --mm ... --density ... --maximum ...` for a dimensional
check; its result is not approval to alter the requested output.

Retain unresolved facts as conditional. Describe the smallest verification that
would resolve them, rather than selecting a convenient default.
