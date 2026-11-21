from __future__ import annotations

import json
import urllib.error
import urllib.request

TIMEOUT = 8
MAX_BYTES = 4 * 1024 * 1024
USER_AGENT = "mimic-research"


class HttpJson:
    def get(self, url: str):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("odpowiedź zbyt duża")
        return json.loads(data)
