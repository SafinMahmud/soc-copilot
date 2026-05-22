"""
Generates 500 synthetic security events and uploads to Splunk via HEC.
Run once to populate Splunk with demo data.

Usage: python generate_sample_data.py
Requires: SPLUNK_HEC_TOKEN env var
"""

import json
import os
import random
from datetime import datetime, timedelta

import requests

HEC_URL = "http://localhost:8088/services/collector"
HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "your-hec-token")

MALICIOUS_IP = "23.20.239.12"
TARGET_HOST = "wrk-splunk"
ATTACKER_USER = "administrator"


def generate_failed_login(timestamp):
    return {
        "sourcetype": "WinEventLog:Security",
        "index": "main",
        "event": {
            "EventCode": "4625",
            "src_ip": MALICIOUS_IP,
            "user": ATTACKER_USER,
            "dest": TARGET_HOST,
            "action": "failure",
            "LogonType": "3",
            "_time": timestamp.isoformat(),
        },
    }


def generate_successful_login(timestamp):
    return {
        "sourcetype": "WinEventLog:Security",
        "index": "main",
        "event": {
            "EventCode": "4624",
            "src_ip": MALICIOUS_IP,
            "user": ATTACKER_USER,
            "dest": TARGET_HOST,
            "action": "success",
            "LogonType": "3",
            "_time": timestamp.isoformat(),
        },
    }


def generate_network_scan(timestamp):
    return {
        "sourcetype": "stream:tcp",
        "index": "main",
        "event": {
            "src_ip": MALICIOUS_IP,
            "dest_ip": "192.168.0." + str(random.randint(1, 254)),
            "dest_port": random.choice([22, 445, 3389, 80, 443, 8080]),
            "bytes_in": random.randint(40, 200),
            "bytes_out": 0,
            "_time": timestamp.isoformat(),
        },
    }


def generate_large_transfer(timestamp):
    return {
        "sourcetype": "stream:tcp",
        "index": "main",
        "event": {
            "src_ip": TARGET_HOST,
            "dest_ip": MALICIOUS_IP,
            "dest_port": 443,
            "bytes_out": random.randint(5000000, 50000000),
            "bytes_in": random.randint(1000, 5000),
            "_time": timestamp.isoformat(),
        },
    }


def main():
    base_time = datetime.now() - timedelta(hours=6)
    events = []

    for i in range(30):
        events.append(generate_network_scan(base_time + timedelta(minutes=i * 0.5)))

    for i in range(200):
        events.append(
            generate_failed_login(base_time + timedelta(minutes=20 + i * 0.2))
        )

    events.append(generate_successful_login(base_time + timedelta(minutes=62)))

    for i in range(5):
        events.append(
            generate_large_transfer(base_time + timedelta(minutes=65 + i * 3))
        )

    for event in events:
        payload = {
            "time": event["event"].get("_time", datetime.now().isoformat()),
            "sourcetype": event["sourcetype"],
            "index": event["index"],
            "event": json.dumps(event["event"]),
        }
        requests.post(
            HEC_URL,
            headers={"Authorization": f"Splunk {HEC_TOKEN}"},
            json=payload,
            verify=False,
            timeout=30,
        )

    print(f"Uploaded {len(events)} events to Splunk.")
    print(f"Test investigation: entity={MALICIOUS_IP}, entity_type=ip")


if __name__ == "__main__":
    main()
