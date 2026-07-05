"""
Command dispatcher: maps methodName → handler function.

Every handler receives (state: GatewayState, params: list)
and returns a SelveResponse (or SelveEvent list for push notifications).

Method naming follows the official Selve XML spec:
  selve.GW.gateway.*    – gateway management
  selve.GW.device.*     – Commeo device commands
  selve.GW.group.*      – group commands
  selve.GW.iveo.*       – Iveo commands
  selve.GW.sensor.*     – sensor (stub)
  selve.GW.sender.*     – sender (stub)
"""

import logging
from typing import Callable, Dict, List, Optional, Tuple

from .protocol import SelveResponse, SelveEvent, SelveRequest, fault
from .state import GatewayState, SimDevice, SimGroup, DeviceType, CommType

log = logging.getLogger("selve.dispatcher")

# ── Type alias ──────────────────────────────────────────────────────────────
Handler = Callable[[GatewayState, list], Tuple[SelveResponse, List[SelveEvent]]]
_registry: Dict[str, Handler] = {}


def register(method: str):
    def decorator(fn: Handler):
        _registry[method] = fn
        return fn
    return decorator


def dispatch(state: GatewayState, request: SelveRequest
             ) -> Tuple[SelveResponse, List[SelveEvent]]:
    handler = _registry.get(request.method)
    if handler is None:
        log.warning("Unknown method: %s", request.method)
        return fault(f"Unknown method: {request.method}", 99)
    try:
        return handler(state, request.params)
    except Exception as exc:
        log.exception("Handler error for %s", request.method)
        return fault(str(exc), 2), []


def ok(*params) -> Tuple[SelveResponse, List[SelveEvent]]:
    return SelveResponse(params=list(params)), []


def ok_with_events(params, events) -> Tuple[SelveResponse, List[SelveEvent]]:
    return SelveResponse(params=list(params)), events


# ════════════════════════════════════════════════════════════════════════════
# GATEWAY COMMANDS
# ════════════════════════════════════════════════════════════════════════════

@register("selve.GW.gateway.ping")
def gw_ping(state, params):
    return ok(1)


@register("selve.GW.gateway.getState")
def gw_get_state(state, params):
    # Returns: state (int), unused
    return ok(1, 0)


@register("selve.GW.gateway.getSerial")
def gw_get_serial(state, params):
    return ok(state.serial)


@register("selve.GW.gateway.getFirmwareVersion")
def gw_get_firmware(state, params):
    return ok(state.firmware)


@register("selve.GW.gateway.getSpec")
def gw_get_spec(state, params):
    # max devices, max groups, max sensors, max senders
    return ok(64, 16, 8, 8)


@register("selve.GW.gateway.setLed")
def gw_set_led(state, params):
    if params:
        state.led_mode = int(params[0])
    return ok(1)


@register("selve.GW.gateway.getLed")
def gw_get_led(state, params):
    return ok(state.led_mode)


@register("selve.GW.gateway.setForward")
def gw_set_forward(state, params):
    if params:
        state.forward_enabled = bool(params[0])
    return ok(1)


@register("selve.GW.gateway.getForward")
def gw_get_forward(state, params):
    return ok(int(state.forward_enabled))


@register("selve.GW.gateway.setEvents")
def gw_set_events(state, params):
    if params:
        state.events_enabled = bool(params[0])
    return ok(1)


@register("selve.GW.gateway.getEvents")
def gw_get_events(state, params):
    return ok(int(state.events_enabled))


@register("selve.GW.gateway.getDuty")
def gw_get_duty(state, params):
    return ok(state.duty_mode)


@register("selve.GW.gateway.setDuty")
def gw_set_duty(state, params):
    if params:
        state.duty_mode = int(params[0])
    return ok(1)


@register("selve.GW.gateway.getRF")
def gw_get_rf(state, params):
    return ok(state.rf_base_addr)


@register("selve.GW.gateway.setRF")
def gw_set_rf(state, params):
    if params:
        state.rf_base_addr = int(params[0])
    return ok(1)


@register("selve.GW.gateway.getTemperature")
def gw_get_temperature(state, params):
    return ok(state.temperature)


@register("selve.GW.firmware.getVersion")
def fw_get_version(state, params):
    return ok(state.firmware)


@register("selve.GW.firmware.update")
def fw_update(state, params):
    log.info("Firmware update requested (simulated, no-op)")
    return ok(1)


@register("selve.GW.gateway.commandResult")
def gw_command_result(state, params):
    return ok(0, "OK")


