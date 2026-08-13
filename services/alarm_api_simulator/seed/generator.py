"""Deterministic seed generator (06-data-model.md §1-2, §6). `realistic` and `compact`
share one code path, scaled by profile; only volume differs. Scenario-seeded, not purely
random (assumption A-04): the guarantee cases below are deliberately engineered, and a
background randomizer fills out believable volume around them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from alarm_api_simulator.seed.identifiers import alarm_code as make_alarm_code
from alarm_api_simulator.seed.identifiers import alarm_id as make_alarm_id
from alarm_api_simulator.seed.identifiers import asset_id as make_asset_id
from alarm_api_simulator.seed.topology import TOPOLOGY, UnitProfile

# Target alarms/day/unit by character, per profile (01-architecture.md §1 seed profiles).
_DAILY_RATE = {
    "realistic": {
        "well_behaved_baseline": 40,
        "flood_prone": 150,
        "correlation_rich": 40,
        "nuisance_heavy": 150,
        "active_alarm_rich": 40,
    },
    "compact": {
        "well_behaved_baseline": 12,
        "flood_prone": 45,
        "correlation_rich": 12,
        "nuisance_heavy": 45,
        "active_alarm_rich": 12,
    },
}

_MEASUREMENTS_BY_TYPE: dict[str, list[tuple[str, str]]] = {
    "pump": [("VIB", "HH"), ("VIB", "H"), ("TEMP", "HH"), ("PRESS", "LL"), ("FLOW", "L")],
    "compressor": [("VIB", "HH"), ("TEMP", "HH"), ("PRESS", "HH"), ("SURGE", "H")],
    "motor": [("TEMP", "HH"), ("VIB", "H"), ("CURR", "HH"), ("CURR", "LL")],
    "valve": [("POS", "DEV"), ("POS", "FAIL"), ("COMM", "FAIL")],
    "exchanger": [("TEMP", "HH"), ("PRESS", "HH"), ("DP", "HH")],
    "turbine": [("VIB", "HH"), ("TEMP", "HH"), ("SPEED", "HH")],
}

_RESPONSE_TIME_S = {"critical": 120.0, "high": 300.0, "medium": 900.0, "low": 1800.0}


@dataclass
class SeedDataset:
    sites: list[dict] = field(default_factory=list)
    units: list[dict] = field(default_factory=list)
    assets: list[dict] = field(default_factory=list)
    alarm_definitions: list[dict] = field(default_factory=list)
    alarms: list[dict] = field(default_factory=list)
    kpi_definitions: list[dict] = field(default_factory=list)


KPI_DEFINITIONS: tuple[dict, ...] = (
    {
        "kpi_id": "nuisance_alarm_score",
        "name": "Nuisance Alarm Score",
        "description": (
            "Composite 0-100 score combining frequency, chatter, fleeting rate, "
            "and unacknowledged rate."
        ),
        "formula": (
            "round(min(occ_per_day/10,1)*40 + min(chatter_index/6,1)*25 "
            "+ fleeting_rate*20 + unacked_rate*15)"
        ),
        "unit": "score",
        "reference": "EEMUA 191",
    },
    {
        "kpi_id": "priority_score",
        "name": "Priority Score",
        "description": (
            "0-100 ISA-18.2-shaped priority combining severity, asset criticality, "
            "and response urgency."
        ),
        "formula": (
            "round(severity_w*0.45 + criticality_w*0.25 + urgency*0.30); "
            "floored at 90 if SIF-related"
        ),
        "unit": "score",
        "reference": "ISA-18.2-2016",
    },
    {
        "kpi_id": "alarm_count",
        "name": "Alarm Count",
        "description": "Number of alarm occurrences matching the requested scope and time range.",
        "formula": "count(alarms)",
        "unit": "count",
        "reference": None,
    },
    {
        "kpi_id": "recurring_rate",
        "name": "Recurring Rate",
        "description": "Fraction of distinct alarm codes in scope with 5 or more occurrences.",
        "formula": "count(codes where occurrences >= 5) / count(distinct codes)",
        "unit": "ratio",
        "reference": "ISA-18.2-2016",
    },
    {
        "kpi_id": "avg_ack_delay",
        "name": "Average Acknowledgement Delay",
        "description": "Mean time between alarm activation and operator acknowledgement.",
        "formula": "mean(ack_delay_s)",
        "unit": "seconds",
        "reference": "EEMUA 191",
    },
    {
        "kpi_id": "critical_count",
        "name": "Critical Alarm Count",
        "description": "Number of alarm occurrences with severity=critical in scope.",
        "formula": "count(alarms where severity == 'critical')",
        "unit": "count",
        "reference": None,
    },
    {
        "kpi_id": "suppression_candidate_rate",
        "name": "Suppression Candidate Rate",
        "description": "Fraction of distinct alarm codes in scope with 10 or more occurrences.",
        "formula": "count(codes where occurrences >= 10) / count(distinct codes)",
        "unit": "ratio",
        "reference": "EEMUA 191",
    },
)


def _severity_for_condition(condition: str, *, is_sif: bool) -> str:
    if is_sif:
        return "critical"
    if condition in ("HH", "LL"):
        return "high"
    if condition in ("FAIL", "COMM"):
        return "high"
    if condition in ("H", "L"):
        return "medium"
    return "low"  # DEV


def _alarm_type_for(measurement: str, asset_type: str) -> str:
    if measurement in ("FAIL", "COMM"):
        return "device"
    if measurement == "POS":
        return "deviation"
    return "process"


def _cause_consequence_action(
    asset_name: str, measurement: str, condition: str
) -> tuple[str, str, str]:
    cause = (
        f"{measurement} at {asset_name} crossed the {condition} setpoint due to normal "
        "process variation or developing mechanical wear."
    )
    consequence = (
        f"Continued operation beyond setpoint risks equipment damage and a potential "
        f"trip of {asset_name}."
    )
    corrective_action = (
        f"Operator to verify the {measurement.lower()} reading, inspect {asset_name} "
        "locally, and initiate corrective maintenance if the condition persists."
    )
    return cause, consequence, corrective_action


def _build_sites_units() -> tuple[list[dict], list[dict]]:
    sites = [{"name": name} for name in dict.fromkeys(u.site for u in TOPOLOGY)]
    units = [
        {"name": u.unit, "site": u.site, "operator_console_id": u.operator_console_id}
        for u in TOPOLOGY
    ]
    return sites, units


def _build_assets(topology: tuple[UnitProfile, ...]) -> list[dict]:
    rows = []
    for unit in topology:
        for a in unit.assets:
            rows.append(
                {
                    "asset_id": make_asset_id(
                        site=unit.site, unit=unit.unit, tag_prefix=a.tag_prefix, seq=a.seq
                    ),
                    "asset_name": a.name,
                    "asset_type": a.asset_type,
                    "site": unit.site,
                    "unit": unit.unit,
                    "criticality": a.criticality,
                    "service_description": f"{a.asset_type.title()} in {unit.site} {unit.unit}",
                    "manufacturer": None,
                    "model": None,
                    "install_date": None,
                    "parent_asset_id": None,
                    "tag_prefix": a.tag_prefix,
                }
            )
    return rows


def _build_alarm_definitions(
    rng: random.Random, topology: tuple[UnitProfile, ...], sif_asset_name: str, sif_tag_prefix: str
) -> list[dict]:
    rows = []
    for unit in topology:
        for a in unit.assets:
            asset_id = make_asset_id(
                site=unit.site, unit=unit.unit, tag_prefix=a.tag_prefix, seq=a.seq
            )
            candidates = _MEASUREMENTS_BY_TYPE[a.asset_type]
            n_codes = 2 if len(candidates) <= 2 else rng.randint(2, min(4, len(candidates)))
            chosen = rng.sample(candidates, n_codes)
            for measurement, condition in chosen:
                is_sif = a.name == sif_asset_name and measurement == "VIB"
                severity = _severity_for_condition(condition, is_sif=is_sif)
                cause, consequence, corrective_action = _cause_consequence_action(
                    a.name, measurement, condition
                )
                rows.append(
                    {
                        "alarm_code": make_alarm_code(
                            tag_prefix=a.tag_prefix,
                            seq=a.seq,
                            measurement=measurement,
                            condition=condition,
                        ),
                        "asset_id": asset_id,
                        "alarm_name": f"{measurement} {_condition_label(condition)}",
                        "alarm_type": "safety"
                        if is_sif
                        else _alarm_type_for(measurement, a.asset_type),
                        "severity": severity,
                        "measurement": measurement,
                        "unit_of_measure": _unit_of_measure(measurement),
                        "setpoint": round(rng.uniform(50, 500), 1),
                        "deadband": round(rng.uniform(1, 10), 2),
                        "on_delay_s": round(rng.uniform(0, 5), 1),
                        "is_sif_related": is_sif,
                        "safety_classification": "sif" if is_sif else "none",
                        "sif_tag": f"{sif_tag_prefix}-SIF-01" if is_sif else None,
                        "cause": cause,
                        "consequence": consequence,
                        "corrective_action": corrective_action,
                        "allowable_response_time_s": _RESPONSE_TIME_S[severity],
                        "is_suppressed": False,
                        "suppression_reason": None,
                    }
                )
    return rows


def _condition_label(condition: str) -> str:
    return {
        "HH": "High-High",
        "H": "High",
        "L": "Low",
        "LL": "Low-Low",
        "DEV": "Deviation",
        "FAIL": "Failure",
        "COMM": "Comm Loss",
    }[condition]


def _unit_of_measure(measurement: str) -> str:
    return {
        "VIB": "mm/s",
        "TEMP": "degC",
        "PRESS": "bar",
        "FLOW": "m3/h",
        "SURGE": "%",
        "CURR": "A",
        "POS": "%",
        "FAIL": "bool",
        "COMM": "bool",
        "DP": "bar",
        "SPEED": "rpm",
    }[measurement]


def _make_occurrence(
    rng: random.Random,
    *,
    alarm_def: dict,
    asset: dict,
    start_time: datetime,
    duration_s: float | None,
    force_active: bool = False,
    operator_pool: list[str],
) -> dict:
    status: str
    end_time: datetime | None
    ack_time: datetime | None
    ack_delay_s: float | None

    if force_active or duration_s is None:
        status = "active"
        end_time = None
        duration_s = None
    else:
        end_time = start_time + timedelta(seconds=duration_s)
        status = "cleared"

    if status == "active" and rng.random() < 0.6:
        ack_delay_s = round(rng.uniform(5, 300), 1)
        ack_time = start_time + timedelta(seconds=ack_delay_s)
    elif status == "cleared" and rng.random() < 0.85:
        ack_delay_s = round(rng.uniform(2, min(600, max(3, duration_s or 600))), 1)
        ack_time = start_time + timedelta(seconds=ack_delay_s)
    else:
        ack_delay_s = None
        ack_time = None

    setpoint = alarm_def["setpoint"]
    value_at_activation = round(
        setpoint + rng.uniform(1, 20) * (1 if rng.random() < 0.5 else -1), 2
    )

    return {
        "alarm_id": "",  # assigned by caller (global sequence)
        "alarm_code": alarm_def["alarm_code"],
        "asset_id": asset["asset_id"],
        "asset_name": asset["asset_name"],
        "site": asset["site"],
        "unit": asset["unit"],
        "alarm_name": alarm_def["alarm_name"],
        "alarm_type": alarm_def["alarm_type"],
        "severity": alarm_def["severity"],
        "is_sif_related": alarm_def["is_sif_related"],
        "start_time": start_time,
        "end_time": end_time,
        "ack_time": ack_time,
        "status": status,
        "duration_s": duration_s,
        "ack_delay_s": ack_delay_s,
        "value_at_activation": value_at_activation,
        "setpoint": setpoint,
        "operator_id": rng.choice(operator_pool),
    }


def generate_dataset(*, profile: str, seed: int, now: datetime) -> SeedDataset:
    if profile not in _DAILY_RATE:
        raise ValueError(f"unknown profile: {profile!r}")

    rng = random.Random(seed)
    window_start = now - timedelta(days=365)

    sites, units = _build_sites_units()
    assets = _build_assets(TOPOLOGY)
    assets_by_id = {a["asset_id"]: a for a in assets}

    sif_asset_name = "Boiler Feed Pump 102"
    alarm_definitions = _build_alarm_definitions(rng, TOPOLOGY, sif_asset_name, "BFP102")

    alarms: list[dict] = []
    seq = 0

    def emit(row: dict) -> None:
        nonlocal seq
        seq += 1
        row["alarm_id"] = make_alarm_id(year=now.year, seq=seq)
        alarms.append(row)

    operator_pools = {
        u.unit: [f"OP-{u.operator_console_id}-{i}" for i in (1, 2, 3)] for u in TOPOLOGY
    }

    # --- Background volume: every code gets a randomized share of its unit's daily rate.
    codes_by_unit: dict[str, list[dict]] = {}
    for d in alarm_definitions:
        unit = assets_by_id[d["asset_id"]]["unit"]
        codes_by_unit.setdefault(unit, []).append(d)

    for unit_profile in TOPOLOGY:
        rate = _DAILY_RATE[profile][unit_profile.character]
        target_total = int(rate * 365)
        codes = codes_by_unit[unit_profile.unit]
        weights = [rng.random() ** 2 for _ in codes]  # power-law-ish spread
        weight_sum = sum(weights) or 1.0

        for d, weight in zip(codes, weights, strict=True):
            asset = assets_by_id[d["asset_id"]]
            n = max(1, round(target_total * (weight / weight_sum)))
            for _ in range(n):
                start = window_start + timedelta(
                    seconds=rng.uniform(0, (now - window_start).total_seconds())
                )
                duration = max(0.5, rng.lognormvariate(mu=5.5, sigma=1.2))
                emit(
                    _make_occurrence(
                        rng,
                        alarm_def=d,
                        asset=asset,
                        start_time=start,
                        duration_s=duration,
                        operator_pool=operator_pools[unit_profile.unit],
                    )
                )

    # --- Deliberate scenario overlays (assumption A-04) -------------------------------

    # Stale + fleeting population: guaranteed on a NorthPlant Unit 1 code, independent
    # of whatever the random background happened to produce.
    stale_source_code = codes_by_unit["Unit 1"][0]
    stale_asset = assets_by_id[stale_source_code["asset_id"]]
    emit(
        _make_occurrence(
            rng,
            alarm_def=stale_source_code,
            asset=stale_asset,
            start_time=now - timedelta(days=10),
            duration_s=100_000.0,  # > 24h
            operator_pool=operator_pools["Unit 1"],
        )
    )
    fleeting_source_code = codes_by_unit["Unit 4"][0]
    fleeting_asset = assets_by_id[fleeting_source_code["asset_id"]]
    for i in range(6):
        emit(
            _make_occurrence(
                rng,
                alarm_def=fleeting_source_code,
                asset=fleeting_asset,
                start_time=now - timedelta(days=20, minutes=i),
                duration_s=rng.uniform(0.5, 4.5),
                operator_pool=operator_pools["Unit 4"],
            )
        )

    # Chattering: >=3 occurrences of one code within one minute.
    chatter_source_code = codes_by_unit["Unit 4"][1]
    chatter_asset = assets_by_id[chatter_source_code["asset_id"]]
    chatter_base = now - timedelta(days=15)
    for i in range(8):
        emit(
            _make_occurrence(
                rng,
                alarm_def=chatter_source_code,
                asset=chatter_asset,
                start_time=chatter_base + timedelta(seconds=6 * i),
                duration_s=rng.uniform(1, 3),
                operator_pool=operator_pools["Unit 4"],
            )
        )

    # Unit 2 flood window: >10 occurrences within 10 minutes, across several codes on
    # the unit's console (a flood is a console-level event, not one alarm_code).
    flood_codes = codes_by_unit["Unit 2"][:4]
    flood_base = now - timedelta(days=45)
    for i in range(16):
        code = flood_codes[i % len(flood_codes)]
        asset = assets_by_id[code["asset_id"]]
        emit(
            _make_occurrence(
                rng,
                alarm_def=code,
                asset=asset,
                start_time=flood_base + timedelta(seconds=30 * i),
                duration_s=rng.uniform(30, 300),
                operator_pool=operator_pools["Unit 2"],
            )
        )

    # BFP101 recurring high/critical in the last 90 days (§7 mandatory scenario).
    bfp101_code = next(
        d
        for d in alarm_definitions
        if assets_by_id[d["asset_id"]]["asset_name"] == "Boiler Feed Pump 101"
        and d["severity"] in ("high", "critical")
    )
    bfp101_asset = assets_by_id[bfp101_code["asset_id"]]
    for _ in range(30):
        emit(
            _make_occurrence(
                rng,
                alarm_def=bfp101_code,
                asset=bfp101_asset,
                start_time=now - timedelta(days=rng.uniform(0, 89), hours=rng.uniform(0, 23)),
                duration_s=rng.uniform(60, 1800),
                operator_pool=operator_pools["Unit 1"],
            )
        )

    # EastRefinery: guaranteed active alarms (recent, unresolved).
    er_codes = codes_by_unit["Unit 5"][:5]
    for i, code in enumerate(er_codes):
        asset = assets_by_id[code["asset_id"]]
        emit(
            _make_occurrence(
                rng,
                alarm_def=code,
                asset=asset,
                start_time=now - timedelta(minutes=10 * (i + 1)),
                duration_s=None,
                force_active=True,
                operator_pool=operator_pools["Unit 5"],
            )
        )

    # SIF demo case: high-frequency occurrences on the deliberately SIF-flagged code so
    # its nuisance_score lands near the top of the achievable range (Phase 7 refuses it
    # anyway, regardless of score).
    sif_code = next(d for d in alarm_definitions if d["is_sif_related"])
    sif_asset = assets_by_id[sif_code["asset_id"]]
    for i in range(45):
        emit(
            _make_occurrence(
                rng,
                alarm_def=sif_code,
                asset=sif_asset,
                start_time=now - timedelta(days=rng.uniform(0, 89), hours=rng.uniform(0, 23)),
                duration_s=rng.uniform(0.5, 4.5) if i % 3 == 0 else rng.uniform(60, 600),
                operator_pool=operator_pools["Unit 1"],
            )
        )
    for i in range(8):
        emit(
            _make_occurrence(
                rng,
                alarm_def=sif_code,
                asset=sif_asset,
                start_time=now - timedelta(days=5, seconds=6 * i),
                duration_s=rng.uniform(1, 3),
                operator_pool=operator_pools["Unit 1"],
            )
        )

    return SeedDataset(
        sites=sites,
        units=units,
        assets=assets,
        alarm_definitions=alarm_definitions,
        alarms=alarms,
        kpi_definitions=list(KPI_DEFINITIONS),
    )
