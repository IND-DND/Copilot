"""Verify the deployed Gradio app, including real English/Hindi model use."""

import argparse
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--sources-only", action="store_true", help="Skip GPU requests, without claiming inference readiness")
    parser.add_argument("--account-quota", action="store_true", help="Use the authenticated account's free quota via a short-lived Space access token")
    parser.add_argument("--space-id", help="Required with --account-quota, e.g. ACCOUNT/NAME")
    args = parser.parse_args()
    from gradio_client import Client

    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    access_token = None
    if args.account_quota:
        if not args.space_id:
            parser.error("--account-quota requires --space-id")
        import httpx
        from urllib.parse import urlsplit
        from huggingface_hub import HfApi

        token = os.environ.get("NOOR_HF_TOKEN")
        if not token:
            parser.error("Configure NOOR_HF_TOKEN securely to use account quota")
        info = HfApi(token=token).space_info(args.space_id)
        domains = {d["domain"] for d in info.runtime.raw.get("domains", [])}
        url = urlsplit(args.base_url)
        if url.scheme != "https" or url.hostname not in domains or url.username or url.password or url.port not in (None, 443) or url.path not in ("", "/") or url.query or url.fragment:
            parser.error("The URL must match the selected Space's official HTTPS app domain")
        response = httpx.get(f"https://huggingface.co/api/spaces/{args.space_id}/jwt", headers={"Authorization": "Bearer " + token}, timeout=20)
        response.raise_for_status()
        access_token = response.json()["accessToken"]
        # This scoped, short-lived credential is kept in memory; the deployment
        # secret is sent only to huggingface.co through the configured proxy.
    client = Client(args.base_url, token=access_token, verbose=False, download_files=False, analytics_enabled=False)

    def ask(question, language="en", scope="all", model=False):
        output = client.predict(question=question, language=language, scope=scope, use_model=model, api_name="/ask")
        answer = output[1]
        assert isinstance(answer, dict), "Expected a structured cited answer"
        return answer

    charity = ask("What does the Quran say about charity?")
    assert {"quran-2-177", "quran-2-261"} <= {s["id"] for s in charity["citations"]}
    fatiha = ask("Translate Surah Al-Fatiha into Hindi")
    assert fatiha["language"] == "hi" and len(fatiha["citations"]) == 7
    assert all(s["arabic"] for s in fatiha["citations"]) and any(s["footnotes"] for s in fatiha["citations"])
    hadith = ask("What are the Hadiths about prayer times?", scope="hadith")
    assert "muslim-612a" in {s["id"] for s in hadith["citations"]}
    print("PASS: charity citations, seven Hindi Al-Fatiha verses with footnotes, prayer-time Hadith")
    if not args.sources_only:
        for language in ("en", "hi"):
            answer = ask("What does the Quran say about charity?", language=language, model=True)
            assert answer["mode"] == "model" and answer["model_status"] == "used", f"{language}: real inference failed ({answer['model_status']})"
            assert answer["citations"], "Model explanation needs evidence"
            print(f"PASS: real {language} inference: {answer['response']}")


if __name__ == "__main__":
    main()
