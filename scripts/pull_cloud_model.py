"""Download and verify the configured model through local Ollama.

Print progress and destination hostnames on errors, never signed download URLs
or proxy credentials. The server verifies model blob digests itself.
"""
import json
import os
import re
import urllib.request
from urllib.parse import urlsplit


def main():
    model = os.getenv("NOOR_OLLAMA_MODEL", "qwen2.5:1.5b")
    request = urllib.request.Request("http://127.0.0.1:11434/api/pull", data=json.dumps({"model": model, "stream": True}).encode(), headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    previous = None
    with opener.open(request, timeout=300) as response:
        for line in response:
            event = json.loads(line)
            if "error" in event:
                error = event["error"]
                hosts = sorted({urlsplit(url).hostname for url in re.findall(r'https?://[^\s"<>]+', error)})
                print("Model download failed.", flush=True)
                if "403" in error or "forbidden" in error.lower():
                    print("Network destination denied by the proxy.", flush=True)
                for host in hosts:
                    if host:
                        print("Required destination:", host, flush=True)
                raise SystemExit(1)
            status = event.get("status", "")
            total = event.get("total", 0)
            percent = int(event.get("completed", 0) * 100 / total) if total else None
            marker = (status, percent // 10 if percent is not None else None)
            if marker != previous:
                print(status, f"{percent}%" if percent is not None else "", flush=True)
                previous = marker
            if status == "success":
                print(f"Model {model} downloaded and verified by Ollama.", flush=True)
                return
    raise SystemExit("Model download ended before success.")


if __name__ == "__main__":
    main()
