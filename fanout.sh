#!/usr/bin/env bash
# herdr-fanout.sh — build the leader/seed pane layout from the diagram, in herdr.
#
# Layout it builds:
#   Leader pane
#     -> Pane i     (agent pane)   -> split right -> Agent Pane | Normal Pane
#     -> Pane i+1   (agent pane)   -> split right -> Agent Pane | Normal Pane
#     -> Pane i+2   (agent pane)   -> split right -> Agent Pane | Normal Pane
#     ... N branches total
#
# Usage:
#   fanout.sh <N> [agent-kind]
#
# Must run from inside a herdr pane (HERDR_ENV=1).

set -euo pipefail

N="${1:?usage: fanout.sh <N> [agent-kind]}"
KIND="${2:-claude}"

if [ "${HERDR_ENV:-}" != "1" ]; then
  echo "error: not inside a herdr pane" >&2
  exit 1
fi

LEADER_PANE="${HERDR_PANE_ID:?HERDR_PANE_ID is not set}"

# ---------------------------------------------------------------------------
# TODO(you): decide the per-branch task.
#
# Every branch gets its own Agent Pane. This function decides what that
# agent is told to do. The trivial choice is the same prompt N times. The
# useful choice is splitting one big job across branches — by file, by
# module, by test shard, by hypothesis — so N agents do N different things
# instead of the same thing N times.
#
# $1 = branch index (1..N)
# stdout = the prompt text sent to that branch's agent
agent_task_for() {
  local i="$1"
  echo "TODO: fill in agent_task_for() in fanout.sh (branch $i)"
}

# ---------------------------------------------------------------------------
# TODO(you): decide what the paired Normal Pane does.
#
# The diagram pairs every Agent Pane with a plain Normal Pane. That pane has
# no agent — it's just a shell. Decide what's useful to run there while its
# agent works: tailing a log, watching a test suite, tailing a build, or
# just leaving it as an idle shell for you to poke at by hand.
#
# $1 = branch index (1..N)
# $2 = the normal pane's id
normal_pane_setup() {
  local i="$1" pane_id="$2"
  : # TODO: fill in normal_pane_setup() in fanout.sh (e.g. herdr pane run "$pane_id" "...")
}

# ---------------------------------------------------------------------------

trunk="$LEADER_PANE"
agent_pids=()

for i in $(seq 1 "$N"); do
  # Branch off the trunk downward -> this is "Pane i" / "Pane i+1" / ...
  agent_pane=$(herdr pane split --pane "$trunk" --direction down --cwd "$PWD" --no-focus \
    | jq -r '.result.pane.pane_id')
  trunk="$agent_pane"

  # Split that branch right -> "Agent Pane | Normal Pane"
  normal_pane=$(herdr pane split --pane "$agent_pane" --direction right --cwd "$PWD" --no-focus \
    | jq -r '.result.pane.pane_id')

  agent_name="agent$i"
  herdr agent start "$agent_name" --kind "$KIND" --pane "$agent_pane" >/dev/null

  normal_pane_setup "$i" "$normal_pane"

  task="$(agent_task_for "$i")"
  herdr agent prompt "$agent_name" "$task" --wait --timeout 300000 >/dev/null &
  agent_pids+=($!)

  echo "branch $i: agent=$agent_name agent_pane=$agent_pane normal_pane=$normal_pane"
done

echo "waiting for $N agents..."
wait "${agent_pids[@]}"
echo "done."
