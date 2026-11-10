# saas-analyst-agent

> **ALL DATA IN THIS REPOSITORY IS SYNTHETIC.** Brindlecove Software, its
> customers, staff, emails, contracts and numbers are invented by a seeded
> program. Any resemblance to real companies or people is coincidental. Phone
> numbers use the reserved 555-01xx range, and every email address and web
> domain uses the reserved `.example` suffix. There are no real credentials;
> anything that looks like a key is a placeholder such as `REDACTED`.

A learning and portfolio project: build an AI analyst agent that can answer
questions over a large, messy enterprise data estate, and show its work by
citing the exact file it pulled each fact from.

## What is here

| Path | What it is |
|---|---|
| `docs/COMPANY_BIBLE.md` | The fake company: history, products, prices, people, systems by era, ID schemes |
| `generator/` | Seeded Python program that builds the whole data estate |
| `data/raw/` | The generated "proprietary" files, ~221 MB, ~8,300 files, 66 source folders |
| `data/CATALOG.md` | Map of every source: format, era, encoding, quirks. Starts with what to review |
| `data/GOLDEN_FACTS.yaml` | 52 answer-key questions and 4 planted cross-source patterns, each with a trail of files and the traps along the way |

## Regenerate and verify

```bash
pip install -r requirements.txt
python -m generator            # seed 42 -> data/raw/ and data/GOLDEN_FACTS.yaml (~80 s)
python -m generator.verify     # re-derives 31 golden answers and 2 patterns by parsing the raw files
```

The same seed gives byte-identical files on every run. Options:
`--seed N`, `--out DIR`, `--scale 0.25` (fewer customers), `--only crm billing`.

## Status

The data store and agent stack are not chosen yet. The raw data is
deliberately store-agnostic. Decisions are recorded as we go using the
Spec Kit workflow.
