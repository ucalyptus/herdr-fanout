#!/usr/bin/env python3
"""herdr-fanout: build a leader/seed multi-agent herdr pane layout from a YAML config.

Layout built by `apply`:

    Leader tab (untouched)          Branches tab (new)
    +-------------------+           +-----------------------------+
    |                   |           |  Pane i    -> Agent | Normal |
    |    Leader pane    |           |  Pane i+1  -> Agent | Normal |
    |                   |           |  Pane i+2  -> Agent | Normal |
    +-------------------+           +-----------------------------+

The leader pane is never split. Branches live in a separate tab, split into
N even rows. Each pane's herdr sidebar label ("Leader", "Pane i", "Pane
i+1", ...) is cosmetic only — set via `pane report-metadata
--display-agent` — and is separate from the real, regex-constrained agent
name used to address it (`herdr agent prompt <name>`).

Must run from inside a herdr pane (HERDR_ENV=1).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
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


class HerdrError(RuntimeError):
    """A failed herdr CLI call. `.code` is the machine-readable error code
    from herdr's JSON error body (e.g. "agent_pane_busy"), or None if the
    failure wasn't in that shape (a crash, a CLI syntax error, ...)."""

    def __init__(self, args, stderr):
        self.code = None
        try:
            self.code = json.loads(stderr).get("error", {}).get("code")
        except (json.JSONDecodeError, AttributeError):
            pass
        super().__init__(f"herdr {' '.join(args)} failed: {stderr}")


