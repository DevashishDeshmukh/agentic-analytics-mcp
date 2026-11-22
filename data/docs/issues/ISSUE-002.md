---
id: ISSUE-002
title: Refund reason not tracked before 2024
tables: [analytics.refunds]
status: open
updated_at: "2024-03-20"
---
refunds.reason is NULL for all refunds issued before 2024-01-01. Reason codes
were introduced with the new returns portal on 2024-01-01.

Impact: refund-by-reason analysis is only meaningful from 2024 onward.
