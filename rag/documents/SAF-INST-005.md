---
doc_id: SAF-INST-005
title: Safety Instrumented System Alarm Handling Instruction
doc_type: safety
version: "1.2"
effective_date: 2025-11-01
approval_status: approved
supersedes: null
superseded_by: null
site_scope: ALL
unit_scope: ALL
owner: Process Safety Engineering
source_note: SYNTHETIC — authored for assignment; thresholds reflect published EEMUA 191 / ISA-18.2 benchmarks
---

# Safety Instrumented System Alarm Handling Instruction

## 1 Purpose

This instruction governs the handling of alarms associated with Safety Instrumented
Functions (SIFs) and other alarms providing sole protection against a defined hazard. It
takes precedence over `ALM-CRIT-003` wherever the two documents would otherwise
conflict.

## 2 Handling Requirements

### 2.1 Prohibition on Suppression

Alarms forming part of a Safety Instrumented Function, or providing sole protection
against a defined hazard, shall not be suppressed, shelved, or placed out of service
under any circumstances. This prohibition is absolute: it is not subject to occurrence
count, nuisance score, acknowledgement rate, or any other evidentiary criterion in
`ALM-CRIT-003` §3, and no Management of Change approval can waive it.

### 2.2 Compensating Measures

Where a SIF-linked alarm exhibits nuisance behaviour, the corrective path is engineering
correction of the underlying instrumentation or logic solver configuration, not
suppression of the alarm that reports it. Any such correction shall itself follow the
plant Management of Change process and be reviewed by Process Safety Engineering before
implementation.
