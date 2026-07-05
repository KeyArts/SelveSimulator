"""
Tests for the Selve Gateway Simulator.

Run with:  pytest tests/ -v
"""
import pytest
import xml.etree.ElementTree as ET

from selve_sim.server import LoopbackSimulator
from selve_sim.state import GatewayState, CommType


# ── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sim():
    """Fresh simulator with default devices for each test."""
    s = LoopbackSimulator()
    s.open()
    return s


# ── Helper ──────────────────────────────────────────────────────────────────

def call(sim: LoopbackSimulator, method: str, *params) -> list:
    """Build a methodCall XML, send it, return list of parsed XML strings."""
    parts = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<methodCall>",
             f"<methodName>{method}</methodName>"]
    if params:
        parts.append("<array>")
        for p in params:
            if isinstance(p, int):
                parts.append(f"<int>{p}</int>")
            elif isinstance(p, str):
                parts.append(f"<string>{p}</string>")
            elif isinstance(p, list):
                parts.append("<array>")
                for item in p:
                    parts.append(f"<int>{item}</int>")
                parts.append("</array>")
        parts.append("</array>")
    parts.append("</methodCall>")
    xml = "".join(parts)
    return sim.send_raw(xml)


def first_response(responses: list) -> ET.Element:
    """Parse the first response XML and return root element."""
    assert responses, "No response received"
    return ET.fromstring(responses[0].split("\n", 1)[-1].strip())


def is_ok(root: ET.Element) -> bool:
    return root.tag == "methodResponse" and root.find("fault") is None


def is_fault(root: ET.Element) -> bool:
    return root.find("fault") is not None


def get_int(root: ET.Element, index: int = 0) -> int:
    ints = root.findall(".//int")
    return int(ints[index].text)


def get_string(root: ET.Element, index: int = 0) -> str:
    strs = root.findall(".//string")
    return strs[index].text or ""


# ════════════════════════════════════════════════════════════════════════════
# GATEWAY TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestGateway:
    def test_ping(self, sim):
        r = first_response(call(sim, "selve.GW.gateway.ping"))
        assert is_ok(r)
        assert get_int(r) == 1

    def test_get_serial(self, sim):
        r = first_response(call(sim, "selve.GW.gateway.getSerial"))
        assert is_ok(r)
        assert "SIM" in get_string(r)

    def test_get_firmware(self, sim):
        r = first_response(call(sim, "selve.GW.gateway.getFirmwareVersion"))
        assert is_ok(r)
        assert get_string(r)  # non-empty

    def test_get_spec(self, sim):
        r = first_response(call(sim, "selve.GW.gateway.getSpec"))
        assert is_ok(r)
        ints = [int(e.text) for e in r.findall(".//int")]
        assert len(ints) == 4
        assert ints[0] >= 16  # max devices

    def test_set_get_led(self, sim):
        call(sim, "selve.GW.gateway.setLed", 2)
        r = first_response(call(sim, "selve.GW.gateway.getLed"))
        assert get_int(r) == 2

    def test_get_temperature(self, sim):
        r = first_response(call(sim, "selve.GW.gateway.getTemperature"))
        assert is_ok(r)
        assert 0 <= get_int(r) <= 100

    def test_unknown_method_returns_fault(self, sim):
        r = first_response(call(sim, "selve.GW.does.not.exist"))
        assert is_fault(r)

    def test_factory_reset_clears_devices(self, sim):
        call(sim, "selve.GW.gateway.factoryReset")
        r = first_response(call(sim, "selve.GW.device.getIds"))
        # After factory reset, array of IDs should be empty
        ints = r.findall(".//int")
        assert len(ints) == 0


