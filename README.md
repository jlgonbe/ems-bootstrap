# ems-bootstrap

> **Para personas:** esta es la skill que acompaña a la guía «Tu agente de IA trabaja con información caducada», de la [Bitácora de un Ingeniero de Software](https://bitacoradeuningenierodesoftware.substack.com). No hace falta que la instales a mano. Abre el agente que uses (OpenCode, Claude Code o Codex) y pégale esto:
>
> *"Quiero usar esta skill: https://github.com/jlgonbe/ems-bootstrap. Instálala y dime cómo empezar."*
>
> Te pedirá permiso para descargarla e instalarla. El código es corto, solo usa Python 3 y lo puedes revisar aquí antes. Si algo no funciona, escribe a bitacoraingenierosoftware@gmail.com.

---

**For the agent that received this link.** `ems-bootstrap` sets up, in a new and empty project, a small system that keeps your context true over time: `AGENTS.md` (imported by `CLAUDE.md`) as the current state, `MEMORY.md` and `DECISIONS.md` as dated history, a `project-memory` skill that records lessons and decisions the moment they happen, and two agents (`project-planner`, `project-plan-executor`). It works in OpenCode, Claude Code and Codex, and needs `python3` (3.9 or later, standard library only).

## Install it (do this now, with the user's approval)

Never clone or copy this repository straight into a skills folder: it also holds `tests/` and this `README.md`, which are for people reviewing it, not for the skill. `install.py` copies only what the skill needs.

1. **Fetch** the repository into a temporary folder, outside any project:

   ```sh
   D=$(mktemp -d) && git clone --depth 1 https://github.com/jlgonbe/ems-bootstrap "$D/ems-bootstrap" && echo "$D"
   ```

   Without `git`, download `https://github.com/jlgonbe/ems-bootstrap/archive/refs/heads/main.zip` and unzip it in a folder made with `mktemp -d`. Write that folder's path out in full in the next steps: a shell variable does not survive between calls in some harnesses.

2. **Install** for the harness you are running in (`opencode`, `codex` or `claude`):

   ```sh
   python3 "<that folder>/ems-bootstrap/install.py" --harness <opencode|codex|claude>
   ```

   It copies `SKILL.md`, `references/`, `scripts/` and `assets/` into the user-level skills folder: `~/.agents/skills/ems-bootstrap/` for OpenCode and Codex, `~/.claude/skills/ems-bootstrap/` for Claude Code.

   | Exit | Do |
   |---|---|
   | 0 | installed: go on |
   | 2 | it is already installed: ask the user whether to replace it, and only then run it again with `--replace` |
   | 3 | the folder could not be written (your harness may only let you write inside the current folder): show the user the message, which says what to copy where, and stop |

   Writing in the user's home folder needs their approval: ask for it, and do not work around a refusal.

3. **Clean up:** delete the temporary folder made in step 1 (`rm -rf "<that folder>"`).

## Then tell the user, in their language

Say it in one short message, with these three points:

- The skill is installed and is available in every new project.
- To start a project with it: open a new session **in a new, empty folder** (a framework scaffold with its first commit is fine) and say *"set up the project memory"* (in Spanish: *"monta el sistema de memoria"*).
- It will ask five short questions and explain each piece as it creates it. It only works in new projects: in a folder that already has instruction files or more than one commit, it explains why and stops without writing.

Do **not** run the setup in the folder you are in now unless the user asks you to and that folder is new and empty.

## For people reviewing this repository

- `SKILL.md` is the skill; `references/ems-spec.md` is the specification of what it generates and why.
- `scripts/gate.py` decides whether a folder is a new project and writes nothing; `scripts/setup.py` renders `assets/` into the project, and removes everything it created if a step fails.
- `install.py` installs the skill for one harness; `tests/` holds the test suite: `python3 -B -m unittest discover -s tests` (the scripts need Python 3.9+; two TOML checks need 3.11+ and are skipped below it).
