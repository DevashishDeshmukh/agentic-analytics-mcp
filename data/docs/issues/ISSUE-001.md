---
id: ISSUE-001
title: Order channel missing before March 2023
tables: [analytics.orders]
status: open
updated_at: "2025-02-11"
---
orders.channel is NULL for every order with order_date before 2023-03-01. The
channel field was added to checkout in March 2023 and was never backfilled.

Impact: channel breakdowns that include January or February 2023 show a NULL
group. Report NULL as "unknown" and mention this gap in the answer.
