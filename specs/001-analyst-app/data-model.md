# Data model: Brindlecove Analyst

Postgres 17 with pgvector. Three schemas, so database roles can be scoped.

## Schema `corpus` (documents)

**source_file**: one row per file in `data/raw/`.
`id`, `path` (unique), `sha256`, `format`, `source_system`, `bytes`,
`parse_status` (ok, partial, failed), `parse_notes`.

**passage**: one row per searchable passage.
`id`, `source_file_id`, `ordinal`, `text`, `char_start`, `char_end`, `page`,
`doc_date`, `author`, `version`, `kind` (email, ticket, slide, page, section,
chat, image_description, ...), `is_machine_text` (true for OCR and vision
output), `injection_suspect` (bool), `tsv` (tsvector, GIN index),
`embedding` (vector(1024), HNSW index).

## Schema `analytics` (structured data)
One table per structured dataset (CSV, parquet, Avro, legacy tables, logs).
Every table carries `_source_file_id` and `_source_line` so a SQL result can
cite the rows it read. Column names are normalised; original headers are kept
in `analytics._columns`.

## Schema `app` (the website)

**invite**: `id`, `company`, `token_hash`, `created_at`, `expires_at` (14 days),
`revoked_at`, `daily_quota` (default 15).

**question**: `id`, `invite_id`, `ip_hash`, `text`, `created_at`, `model`,
`tokens_in`, `tokens_out`, `cost_usd`, `status`, `answer`.

**tool_call**: `id`, `question_id`, `step`, `tool`, `input` (jsonb),
`result_summary`, `ms`.

**citation**: `id`, `question_id`, `passage_id` or `sql_text`, `valid`.

**spend_month**: `month`, `usd`, `cap_usd` (10).

## Roles

| Role | Can do |
|---|---|
| `ingest_writer` | Write `corpus` and `analytics`; used only by `make ingest` |
| `app_api` | Read `corpus`; read and write `app` |
| `agent_reader` | SELECT on `analytics` and `corpus.passage` only; `statement_timeout` 5 s; no access to `app` |
