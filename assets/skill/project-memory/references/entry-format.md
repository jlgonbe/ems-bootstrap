# Entry format — `MEMORY.md` and `DECISIONS.md`

Authoritative format of both logs. `scripts/memory.py` writes every entry with exactly these labels; never write an entry by hand.

## Language
Labels, vocabularies, IDs, paths and anchors are always English (the script parses them). Content is English too; the user's own words go verbatim, in their language, inside `«…»`. `check` rejects a non-English letter outside `«…»` and `backticks`.

## Order and rendering
- **Newest first:** `add` inserts every new entry at the top of its log, right under the header; `check` fails if IDs are not in descending order.
- **Anything with `<…>` in `backticks`:** a raw `<word>` outside backticks is read as an HTML tag and hides the rest of the file when rendered; `add` refuses it and `check` reports it.
- **One line per field:** join sentences with `;`, never a newline.

## `MEMORY.md` — lessons (`M001`, `M002`…)

```markdown
### M001 — <title>
- Date: YYYY-MM-DD
- Type: correction | failure | preference | finding
- Trigger: <recognisable situation where it applies>
- Learning: <what to do or not do, imperative>
- Evidence: <what happened or who said it; the user's words inside «…»>
- Origin: <optional; related M/D IDs, comma-separated>
- Status: active
```

`Status`: `active` · `superseded by M0XX` (a later lesson replaced it).

## `DECISIONS.md` — decisions (`D001`, `D002`…)

```markdown
### D001 — <title>
- Date: YYYY-MM-DD
- Status: accepted
- Context: <why it comes up>
- Alternatives considered: <options and why they were rejected; "none" if there were none>
- Decision: <what is decided>
- Rationale: <why>
- Active rule: <optional; "AGENTS.md rule N" or "AGENTS.md rules N and M" when it creates or changes rules>
```

`Status`: `accepted` · `superseded by D0XX` (a later decision replaced it).

## Supersede, never edit
An entry never changes except its `Status`, and only to `superseded by <later ID of the same log>`, through `memory.py set-status`. That status is final: an entry superseded by mistake can never be made `active` or `accepted` again, so read the dry-run first. `--force` only lets you point an already superseded entry at a different later one. Nothing is deleted.

## Links from AGENTS.md
Every `M0XX` / `D0XX` cited in `AGENTS.md` is a Markdown link to its entry, e.g. `(origin: [D001](DECISIONS.md#d001--adopt-the-ems-project-memory-system))`. The dry-run of `add` prints it as `link:` before the entry exists; afterwards `memory.py link <ID>` prints it. The anchor comes from the heading (lowercase, punctuation dropped, spaces to hyphens). `check` fails on a bare ID, a link to a missing entry or a stale anchor.

## What `check` enforces
- **Headers:** `AGENTS.md`, `MEMORY.md` and `DECISIONS.md` start with `<!-- ems:responsibility:`; no `{{FILL:…}}` left in them or in `CLAUDE.md`; `CLAUDE.md`, if present, imports `@AGENTS.md`.
- **`AGENTS.md`:** at most 150 lines (above that, move what is not needed in every session to a referenced file); the anchors `ems:rules`, `ems:map`, `ems:skills`, `ems:protocol` opened and closed once; every numbered rule ends in `(origin: <link>)` to an existing entry; every ID written as its link; every skill path in `ems:skills` exists.
- **Entries:** only the labels above, each once; IDs unique and newest first; `Date` a real date; `Type` and `Status` within their vocabularies; `Origin` a list of existing IDs without repeats or self-citation; `superseded by X` names a later entry of the same log; a D's `Active rule` names rules that exist and cite it while the D is `accepted`; M entries only in `MEMORY.md`, D entries only in `DECISIONS.md`.

`add` and `set-status` run these checks on the entry they write and write nothing if it fails them; problems elsewhere (an `AGENTS.md` link, another entry) show up only in `check`.