# ════════════════════════════════════════════════════════════════════════════
# DEVICE TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestDevices:
    def test_get_ids_returns_devices(self, sim):
        r = first_response(call(sim, "selve.GW.device.getIds"))
        assert is_ok(r)
        ints = [int(e.text) for e in r.findall(".//int")]
        assert len(ints) > 0

    def test_get_info_device_1(self, sim):
        r = first_response(call(sim, "selve.GW.device.getInfo", 1))
        assert is_ok(r)
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[0] == 1  # device id

    def test_get_info_missing_id_faults(self, sim):
        r = first_response(call(sim, "selve.GW.device.getInfo", 999))
        assert is_fault(r)

    def test_get_values_initial_position(self, sim):
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        assert is_ok(r)
        ints = [int(e.text) for e in r.findall(".//int")]
        # id, position, target, tilt, unreachable
        assert ints[0] == 1

    def test_move_down_sets_position_100(self, sim):
        call(sim, "selve.GW.device.moveDown", 1)
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 100  # position

    def test_move_up_sets_position_0(self, sim):
        call(sim, "selve.GW.device.moveDown", 1)
        call(sim, "selve.GW.device.moveUp", 1)
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 0

    def test_move_pos_exact(self, sim):
        call(sim, "selve.GW.device.movePos", 1, 42)
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 42

    def test_move_pos_clamped(self, sim):
        call(sim, "selve.GW.device.movePos", 1, 150)  # over 100
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 100

    def test_move_generates_event(self, sim):
        responses = call(sim, "selve.GW.device.moveDown", 1)
        # First is the response, second (if events_enabled) is the event
        assert len(responses) >= 1
        if len(responses) > 1:
            ev = ET.fromstring(responses[1].split("\n", 1)[-1].strip())
            assert ev.tag == "methodCall"
            method = ev.findtext("methodName")
            assert "event" in method

    def test_set_label(self, sim):
        call(sim, "selve.GW.device.setLabel", 1, "TestRollladen")
        r = first_response(call(sim, "selve.GW.device.getInfo", 1))
        strings = [e.text for e in r.findall(".//string")]
        assert "TestRollladen" in strings

    def test_delete_device(self, sim):
        call(sim, "selve.GW.device.delete", 1)
        r = first_response(call(sim, "selve.GW.device.getInfo", 1))
        assert is_fault(r)

    def test_update_all_devices_returns_events(self, sim):
        responses = call(sim, "selve.GW.gateway.updateAllDevices")
        # 1 response + N events (one per Commeo device)
        commeo_count = sum(
            1 for d in sim.state.devices.values()
            if d.comm_type == CommType.COMMEO
        )
        assert len(responses) == 1 + commeo_count

    def test_save_and_move_pos1(self, sim):
        call(sim, "selve.GW.device.movePos", 1, 33)
        call(sim, "selve.GW.device.savePos1", 1)
        call(sim, "selve.GW.device.movePos", 1, 0)
        call(sim, "selve.GW.device.movePos1", 1)
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 33


# ════════════════════════════════════════════════════════════════════════════
# GROUP TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestGroups:
    def test_get_group_ids(self, sim):
        r = first_response(call(sim, "selve.GW.group.getIds"))
        assert is_ok(r)

    def test_read_group(self, sim):
        r = first_response(call(sim, "selve.GW.group.read", 1))
        assert is_ok(r)
        # group id returned
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[0] == 1

    def test_group_move_down_affects_members(self, sim):
        call(sim, "selve.GW.group.moveDown", 1)
        # Device 1 is a member of group 1
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 100

    def test_group_move_up(self, sim):
        call(sim, "selve.GW.group.moveDown", 1)
        call(sim, "selve.GW.group.moveUp", 1)
        r = first_response(call(sim, "selve.GW.device.getValues", 1))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 0

    def test_group_stop(self, sim):
        call(sim, "selve.GW.group.stop", 1)
        r = first_response(call(sim, "selve.GW.group.getIds"))
        assert is_ok(r)

    def test_group_read_nonexistent_faults(self, sim):
        r = first_response(call(sim, "selve.GW.group.read", 999))
        assert is_fault(r)


# ════════════════════════════════════════════════════════════════════════════
# IVEO TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestIveo:
    def test_get_iveo_ids(self, sim):
        r = first_response(call(sim, "selve.GW.iveo.getIds"))
        assert is_ok(r)
        ints = [int(e.text) for e in r.findall(".//int")]
        assert 10 in ints  # device_id=10 is Iveo

    def test_iveo_command_up(self, sim):
        call(sim, "selve.GW.iveo.commandManual", 10, 1)  # 1=UP
        r = first_response(call(sim, "selve.GW.device.getValues", 10))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 0  # position

    def test_iveo_command_down(self, sim):
        call(sim, "selve.GW.iveo.commandManual", 10, 2)  # 2=DOWN
        r = first_response(call(sim, "selve.GW.device.getValues", 10))
        ints = [int(e.text) for e in r.findall(".//int")]
        assert ints[1] == 100


# ════════════════════════════════════════════════════════════════════════════
# PROTOCOL ROBUSTNESS
# ════════════════════════════════════════════════════════════════════════════

class TestRobustness:
    def test_malformed_xml_returns_fault(self, sim):
        responses = sim.send_raw("<methodCall><methodName>selve.GW.gateway.ping</BAD>")
        # Should get a fault or nothing (no crash)
        # If we get a response, it must be a fault
        if responses:
            r = ET.fromstring(responses[0].split("\n", 1)[-1].strip())
            assert is_fault(r)

    def test_empty_params_on_device_info(self, sim):
        r = first_response(call(sim, "selve.GW.device.getInfo"))
        assert is_fault(r)

    def test_two_commands_in_sequence(self, sim):
        r1 = first_response(call(sim, "selve.GW.gateway.ping"))
        r2 = first_response(call(sim, "selve.GW.gateway.ping"))
        assert is_ok(r1)
        assert is_ok(r2)

    def test_two_commands_concatenated(self, sim):
        """Simulate two XML messages arriving in one read() call."""
        msg1 = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<methodCall><methodName>selve.GW.gateway.ping</methodName></methodCall>')
        msg2 = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<methodCall><methodName>selve.GW.gateway.getSerial</methodName></methodCall>')
        responses = sim.send_raw(msg1 + msg2)
        assert len(responses) >= 2
