"""Supervise the web app and private Ollama on a cloud server.

Model files stay on the server. Source retrieval remains available during the
first download or a download failure. Never write conversations to disk.
"""
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    children = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    environment = dict(os.environ)
    # Enforce a private model endpoint in the hosted container.
    environment["OLLAMA_HOST"] = "127.0.0.1:11434"
    environment["NOOR_OLLAMA_URL"] = "http://127.0.0.1:11434"
    model_enabled = environment.get("NOOR_OLLAMA_ENABLED", "true").lower() == "true"
    exit_code = 0
    try:
        if model_enabled:
            ollama = subprocess.Popen(["ollama", "serve"], cwd=ROOT, env=environment)
            children.append(ollama)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 30
            while not stopping:
                if ollama.poll() is not None:
                    raise RuntimeError("The private model server stopped during startup.")
                try:
                    with opener.open("http://127.0.0.1:11434/api/version", timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("The private model server did not start in time.")
                    time.sleep(0.25)
        if stopping:
            return 0
        web = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
             "--port", environment.get("PORT", "7860"), "--no-access-log"],
            cwd=ROOT, env=environment,
        )
        children.append(web)
        pull = None
        if model_enabled:
            print("Downloading the model on the cloud server; cited sources remain available.", flush=True)
            pull = subprocess.Popen([sys.executable, "scripts/pull_cloud_model.py"], cwd=ROOT, env=environment)
            children.append(pull)
        while not stopping:
            if web.poll() is not None:
                exit_code = web.returncode or 1
                break
            if model_enabled and ollama.poll() is not None:
                raise RuntimeError("The private model server stopped.")
            if pull is not None and pull.poll() is not None:
                if pull.returncode:
                    print("Model download failed. Noor will display cited sources with an availability notice.", flush=True)
                pull = None
            time.sleep(0.25)
    except (OSError, RuntimeError) as error:
        print(f"Cloud startup failed: {type(error).__name__}.", file=sys.stderr, flush=True)
        exit_code = 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 10
        for child in reversed(children):
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
