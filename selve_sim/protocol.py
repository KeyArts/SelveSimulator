"""
Selve XML protocol constants and message parser/builder.

The Selve USB-RF Gateway uses a simple XML-RPC-like protocol:
  Request:  <methodCall><methodName>selve.GW.xxx</methodName><array>...</array></methodCall>
  Response: <methodResponse><array>...</array></methodResponse>
  Fault:    <methodResponse><fault><array><string>msg</string><int>code</int></array></fault></methodResponse>
  Event:    <methodCall><methodName>selve.GW.event.xxx</methodName><array>...</array></methodCall>
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Parameter type helpers ──────────────────────────────────────────────────

def _parse_value(elem: ET.Element) -> Any:
    """Parse a single typed XML element into a Python value."""
    tag = elem.tag
    text = (elem.text or "").strip()
    if tag == "int":
        return int(text) if text else 0
    if tag == "string":
        return text
    if tag == "boolean":
        return text.lower() in ("true", "1")
    if tag == "base64":
        import base64
        return base64.b64decode(text) if text else b""
    if tag == "array":
        return [_parse_value(c) for c in elem]
    return text  # fallback


def _build_value(value: Any) -> ET.Element:
    """Build a typed XML element from a Python value."""
    if isinstance(value, bool):
        e = ET.Element("boolean")
        e.text = "true" if value else "false"
    elif isinstance(value, int):
        e = ET.Element("int")
        e.text = str(value)
    elif isinstance(value, str):
        e = ET.Element("string")
        e.text = value
    elif isinstance(value, bytes):
        import base64
        e = ET.Element("base64")
        e.text = base64.b64encode(value).decode()
    elif isinstance(value, (list, tuple)):
        e = ET.Element("array")
        for item in value:
            e.append(_build_value(item))
    else:
        e = ET.Element("string")
        e.text = str(value)
    return e


# ── Message dataclasses ─────────────────────────────────────────────────────

@dataclass
class SelveRequest:
    method: str
    params: list = field(default_factory=list)

    @classmethod
    def parse(cls, xml_str: str) -> "SelveRequest":
        root = ET.fromstring(xml_str.strip())
        method = root.findtext("methodName", "").strip()
        params = []
        array = root.find("array")
        if array is not None:
            params = [_parse_value(c) for c in array]
        return cls(method=method, params=params)


@dataclass
class SelveResponse:
    params: list = field(default_factory=list)
    fault_msg: Optional[str] = None
    fault_code: int = 0

    def to_xml(self) -> str:
        root = ET.Element("methodResponse")
        if self.fault_msg is not None:
            fault = ET.SubElement(root, "fault")
            arr = ET.SubElement(fault, "array")
            arr.append(_build_value(self.fault_msg))
            arr.append(_build_value(self.fault_code))
        else:
            arr = ET.SubElement(root, "array")
            for p in self.params:
                arr.append(_build_value(p))
        xml_bytes = ET.tostring(root, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_bytes}\n'


@dataclass
class SelveEvent:
    """Unsolicited event pushed by the gateway (e.g. position feedback)."""
    method: str
    params: list = field(default_factory=list)

    def to_xml(self) -> str:
        root = ET.Element("methodCall")
        name = ET.SubElement(root, "methodName")
        name.text = self.method
        arr = ET.SubElement(root, "array")
        for p in self.params:
            arr.append(_build_value(p))
        xml_bytes = ET.tostring(root, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_bytes}\n'


def fault(msg: str, code: int = 1):
    """Return (SelveResponse, []) tuple so callers can always unpack."""
    return SelveResponse(fault_msg=msg, fault_code=code), []
