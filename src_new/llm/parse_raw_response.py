import json
import re
from typing import cast

def parse_raw_response(reply: str) -> list[str]:
    try:
        reply = reply.strip()

        # First try direct JSON parsing
        try:
            data = json.loads(reply)
            if isinstance(data, list):
                return cast(list[str], data)
            else:
                raise ValueError("Expected a list")
        except json.JSONDecodeError:
            pass  # fallback

        # Try regex extraction
        match = re.search(r"```json(.*?)```", reply, re.DOTALL)
        if match:
            json_snippet = match.group(1)
            data = json.loads(json_snippet)
            if isinstance(data, list):
                return cast(list[str], data)
            else:
                raise ValueError("Extracted JSON is not a list")

        # IMPORTANT: never fall through
        raise ValueError("No valid JSON found in response")

    except Exception as e:
        # This preserves the full traceback chain
        raise ValueError(f"Failed to parse response:\n{reply}") from e