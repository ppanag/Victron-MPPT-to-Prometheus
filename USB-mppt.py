import serial
import time
from datetime import datetime
import struct
import re
import os


# Configuration
SERIAL_PORT = "/dev/mppt1"  # change here
BAUD_RATE = 19200
TIMEOUT = 2
POLL_INTERVAL = 10  # seconds
OUTPUT_FILE = "/ramdisk/MPPT1.prom"  # Standard node_exporter textfile directory
# VE.Direct Hex protocol constants for internal temperature reading
GET = 0x01
TEMP_REGISTER = 0xEDDB
TEMP_INTERVAL = 10 # seconds


# Initialize data structure with default values
current_data = {
    'I': None,          # Charging current (A * 1000)
    'V': None,          # Battery voltage (V * 1000)
    'PPV': None,        # Panel power (W)
    'VPV': None,        # Panel Voltage (V * 1000)
    'CS': None,         # Charging state
    'ERR': None,        # Error code
    'H20': None,        # Yield today  (kWh *100)
#    'TEMP': None,       # Internal temperature (°C)
    'OR'  : None,       # Off Reason code
    'MPPT' : None,      # MPPT or Cliping
    'SER#':None         # Serial number
}

def parse_line(line):
    """Parse a line of data from the MPPT device"""
    try:
        if '\t' in line:
            key, value = line.split('\t', 1)
            return key.strip(), value.strip()
    except Exception as e:
        print(f"Error parsing line: {line} - {e}")
    return None, None


def to_prometheus_number(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        try:
            return float(int(s, 16))
        except ValueError:
            return -1.0


def update_data(key, value):
    """Update the current data structure with new values"""
    if key in current_data:
        try:
            if key == 'SER#':
                # deal with serial-number later..
                current_data[key] = value
            else:
                # Convert values to floats
                current_data[key] = to_prometheus_number(value)
        except ValueError:
            print(f"Could not convert value {value} for key {key}")
            current_data[key] = None


def is_data_stale():
    """Check if any critical data is missing"""
    required_keys = ['I', 'V']
    for key in required_keys:
        if current_data[key] is None:
            print(f"Missing data for {key}")
            return True
    return False

"""
def send_hex_to_read_temp(ser):
    # Construct the query message
    message = ":7DBED0086\n".encode()
    # Send query
    ser.write(message)
        

def check_frame(frame: str) -> bool:
    f = frame.strip().removeprefix(':').removesuffix('\n')
    cmd = int(f[0], 16)
    data = (int(f[i:i+2], 16) for i in range(1, len(f), 2))
    return (cmd + sum(data)) & 0xFF == 0x55


def extract_temp(s: str) -> float | None:
    m = re.search(r":7DBED00([0-9A-F]+\n)", s)
    if not m:
        return None
    frame = ":7DBED00" + m.group(1) 
    if not check_frame(frame):
        return None
    fdata = frame[8:-2]  # keep just value
    val = int(fdata[2:4] + fdata[0:2], 16)  # little endian
    return val / 100.0
"""

  
def write_prometheus_file():
    """Write data to file in Prometheus format"""
    if is_data_stale():
        print("Skipping Prometheus write due to missing or stale data")
        return
    try:
        TMPFILE = OUTPUT_FILE + ".tmp"
        with open(TMPFILE, 'w') as f:
            # Write metrics with device model as a label
            label = 'MPPT1'
        
            charging_current = current_data['I'] / 1000.0
            battery_voltage = current_data['V'] / 1000.0
            power = current_data["PPV"] or (charging_current * battery_voltage)

            f.write(f'{label}{{mode="batAmps"}} {charging_current}\n')
            f.write(f'{label}{{mode="batVolts"}} {battery_voltage}\n')
            f.write(f'{label}{{mode="outputW"}} {power}\n')
            if current_data['VPV']:
                f.write(f'{label}{{mode="stringVolts"}} {current_data["VPV"] / 1000.0}\n')
            if current_data['H20']:
                f.write(f'{label}{{mode="yieldToday"}} {current_data["H20"] / 100.0}\n')
            if current_data['CS']:
                f.write(f'{label}{{mode="chargingState"}} {current_data["CS"]}\n')
            if current_data['ERR']:
                f.write(f'{label}{{mode="errorCode"}} {current_data["ERR"]}\n')
            if current_data['OR']:
                f.write(f'{label}{{mode="offReason"}} {current_data["OR"]}\n')
            if current_data['MPPT']:
                f.write(f'{label}{{mode="mppt"}} {current_data["MPPT"]}\n')
            serialno = current_data['SER#']
            if serialno:
                f.write(f'{label}{{serial="{serialno}"}} 1\n')
            
        outLine = os.system(f'/bin/mv {TMPFILE} {OUTPUT_FILE}')
        
        print(label+ ":  Data written to Prometheus file")
    except Exception as e:
        print(f"Error writing to Prometheus file: {e}")


def main():
    """Main function to read from serial and update data"""
    print("Starting Victron MPPT monitor")   
    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=TIMEOUT)
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Failed to open serial port: {e}")
        return    
    last_write_time = time.time()   
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()           
            if line:
                key, value = parse_line(line)
                if key:
                    update_data(key, value) 
                #temp = extract_temp(line)
                #print(">>> line: " + line + "\n")
                #if temp is not None:
                #    current_data['TEMP'] = temp   
                           
            # Check if it's time to write to file
            current_time = time.time()
            if current_time - last_write_time >= POLL_INTERVAL:
                #send_hex_to_read_temp(ser)       
                write_prometheus_file()
                last_write_time = current_time               
    except KeyboardInterrupt:
        print("Monitoring interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        ser.close()
        print("Serial connection closed")

if __name__ == "__main__":
    main()
