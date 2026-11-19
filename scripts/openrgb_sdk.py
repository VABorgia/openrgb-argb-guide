#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal OpenRGB SDK client (protocol 6) - pure stdlib."""
import socket, struct, sys, time

MAGIC = b"ORGB"
HOST, PORT = "127.0.0.1", 6742

REQ_CONTROLLER_COUNT = 0
REQ_CONTROLLER_DATA = 1
ACK = 10
REQ_PROTOCOL_VERSION = 40
SET_CLIENT_NAME = 50
SET_CLIENT_FLAGS = 52
SETCUSTOMMODE = 1100
UPDATELEDS = 1050
UPDATEMODE = 1101
SAVEMODE = 1102
RESIZEZONE = 1000
CONFIGUREZONE = 1003

PROFILE_GET_PROFILE_LIST = 150
PROFILE_SAVE_PROFILE = 151
PROFILE_LOAD_PROFILE = 152
PROFILE_DELETE_PROFILE = 153
PROFILE_GET_ACTIVE_PROFILE = 156
PROFILE_CLEAR_ACTIVE_PROFILE = 159

SETTINGS_GET_SETTINGS = 250
SETTINGS_GET_SETTINGS_SCHEMA = 251
SETTINGS_MODIFY_SETTINGS = 252
SETTINGS_SET_SETTINGS = 253
SETTINGS_SAVE_SETTINGS = 254

CLIENT_FLAG_SUPPORTS_RGBCONTROLLER = 1
CLIENT_FLAG_SUPPORTS_PROFILEMANAGER = 4
CLIENT_FLAG_SUPPORTS_SETTINGSMANAGER = 1 << 4
CLIENT_FLAG_REQUEST_LOCAL_CLIENT = 1 << 16


