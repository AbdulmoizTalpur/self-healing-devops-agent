import requests
from typing import Optional
from agent.config import Config

class ProgressStreamer:
    def __init__(self, slack_webhook_url: Optional[str] = None):
        self.slack_url = slack_webhook_url or Config.SLACK_WEBHOOK_URL

    def log(self, message: str, level: str = "INFO"):
        """Print a nicely formatted message to the terminal and trigger Slack updates."""
        prefix = "[*]"
        if level == "SUCCESS":
            prefix = "[+]"
        elif level == "WARNING":
            prefix = "[!]"
        elif level == "ERROR":
            prefix = "[-]"
        elif level == "PROGRESS":
            prefix = "[>]"
        elif level == "SAFETY":
            prefix = "[S]"

        formatted_msg = f"{prefix} [{level}] {message}"
        print(formatted_msg, flush=True)

        if self.slack_url:
            self._send_to_slack(formatted_msg)

    def _send_to_slack(self, message: str):
        """Send a simple JSON payload to the Slack webhook URL."""
        try:
            # We run asynchronously or synchronously; for simple CLI sync is fine since it's just a POST request
            payload = {"text": message}
            response = requests.post(self.slack_url, json=payload, timeout=5)
            if response.status_code != 200:
                # Avoid infinite recursion or log loops, print directly to stderr
                pass
        except Exception:
            # Silent fail for Slack webhook issues so we don't break the agent loop
            pass

    def stream_stage(self, stage_number: int, total_stages: int, description: str):
        """Format and log major workflow stages."""
        self.log(f"[{stage_number}/{total_stages}] {description}", level="PROGRESS")
