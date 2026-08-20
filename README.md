# herdr-fanout

Build a leader/seed multi-agent [herdr](https://herdr.dev) pane layout from a YAML config.

```text
leader pane
  -> branch 1 pane  -> split right -> Agent Pane | Normal Pane
  -> branch 2 pane  -> split right -> Agent Pane | Normal Pane
  -> branch N pane  -> split right -> Agent Pane | Normal Pane
```

Each branch runs one agent (any kind herdr supports: `claude`, `pi`, `omp`, `codex`,
`gemini`, `cursor`, `cline`, ...) with its own prompt, paired with a plain
"normal pane" you can point at a log, a test watcher, or leave idle.

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
