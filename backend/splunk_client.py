import os
from pathlib import Path
from typing import List

import splunklib.client as splunk_client
import splunklib.results as splunk_results
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


class SplunkClient:
    def __init__(self):
        self.service = self._connect()

    def _connect(self):
        return splunk_client.connect(
            host=os.getenv("SPLUNK_HOST", "localhost"),
            port=int(os.getenv("SPLUNK_PORT", 8089)),
            username=os.getenv("SPLUNK_USER", os.getenv("SPLUNK_USERNAME", "admin")),
            password=os.getenv("SPLUNK_PASSWORD", "changeme"),
            scheme="https",
        )

    def _should_reconnect(self, error: Exception) -> bool:
        message = str(error).lower()
        return "session is not logged in" in message or "authentication failed" in message

    def run_query(self, spl: str, max_results: int = 100) -> List[dict]:
        """Execute SPL query, return list of result dicts."""
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                job = self.service.jobs.create(
                    spl,
                    **{
                        "exec_mode": "blocking",
                        "count": max_results,
                        "output_mode": "json",
                    },
                )
                results = []
                for result in splunk_results.JSONResultsReader(
                    job.results(output_mode="json")
                ):
                    if isinstance(result, dict):
                        results.append(result)
                job.cancel()
                return results
            except Exception as e:
                last_error = e
                if attempt == 0 and self._should_reconnect(e):
                    self.service = self._connect()
                    continue
                break
        return [{"error": str(last_error)}]

    def get_field_values(
        self, field: str, index: str, time_range: str = "-24h"
    ) -> List[str]:
        """Get top unique values for a field — used by agent for pivoting."""
        spl = (
            f"search index={index} earliest={time_range} "
            f"| top limit=20 {field} | fields {field}"
        )
        results = self.run_query(spl)
        return [r.get(field, "") for r in results if field in r]
