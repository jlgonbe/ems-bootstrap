# EMS spec — what `ems-bootstrap` generates and why

The single specification of the system that `ems-bootstrap` sets up in a **new** project. `SKILL.md` says how to run the setup; this file says what the result is. Read it when you need to explain a piece to the user or when something in the result looks wrong.

## The idea in four lines

- **Current state** lives in `AGENTS.md` (read through `CLAUDE.md` by Claude Code): what the project is, how it is worked on, the rules in force. It is rewritten when things change.
- **Dated history** lives in `MEMORY.md` (lessons) and `DECISIONS.md` (choices between alternatives). Entries are only added; one that stops being true is superseded by a new entry, never edited.
- **Loop 1 (record):** a decision or a lesson is written the moment it happens, by the agent, without asking first, and reported in one line.
- **Loop 2 (close):** before reporting a task done, the agent records what is pending and checks whether the picture in `AGENTS.md` is still true; a rule of `AGENTS.md` changes only after the decision that changes it is recorded.

Curating memory (consolidating lessons into rules, archiving what no longer applies) is deliberately **not** part of this system.

## Generated layout

```
AGENTS.md                               current state; ≤150 lines (check fails above: split it)
CLAUDE.md                               @AGENTS.md and @MEMORY.md (Claude Code entry point)
MEMORY.md                               lessons M001…, newest first
DECISIONS.md                            decisions D001…, newest first; born with D001 (adoption)
opencode.json                           only with OpenCode: "instructions": ["MEMORY.md"]
.agents/skills/project-memory/          the only writer of MEMORY.md and DECISIONS.md
  SKILL.md · references/entry-format.md · scripts/memory.py
.claude/skills/project-memory           only with Claude Code: relative symlink to the folder above (a copy if symlinks fail)
.opencode/agents/project-planner.md     only with OpenCode
.opencode/agents/project-plan-executor.md
.claude/agents/project-planner.md       only with Claude Code
.claude/agents/project-plan-executor.md
.codex/agents/project-planner.toml       only with Codex
.codex/agents/project-plan-executor.toml
```

Everything above is in **English**. The user's own words are quoted verbatim, in their language, inside `«…»`. Only the project's own files (code, docs, content) use the language the user chose at setup; `AGENTS.md` records that language.

## Load protocol

| File | Loaded | How |
|---|---|---|
| `AGENTS.md` | always, at the start | OpenCode reads it natively; Claude Code through `@AGENTS.md` in `CLAUDE.md` |
| `MEMORY.md` | always, at the start | Claude Code through `@MEMORY.md`; OpenCode through `opencode.json` `instructions`; Codex, and any other harness, because the `ems:protocol` block of `AGENTS.md` says so |
| `DECISIONS.md` | on demand | read only to record a decision or to find out why something is the way it is; `AGENTS.md` rules link to the entry they come from |

Lessons change how the agent works on every task, so they are always at hand. Decisions explain why; they are needed only when that why is touched, and loading them always would spend tokens on history.

## Entry formats

`MEMORY.md`:

```markdown
### M001 — <title>
- Date: YYYY-MM-DD
- Type: correction | failure | preference | finding
- Trigger: <recognisable situation where it applies>
- Learning: <what to do or not do, imperative>
- Evidence: <what happened or who said it; the user's words inside «…»>
- Origin: <optional; related M/D IDs, comma-separated>
- Status: active | superseded by M0XX
```

`DECISIONS.md`:

```markdown
### D001 — <title>
- Date: YYYY-MM-DD
- Status: accepted | superseded by D0XX
- Context: <why it comes up>
- Alternatives considered: <options and why they were rejected; "none" if there were none>
- Decision: <what is decided>
- Rationale: <why>
- Active rule: <optional; "AGENTS.md rule N" when it creates or changes a rule>
```

IDs are assigned by `memory.py` (`max + 1`, never reused) and are immutable: `AGENTS.md` cites them as Markdown links (`(origin: [D001](DECISIONS.md#d001--adopt-the-ems-project-memory-system))`). A lesson or a decision that changes is a **new** entry; the old one gets `Status: superseded by <new>` through `memory.py set-status`. Nothing is deleted.

## `AGENTS.md` anchors

`memory.py check` reads these HTML comments, so they stay in English whatever the project language:

- `<!-- ems:responsibility: … -->` — first line of `AGENTS.md`, `MEMORY.md` and `DECISIONS.md`.
- `<!-- ems:rules -->` … `<!-- /ems:rules -->` — numbered rules, each ending in `(origin: <link>)`.
- `<!-- ems:map -->` … `<!-- /ems:map -->` — which file holds what.
- `<!-- ems:skills -->` … `<!-- /ems:skills -->` — skills and agents by path.
- `<!-- ems:protocol -->` … `<!-- /ems:protocol -->` — the load protocol and the two loops.

## The two agents

