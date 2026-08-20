# Example configs

Every field these examples use is supported by the current `herdr_fanout.py`.
Run any of them with:

```bash
herdr-fanout apply examples/01-minimal.yaml
```

(from inside a herdr pane).

| File | Shows |
|---|---|
| `01-minimal.yaml` | The smallest valid config — one branch, only `name`/`kind`/`prompt` set. |
| `02-multi-kind.yaml` | Three branches, three agent kinds (`claude`, `omp`, `pi`), no naming or command overrides. Same shape as the repo's `demo.yaml`. |
| `03-shared-cwd-and-kind.yaml` | Top-level `agent_kind` and `cwd` shared by all branches, with one branch overriding `kind`. |
| `04-custom-names.yaml` | `leader_name` plus a `display_name` for every agent pane and every normal pane. |
| `05-normal-pane-commands.yaml` | `normal_pane.command` running a real command (dev server, test watcher) instead of an idle shell. |

## Supported config fields

```yaml
version: 1                 # required, must be 1
agent_kind: claude          # optional, default kind for branches without their own kind
cwd: /path/to/project       # optional, defaults to the current directory
wait_timeout_ms: 300000     # optional, default --wait timeout per agent
leader_name: Leader          # optional, tab + sidebar label for the leader pane

branches:                    # required, at least one
  - name: agent1              # required, must match [a-z][a-z0-9_-]{0,31}, unique
    kind: claude               # optional, overrides agent_kind for this branch
    display_name: "claude-177" # optional, tab + sidebar label; defaults to "<kind>-<random 3 digits>"
    prompt: "..."               # required
    normal_pane:                 # optional block
      display_name: "claude-177-shell" # optional, defaults to "<agent's display_name>-shell"
      command: null                     # optional, a shell command to run, or null for an idle shell
```
