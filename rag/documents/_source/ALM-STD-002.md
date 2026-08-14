---
doc_id: ALM-STD-002
title: Alarm Rationalization Standard
doc_type: standard
version: "1.4"
effective_date: 2025-08-01
approval_status: approved
supersedes: "ALM-STD-002 v1.3"
superseded_by: null
site_scope: ALL
unit_scope: ALL
owner: Alarm Management Team
source_note: SYNTHETIC - authored for assignment; see MANIFEST.md
---

# Alarm Rationalization Standard

## 1 Purpose and Scope

This standard defines the process by which an existing alarm is reviewed, documented,
and either retained, modified, or removed from service. It applies to every alarm
configured on a monitored console at any site and is the governing reference for the
rationalization workflow the copilot supports. It does not itself set suppression
eligibility criteria - those live in `ALM-CRIT-003` - but it defines the process a
suppression decision must be produced through.

## 2 References and Terms

### 2.1 Referenced Standards

This standard is informed by, but does not reproduce, the ANSI/ISA-18.2 alarm
management lifecycle and the EEMUA 191 alarm systems guide. Where a numeric threshold in
this standard or a related document reflects a published benchmark from either source,
the originating document's front matter carries a `source_note` recording that fact.

### 2.2 Definitions

Terms used in this standard - alarm, stale alarm, chattering alarm, fleeting alarm,
nuisance alarm, alarm flood - carry the meanings defined in `ALM-PHIL-001` Section 2 and
are not redefined here. This standard adds only the process vocabulary in Section 2.3.

### 2.3 Rationalization Record Elements

Every rationalized alarm shall carry a documented rationalization record consisting of
exactly four elements: (1) **cause** - the process condition or equipment state that
activates the alarm; (2) **consequence** - what happens if the operator does not
respond; (3) **corrective action** - the specific step the operator takes in response;
and (4) **allowable response time** - the maximum time, in seconds, between alarm
activation and the required operator action before the consequence becomes
unavoidable. A rationalization record missing any of these four elements is incomplete
and shall not be treated as a valid basis for a priority or suppression decision.

## 3 Documentation Requirements

### 3.1 Minimum Documentation Set

A complete rationalization record shall reference the specific alarm code, the asset it
is configured on, and the rationalization record elements defined in Section 2.3.
Records lacking a documented cause or consequence shall not be used to justify any
change to the alarm's priority, setpoint, or suppression state.

### 3.2 Record Retention

Rationalization records shall be retained for the operational life of the alarm
configuration and superseded, not deleted, when a review changes any element. A
superseded record's `superseded_by` reference shall point at its replacement so the
revision chain remains traceable.

## 4 Rationalization Triggers

### 4.1 Recurrence Trigger

An alarm that has occurred **25 or more times within the preceding 90 days** shall be
opened for rationalization review under this standard. Opening a review is not itself a
decision to suppress, shelve, or otherwise change the alarm - it is a requirement that
the alarm's documentation be examined and, where warranted, a decision recorded through
the process this standard defines and against the criteria `ALM-CRIT-003` sets.

### 4.2 Manual Trigger

A rationalization review may also be opened manually by the Alarm Owner at any time,
independent of any recurrence or chattering trigger, where operational experience
indicates review is warranted.

### 4.3 Chattering Trigger

An alarm whose chatter index reaches **6 or more** within the review period shall be
opened for rationalization review under this standard, in addition to any review opened
under Section 4.1. A high chatter index is frequently a stronger signal of a nuisance
condition than raw occurrence count alone, since it reflects instability at the
setpoint rather than a merely frequent but stable condition.

## 5 Documentation, Rationalization, and Management of Change

### 5.1 Process Overview

Every change to an alarm's priority, setpoint, or suppression state proceeds through
three stages in order: **Documentation** (Section 3, producing or updating the
rationalization record), **Rationalization** (evaluating the documented alarm against
the eligibility criteria in `ALM-CRIT-003` and any applicable site policy), and
**Management of Change** (formal approval under `ALM-CRIT-003` Section 4.1 before the
change takes effect). No stage may be skipped, and a change implemented out of this
order is not valid regardless of the strength of the underlying evidence.

### 5.2 Roles

The Alarm Owner is accountable for the rationalization record and for opening reviews
under Section 4. The Operations Supervisor for the affected unit co-approves the
Management of Change record. Neither role may approve a change unilaterally; both
approvals are required under `ALM-CRIT-003` Section 4.1.
