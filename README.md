# herdr-fanout

Build a leader/seed multi-agent [herdr](https://herdr.dev) pane layout from a YAML config.

```text
Tab: Leader        Tab: claude-177     Tab: omp-233        Tab: pi-134
+-----------+      +---------------+   +---------------+   +---------------+
| Leader    |      | Agent | Normal|   | Agent | Normal|   | Agent | Normal|
| pane      |      | Pane  | Pane  |   | Pane  | Pane  |   | Pane  | Pane  |
+-----------+      +---------------+   +---------------+   +---------------+
```

4 tabs for 3 branches: the leader keeps its own tab with one pane, never
split. Every branch gets its own separate tab holding two panes — Agent
Pane | Normal Pane, split right (vertical dividing line, side by side).
Each agent (any kind herdr supports: `claude`, `pi`, `omp`, `codex`,
`gemini`, `cursor`, `cline`, ...) runs its own prompt; the normal pane is a
plain shell you can point at a log, a test watcher, or leave idle.

Every pane gets a cosmetic display name — agent pane, normal pane, and the
leader, all controllable from the YAML — and the tab itself is renamed to
match (`pane rename`, `pane report-metadata --display-agent`, `tab rename`
/ `tab create --label`). The leader defaults to "Leader" (override with
`leader_name`); each branch's agent pane defaults to `<kind>-<random
3-digit number>` — e.g. "omp-233", "claude-177", "pi-134" — or set your own
with `display_name`; its normal pane defaults to `<that name>-shell` —
e.g. "omp-233-shell" — or set your own with `normal_pane.display_name`.
These labels are cosmetic only, separate from the real agent name used to
address it (`herdr agent prompt demo1 ...` still works even though the
sidebar shows "omp-233"), because herdr's live agent names must be
lowercase identifiers and can't hold text like that — and a normal pane
has no agent name at all.

## Install

Requires `python3` and `herdr` already on the target machine.

```bash
git clone https://github.com/ucalyptus/herdr-fanout.git
cd herdr-fanout
./install.sh
```

This installs `herdr-fanout` to `~/.local/bin` and installs PyYAML if it's
missing.

## Use

From inside a herdr pane:

```bash
herdr-fanout init my-fanout.yaml     # write a starting config
# edit my-fanout.yaml: set prompts, kinds, normal_pane commands
herdr-fanout apply my-fanout.yaml    # build the layout
```

## Config format

```yaml
version: 1
agent_kind: claude          # default kind for branches that don't set their own
wait_timeout_ms: 300000     # default --wait timeout per agent
leader_name: Leader         # tab + sidebar label for the leader pane
# cwd: /path/to/project     # defaults to the current directory

branches:
  - name: agent1
    kind: claude             # optional per-branch override
    # display_name: "claude-177"  # tab + sidebar label; defaults to "<kind>-<random 3 digits>"
    prompt: "..."
    normal_pane:
      # display_name: "claude-177-shell"  # defaults to "<agent's display_name>-shell"
      command: null          # e.g. "tail -f logs/agent1.log", or null for an idle shell

  - name: agent2
    kind: omp
    prompt: "..."
    normal_pane:
      command: null

  - name: agent3
    kind: pi
    prompt: "..."
    normal_pane:
      command: null
```

`name` must match `[a-z][a-z0-9_-]{0,31}` and be unique — herdr's rule for
live agent names.

## Files

- `herdr_fanout.py` — the configurator (`init` / `apply`).
- `install.sh` — installs it to `~/.local/bin/herdr-fanout`.
- `examples/` — several ready-to-run configs, one per supported feature
  (minimal, multiple kinds, shared `cwd`/`agent_kind`, custom names,
  `normal_pane.command`). See `examples/README.md`.
- `demo.yaml` — the fixture used to test this tool during development.
- `fanout.sh` — earlier bash prototype, kept for reference. `herdr_fanout.py`
  supersedes it.
