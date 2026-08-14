# Corpus Manifest

Provenance record for every document the RAG pipeline ingests (07-rag-corpus.md §1).
**All eight documents are authored for this assignment.** ISA-18.2-2016 and EEMUA 191
are paid, copyrighted publications; committing them would be redistribution. These are
original documents built around real, publicly-referenced benchmark *figures* (freely
citable facts), never copied standard *prose* (the copyrighted expression).

| doc_id | Title | Type | Format | Benchmark figure(s) reflected |
|---|---|---|---|---|
| `ALM-PHIL-001` | Alarm Philosophy | philosophy | md | Stale >24h, chattering ≥3/min, flood >10/10min, ≤150/day/operator, ≤300 max, 80/15/5 priority mix (EEMUA 191) |
| `ALM-STD-002` | Alarm Rationalization Standard | standard | **pdf** (source: `_source/ALM-STD-002.md`) | Documentation → Rationalization → MoC workflow (ISA-18.2 D-R-M) |
| `ALM-CRIT-003` | Suppression & Shelving Approval Criteria | criteria | md | ≥25 occurrences/90d, nuisance score ≥60, 8h shelving limit |
| `SAF-INST-005` | SIS Alarm Handling Instruction | safety | md | SIF alarms never suppressible (ISA-18.2 safety-instrumented-function handling) |
| `SITE-POL-007` | NorthPlant Site Operating Policy | policy | md | Adopts the ≥25/90d corporate threshold unmodified |
| `SITE-POL-008` | EastRefinery Site Operating Policy | policy | md | Raises the threshold to ≥40/90d + nuisance score ≥75 (deliberate conflict with `SITE-POL-007`) |
| `SOP-BFP-014` | Boiler Feed Pump Operating Procedure | procedure | md | Site/unit-specific operator response steps |
| `SEC-TEST-999` | Quarantine Test Fixture | quarantined | md | None — deliberately poisoned; never a real benchmark source |

Every file's front matter carries:

```yaml
source_note: SYNTHETIC — authored for assignment; thresholds reflect published EEMUA 191 / ISA-18.2 benchmarks
```

`SEC-TEST-999` carries a distinct `source_note` explaining it is a deliberately poisoned
injection-defence test fixture, not a benchmark-derived policy document.

## Ingestion scope

The ingester reads `rag/documents/*.md` and `rag/documents/*.pdf` only — never
`rag/documents/_source/`, so `ALM-STD-002`'s markdown source and its rendered PDF
artifact cannot both be indexed (07-rag-corpus.md §5). `ALM-STD-002.pdf` is generated
from `_source/ALM-STD-002.md` by `scripts/build_pdf_corpus.py`.