class ORGB:
    def __init__(self, host=HOST, port=PORT):
        self.s = socket.create_connection((host, port), timeout=10)
        self.s.settimeout(10)
        self.proto = 6

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass

    def send(self, dev_id, pkt_id, data=b""):
        hdr = MAGIC + struct.pack("<III", dev_id, pkt_id, len(data))
        self.s.sendall(hdr + data)

    def recv_packet(self):
        buf = b""
        while len(buf) < 16:
            chunk = self.s.recv(16 - len(buf))
            if not chunk:
                raise ConnectionError("socket closed")
            buf += chunk
        magic, dev_id, pkt_id, size = struct.unpack("<4sIII", buf)
        assert magic == MAGIC, magic
        data = b""
        while len(data) < size:
            chunk = self.s.recv(size - len(data))
            if not chunk:
                raise ConnectionError("socket closed mid-packet")
            data += chunk
        return dev_id, pkt_id, data

    def recv_reply(self, want_pkt_id=None, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            try:
                dev, pid, data = self.recv_packet()
            except socket.timeout:
                return None
            if pid == ACK:
                continue
            if want_pkt_id is not None and pid != want_pkt_id:
                continue          # e.g. SIGNALUPDATE(1150) pushes
            return dev, pid, data
        return None

    def handshake(self, name=b"dsh-agent", local=False):
        self.proto = 6
        self.send(0, REQ_PROTOCOL_VERSION, struct.pack("<I", self.proto))
        time.sleep(0.05)
        self.send(0, SET_CLIENT_NAME, struct.pack("<H", len(name) + 1) + name + b"\x00")
        flags = CLIENT_FLAG_SUPPORTS_RGBCONTROLLER
        if local:
            flags |= (CLIENT_FLAG_SUPPORTS_PROFILEMANAGER
                      | CLIENT_FLAG_SUPPORTS_SETTINGSMANAGER
                      | CLIENT_FLAG_REQUEST_LOCAL_CLIENT)
        self.send(0, SET_CLIENT_FLAGS, struct.pack("<I", flags))
        time.sleep(0.08)
        self.s.settimeout(0.3)
        try:
            while True:
                self.recv_packet()
        except Exception:
            pass
        self.s.settimeout(10)
        return self.proto

    def controller_count(self):
        self.send(0, REQ_CONTROLLER_COUNT)
        r = self.recv_reply(REQ_CONTROLLER_COUNT, timeout=5)
        if not r:
            return 0, []
        n = struct.unpack("<I", r[2][:4])[0]
        ids = list(struct.unpack("<%dI" % n, r[2][4:4 + 4 * n])) if n else []
        return n, ids

    def controller_data(self, dev_id):
        self.send(dev_id, REQ_CONTROLLER_DATA)
        r = self.recv_reply(REQ_CONTROLLER_DATA, timeout=8)
        return r[2] if r else None

    def save_profile(self, name):
        self.send(0, PROFILE_SAVE_PROFILE, name.encode("utf-8"))
        return self.recv_reply(PROFILE_SAVE_PROFILE, timeout=10)

    def load_profile(self, name):
        self.send(0, PROFILE_LOAD_PROFILE, name.encode("utf-8"))
        return self.recv_reply(PROFILE_LOAD_PROFILE, timeout=10)

    # ---- SettingsManager (needs local client) ----
    def get_settings(self, key):
        self.send(0, SETTINGS_GET_SETTINGS, key.encode("utf-8"))
        r = self.recv_reply(SETTINGS_GET_SETTINGS, timeout=10)
        if not r:
            return None
        return r[2].split(b"\x00")[0].decode("utf-8", "replace")

    def get_settings_schema(self, key):
        self.send(0, SETTINGS_GET_SETTINGS_SCHEMA, key.encode("utf-8"))
        r = self.recv_reply(SETTINGS_GET_SETTINGS_SCHEMA, timeout=10)
        if not r:
            return None
        return r[2].split(b"\x00")[0].decode("utf-8", "replace")

    def set_settings(self, settings_json_str):
        self.send(0, SETTINGS_SET_SETTINGS, settings_json_str.encode("utf-8"))
        return self.recv_reply(SETTINGS_SET_SETTINGS, timeout=10)

    def save_settings(self):
        self.send(0, SETTINGS_SAVE_SETTINGS)
        return self.recv_reply(SETTINGS_SAVE_SETTINGS, timeout=10)

    def set_custom_mode(self, dev_id):
        self.send(dev_id, SETCUSTOMMODE)
        time.sleep(0.1)

    def update_leds(self, dev_id, colors):
        """colors: list of (r,g,b)"""
        n = len(colors)
        payload = bytearray()
        total = 4 + 2 + 4 * n
        payload += struct.pack("<IH", total, n)
        for (r, g, b) in colors:
            payload += bytes((r & 0xFF, g & 0xFF, b & 0xFF, 0))
        self.send(dev_id, UPDATELEDS, bytes(payload))

    def update_mode(self, dev_id):
        self.send(dev_id, UPDATEMODE)


class _R:
    def __init__(self, d):
        self.d = d
        self.p = 0

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v

    def s(self):
        ln = self.u16()
        raw = self.d[self.p:self.p + ln]; self.p += ln
        return raw.rstrip(b"\x00").decode("utf-8", "replace")

    def color(self):
        c = self.u32()
        return (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)

    def matrix(self):
        size = self.u16()
        if size == 0:
            return None
        h = self.u32(); w = self.u32()
        cells = []
        for _ in range(h * w):
            cells.append(self.u32())
        return {"height": h, "width": w, "map": cells}

    def mode(self):
        m = {}
        m["name"] = self.s()
        m["flags"] = self.u32()
        m["speed_min"] = self.u32()
        m["speed_max"] = self.u32()
        m["brightness_min"] = self.u32()
        m["brightness_max"] = self.u32()
        m["colors_min"] = self.u32()
        m["colors_max"] = self.u32()
        m["speed"] = self.u32()
        m["brightness"] = self.u32()
        m["direction"] = self.u32()
        m["color_mode"] = self.u32()
        n = self.u16()
        m["colors"] = [self.color() for _ in range(n)]
        return m

    def segment(self):
        g = {}
        g["name"] = self.s()
        g["type"] = self.u32()
        g["start_idx"] = self.u32()
        g["leds_count"] = self.u32()
        g["matrix"] = self.matrix()
        g["flags"] = self.u32()
        return g

    def zone(self):
        z = {}
        z["name"] = self.s()
        z["type"] = self.u32()
        z["leds_min"] = self.u32()
        z["leds_max"] = self.u32()
        z["leds_count"] = self.u32()
        z["matrix"] = self.matrix()
        nseg = self.u16()
        z["segments"] = [self.segment() for _ in range(nseg)]
        z["flags"] = self.u32()
        z["active_mode"] = self.i32()
        nm = self.u16()
        z["modes"] = [self.mode() for _ in range(nm)]
        z["display_name"] = self.s()
        return z

    def device(self):
        r = {}
        r["reply_size"] = self.u32()
        r["type"] = self.u32()
        r["name"] = self.s()
        r["vendor"] = self.s()
        r["description"] = self.s()
        r["version"] = self.s()
        r["serial"] = self.s()
        r["location"] = self.s()
        nm = self.u16()
        r["active_mode"] = self.i32()
        r["modes"] = [self.mode() for _ in range(nm)]
        nz = self.u16()
        r["zones"] = [self.zone() for _ in range(nz)]
        nl = self.u16()
        r["leds"] = [self.s() for _ in range(nl)]
        nc = self.u16()
        r["colors"] = [self.color() for _ in range(nc)]
        ndn = self.u16()
        r["led_display_names"] = [self.s() for _ in range(ndn)]
        r["flags"] = self.u32()
        r["display_name"] = self.s()
        cfg_len = self.u32()
        raw = self.d[self.p:self.p + cfg_len]; self.p += cfg_len
        r["configuration"] = raw.rstrip(b"\x00").decode("utf-8", "replace")
        r["_consumed"] = self.p
        r["_total"] = len(self.d)
        return r


def parse_device(data):
    return _R(data).device()


def show(dev, dev_id=None):
    print("=" * 70)
    print("device id:", dev_id, "|", dev["name"], "|", dev["description"])
    print("  display_name :", dev["display_name"])
    print("  type/vendor  :", dev["type"], "/", dev["vendor"], "| flags:", dev["flags"])
    print("  active_mode  :", dev["active_mode"], "of", len(dev["modes"]))
    print("  leds         :", len(dev["leds"]), " colors:", len(dev["colors"]))
    print("  parse        :", dev["_consumed"], "/", dev["_total"], "bytes",
          "OK" if dev["_consumed"] == dev["_total"] else "MISMATCH")
    print("  zones:")
    for i, z in enumerate(dev["zones"]):
        print("   [%d] %-14s type=%d count=%-4d min=%-3d max=%-4d flags=%-6d segs=%d active_mode=%d" % (
            i, z["name"], z["type"], z["leds_count"], z["leds_min"], z["leds_max"],
            z["flags"], len(z["segments"]), z["active_mode"]))
    print("  modes:")
    for i, m in enumerate(dev["modes"]):
        mark = " <== ACTIVE" if i == dev["active_mode"] else ""
        print("   [%2d] %-22s flags=%-5d color_mode=%d colors=%d%s" % (
            i, m["name"], m["flags"], m["color_mode"], len(m["colors"]), mark))


if __name__ == "__main__":
    c = ORGB()
    print("protocol:", c.handshake())
    n, ids = c.controller_count()
    print("controllers:", n, "ids:", ids)
    for did in ids:
        d = c.controller_data(did)
        dev = parse_device(d)
        show(dev, did)
    c.close()
