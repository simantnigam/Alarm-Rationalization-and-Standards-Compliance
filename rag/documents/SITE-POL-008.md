---
doc_id: SITE-POL-008
title: EastRefinery Site Operating Policy
doc_type: policy
version: "1.4"
effective_date: 2026-02-01
approval_status: approved
supersedes: null
superseded_by: null
site_scope: EastRefinery
unit_scope: ALL
owner: EastRefinery Operations
source_note: SYNTHETIC — authored for assignment; thresholds reflect published EEMUA 191 / ISA-18.2 benchmarks
---

# EastRefinery Site Operating Policy

## 3 Alarm Rationalization Supplement

### 3.1 Applicability

This section supplements, and does not replace, `ALM-CRIT-003`. Where this policy
states a numeric threshold, that threshold applies at EastRefinery in place of the
corresponding value in `ALM-CRIT-003`; where it is silent, `ALM-CRIT-003` governs
directly.

### 3.2 Occurrence Evidence at EastRefinery

EastRefinery's console loading is materially higher than NorthPlant's, so an alarm at
EastRefinery shall not be considered for suppression or shelving unless it has occurred
**40 or more times within the preceding 90 days** — a higher bar than the corporate
threshold in `ALM-CRIT-003` §3.1.

### 3.3 Nuisance Score Threshold at EastRefinery

In addition to §3.2, an alarm at EastRefinery shall not be considered for suppression or
shelving unless its composite nuisance score is **75 or greater**, a higher bar than the
corporate threshold in `ALM-CRIT-003` §3.2. Both §3.2 and §3.3 must be satisfied
together; meeting only one is not sufficient.
