"""Publish an allowlisted application bundle to a Hugging Face Docker Space.

Run from this cloud workspace. Supply NOOR_HF_TOKEN through secure environment
settings, never as a command argument. No token, model cache, or chat is uploaded.
"""
import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def stage(destination):
    files = []
    for directory in ("app", "data", "deploy/licenses"):
        for source in sorted((ROOT / directory).rglob("*")):
            if not source.is_file() or source.is_symlink():
                continue
            if "__pycache__" in source.parts or source.suffix in {".pyc", ".log"}:
                continue
            if source.name.startswith("."):
                continue
            files.append((source, source.relative_to(ROOT)))
    for name in ("requirements.txt", "LICENSE", "scripts/cloud_start.py", "scripts/pull_cloud_model.py"):
        files.append((ROOT / name, Path(name)))
    for name in ("Dockerfile", "README.md"):
        files.append((ROOT / "deploy/huggingface" / name, Path(name)))
    files.append((ROOT / ".dockerignore", Path(".dockerignore")))
    for source, relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)
    return len(files), sum(source.stat().st_size for source, _ in files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--space-id", help="Account/space-name; defaults to your-account/noor-islamic-assistant")
    parser.add_argument("--update", action="store_true", help="Permit updating this explicitly selected existing Space")
    parser.add_argument("--dry-run", action="store_true", help="Validate the upload bundle without credentials or network")
    args = parser.parse_args()
    if args.update and not args.space_id:
        parser.error("--update requires --space-id")
    if args.space_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", args.space_id):
        parser.error("Use an account/space-name ID.")
    with tempfile.TemporaryDirectory(prefix="noor-space-") as directory:
        destination = Path(directory)
        count, size = stage(destination)
        print(f"Cloud bundle: {count} files, {size:,} bytes; excludes credentials and model caches.")
        if args.dry_run:
            return 0
        token = os.environ.get("NOOR_HF_TOKEN") or os.environ.get("HF_TOKEN")
        if not token:
            print("Deployment requires a Hugging Face write token in secure environment settings (NOOR_HF_TOKEN).")
            return 2
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
        from huggingface_hub import HfApi

        api = HfApi(token=token)
        try:
            account = api.whoami()["name"]
            space_id = args.space_id or f"{account}/noor-islamic-assistant"
            api.create_repo(repo_id=space_id, repo_type="space", space_sdk="docker",
                            private=False, exist_ok=args.update)
            api.upload_folder(repo_id=space_id, repo_type="space", folder_path=str(destination),
                              commit_message="Deploy Noor cloud app with private Ollama and memory-only chats")
        except Exception as error:
            # Error bodies can include network credentials or signed URLs.
            response = getattr(error, "response", None)
            status = getattr(response, "status_code", None)
            print(f"Deployment failed: {type(error).__name__}" + (f" (HTTP {status})" if status else "") + ".")
            if status == 409:
                print("The Space already exists. Review it before using --space-id ACCOUNT/NAME --update.")
            return 1
        print(f"Uploaded to https://huggingface.co/spaces/{space_id}")
        print("The cloud build is starting. Verify the deployed UI, source smoke checks, and real model smoke checks before calling it ready.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
