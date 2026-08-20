# herdr-fanout

Build a leader/seed multi-agent [herdr](https://herdr.dev) pane layout from a YAML config.

```text
Tab: Leader        Tab: Tab i          Tab: Tab i+1        Tab: Tab i+2
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

Every pane also gets a cosmetic herdr sidebar label — "Leader", "Tab i",
"Tab i+1", ... — set via `pane report-metadata --display-agent`, and the
tabs themselves are renamed to match (`tab rename` / `tab create --label`).
This is separate from the real agent name used to address it (`herdr agent
prompt demo1 ...` still works even though the sidebar shows "Tab i"),
because herdr's live agent names must be lowercase identifiers and can't
hold text like "Tab i+1".

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
# cwd: /path/to/project     # defaults to the current directory

branches:
  - name: agent1
    kind: claude             # optional per-branch override
    # display_name: "Tab i"  # tab + sidebar label; defaults to "Tab i", "Tab i+1", ...
    prompt: "..."
    normal_pane:
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
- `fanout.sh` — earlier bash prototype, kept for reference. `herdr_fanout.py`
  supersedes it.