| Agent | Model | Job | Tools |
|---|---|---|---|
| `project-planner` | a deep-thinking model (the author suggests Opus on Claude, Sol on OpenAI; the exact ID comes from the harness: `opencode models`, or `/model` in Codex) | turns a complex request into a short numbered plan with files, risks and how to verify; never edits | read-only |
| `project-plan-executor` | a cheaper model (the author suggests Sonnet on Claude, Terra or Luna on OpenAI; the exact ID comes from the harness: `opencode models`, or `/model` in Codex) | carries out an approved plan step by step and reports what it verified; stops and asks if the plan does not fit reality | all |

Planning needs depth; executing a plan the user already reviewed does not. The user picks the models; the setup writes only what the user confirmed and, with no choice, leaves the model out so the agent inherits the session's model. In Codex they are custom agents in `.codex/agents/` that the main agent spawns. In OpenCode both have `mode: all`: the user can switch to them with Tab and the main agent can also hand work to them; in Claude Code they are subagents the main agent delegates to.

## What counts as a new project

`scripts/gate.py` exits 0 only if none of these exists in the project root: `AGENTS.md`, `CLAUDE.md`, `MEMORY.md`, `DECISIONS.md`, `opencode.json`, `.agents/`, `.claude/`, `.codex/`, `.opencode/`, and git history has at most one commit (or there is no git). A framework scaffold with its first commit is new. A harness folder that is empty or holds only what the harness writes by itself when a session starts (Claude Code's `.claude/.cc-writes/` and `settings.local.json`; OpenCode's `.gitignore` and plugin dependencies in `.opencode/`) does not count: there is no context in it. Neither does a `skills/ems-bootstrap/` folder inside one of them, in case the reader installed this skill in the project. A mature project with no git and no agent files passes too: it has no agent context to rescue. Anything else has history: setting this system up there means deciding what to rescue from the existing context, which is not what this skill does. The gate writes nothing.

## Harness facts

Verified on 2026-11-18 against the official docs (OpenCode 1.19.5 and Claude Code 2.1.327 installed locally); Codex on 2026-11-19 against its official docs and source:

- **OpenCode** reads `AGENTS.md`; `CLAUDE.md` only in a directory without `AGENTS.md`, so both files can coexist. — https://github.com/anomalyco/opencode/blob/dev/services/site/src/docs/content/instructions.mdx
- **OpenCode** loads extra instruction files listed in `opencode.json` `"instructions"`, after `AGENTS.md`. — https://github.com/anomalyco/opencode/blob/dev/services/site/src/docs/v1/content/rules.mdx
- **OpenCode** discovers project skills in `.opencode/skills/`, `.claude/skills/` and `.agents/skills/`. — https://github.com/anomalyco/opencode/blob/dev/services/site/src/docs/content/skills.mdx
- **OpenCode** agents are Markdown files in `.opencode/agents/`; the file name is the agent name; frontmatter `description`, `mode` (`primary` · `subagent` · `all`), `model` (`provider/model-id`), `permission`. — https://github.com/anomalyco/opencode/blob/dev/services/site/src/docs/v1/content/agents.mdx
- **Claude Code** reads `AGENTS.md` only when there is no `CLAUDE.md`; with both, it reads `CLAUDE.md`, which therefore imports `@AGENTS.md` (and here `@MEMORY.md`). — https://code.claude.com/docs/en/memory
- **Claude Code** discovers project skills only in `.claude/skills/`, hence the symlink to `.agents/skills/project-memory`. — https://code.claude.com/docs/en/skills
- **Codex** reads `AGENTS.md` from the project root down to the working directory (32 KiB budget by default); other file names count only as a fallback when there is no `AGENTS.md`, and no project setting loads an extra file in every session, so Codex reads `MEMORY.md` because the `ems:protocol` block of `AGENTS.md` tells it to. — https://learn.chatgpt.com/docs/agent-configuration/agents-md
- **Codex** discovers project skills in `.agents/skills/` and `.codex/skills/`, and user skills in `~/.agents/skills/`. — https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/host_roots.rs
- **Codex** custom agents are TOML files in `.codex/agents/` with `name`, `description`, `developer_instructions` (required) and an optional `model`; they inherit the parent's sandbox and permissions, so the planner is read-only by instruction, not by a setting. — https://learn.chatgpt.com/docs/agent-configuration/subagents
- **Codex**, in its default `workspace-write` sandbox, keeps `.git`, `.agents` and `.codex` read-only once they exist, which is why `setup.py` stages what it cannot write there. — https://learn.chatgpt.com/docs/agent-approvals-security
- **Claude Code** subagents are Markdown files in `.claude/agents/` with frontmatter `name`, `description` (required), `tools`, `model` (`opus` · `sonnet` · `haiku` · a full model ID · `inherit`). — https://code.claude.com/docs/en/sub-agents
