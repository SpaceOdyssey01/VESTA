# ASB to VESTA import helpers

This directory keeps scripts for converting `Benchmark/ASB` cases into VESTA-style seed files.

The current default target mapping is:

- ASB source: DPI-native prompt injection cases
- VESTA architecture: `architecture_and_modules -> input_perception_risk -> instruction_injection`
- VESTA ids: `input_perception_risk.instruction_injection`
- Risk tool role: `input_injection_action`

Migration records must be updated in `docs/asb_migration_record.md` whenever ASB cases, tools, subtype mappings, or runtime behavior are migrated or changed.

Example for generating a small VESTA-compatible seed file:

```powershell
python scripts/asb_import/import_asb_to_vesta.py `
  --channels dpi `
  --attack-types naive `
  --limit-cases 7
```

By default this writes:

```text
data/architecture_and_modules/tasks/input_perception_risk/instruction_injection_seeds/asb_seeds.json
```

Use `--output` to write to a staging path first when reviewing generated instances.
