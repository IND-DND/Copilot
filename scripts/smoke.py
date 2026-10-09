"""Functional checks against the running service; no browser is required."""
import argparse
import json
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    with urllib.request.urlopen(base + "/api/health", timeout=10) as response:
        health = json.load(response)
        assert health["status"] == "ok" and health["quran_verses"] == 6236
    checks = [
        ({"question": "What does the Quran say about charity?", "scope": "quran"}, "en", "quran-2-177", 3),
        ({"question": "Translate Surah Al-Fatiha into Hindi"}, "hi", "quran-1-7", 7),
        ({"question": "What are the Hadiths about prayer times?"}, "en", "muslim-612a", 2),
    ]
    for body, language, id, count in checks:
        req = urllib.request.Request(base + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.load(response)
        assert result["language"] == language
        assert id in {s["id"] for s in result["citations"]}
        assert len(result["citations"]) == count
        print("PASS", body["question"], "·", count, "sources")
    print("Functional smoke checks passed.")


if __name__ == "__main__":
    main()
