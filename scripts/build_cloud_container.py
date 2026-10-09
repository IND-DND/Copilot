"""Build using this cloud's supplied proxy DNS and trusted CA bundle.

Public certificates are mounted only during the build. Proxy credentials are
never printed, stored in source, or added to the image. Package hashes and TLS
verification remain enabled. Ordinary hosts can use docker compose directly.
"""
import argparse
import os
import socket
import ssl
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="noor-chatbot:local")
    parser.add_argument("--dockerfile", default="Dockerfile")
    args = parser.parse_args()
    command = ["docker", "build", "--network=host", "--build-arg", "HTTPS_PROXY", "--build-arg", "HTTP_PROXY", "--build-arg", "NO_PROXY"]
    hosts = {urlsplit(os.environ[name]).hostname for name in ("HTTP_PROXY", "HTTPS_PROXY") if os.environ.get(name)}
    for host in sorted(h for h in hosts if h):
        address = socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
        command.extend(["--add-host", f"{host}:{address}"])
    bundle = ssl.get_default_verify_paths().cafile
    if bundle:
        command.extend(["--secret", f"id=build_ca_bundle,src={bundle}"])
    root = Path(__file__).resolve().parent.parent
    environment = dict(os.environ)
    environment.setdefault("DOCKER_CONFIG", "/workspace/.cache/noor-docker")
    subprocess.run(command + ["--file", args.dockerfile, "--tag", args.tag, "."], cwd=root, env=environment, check=True)


if __name__ == "__main__":
    main()
