import asyncio, os, json, time
from victron_ble.scanner import Scanner, DeviceDataEncoder

OUT_TMP = "/ramdisk/smartsolar1.prom.tmp"
OUT_FINAL = "/ramdisk/smartsolar1.prom"
DEVICE_ADDR = "de:a7:3a:c0:ab:04" # change here
DEVICE_KEY  = "558eeb26b8a728462947253451840971"  # change here
METRIC      = "VICTRON_MPPT1"

CHARGE_STATE_MAP = {
    "off": 0,
    "bulk": 1,
    "absorption": 2,
    "float": 3,
    "equalize": 4
}

class PrometheusScanner(Scanner):
    def __init__(self, device_keys, indent=None):
        super().__init__(device_keys, indent=indent)
        self.last_write = 0

    def callback(self, ble_device, raw_data):
        try:
            device = self.get_device(ble_device, raw_data)
        except Exception:
            return
        parsed = device.parse(raw_data)
        payload = json.loads(json.dumps(parsed, cls=DeviceDataEncoder))

        now = time.time()
        if now - self.last_write < 10:
            return
        self.last_write = now

        lines = []
        if "battery_voltage" in payload:
            lines.append(f'{METRIC}{{mode="batt_voltage"}} {payload["battery_voltage"]}')
        if "battery_charging_current" in payload:
            lines.append(f'{METRIC}{{mode="batt_current"}} {payload["battery_charging_current"]}')
        if "solar_power" in payload:
            lines.append(f'{METRIC}{{mode="power"}} {payload["solar_power"]}')
        if "yield_today" in payload:
            lines.append(f'{METRIC}{{mode="yield_today"}} {payload["yield_today"]}')
        if "charge_state" in payload:
            state_str = payload["charge_state"]
            state_int = CHARGE_STATE_MAP.get(state_str.lower(), -1)
            lines.append(f'{METRIC}{{mode="charge_state",state="{state_str}"}} 1')
            lines.append(f'{METRIC}{{mode="charge_state_int"}} {state_int}')

        try:
            with open(OUT_TMP, "w") as f:
                f.write("\n".join(lines) + "\n")
            os.replace(OUT_TMP, OUT_FINAL)
            print(f"[WRITE] Metrics updated for {ble_device.address}")
        except Exception as e:
            print("[ERROR] Writing metrics:", e)

async def main():
    print(f"[START] Scanner for device {DEVICE_ADDR}")
    scanner = PrometheusScanner({DEVICE_ADDR: DEVICE_KEY}, indent=None)
    await scanner.start()
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
