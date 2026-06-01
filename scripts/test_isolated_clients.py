#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MCP_URL = "https://wiki.andykong.top/mcp"
MCP_SERVER_NAME = "cann-infer-wiki-cloud"
TEST_UPLOAD_TOKEN = "llmw_test_token"
PRODUCTION_UPLOAD_URL = "https://wiki.andykong.top/upload/backflow"
GLOBAL_PATHS = [
    Path.home() / ".claude",
    Path.home() / ".codex",
    Path.home() / ".agents",
    Path.home() / ".config/opencode",
]
CLAUDE_VOLATILE_TOP_LEVEL = {
    ".DS_Store",
    ".last-cleanup",
    ".last-update-result.json",
    "backups",
    "cache",
    "debug",
    "file-history",
    "history.jsonl",
    "ide",
    "llm-wiki",
    "projects",
    "sessions",
}
CODEX_VOLATILE_TOP_LEVEL = {
    ".DS_Store",
    ".codex-global-state.json",
    ".codex-global-state.json.bak",
    ".tmp",
    "cache",
    "models_cache.json",
    "process_manager",
    "session_index.jsonl",
    "sessions",
    "shell_snapshots",
    "tmp",
    "worktrees",
}
CODEX_VOLATILE_PREFIXES = (
    "goals_",
    "logs_",
    "memories_",
    "state_",
)


class HarnessError(RuntimeError):
    pass


def _update_digest(digest: "hashlib._Hash", *parts: str) -> None:
    for part in parts:
        digest.update(part.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")


SkipDigestPath = Callable[[Path, str], bool]


def _digest_entry(
    digest: "hashlib._Hash",
    path: Path,
    rel: str,
    should_skip: SkipDigestPath | None,
) -> None:
    if should_skip is not None and should_skip(path, rel):
        return

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        _update_digest(digest, rel, "missing")
        return
    except OSError as exc:
        _update_digest(digest, rel, "lstat-error", exc.__class__.__name__, str(getattr(exc, "errno", "")))
        return

    mode = metadata.st_mode
    if stat.S_ISLNK(mode):
        try:
            target = os.readlink(path)
        except OSError as exc:
            target = f"<readlink-error:{exc.__class__.__name__}:{getattr(exc, 'errno', '')}>"
        _update_digest(digest, rel, "symlink", target)
        return

    if stat.S_ISDIR(mode):
        _update_digest(digest, rel, "dir")
        try:
            children = sorted(path.iterdir(), key=lambda child: child.name)
        except OSError as exc:
            _update_digest(digest, rel, "iterdir-error", exc.__class__.__name__, str(getattr(exc, "errno", "")))
            return
        for child in children:
            child_rel = child.name if rel in {"", "."} else f"{rel}/{child.name}"
            _digest_entry(digest, child, child_rel, should_skip)
        return

    if stat.S_ISREG(mode):
        _update_digest(digest, rel, "file")
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            _update_digest(digest, rel, "read-error", exc.__class__.__name__, str(getattr(exc, "errno", "")))
        return

    _update_digest(digest, rel, "special", oct(mode & 0o170000))


def tree_digest(path: Path, should_skip: SkipDigestPath | None = None) -> str:
    try:
        path.lstat()
    except FileNotFoundError:
        return "missing"

    digest = hashlib.sha256()
    _digest_entry(digest, path, ".", should_skip)
    return digest.hexdigest()


class MockBackflowHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        self.rfile.read(max(length, 0))

        body = {
            "status": "ok",
            "id": "test-backflow-id",
            "path": "sources/sessions/uploaded/test",
            "entrypoint": "test.md",
        }
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def start_mock_server() -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), MockBackflowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}/upload/backflow"


def format_command(cmd: list[str]) -> str:
    return " ".join(cmd)


def run(cmd: list[str], *, env: dict[str, str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HarnessError(f"required command not found: {cmd[0]}") from exc

    if completed.returncode != 0:
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        details = "\n".join(part for part in [stdout, stderr] if part)
        if details:
            raise HarnessError(f"command failed ({completed.returncode}): {format_command(cmd)}\n{details}")
        raise HarnessError(f"command failed ({completed.returncode}): {format_command(cmd)}")
    return completed


def _mkdir_env_paths(env: dict[str, str], keys: list[str]) -> None:
    for key in keys:
        path = Path(env[key])
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)


def isolated_env(root: Path, upload_url: str) -> dict[str, str]:
    if upload_url == PRODUCTION_UPLOAD_URL or not upload_url.startswith("http://127.0.0.1:"):
        raise HarnessError(f"mock upload URL must be local, got: {upload_url}")

    env = dict(os.environ)
    env.update(
        {
            "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "CODEX_HOME": str(root / "codex-home"),
            "CLAUDE_CONFIG_DIR": str(root / "claude-config"),
            "CLAUDE_HOME": str(root / "claude-home"),
            "AGENTS_HOME": str(root / "agents-home"),
            "OPENCODE_CONFIG": str(root / "opencode/opencode.json"),
            "OPENCODE_CONFIG_DIR": str(root / "opencode"),
            "LLM_WIKI_UPLOAD_TOKEN": TEST_UPLOAD_TOKEN,
            "LLM_WIKI_UPLOAD_URL": upload_url,
        }
    )
    _mkdir_env_paths(
        env,
        [
            "HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "CODEX_HOME",
            "CLAUDE_CONFIG_DIR",
            "CLAUDE_HOME",
            "AGENTS_HOME",
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_DIR",
        ],
    )
    return env


def check_static(env: dict[str, str]) -> None:
    run([sys.executable, "scripts/validate_release.py"], env=env)
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], env=env)