def herdr(*args, timeout=None):
    result = subprocess.run(
        ["herdr", *args], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise HerdrError(args, result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def prompt_agent(name, prompt, timeout_ms):
    """Submit a prompt and wait for the agent to settle.

    herdr sends the prompt text and Enter atomically before it starts
    waiting, so the agent gets the task either way. agent_prompt_stalled
    just means herdr's 5-second grace window didn't catch a state
    transition afterward — which happens for tasks (or agent kinds) fast
    enough that idle -> working -> idle completes before herdr samples it.
    Treat that as a warning, not a failure; any other error is real.
    """
    try:
        herdr("agent", "prompt", name, prompt, "--wait", "--timeout", str(timeout_ms))
    except HerdrError as e:
        if e.code == "agent_prompt_stalled":
            print(
                f"{name}: warning: reply likely landed before herdr could confirm it "
                f"(agent_prompt_stalled) — check with: herdr agent read {name}",
                file=sys.stderr,
            )
            return
        raise


def start_agent_with_retry(name, kind, pane, settle_timeout_s=10):
    """Start an agent in a freshly split pane.

    A pane split returns before its shell has necessarily reached its
    interactive prompt — startup files, session-restore banners, etc. can
    still be running. `agent start` doesn't wait that out itself; it fails
    fast with agent_pane_busy if the pane isn't at a prompt yet. Retry on
    that specific error until the shell settles or settle_timeout_s runs out.
    Any other error (bad kind, pane doesn't exist, ...) is not a timing
    issue and is raised immediately.
    """
    deadline = time.monotonic() + settle_timeout_s
    delay = 0.25
    while True:
        try:
            herdr("agent", "start", name, "--kind", kind, "--pane", pane)
            return
        except HerdrError as e:
            if e.code != "agent_pane_busy" or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 2.0)


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


def label_agent_pane(pane_id, text):
    """Set a cosmetic sidebar label for a pane, without touching its real
    (regex-constrained) agent identity.

    herdr's live agent name (the thing `agent start`/`agent prompt` address)
    must match NAME_RE — lowercase, no spaces. But the sidebar text is a
    separate "display-only" field (`effective_display_agent`, confirmed in
    herdr's own source) that falls back to the real name only when unset.
    `pane report-metadata --display-agent` sets that field directly, so a
    pane can be addressed as "demo2" while the sidebar reads "Pane i+1".
    `--source` is just a namespace tag for who reported this metadata.
    """
    herdr(
        "pane", "report-metadata", pane_id,
        "--source", "herdr-fanout", "--display-agent", text,
    )


def row_ratios(n):
    """Ratios to split a chain of n panes into n even rows.

    Splitting a pane in half twice (the naive/default approach) gives rows
    of 1/2, 1/4, 1/8, ... — not what "N even branches" means. Instead, peel
    rows off the BOTTOM of the trunk, working backwards from the last row:
    with `remaining` rows still sitting in the trunk, the bottom one is a
    1/remaining slice, so the trunk keeps (remaining-1)/remaining. Do this
    for remaining = n, n-1, ..., 2, and every row ends up 1/n of the total.
    """
    return [(r - 1) / r for r in range(n, 1, -1)]


def cmd_apply(args):
    if os.environ.get("HERDR_ENV") != "1":
        sys.exit("error: not inside a herdr pane")
    leader = os.environ.get("HERDR_PANE_ID")
    workspace = os.environ.get("HERDR_WORKSPACE_ID")
    if not leader or not workspace:
        sys.exit("error: HERDR_PANE_ID / HERDR_WORKSPACE_ID is not set")

    cfg = load_config(args.config)
    cwd = cfg.get("cwd", os.getcwd())
    default_kind = cfg.get("agent_kind", "claude")
    timeout_ms = cfg.get("wait_timeout_ms", 300000)
    tab_label = cfg.get("tab_label", "Agents")
    branches = cfg["branches"]
    n = len(branches)

    label_agent_pane(leader, "Leader")

    # The leader pane is never split — not even once. Branches live in their
    # own tab instead, so the leader stays exactly as it was before `apply`
    # ran. That tab's root pane becomes the "column", divided into N even
    # rows.
    #
    # Building all N rows is its own pass, finished before phase 2 splits
    # any row into Agent Pane | Normal Pane. Splitting a row right *before*
    # the rows below it exist would fix that row's normal pane to whatever
    # height the row had at that moment — then later down-splits shrink the
    # row without ever resizing a pane that's no longer its direct sibling.
    column = herdr(
        "tab", "create", "--workspace", workspace, "--cwd", cwd,
        "--label", tab_label, "--no-focus",
    )["result"]["root_pane"]["pane_id"]

    rows = [None] * n
    trunk = column
    for remaining, ratio in zip(range(n, 1, -1), row_ratios(n)):
        row_pane = herdr(
            "pane", "split", "--pane", trunk, "--direction", "down",
            "--ratio", str(ratio), "--cwd", cwd, "--no-focus",
        )["result"]["pane"]["pane_id"]
        rows[remaining - 1] = row_pane
    rows[0] = trunk

    # Phase 2: split each row right into Agent Pane | Normal Pane, and start
    # each agent. Safe to do now — no row's height changes after this point.
    started = []
    for i, (b, row_pane) in enumerate(zip(branches, rows)):
        agent_pane = row_pane
        normal_pane = herdr(
            "pane", "split", "--pane", agent_pane, "--direction", "right",
            "--cwd", cwd, "--no-focus",
        )["result"]["pane"]["pane_id"]

        name = b["name"]
        kind = b.get("kind", default_kind)
        start_agent_with_retry(name, kind, agent_pane)

        display_name = b.get("display_name") or ("Pane i" if i == 0 else f"Pane i+{i}")
        label_agent_pane(agent_pane, display_name)

        normal_cmd = (b.get("normal_pane") or {}).get("command")
        if normal_cmd:
            herdr("pane", "run", normal_pane, normal_cmd)

        print(f"branch {name} ({display_name}): agent_pane={agent_pane} normal_pane={normal_pane}")
        started.append((name, b["prompt"]))

    # Now that every agent exists, prompt them all at once. This is the part
    # that benefits from running concurrently: N agents should work on their
    # N tasks in parallel, not one after another.
    print(f"prompting {len(started)} agents...")
    with ThreadPoolExecutor(max_workers=len(started)) as pool:
        futures = {
            pool.submit(prompt_agent, name, prompt, timeout_ms): name
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

# Label for the new tab the branches are built in. The leader pane's own
# tab is never touched.
tab_label: Agents

branches:
  - name: agent1
    kind: claude
    # display_name: "Pane i"      # sidebar label; defaults to "Pane i", "Pane i+1", ...
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
