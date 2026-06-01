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
import time
import urllib.request
from pathlib import Path


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


class HarnessError(RuntimeError):
    pass


SnapshotEntry = tuple[str, ...]
PathSnapshot = dict[str, SnapshotEntry]
GlobalSnapshot = dict[str, PathSnapshot]
VolatileTopLevels = dict[str, set[str]]


def _update_digest(digest: "hashlib._Hash", *parts: str) -> None:
    for part in parts:
        digest.update(part.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")


def _errno(exc: OSError) -> str:
    return str(getattr(exc, "errno", ""))


def _file_entry(metadata: os.stat_result) -> SnapshotEntry:
    ctime_ns = getattr(metadata, "st_ctime_ns", 0)
    return (
        "file",
        str(metadata.st_size),
        str(metadata.st_mtime_ns),
        str(ctime_ns),
        oct(metadata.st_mode & 0o7777),
    )


def _snapshot_entry(path: Path, rel: str, entries: PathSnapshot) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        entries[rel] = ("missing",)
        return
    except OSError as exc:
        entries[rel] = ("lstat-error", exc.__class__.__name__, _errno(exc))
        return

    mode = metadata.st_mode
    if stat.S_ISLNK(mode):
        try:
            target = os.readlink(path)
        except OSError as exc:
            target = f"<readlink-error:{exc.__class__.__name__}:{_errno(exc)}>"
        entries[rel] = ("symlink", target, oct(mode & 0o7777))
        return

    if stat.S_ISDIR(mode):
        entries[rel] = ("dir", oct(mode & 0o7777))
        try:
            children = sorted(path.iterdir(), key=lambda child: child.name)
        except OSError as exc:
            entries[rel] = ("dir", oct(mode & 0o7777), "iterdir-error", exc.__class__.__name__, _errno(exc))
            return
        for child in children:
            child_rel = child.name if rel in {"", "."} else f"{rel}/{child.name}"
            _snapshot_entry(child, child_rel, entries)
        return

    if stat.S_ISREG(mode):
        entries[rel] = _file_entry(metadata)
        return

    entries[rel] = ("special", oct(mode & 0o170000), oct(mode & 0o7777))


def snapshot_path(path: Path) -> PathSnapshot:
    entries: PathSnapshot = {}
    _snapshot_entry(path, ".", entries)
    return entries


def tree_digest(path: Path) -> str:
    snapshot = snapshot_path(path)
    if snapshot == {".": ("missing",)}:
        return "missing"
    digest = hashlib.sha256()
    for rel, entry in sorted(snapshot.items()):
        _update_digest(digest, rel, *entry)
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


def snapshot_global_configs() -> GlobalSnapshot:
    return {str(path): snapshot_path(path) for path in GLOBAL_PATHS}


def changed_snapshot_entries(before: PathSnapshot, after: PathSnapshot) -> list[str]:
    return [
        rel
        for rel in sorted(set(before) | set(after))
        if before.get(rel) != after.get(rel)
    ]


def global_config_changes(before: GlobalSnapshot, after: GlobalSnapshot) -> dict[str, list[str]]:
    changes: dict[str, list[str]] = {}
    for root in sorted(set(before) | set(after)):
        changed = changed_snapshot_entries(before.get(root, {}), after.get(root, {}))
        if changed:
            changes[root] = changed
    return changes


def _top_level(rel: str) -> str:
    if rel in {"", "."}:
        return "."
    return rel.split("/", 1)[0]


def detect_volatile_top_levels(before: GlobalSnapshot, after: GlobalSnapshot) -> VolatileTopLevels:
    volatile: VolatileTopLevels = {}
    for root, rels in global_config_changes(before, after).items():
        volatile[root] = {_top_level(rel) for rel in rels}
    return volatile


def _merge_volatile_top_levels(target: VolatileTopLevels, source: VolatileTopLevels) -> None:
    for root, top_levels in source.items():
        target.setdefault(root, set()).update(top_levels)


def unexpected_global_config_changes(
    before: GlobalSnapshot,
    after: GlobalSnapshot,
    volatile_top_levels: VolatileTopLevels | None = None,
    *,
    strict_global_digest: bool = False,
) -> dict[str, list[str]]:
    changes = global_config_changes(before, after)
    if strict_global_digest or not volatile_top_levels:
        return changes

    unexpected: dict[str, list[str]] = {}
    for root, rels in changes.items():
        allowed = volatile_top_levels.get(root, set())
        filtered = [rel for rel in rels if _top_level(rel) not in allowed]
        if filtered:
            unexpected[root] = filtered
    return unexpected


def describe_global_config_changes(
    before: GlobalSnapshot,
    after: GlobalSnapshot,
    changes: dict[str, list[str]] | None = None,
) -> str:
    changes = changes if changes is not None else global_config_changes(before, after)
    changed = []
    for root, rels in changes.items():
        sample = rels[:20]
        suffix = "" if len(rels) <= len(sample) else f", ... +{len(rels) - len(sample)} more"
        changed.append(f"{root}: changed {', '.join(sample)}{suffix}")
    return "; ".join(changed)


def describe_digest_changes(before: dict[str, object], after: dict[str, object]) -> str:
    if all(isinstance(value, dict) for value in [*before.values(), *after.values()]):
        return describe_global_config_changes(before, after)  # type: ignore[arg-type]
    changed = [
        f"{path}: before={before.get(path)} after={after.get(path)}"
        for path in sorted(set(before) | set(after))
        if before.get(path) != after.get(path)
    ]
    return "; ".join(changed)


def _format_volatile_top_levels(volatile_top_levels: VolatileTopLevels) -> str:
    return "; ".join(
        f"{root}: {', '.join(sorted(top_levels))}"
        for root, top_levels in sorted(volatile_top_levels.items())
    )


def probe_global_stability(delay_seconds: float = 0.25, samples: int = 4) -> tuple[GlobalSnapshot, VolatileTopLevels]:
    previous = snapshot_global_configs()
    volatile: VolatileTopLevels = {}
    for _ in range(max(samples, 2) - 1):
        time.sleep(delay_seconds)
        current = snapshot_global_configs()
        _merge_volatile_top_levels(volatile, detect_volatile_top_levels(previous, current))
        previous = current
    return previous, volatile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated multi-client smoke checks.")
    parser.add_argument("--keep-root", action="store_true", help="preserve the temporary test root")
    parser.add_argument(
        "--strict-global-digest",
        action="store_true",
        help="fail on any global config change, including top-levels seen changing during the probe",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    before, volatile_top_levels = probe_global_stability()
    if volatile_top_levels:
        volatile_message = _format_volatile_top_levels(volatile_top_levels)
        if args.strict_global_digest:
            print(
                "warning: external global config activity observed during probe; "
                f"strict mode will not ignore it: {volatile_message}",
                file=sys.stderr,
            )
        else:
            print(
                "warning: external global config activity observed during probe; "
                f"ignoring these top-levels for this run: {volatile_message}",
                file=sys.stderr,
            )
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
        unexpected_changes = unexpected_global_config_changes(
            before,
            after,
            volatile_top_levels,
            strict_global_digest=args.strict_global_digest,
        )
        if unexpected_changes:
            errors.append(
                f"global config changed: {describe_global_config_changes(before, after, unexpected_changes)}"
            )
        if not args.keep_root:
            shutil.rmtree(test_root, ignore_errors=True)

    if errors:
        print(f"isolated_clients=failed reason={' | '.join(errors)}", file=sys.stderr)
        return 1

    print(f"isolated_clients=ok root={test_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
