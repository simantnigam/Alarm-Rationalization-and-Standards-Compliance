"""Plant topology (06-data-model.md §2), derived from the Postman chaining collection:
CHAIN-06 pins NorthPlant+Unit 1; CHAIN-07/04 pin SouthPlant+Unit 3; CHAIN-09/08 pin
EastRefinery+Unit 5. Unit names are globally unique across sites.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetSpec:
    name: str
    asset_type: str  # pump | compressor | motor | valve | exchanger | turbine
    tag_prefix: str
    seq: int
    criticality: str  # low | medium | high | critical


@dataclass(frozen=True)
class UnitProfile:
    site: str
    unit: str
    character: str
    operator_console_id: str
    assets: tuple[AssetSpec, ...]

    @property
    def asset_names(self) -> tuple[str, ...]:
        return tuple(a.name for a in self.assets)


TOPOLOGY: tuple[UnitProfile, ...] = (
    UnitProfile(
        site="NorthPlant",
        unit="Unit 1",
        character="well_behaved_baseline",
        operator_console_id="NP-U1-CONSOLE",
        assets=(
            AssetSpec("Boiler Feed Pump 101", "pump", "BFP", 101, "critical"),
            AssetSpec("Boiler Feed Pump 102", "pump", "BFP", 102, "critical"),
            AssetSpec("Condensate Pump 103", "pump", "CDP", 103, "high"),
            AssetSpec("Condensate Pump 104", "pump", "CDP", 104, "high"),
            AssetSpec("Cooling Water Pump 105", "pump", "CWP", 105, "medium"),
            AssetSpec("Cooling Water Pump 106", "pump", "CWP", 106, "medium"),
            AssetSpec("Lube Oil Pump 107", "pump", "LOP", 107, "high"),
            AssetSpec("Feedwater Valve 108", "valve", "FWV", 108, "high"),
            AssetSpec("Feedwater Valve 109", "valve", "FWV", 109, "high"),
            AssetSpec("Steam Turbine 110", "turbine", "STB", 110, "critical"),
            AssetSpec("Deaerator Level Valve 111", "valve", "DLV", 111, "medium"),
            AssetSpec("Heat Exchanger 112", "exchanger", "HEX", 112, "medium"),
            AssetSpec("Startup Pump 113", "pump", "SUP", 113, "low"),
            AssetSpec("Vent Valve 114", "valve", "VTV", 114, "low"),
        ),
    ),
    UnitProfile(
        site="NorthPlant",
        unit="Unit 2",
        character="flood_prone",
        operator_console_id="NP-U2-CONSOLE",
        assets=(
            AssetSpec("Recycle Compressor 201", "compressor", "RCP", 201, "high"),
            AssetSpec("Recycle Compressor 202", "compressor", "RCP", 202, "high"),
            AssetSpec("Process Pump 203", "pump", "PRP", 203, "high"),
            AssetSpec("Process Pump 204", "pump", "PRP", 204, "high"),
            AssetSpec("Cooling Fan 205", "motor", "CLF", 205, "medium"),
            AssetSpec("Cooling Fan 206", "motor", "CLF", 206, "medium"),
            AssetSpec("Reactor Feed Valve 207", "valve", "RFV", 207, "critical"),
            AssetSpec("Reactor Feed Valve 208", "valve", "RFV", 208, "critical"),
            AssetSpec("Quench Exchanger 209", "exchanger", "QEX", 209, "medium"),
            AssetSpec("Quench Exchanger 210", "exchanger", "QEX", 210, "medium"),
            AssetSpec("Separator Level Valve 211", "valve", "SLV", 211, "high"),
            AssetSpec("Booster Pump 212", "pump", "BSP", 212, "medium"),
            AssetSpec("Trim Cooler 213", "exchanger", "TMC", 213, "low"),
            AssetSpec("Vent Fan 214", "motor", "VNF", 214, "low"),
        ),
    ),
    UnitProfile(
        site="SouthPlant",
        unit="Unit 3",
        character="correlation_rich",
        operator_console_id="SP-U3-CONSOLE",
        assets=(
            AssetSpec("Gas Compressor 301", "compressor", "CMP", 301, "critical"),
            AssetSpec("Gas Compressor 302", "compressor", "CMP", 302, "critical"),
            AssetSpec("Gas Compressor 303", "compressor", "CMP", 303, "high"),
            AssetSpec("Gas Compressor 304", "compressor", "CMP", 304, "high"),
            AssetSpec("Gas Compressor 305", "compressor", "CMP", 305, "medium"),
            AssetSpec("Suction Valve 306", "valve", "SUV", 306, "medium"),
            AssetSpec("Discharge Valve 307", "valve", "DIV", 307, "medium"),
            AssetSpec("Interstage Cooler 308", "exchanger", "ISC", 308, "medium"),
            AssetSpec("Knockout Drum Pump 309", "pump", "KOP", 309, "low"),
            AssetSpec("Suction Filter Valve 310", "valve", "SFV", 310, "low"),
        ),
    ),
    UnitProfile(
        site="SouthPlant",
        unit="Unit 4",
        character="nuisance_heavy",
        operator_console_id="SP-U4-CONSOLE",
        assets=(
            AssetSpec("Control Valve 401", "valve", "CTV", 401, "medium"),
            AssetSpec("Control Valve 402", "valve", "CTV", 402, "medium"),
            AssetSpec("Control Valve 403", "valve", "CTV", 403, "medium"),
            AssetSpec("Control Valve 404", "valve", "CTV", 404, "low"),
            AssetSpec("Control Valve 409", "valve", "CTV", 409, "low"),
            AssetSpec("Shell Exchanger 405", "exchanger", "SHX", 405, "medium"),
            AssetSpec("Shell Exchanger 406", "exchanger", "SHX", 406, "medium"),
            AssetSpec("Shell Exchanger 410", "exchanger", "SHX", 410, "low"),
            AssetSpec("Trim Exchanger 407", "exchanger", "TRX", 407, "low"),
            AssetSpec("Bypass Valve 408", "valve", "BPV", 408, "low"),
        ),
    ),
    UnitProfile(
        site="EastRefinery",
        unit="Unit 5",
        character="active_alarm_rich",
        operator_console_id="ER-U5-CONSOLE",
        assets=(
            AssetSpec("Blower Motor 501", "motor", "BLM", 501, "high"),
            AssetSpec("Blower Motor 502", "motor", "BLM", 502, "high"),
            AssetSpec("Blower Motor 503", "motor", "BLM", 503, "medium"),
            AssetSpec("Blower Motor 504", "motor", "BLM", 504, "medium"),
            AssetSpec("Blower Motor 510", "motor", "BLM", 510, "low"),
            AssetSpec("Feed Pump 505", "pump", "FDP", 505, "critical"),
            AssetSpec("Feed Pump 506", "pump", "FDP", 506, "critical"),
            AssetSpec("Feed Pump 511", "pump", "FDP", 511, "high"),
            AssetSpec("Product Compressor 507", "compressor", "PCP", 507, "high"),
            AssetSpec("Surge Drum Valve 508", "valve", "SDV", 508, "medium"),
            AssetSpec("Export Compressor 509", "compressor", "XCP", 509, "high"),
        ),
    ),
)