def check_mock_upload(upload_url: str) -> None:
    request = urllib.request.Request(
        upload_url,
        data=b'{"source":"isolated-harness"}',
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HarnessError(f"mock upload failed: {exc}") from exc

    if payload.get("status") != "ok" or payload.get("id") != "test-backflow-id":
        raise HarnessError(f"unexpected mock upload response: {payload}")


def check_opencode_install(env: dict[str, str], root: Path) -> None:
    prefix = root / "opencode-prefix"
    run(["bash", "dist/opencode/install-opencode.sh", "--prefix", str(prefix)], env=env)

    required = [
        prefix / "commands/wiki-cloud-mount.md",
        prefix / "commands/wiki-cloud-backflow.md",
        prefix / "skills/llm-wiki-cloud-mount/SKILL.md",
        prefix / "skills/llm-wiki-cloud-query/SKILL.md",
        prefix / "skills/llm-wiki-cloud-backflow/SKILL.md",
        prefix / "opencode.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise HarnessError(f"OpenCode install missing expected files: {missing}")

    config = json.loads((prefix / "opencode.json").read_text(encoding="utf-8"))
    try:
        actual_url = config["mcp"][MCP_SERVER_NAME]["url"]
    except KeyError as exc:
        raise HarnessError(f"OpenCode config missing MCP server {MCP_SERVER_NAME}") from exc
    if actual_url != CANONICAL_MCP_URL:
        raise HarnessError(f"OpenCode MCP URL mismatch: {actual_url} != {CANONICAL_MCP_URL}")


def check_cli_visibility(env: dict[str, str]) -> None:
    for executable in ["claude", "codex", "opencode"]:
        if shutil.which(executable, path=env.get("PATH")) is None:
            raise HarnessError(f"required CLI not found on PATH: {executable}")
        completed = run([executable, "--help"], env=env)
        if not completed.stdout and not completed.stderr:
            raise HarnessError(f"{executable} --help produced no output")


def snapshot_global_configs() -> dict[str, str]:
    return {str(path): tree_digest(path, should_skip_global_digest_path) for path in GLOBAL_PATHS}


def should_skip_global_digest_path(path: Path, rel: str) -> bool:
    rel = rel.removeprefix("./")
    if rel == ".":
        return False

    root_name = path.anchor
    for parent in path.parents:
        if parent in GLOBAL_PATHS:
            root_name = parent.name
            break

    first = rel.split("/", 1)[0]
    if root_name == ".claude":
        if first in CLAUDE_VOLATILE_TOP_LEVEL:
            return True
        parts = rel.split("/")
        return any(part.endswith("-cache") for part in parts)

    if root_name == ".codex":
        if first in CODEX_VOLATILE_TOP_LEVEL:
            return True
        if rel.startswith("plugins/cache/"):
            return True
        return first.startswith(CODEX_VOLATILE_PREFIXES)

    return False


def describe_digest_changes(before: dict[str, str], after: dict[str, str]) -> str:
    changed = [
        f"{path}: before={before.get(path)} after={after.get(path)}"
        for path in sorted(set(before) | set(after))
        if before.get(path) != after.get(path)
    ]
    return "; ".join(changed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated multi-client smoke checks.")
    parser.add_argument("--keep-root", action="store_true", help="preserve the temporary test root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    before = snapshot_global_configs()
    server, upload_url = start_mock_server()
    test_root = Path(tempfile.mkdtemp(prefix="llm-wiki-client-test-"))
    errors: list[str] = []

    try:
        env = isolated_env(test_root, upload_url)
        check_static(env)
        check_mock_upload(upload_url)
        check_opencode_install(env, test_root)
        check_cli_visibility(env)
    except Exception as exc:
        errors.append(str(exc))
    finally:
        server.shutdown()
        server.server_close()
        after = snapshot_global_configs()
        if before != after:
            errors.append(f"global config changed: {describe_digest_changes(before, after)}")
        if not args.keep_root:
            shutil.rmtree(test_root, ignore_errors=True)

    if errors:
        print(f"isolated_clients=failed reason={' | '.join(errors)}", file=sys.stderr)
        return 1

    print(f"isolated_clients=ok root={test_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
