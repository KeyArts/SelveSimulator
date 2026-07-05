"""
In-memory state model for the simulated Selve gateway.

Supports Commeo (bidirectional, position feedback) and Iveo (unidirectional).
Device positions are 0 (open) … 100 (closed), matching the Selve convention.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional
import time


class DeviceType(IntEnum):
    SHUTTER    = 1   # Rollladen
    AWNING     = 2   # Markise
    BLIND      = 3   # Jalousie (with tilt)
    DIMMER     = 4
    SWITCH     = 5


class CommType(IntEnum):
    COMMEO = 1   # bidirectional
    IVEO   = 2   # unidirectional


@dataclass
class SimDevice:
    device_id: int
    name: str
    device_type: DeviceType = DeviceType.SHUTTER
    comm_type: CommType = CommType.COMMEO
    position: int = 0          # 0=open, 100=closed
    tilt: int = 0              # degrees (blinds only)
    target_position: int = 0
    unreachable: bool = False
    # Saved positions
    pos1: int = 25
    pos2: int = 75
    # RF address (24-bit)
    rf_address: int = 0

    def move_to(self, target: int):
        self.target_position = max(0, min(100, target))
        self.position = self.target_position  # instant in simulator

    def stop(self):
        self.target_position = self.position


@dataclass
class SimGroup:
    group_id: int
    name: str
    device_ids: List[int] = field(default_factory=list)


@dataclass
class GatewayState:
    serial: str = "SIM-0001"
    firmware: str = "3.3.1"
    led_mode: int = 1
    duty_mode: int = 0
    rf_base_addr: int = 0x000000
    temperature: int = 28      # °C
    forward_enabled: bool = False
    events_enabled: bool = True
    devices: Dict[int, SimDevice] = field(default_factory=dict)
    groups: Dict[int, SimGroup] = field(default_factory=dict)
    # Iveo devices share the same device dict, filtered by comm_type
    # Sensors / senders omitted for brevity (can be added)

    def add_default_devices(self):
        """Populate with a few demo Commeo shutters and one Iveo shutter."""
        for i in range(1, 4):
            self.devices[i] = SimDevice(
                device_id=i,
                name=f"Rollladen {i}",
                device_type=DeviceType.SHUTTER,
                comm_type=CommType.COMMEO,
                position=0,
                rf_address=0x100000 + i,
            )
        # One Iveo device
        self.devices[10] = SimDevice(
            device_id=10,
            name="Iveo Markise",
            device_type=DeviceType.AWNING,
            comm_type=CommType.IVEO,
            position=0,
            rf_address=0x200001,
        )
        # One blind with tilt
        self.devices[5] = SimDevice(
            device_id=5,
            name="Jalousie Wohnzimmer",
            device_type=DeviceType.BLIND,
            comm_type=CommType.COMMEO,
            position=50,
            tilt=45,
            rf_address=0x100010,
        )
        # A group
        self.groups[1] = SimGroup(
            group_id=1,
            name="Alle Rollläden",
            device_ids=[1, 2, 3, 5],
        )

    def commeo_ids(self) -> List[int]:
        return [d.device_id for d in self.devices.values()
                if d.comm_type == CommType.COMMEO]

    def iveo_ids(self) -> List[int]:
        return [d.device_id for d in self.devices.values()
                if d.comm_type == CommType.IVEO]