@register("selve.GW.gateway.updateAllDevices")
def gw_update_all(state, params):
    events = []
    for dev in state.devices.values():
        if dev.comm_type == CommType.COMMEO:
            events.append(_device_event(dev))
    return ok_with_events([1], events)


@register("selve.GW.gateway.reset")
def gw_reset(state, params):
    log.warning("Gateway reset requested (simulated)")
    return ok(1)


@register("selve.GW.gateway.factoryReset")
def gw_factory_reset(state, params):
    log.warning("FACTORY RESET requested – clearing all devices/groups (simulated)")
    state.devices.clear()
    state.groups.clear()
    return ok(1)


# ════════════════════════════════════════════════════════════════════════════
# DEVICE SCAN
# ════════════════════════════════════════════════════════════════════════════

@register("selve.GW.device.scanStart")
def dev_scan_start(state, params):
    log.info("Device scan started (simulated)")
    return ok(1)


@register("selve.GW.device.scanStop")
def dev_scan_stop(state, params):
    return ok(1)


@register("selve.GW.device.scanResult")
def dev_scan_result(state, params):
    # Return list of found device IDs
    return ok(list(state.devices.keys()))


@register("selve.GW.device.save")
def dev_save(state, params):
    return ok(1)


# ════════════════════════════════════════════════════════════════════════════
# DEVICE INFO / VALUES
# ════════════════════════════════════════════════════════════════════════════

@register("selve.GW.device.getIds")
def dev_get_ids(state, params):
    ids = list(state.devices.keys())
    return ok(ids)


@register("selve.GW.device.getInfo")
def dev_get_info(state, params):
    if not params:
        return fault("Missing device id", 3)
    dev_id = int(params[0])
    dev = state.devices.get(dev_id)
    if dev is None:
        return fault(f"Device {dev_id} not found", 4)
    # id, name, type, comm_type, rf_address
    return ok(dev.device_id, dev.name, int(dev.device_type),
              int(dev.comm_type), dev.rf_address)


@register("selve.GW.device.getValues")
def dev_get_values(state, params):
    if not params:
        return fault("Missing device id", 3)
    dev_id = int(params[0])
    dev = state.devices.get(dev_id)
    if dev is None:
        return fault(f"Device {dev_id} not found", 4)
    # id, position, target, tilt, unreachable
    return ok(dev.device_id, dev.position, dev.target_position,
              dev.tilt, int(dev.unreachable))


@register("selve.GW.device.setFunction")
def dev_set_function(state, params):
    return ok(1)


