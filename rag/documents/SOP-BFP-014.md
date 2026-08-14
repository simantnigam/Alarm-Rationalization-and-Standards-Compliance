---
doc_id: SOP-BFP-014
title: Boiler Feed Pump Operating Procedure
doc_type: procedure
version: "4.0"
effective_date: 2025-09-15
approval_status: approved
supersedes: "SOP-BFP-014 v3.2"
superseded_by: null
site_scope: NorthPlant
unit_scope: Unit 1
owner: NorthPlant Operations
source_note: SYNTHETIC — authored for assignment; thresholds reflect published EEMUA 191 / ISA-18.2 benchmarks
---

# Boiler Feed Pump Operating Procedure

## 6 Alarm Response

### 6.1 General

This section defines the operator's required response to each alarm configured on the
Boiler Feed Pump train. Response times reference the rationalization record's
`allowable_response_time_s` for the alarm code.

### 6.2 Response to Vibration High-High

On receipt of a Vibration High-High alarm, the operator shall: (1) confirm the reading
on the local vibration monitor before taking action on the DCS indication alone; (2) if
confirmed, reduce pump speed to the minimum stable flow setpoint within the allowable
response time; (3) if vibration does not fall below the high setpoint within 5 minutes
of speed reduction, initiate an orderly shutdown of the affected train and notify the
Unit 1 shift supervisor. This alarm shall not be suppressed or shelved while the pump
train is in service — persistent Vibration High-High activity is evidence of a
mechanical condition requiring maintenance attention, not nuisance behaviour.
