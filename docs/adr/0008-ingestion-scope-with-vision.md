# ADR-0008: Ingest text, OCR text and legacy tables, plus images read by a vision model

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
Every format needs a parser. Sorted by the hardest file in each answer trail,
my count of the 52 golden facts is 38 text, 12 legacy and 2 image (GF20, a faxed
purchase order; GF21, a whiteboard photo). The estate holds about 146 image
files (jpg, tif, png).

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
1. Text-native formats only: about 38 of 52 facts reachable.
2. Plus existing OCR text and legacy tables (mainframe, dBase, Lotus, old Excel,
   parquet, Avro, protobuf, event logs): up to 50 of 52.
3. Option 2 plus images described by a vision model at ingest: all 52.

## Decision
Option 2 **plus images read by a vision model** at ingest. Each image gets a
text description that becomes a searchable passage tied to the image file.

## Consequences
- All 52 golden facts are reachable in version 1.
- A one-time model bill at ingest. With Haiku 5.5 my estimate is well under $1
  for about 146 images; it counts against the monthly cap and is cached so a
  rebuild does not pay again unless an image changes.
- An image citation points to the picture plus the generated description, and
  the viewer shows both, labelled as a machine description.
- A description is model output, so it is treated as untrusted document text
  like everything else (Principle II).
