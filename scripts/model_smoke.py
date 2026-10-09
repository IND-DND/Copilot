"""Require real English and Hindi model explanations from the running app."""
import json
import urllib.request


def main():
    for language in ("en", "hi"):
        payload = {"question": "What does the Quran say about charity?", "language": language, "scope": "quran"}
        request = urllib.request.Request("http://127.0.0.1:8000/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        assert result["mode"] == "model" and result["model_status"] == "used", f"{language}: model status was {result['model_status']}"
        assert result["language"] == language and result["citations"]
        print(f"PASS {language}: real model explanation with {len(result['citations'])} verified sources")


if __name__ == "__main__":
    main()
