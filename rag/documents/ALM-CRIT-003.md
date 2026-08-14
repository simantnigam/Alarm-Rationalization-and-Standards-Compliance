---
doc_id: ALM-CRIT-003
title: Suppression and Shelving Approval Criteria
doc_type: criteria
version: "3.0"
effective_date: 2026-01-10
approval_status: approved
supersedes: "ALM-CRIT-003 v2.4"
superseded_by: null
site_scope: ALL
unit_scope: ALL
owner: Alarm Management Team
source_note: SYNTHETIC — authored for assignment; thresholds reflect published EEMUA 191 / ISA-18.2 benchmarks
---

# Suppression and Shelving Approval Criteria

## 1 Purpose

This document establishes the minimum evidentiary and approval requirements an alarm
must satisfy before it may be suppressed, shelved, or otherwise placed out of service.
It is the primary reference the rationalization workflow evaluates every suppression or
shelving request against.

## 3 Eligibility Criteria

### 3.1 Minimum Occurrence Evidence

An alarm shall not be considered for suppression or shelving unless it has occurred **25
or more times within the preceding 90 days**. Occurrence counts shall be taken from a
fixed 90-day lookback window, independent of any shorter reporting period a request may
otherwise reference, so that eligibility decisions remain stable regardless of how the
request was framed.

### 3.2 Nuisance Score Threshold

An alarm shall not be considered for suppression or shelving unless its composite
nuisance score (see `ALM-PHIL-001` §2.5) is **60 or greater**. Scores below this
threshold indicate the alarm, while frequent, is not yet disproportionate to the
attention it demands.

### 3.3 Severity Exclusion

An alarm classified as **critical** severity shall never be eligible for suppression or
shelving under this document, regardless of occurrence count or nuisance score. Critical
alarms may only be addressed through engineering correction, setpoint review, or formal
management of change to the underlying alarm configuration.

### 3.4 Acknowledgement Evidence

An alarm with an unacknowledged rate of **30% or greater** does not, by itself, prohibit
suppression, but requires manual review by the Alarm Owner before a decision is recorded
(`NEEDS_REVIEW`). A high unacknowledged rate can indicate either genuine nuisance
behaviour or an operator workload problem that suppression alone will not fix.

## 4 Approval Requirements

### 4.1 Management of Change Approval

Every suppression or shelving decision requires a completed Management of Change (MoC)
record co-approved by both the Alarm Owner and the Operations Supervisor for the
affected unit before it takes effect. A decision recorded without both approvals is not
valid regardless of how strong the supporting evidence is.

### 4.2 Shelving Time Limit

Where an alarm is shelved rather than permanently suppressed, the shelving period shall
not exceed **8 hours** from the time of approval. Shelving beyond this limit requires a
new approval under §4.1; it is not renewable by simple extension.

## 5 Prohibitions

### 5.1 Safety Instrumented Function Alarms

Alarms forming part of a Safety Instrumented Function, or otherwise providing sole
protection against a defined hazard, are never eligible for suppression or shelving
under this document. See `SAF-INST-005` §2.1, which governs without exception and
overrides every criterion in §3 regardless of how favourable the evidence is.
