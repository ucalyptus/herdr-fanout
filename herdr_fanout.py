#!/usr/bin/env python3
"""herdr-fanout: build a leader/seed multi-agent herdr pane layout from a YAML config.

Layout built by `apply`:

    leader pane
      -> branch 1 pane  -> split right -> Agent Pane | Normal Pane
      -> branch 2 pane  -> split right -> Agent Pane | Normal Pane
      -> branch N pane  -> split right -> Agent Pane | Normal Pane

Must run from inside a herdr pane (HERDR_ENV=1).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML is required. Install it with: pip3 install --user pyyaml")

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
CONFIG_VERSION = 1

# Kinds accepted by `herdr agent start --kind` as of herdr 0.8.0. Checked at
# load time to catch typos before any panes are built. Not a hard gate: a
# newer herdr may support more kinds than this list knows about, so an
# unknown kind is a warning, not a load failure — herdr itself is the final
# authority. Run `herdr agent start --help` to see the live list.
KNOWN_KINDS = {
    "pi", "claude", "codex", "gemini", "cursor", "devin", "agy", "cline",
    "omp", "mastracode", "opencode", "copilot", "kimi", "kiro", "droid",
    "amp", "grok", "hermes", "kilo", "qodercli", "maki",
}


def herdr(*args, timeout=None):
    result = subprocess.run(
        ["herdr", *args], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"herdr {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    if cfg.get("version") != CONFIG_VERSION:
        raise ValueError(f"unsupported config version, expected {CONFIG_VERSION}")

    branches = cfg.get("branches") or []
    if not branches:
        raise ValueError("config has no branches")

    default_kind = cfg.get("agent_kind", "claude")
    if default_kind not in KNOWN_KINDS:
        print(f"warning: agent_kind {default_kind!r} is not in the known kind list", file=sys.stderr)

    seen = set()
    for b in branches:
        name = b.get("name")
        if not name or not NAME_RE.match(name):
            raise ValueError(f"invalid branch name: {name!r}")
        if name in seen:
            raise ValueError(f"duplicate branch name: {name}")
        seen.add(name)
        if not b.get("prompt"):
            raise ValueError(f"branch {name!r} has no prompt")
        kind = b.get("kind", default_kind)
        if kind not in KNOWN_KINDS:
            print(f"warning: branch {name!r} kind {kind!r} is not in the known kind list", file=sys.stderr)

    return cfg


def cmd_apply(args):
    if os.environ.get("HERDR_ENV") != "1":
        sys.exit("error: not inside a herdr pane")
    leader = os.environ.get("HERDR_PANE_ID")
    if not leader:
        sys.exit("error: HERDR_PANE_ID is not set")

    cfg = load_config(args.config)
    cwd = cfg.get("cwd", os.getcwd())
    default_kind = cfg.get("agent_kind", "claude")
    timeout_ms = cfg.get("wait_timeout_ms", 300000)
    branches = cfg["branches"]

    # Build the pane tree and start every agent first. These calls must run
    # one at a time: each branch splits off the pane the previous branch
    # just created, so the tree stays evenly sized instead of squeezing the
    # leader pane thinner on every iteration.
    trunk = leader
    started = []
    for b in branches:
        agent_pane = herdr(
            "pane", "split", "--pane", trunk, "--direction", "down",
            "--cwd", cwd, "--no-focus",
        )["result"]["pane"]["pane_id"]
        trunk = agent_pane

        normal_pane = herdr(
            "pane", "split", "--pane", agent_pane, "--direction", "right",
            "--cwd", cwd, "--no-focus",
        )["result"]["pane"]["pane_id"]

        name = b["name"]
        kind = b.get("kind", default_kind)
        herdr("agent", "start", name, "--kind", kind, "--pane", agent_pane)

        normal_cmd = (b.get("normal_pane") or {}).get("command")
        if normal_cmd:
            herdr("pane", "run", normal_pane, normal_cmd)

        print(f"branch {name}: agent_pane={agent_pane} normal_pane={normal_pane}")
        started.append((name, b["prompt"]))

    # Now that every agent exists, prompt them all at once. This is the part
    # that benefits from running concurrently: N agents should work on their
    # N tasks in parallel, not one after another.
    print(f"prompting {len(started)} agents...")
    with ThreadPoolExecutor(max_workers=len(started)) as pool:
        futures = {
            pool.submit(
                herdr, "agent", "prompt", name, prompt,
                "--wait", "--timeout", str(timeout_ms),
            ): name
            for name, prompt in started
        }
        exit_code = 0
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                print(f"{name}: done")
            except Exception as e:
                print(f"{name}: error: {e}", file=sys.stderr)
                exit_code = 1
    sys.exit(exit_code)


EXAMPLE_CONFIG = """\
version: 1

# Default agent kind for branches that don't set their own.
agent_kind: claude

# Working directory for every split pane. Defaults to the current directory
# if omitted.
# cwd: /path/to/project

# Default timeout (ms) for each agent's --wait.
wait_timeout_ms: 300000

branches:
  - name: agent1
    kind: claude
    prompt: "TODO: describe agent1's slice of the task"
    normal_pane:
      command: null          # e.g. "tail -f logs/agent1.log", or omit for an idle shell

  - name: agent2
    kind: omp
    prompt: "TODO: describe agent2's slice of the task"
    normal_pane:
      command: null

  - name: agent3
    kind: pi
    prompt: "TODO: describe agent3's slice of the task"
    normal_pane:
      command: null
"""


def cmd_init(args):
    if os.path.exists(args.path) and not args.force:
        sys.exit(f"error: {args.path} already exists (use --force to overwrite)")
    with open(args.path, "w") as f:
        f.write(EXAMPLE_CONFIG)
    print(f"wrote {args.path}")


def main():
    parser = argparse.ArgumentParser(prog="herdr-fanout")
    sub = parser.add_subparsers(dest="cmd", required=True)

    apply_p = sub.add_parser("apply", help="build the pane layout from a YAML config")
    apply_p.add_argument("config")
    apply_p.set_defaults(func=cmd_apply)

    init_p = sub.add_parser("init", help="write an example config")
    init_p.add_argument("path", nargs="?", default="herdr-fanout.yaml")
    init_p.add_argument("--force", action="store_true")
    init_p.set_defaults(func=cmd_init)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
