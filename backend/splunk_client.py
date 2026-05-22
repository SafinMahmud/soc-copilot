import os
from typing import List

import splunklib.client as splunk_client
import splunklib.results as splunk_results


class SplunkClient:
    def __init__(self):
        self.service = splunk_client.connect(
            host=os.getenv("SPLUNK_HOST", "localhost"),
            port=int(os.getenv("SPLUNK_PORT", 8089)),
            username=os.getenv("SPLUNK_USERNAME", "admin"),
            password=os.getenv("SPLUNK_PASSWORD", "changeme"),
            scheme="https",
        )

    def run_query(self, spl: str, max_results: int = 100) -> List[dict]:
        """Execute SPL query, return list of result dicts."""
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
            return [{"error": str(e)}]

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
