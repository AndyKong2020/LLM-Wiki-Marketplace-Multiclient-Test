# 2026-06-01 Multi-Client Smoke Test

## Environment

- branch: `codex/multiclient-distribution-spec`
- remote: `multiclient-test`
- date: `2026-06-01`
- test root: `/var/folders/0n/khrtrwdd6rz26fr8_ygfchf00000gn/T/llm-wiki-client-test-4qwf_hw7`
- preserved root check: `root_exists=yes`
- pre-commit working tree: existing untracked `.idea/` plus this test record only

## Commands

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
python3 -m unittest discover -s tests -v
python3 scripts/test_isolated_clients.py --keep-root
```

- `python3 scripts/sync_adapters.py`: exit 0, no stdout.
- `python3 scripts/validate_release.py`: exit 0, stdout `validate_release=ok`.
- `python3 -m unittest discover -s tests -v`: exit 0, stdout ended with `Ran 50 tests in 11.133s` and `OK`.
- `python3 scripts/test_isolated_clients.py --keep-root`: exit 0, stderr reported external global config activity during the probe and default mode ignored exact paths / learned prefixes for this run; stdout `isolated_clients=ok root=/var/folders/0n/khrtrwdd6rz26fr8_ygfchf00000gn/T/llm-wiki-client-test-4qwf_hw7`.

## Results

- Static validation: passed, `validate_release=ok`.
- Unit tests: passed, 50 tests via `python3 -m unittest discover -s tests -v`.
- Claude Code CLI visibility: passed via isolated `claude --help`.
- Codex CLI visibility: passed via isolated `codex --help`.
- OpenCode CLI visibility: passed via isolated `opencode --help`.
- OpenCode installer isolation: passed, writes only under test prefix; observed `opencode-prefix/commands`, `opencode-prefix/skills`, and `opencode-prefix/opencode.json` under the preserved root.
- Global config digest check: passed. Default mode observed external runtime noise and dynamically ignored exact paths / learned prefixes; `--strict-global-digest` remains available for quiet CI where any global config change should fail.
- Mock backflow: passed through local `127.0.0.1` HTTP server; no production upload endpoint was hit.

## Notes

- No push to `origin` or `cloud`.
- No production upload endpoint used.
- The preserved test root is intentionally left in place for follow-up inspection.
