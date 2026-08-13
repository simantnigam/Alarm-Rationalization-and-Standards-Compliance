---
doc_id: ALM-PHIL-001
title: Alarm Philosophy
doc_type: philosophy
version: "1.0"
effective_date: 2026-01-10
approval_status: approved
supersedes: null
superseded_by: null
site_scope: ALL
unit_scope: ALL
owner: Alarm Management Team
source_note: SYNTHETIC — authored for assignment; thresholds reflect published EEMUA 191 / ISA-18.2 benchmarks
---

# Alarm Philosophy

## 2 Definitions

### 2.1 Alarm

An audible and/or visible means of indicating to the operator an equipment malfunction,
process deviation, or abnormal condition requiring a timely response.

### 2.2 Stale Alarm

An alarm that has remained continuously active for more than **24 hours** without
returning to normal. A stale alarm has typically stopped conveying useful information to
the operator and is a primary candidate for rationalization review.

### 2.3 Chattering Alarm

An alarm that repeatedly transitions between active and normal (clear) states at a rate
of **three or more transitions per minute**. Chattering alarms consume operator attention
disproportionately to the risk they represent and are prohibited without engineering
correction under §5 of `ALM-CRIT-003`.

### 2.4 Fleeting Alarm

An alarm that returns to normal in under **5 seconds** of activation. A high fleeting
rate for a given alarm code indicates the alarm setpoint sits too close to normal
process variation.

### 2.5 Nuisance Alarm

An alarm that activates excessively, unnecessarily, or without an operator response
being required — typically evidenced by a high composite nuisance score (frequency,
chattering, fleeting rate, and unacknowledged rate combined; see
`GET /analytics/kpi-definitions` for the exact formula).

### 2.6 Alarm Flood

A condition in which more than **10 alarms occur within any rolling 10-minute window**
on a single operator console. During a flood, the operator's ability to respond to any
individual alarm is materially degraded.

## 3 Performance Targets

### 3.1 Acceptable Average Alarm Rate

The long-term average alarm rate presented to a single operator console should not
exceed **150 alarms per day** (approximately 1 every 10 minutes during a 16-hour
console-attended period). This is the target rate; sustained operation above it is
evidence that rationalization is overdue.

### 3.2 Maximum Manageable Alarm Rate

A sustained rate above **300 alarms per day** per operator console is considered
unmanageable and requires immediate corrective action, not merely scheduled review.

### 3.3 Peak Alarm Rate

No operator console should be presented with more than **10 alarms in any 10-minute
window** under normal operating conditions (see §2.6, Alarm Flood).

### 3.4 Priority Distribution

A well-rationalized alarm system exhibits a priority mix of approximately **80% low,
15% high, 5% critical**. A distribution skewed toward high and critical priorities
indicates over-prioritization and erodes the operator's ability to distinguish genuinely
urgent conditions.

## 4 Priority Assignment

Alarm priority shall be assigned based on the consequence of not responding and the time
available to respond, not on the frequency or ease of detection of the underlying
condition. Safety-related consequences take precedence over production or equipment
consequences of equal time-to-respond.

## 6 Management of Change

Changes to this philosophy, and to any alarm setpoint, priority, or suppression state
governed by it, shall follow the plant Management of Change (MoC) process. A change is
authoritative only once it carries `approval_status: approved` and an `effective_date`
that has passed; documents in `draft` status, or dated in the future, are not to be
relied upon and are excluded from retrieval by the ingestion pipeline.
