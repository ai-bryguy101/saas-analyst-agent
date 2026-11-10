# usage_daily

Daily rollup per tenant, written by the usage-rollup-job (Glue). Partitioned by year/month.
Schema v2 from 2025-07: `api_calls` widened to int64 (v1 capped at int32 max), `mobile_sessions` added.
`tenant_id` is the tenant slug; join to `product_events/tenants.csv` for the customer.
