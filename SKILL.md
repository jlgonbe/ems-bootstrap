---
name: ems-bootstrap
description: "Sets up project memory in a NEW, empty project so an AI agent's context does not go stale: AGENTS.md (imported by CLAUDE.md) as the current state, dated MEMORY.md and DECISIONS.md, a project-memory skill that records lessons and decisions as they happen and closes every task, and planner/executor agents for OpenCode, Claude Code and Codex, after a 5-question interview. Use when the user wants to start a project with this system, says «set up project memory», «bootstrap AGENTS.md», «create AGENTS.md, MEMORY.md and DECISIONS.md», «install the memory system», «monta el sistema de memoria», «prepara el proyecto para el agente», or runs the skill from the lead magnet «Tu agente de IA trabaja con información caducada». NOT for a project that already has history (instruction or memory files, or more than one git commit): it says so and stops without writing."
---

# ems-bootstrap

You set up a small system that keeps what an AI agent knows about a project true over time. The user gets it working in a new project in a few minutes, and understands each piece because you explain it while you create it. You do not decide for them: the five answers below are theirs.

`SKILL_DIR` is the absolute path of the folder that holds this `SKILL.md`, as the harness reported it when it loaded the skill; write it out in full in every command (a shell variable does not survive between calls in some harnesses). Run everything from the project root, and talk to the user in the language they write in. If `python3` is not found or does not print the help (Windows), use `py -3` or `python` with the same arguments. This skill works best installed at user level (`~/.agents/skills/` for OpenCode and Codex, `~/.claude/skills/` for Claude Code, through `install.py` of https://github.com/jlgonbe/ems-bootstrap); installed inside the project it also works, because the gate ignores its own folder.

**Read [`references/ems-spec.md`](references/ems-spec.md)** when the user asks how a piece works or why it is there, when the result looks wrong, when the gate's verdict surprises them (section «What counts as a new project»), or when step 3 exits 5 and the staged paths surprise you (section «Harness facts»). Do not load it just to run the setup: this file is enough.

## 1. The gate: is this a new project?

```sh
python3 "<SKILL_DIR>/scripts/gate.py" --root .
```

- `new project` (exit 0) → continue.
- `not a new project: …` (exit 1) → tell the user, in one or two sentences, what was found and that this skill only sets up new projects: moving a project that already has context (an old `AGENTS.md`, decisions spread around, more than one commit) means deciding what to rescue and where it goes, which is a different job. **Stop. Write nothing.** The only way forward you offer is running the skill in a new, empty folder. One exception: `there is a .git folder but git could not be run` is not history; tell the user to install git, or to run it in a folder without `.git`.

## 2. The interview (at most 5 questions)

Ask them together in one message, each with its default, so the user can answer in one go:

1. **Language of the project's own files** (code comments, docs, content). Default: the language they are writing to you in. Explain in one line that the agent's own files (`AGENTS.md`, memory, skills, agents) stay in English so the agent always reads one language, and that their words are quoted verbatim in their language.
2. **Name of the project and what it is**, in one to three sentences. Default name: the folder's name.
3. **How it is worked on**: commands to run, build or test, conventions. Default: «not defined yet», which they update later.
4. **Harnesses**: OpenCode, Claude Code, Codex, or several. Default: the one you are running in.
5. **Models of the two agents.** `project-planner` thinks before anything is edited, so it deserves a deep model; `project-plan-executor` carries out a plan the user already approved, so a cheaper one is enough. Suggest:
   - Claude Code: the aliases `opus` (planner) and `sonnet` (executor).
   - OpenCode: IDs exactly as `opencode models` prints them (`provider/model-id`): Opus-class to plan, Sonnet-class to execute; on OpenAI, Sol, then Terra or Luna.
   - Codex: IDs exactly as its `/model` picker shows them: Sol to plan, Terra or Luna to execute.
   - Default: no model written, so both agents use the session's model.

If an answer is ambiguous, ask once more about that point only.

## 3. Run the setup

Translate answers 2 and 3 into English for the harness files; a proper name that is not plain English keeps its spelling inside `«…»`, and commands and paths go inside `backticks` (the script accepts accented letters in both). Give the language its English name (`Spanish`, not `Español`). Write 3 to 6 short phrases the user would say in their language to record or close, each inside `«…»`, for the skill's triggers (if the language is English, pass no `--triggers`: the defaults cover it). Show the user the translated answers and the trigger phrases in one line each and wait for their OK; then run it, with every answer in **single quotes** (inside double quotes a shell runs anything between backticks):

```sh
python3 "<SKILL_DIR>/scripts/setup.py" --root . \
  --project-name '<name>' --project '<answer 2, English>' --how '<answer 3, English>' \
  --language '<English name>' --harness '<opencode,claude,codex: the ones chosen>' \
  [--planner-model-opencode '<provider/model-id>'] [--executor-model-opencode '<provider/model-id>'] \
  [--planner-model-claude opus] [--executor-model-claude sonnet] \
  [--planner-model-codex '<id>'] [--executor-model-codex '<id>'] \
  --triggers '«…», «…», «…»'
```

| Exit | Meaning | Do |
|---|---|---|
| 0 | everything created, `check: OK` | go to step 4 |
| 1 | the gate failed now (something appeared since step 1) | as in step 1: explain and stop |
| 2 | an answer is invalid (the message names it); nothing was written | fix that argument, or ask the user about it, and run again |
| 3 | D001 could not be written; the run removed everything it had created | show the user the error lines; fix the argument they name and run again |
| 4 | the final check failed; the run removed everything it had created | show the user the `check` lines and stop: it means the templates are broken, not the answers |
| 5 | done, `check: OK`, but the harness sandbox did not let the script write some files (Claude Code protects `.claude/`; Codex protects `.agents/` and `.codex/`) | each line under `pending:` reads `<path> <- <staged file>`: read the staged file and create `<path>` with the same content using your own file-writing tool (not the shell); then delete `.ems-pending/`, run `python3 .agents/skills/project-memory/scripts/memory.py check` and go to step 4. If your tool is refused too, tell the user which files are still in `.ems-pending/` and where each one goes, so they can copy them themselves |
| 6 | an unexpected error while writing (the message names it); the run removed everything it had created | show the user the error and stop; never delete anything by hand |

Any other exit, or a Python traceback: show the user the output and stop.

## 4. Explain what was created

Walk the user through the result in their language, one line per piece, saying **why** it exists, not just what it is:

- `AGENTS.md` — the picture of the project **today**, with five working rules; rewritten when something changes. `CLAUDE.md` only imports it (and `MEMORY.md`) because Claude Code reads `CLAUDE.md` instead.
- `MEMORY.md` — lessons with their date, loaded in every session because they change how the agent works on each task.
- `DECISIONS.md` — decisions with their date, the alternatives and the reason; read only when needed, so they do not spend tokens on every message. It already holds `D001`, the decision of adopting this system, and every rule in `AGENTS.md` points to it.
- `project-memory` — the skill that writes both logs: it records the moment something happens (loop 1) and closes every task by checking that `AGENTS.md` is still true (loop 2). It writes without asking and tells them what it wrote.
- `project-planner` and `project-plan-executor` — plan first, approve, then execute. In OpenCode the user can switch to them with Tab and the main agent can hand work to them; in Claude Code and Codex the main agent hands work to them.

Close with three practical lines: correct the agent whenever it gets something wrong (that is how `MEMORY.md` grows); when a choice between alternatives is made, the agent records it; and when `AGENTS.md` passes 150 lines, `memory.py check` fails as a reminder to move what is not needed in every session to a file read only when it applies. If this skill was installed inside the project (`<harness folder>/skills/ems-bootstrap/`), tell the user they can delete that folder now.

## Never, and why

- **Never write anything when the gate fails, or help the user get past it** (deleting or moving files, squashing history, a hand migration): an existing context has to be rescued with judgement, and overwriting it destroys exactly what the user would need.
- **Never invent a model ID:** a wrong ID makes the agent fail the first time it is used; write only what `opencode models` or Codex's `/model` lists, or a Claude Code alias the user accepted, or leave it out.
- **Never edit the generated files by hand to get past a failed check:** the check is what guarantees the links between rules and decisions; fix the input and run `setup.py` again (a failed run cleans up after itself, so the gate passes).
- **Never run `setup.py` before the user confirmed the translated answers:** a successful run cannot be repeated (the gate then sees `AGENTS.md`), and D001 keeps the answers for good.
- **Never run the gate or the setup anywhere but the root of the project the user means:** the gate only inspects `--root .`, so a subfolder of a project whose `AGENTS.md` is above it would pass.
- **Never delete `.ems-pending/` before every pending file exists at its target:** it is the only copy of those files.
- **Never leave this skill inside the project without telling the user:** its description would load in every session and its triggers could fire again, only to be stopped by the gate.
- **Never put the user's answers untranslated in the harness files:** the agent reads them every session in English; the user's own words go only inside `«…»`.