@register("selve.GW.device.setLabel")
def dev_set_label(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev = state.devices.get(int(params[0]))
    if dev:
        dev.name = str(params[1])
    return ok(1)


@register("selve.GW.device.setType")
def dev_set_type(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev = state.devices.get(int(params[0]))
    if dev:
        dev.device_type = DeviceType(int(params[1]))
    return ok(1)


@register("selve.GW.device.delete")
def dev_delete(state, params):
    if params:
        state.devices.pop(int(params[0]), None)
    return ok(1)


@register("selve.GW.device.writeManual")
def dev_write_manual(state, params):
    # params: id, rf_address, name, type
    if len(params) < 4:
        return fault("Missing parameters", 3)
    dev_id = int(params[0])
    state.devices[dev_id] = SimDevice(
        device_id=dev_id,
        rf_address=int(params[1]),
        name=str(params[2]),
        device_type=DeviceType(int(params[3])),
    )
    return ok(1)


@register("selve.GW.device.updateValues")
def dev_update_values(state, params):
    if not params:
        return fault("Missing device id", 3)
    dev = state.devices.get(int(params[0]))
    events = []
    if dev and dev.comm_type == CommType.COMMEO:
        events.append(_device_event(dev))
    return ok_with_events([1], events)


@register("selve.GW.device.setValue")
def dev_set_value(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev = state.devices.get(int(params[0]))
    if dev:
        dev.position = max(0, min(100, int(params[1])))
    return ok(1)


@register("selve.GW.device.setTargetValue")
def dev_set_target_value(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev = state.devices.get(int(params[0]))
    if dev:
        dev.target_position = max(0, min(100, int(params[1])))
    return ok(1)


@register("selve.GW.device.setState")
def dev_set_state(state, params):
    return ok(1)


# ── Movement ────────────────────────────────────────────────────────────────

def _move_and_event(state, dev_id, position) -> Tuple[SelveResponse, List[SelveEvent]]:
    dev = state.devices.get(dev_id)
    if dev is None:
        return fault(f"Device {dev_id} not found", 4), []
    dev.move_to(position)
    events = [_device_event(dev)] if state.events_enabled else []
    return ok_with_events([1], events)


@register("selve.GW.device.moveUp")
def dev_move_up(state, params):
    dev_id = int(params[0]) if params else None
    if dev_id is None:
        return fault("Missing device id", 3)
    return _move_and_event(state, dev_id, 0)


@register("selve.GW.device.moveDown")
def dev_move_down(state, params):
    dev_id = int(params[0]) if params else None
    if dev_id is None:
        return fault("Missing device id", 3)
    return _move_and_event(state, dev_id, 100)


@register("selve.GW.device.movePos1")
def dev_move_pos1(state, params):
    dev_id = int(params[0]) if params else None
    if dev_id is None:
        return fault("Missing device id", 3)
    dev = state.devices.get(dev_id)
    return _move_and_event(state, dev_id, dev.pos1 if dev else 25)


@register("selve.GW.device.movePos2")
def dev_move_pos2(state, params):
    dev_id = int(params[0]) if params else None
    if dev_id is None:
        return fault("Missing device id", 3)
    dev = state.devices.get(dev_id)
    return _move_and_event(state, dev_id, dev.pos2 if dev else 75)


@register("selve.GW.device.movePos")
def dev_move_pos(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    return _move_and_event(state, int(params[0]), int(params[1]))


@register("selve.GW.device.moveStop")
def dev_move_stop(state, params):
    dev_id = int(params[0]) if params else None
    if dev_id is None:
        return fault("Missing device id", 3)
    dev = state.devices.get(dev_id)
    if dev:
        dev.stop()
    events = [_device_event(dev)] if dev and state.events_enabled else []
    return ok_with_events([1], events)


@register("selve.GW.device.moveStepUp")
def dev_move_step_up(state, params):
    dev_id = int(params[0]) if params else None
    step = int(params[1]) if len(params) > 1 else 5
    dev = state.devices.get(dev_id)
    if dev:
        dev.move_to(dev.position - step)
    return ok(1)


@register("selve.GW.device.moveStepDown")
def dev_move_step_down(state, params):
    dev_id = int(params[0]) if params else None
    step = int(params[1]) if len(params) > 1 else 5
    dev = state.devices.get(dev_id)
    if dev:
        dev.move_to(dev.position + step)
    return ok(1)


@register("selve.GW.device.savePos1")
def dev_save_pos1(state, params):
    dev = state.devices.get(int(params[0])) if params else None
    if dev:
        dev.pos1 = dev.position
    return ok(1)


@register("selve.GW.device.savePos2")
def dev_save_pos2(state, params):
    dev = state.devices.get(int(params[0])) if params else None
    if dev:
        dev.pos2 = dev.position
    return ok(1)


# ════════════════════════════════════════════════════════════════════════════
# GROUP COMMANDS
# ════════════════════════════════════════════════════════════════════════════

@register("selve.GW.group.read")
def grp_read(state, params):
    grp_id = int(params[0]) if params else None
    grp = state.groups.get(grp_id)
    if grp is None:
        return fault(f"Group {grp_id} not found", 4)
    return ok(grp.group_id, grp.name, grp.device_ids)


@register("selve.GW.group.getIds")
def grp_get_ids(state, params):
    return ok(list(state.groups.keys()))


@register("selve.GW.group.write")
def grp_write(state, params):
    if len(params) < 3:
        return fault("Missing parameters", 3)
    grp_id = int(params[0])
    state.groups[grp_id] = SimGroup(
        group_id=grp_id,
        name=str(params[1]),
        device_ids=[int(x) for x in params[2]] if isinstance(params[2], list) else [],
    )
    return ok(1)


@register("selve.GW.group.delete")
def grp_delete(state, params):
    if params:
        state.groups.pop(int(params[0]), None)
    return ok(1)


def _group_move(state, grp_id, position):
    grp = state.groups.get(grp_id)
    if grp is None:
        return fault(f"Group {grp_id} not found", 4), []
    events = []
    for dev_id in grp.device_ids:
        dev = state.devices.get(dev_id)
        if dev:
            dev.move_to(position)
            if state.events_enabled:
                events.append(_device_event(dev))
    return ok_with_events([1], events)


@register("selve.GW.group.moveUp")
def grp_move_up(state, params):
    return _group_move(state, int(params[0]) if params else 0, 0)


@register("selve.GW.group.moveDown")
def grp_move_down(state, params):
    return _group_move(state, int(params[0]) if params else 0, 100)


@register("selve.GW.group.stop")
def grp_stop(state, params):
    grp_id = int(params[0]) if params else None
    grp = state.groups.get(grp_id)
    events = []
    if grp:
        for dev_id in grp.device_ids:
            dev = state.devices.get(dev_id)
            if dev:
                dev.stop()
                if state.events_enabled:
                    events.append(_device_event(dev))
    return ok_with_events([1], events)


# ════════════════════════════════════════════════════════════════════════════
# IVEO COMMANDS
# ════════════════════════════════════════════════════════════════════════════

@register("selve.GW.iveo.getIds")
def iveo_get_ids(state, params):
    return ok(state.iveo_ids())


@register("selve.GW.iveo.setLabel")
def iveo_set_label(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev = state.devices.get(int(params[0]))
    if dev:
        dev.name = str(params[1])
    return ok(1)


@register("selve.GW.iveo.setType")
def iveo_set_type(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev = state.devices.get(int(params[0]))
    if dev:
        dev.device_type = DeviceType(int(params[1]))
    return ok(1)


@register("selve.GW.iveo.getType")
def iveo_get_type(state, params):
    dev_id = int(params[0]) if params else None
    dev = state.devices.get(dev_id)
    if dev is None:
        return fault("Device not found", 4)
    return ok(int(dev.device_type))


@register("selve.GW.iveo.setRepeater")
def iveo_set_repeater(state, params):
    return ok(1)


@register("selve.GW.iveo.getRepeater")
def iveo_get_repeater(state, params):
    return ok(0)


@register("selve.GW.iveo.factoryReset")
def iveo_factory_reset(state, params):
    return ok(1)


@register("selve.GW.iveo.teach")
def iveo_teach(state, params):
    return ok(1)


@register("selve.GW.iveo.learn")
def iveo_learn(state, params):
    return ok(1)


@register("selve.GW.iveo.commandManual")
def iveo_cmd_manual(state, params):
    # params: dev_id, command (0=stop,1=up,2=down,3=pos1,4=pos2)
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev_id, cmd = int(params[0]), int(params[1])
    _iveo_apply_command(state, dev_id, cmd)
    return ok(1)


@register("selve.GW.iveo.commandAutomatic")
def iveo_cmd_automatic(state, params):
    if len(params) < 2:
        return fault("Missing parameters", 3)
    dev_id, cmd = int(params[0]), int(params[1])
    _iveo_apply_command(state, dev_id, cmd)
    return ok(1)


@register("selve.GW.iveo.commandResult")
def iveo_cmd_result(state, params):
    return ok(0, "OK")


def _iveo_apply_command(state, dev_id, cmd):
    dev = state.devices.get(dev_id)
    if dev is None:
        return
    mapping = {0: dev.position, 1: 0, 2: 100, 3: dev.pos1, 4: dev.pos2}
    dev.move_to(mapping.get(cmd, dev.position))


# ════════════════════════════════════════════════════════════════════════════
# SENSOR / SENDER STUBS  (enough for HA not to crash on discovery)
# ════════════════════════════════════════════════════════════════════════════

for _m in [
    "selve.GW.sensor.teachStart", "selve.GW.sensor.teachStop",
    "selve.GW.sensor.teachResult", "selve.GW.sensor.getIds",
    "selve.GW.sensor.getInfo", "selve.GW.sensor.getValues",
    "selve.GW.sensor.setLabel", "selve.GW.sensor.delete",
    "selve.GW.sensor.writeManual", "selve.GW.sensor.updateValues",
    "selve.GW.sender.teachStart", "selve.GW.sender.teachStop",
    "selve.GW.sender.teachResult", "selve.GW.sender.getIds",
    "selve.GW.sender.getInfo", "selve.GW.sender.getValues",
    "selve.GW.sender.setLabel", "selve.GW.sender.delete",
    "selve.GW.sender.writeManual", "selve.GW.sender.updateValues",
    "selve.GW.senSim.getIds", "selve.GW.senSim.getConfig",
    "selve.GW.senSim.setConfig", "selve.GW.senSim.getValues",
    "selve.GW.senSim.setValues", "selve.GW.senSim.drive",
    "selve.GW.senSim.store", "selve.GW.senSim.delete",
    "selve.GW.senSim.factory", "selve.GW.senSim.setLabel",
    "selve.GW.senSim.getTest", "selve.GW.senSim.setTest",
]:
    _registry[_m] = lambda state, params, m=_m: ok([] if "getIds" in m else 1)


# ════════════════════════════════════════════════════════════════════════════
# Event builder helper
# ════════════════════════════════════════════════════════════════════════════

def _device_event(dev: SimDevice) -> SelveEvent:
    """Build a device value-update event as the real gateway would push it."""
    return SelveEvent(
        method="selve.GW.event.device.moveResult",
        params=[dev.device_id, dev.position, dev.target_position,
                dev.tilt, int(dev.unreachable)],
    )
