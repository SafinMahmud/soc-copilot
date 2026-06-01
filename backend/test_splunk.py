import splunklib.client as splunk_client
import os
from dotenv import load_dotenv

load_dotenv()

print("Connecting to Splunk...")
print(f"Host: {os.getenv('SPLUNK_HOST')}")
print(f"Port: {os.getenv('SPLUNK_PORT')}")
print(f"Username: {os.getenv('SPLUNK_USER', os.getenv('SPLUNK_USERNAME'))}")

try:
    service = splunk_client.connect(
        host=os.getenv("SPLUNK_HOST", "localhost"),
        port=int(os.getenv("SPLUNK_PORT", 8089)),
        username=os.getenv("SPLUNK_USER", os.getenv("SPLUNK_USERNAME", "admin")),
        password=os.getenv("SPLUNK_PASSWORD", "changeme"),
        scheme="https",
        verify=False
    )
    print("✅ Connected successfully!")
    print(f"Splunk version: {service.info()['version']}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
