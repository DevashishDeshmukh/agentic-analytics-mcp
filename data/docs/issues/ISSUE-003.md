---
id: ISSUE-003
title: About 2% of customers have no region
tables: [analytics.customers, analytics.regions]
status: open
updated_at: "2025-05-30"
---
customers.region_id is NULL for about 2% of customers whose address could not
be geocoded.

Impact: regional breakdowns using an inner join to regions silently drop these
customers. Totals by region will not add up to the overall total. Mention the
gap when reporting regional numbers.
