"""Start pinned Ollama on loopback using the cloud's supplied proxy and CA.

State lives outside the Git checkout. No proxy values or generated keys are
printed or copied into the application. Download models separately after
confirming registry network access.
"""
import json
import os
import socket
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

IMAGE = "ollama/ollama:0.6.8@sha256:50ab2378567a62b811a2967759dd91f254864c3495cbe50576bd8a85bc6edd56"
NAME = "noor-ollama"


def ready():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:11434/api/version", timeout=2) as response:
            return json.load(response).get("version")
    except (OSError, ValueError):
        return None


def main():
    version = ready()
    if version:
        print(f"Existing Ollama server available on loopback: {version}")
        return
    environment = dict(os.environ)
    environment.setdefault("DOCKER_CONFIG", "/workspace/.cache/noor-docker")
    inspect = subprocess.run(["docker", "inspect", "--format", '{{index .Config.Labels "org.noor.service"}}', NAME], capture_output=True, text=True, env=environment)
    if inspect.returncode == 0:
        if inspect.stdout.strip() != "ollama":
            raise SystemExit("The container name is in use by another service; it was left unchanged.")
        subprocess.run(["docker", "rm", "--force", NAME], check=True, env=environment, stdout=subprocess.DEVNULL)
    found = subprocess.run(["docker", "image", "inspect", IMAGE], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if found.returncode:
        subprocess.run(["docker", "pull", IMAGE], check=True, env=environment)
    state = Path("/workspace/.cache/ollama")
    state.mkdir(parents=True, exist_ok=True)
    command = ["docker", "run", "--detach", "--name", NAME, "--label", "org.noor.service=ollama", "--network=host", "--restart=unless-stopped", "--env", "OLLAMA_HOST=127.0.0.1:11434", "--env", "OLLAMA_KEEP_ALIVE=30m", "--env", "OLLAMA_NUM_PARALLEL=1", "--env", "OLLAMA_MAX_LOADED_MODELS=1", "--mount", f"type=bind,source={state},target=/root/.ollama"]
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        if environment.get(name):
            command.extend(["--env", name])
    hosts = {urlsplit(environment[name]).hostname for name in ("HTTP_PROXY", "HTTPS_PROXY") if environment.get(name)}
    for host in sorted(h for h in hosts if h):
        address = socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
        command.extend(["--add-host", f"{host}:{address}"])
    bundle = ssl.get_default_verify_paths().cafile
    if bundle:
        command.extend(["--mount", f"type=bind,source={bundle},target=/run/noor-trust.pem,readonly", "--env", "SSL_CERT_FILE=/run/noor-trust.pem"])
    subprocess.run(command + [IMAGE, "serve"], check=True, env=environment, stdout=subprocess.DEVNULL)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        version = ready()
        if version:
            print(f"Ollama {version} is serving on loopback port 11434.")
            print("Model state is retained outside the checkout in /workspace/.cache/ollama.")
            return
        time.sleep(.5)
    raise SystemExit("Ollama did not become available; inspect this service's startup logs.")


if __name__ == "__main__":
    main()
