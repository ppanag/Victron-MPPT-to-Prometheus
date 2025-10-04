# Victron-MPPT-to-Prometheus
Get Victron SmartSolar MPPT data and store to Prometheus database.

Two versions: 1. Through USB-serial cable and 2. Through Bluetooth BLE (recommended) <br>

Install dependencies: <br>
```
sudo apt install bluez bluez-tools
pip3 install victron_ble pyserial bleak==0.19.0
```
