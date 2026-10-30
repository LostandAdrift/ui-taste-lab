# Agent contract

- Use `python tastelab.py --data PATH COMMAND`; place global flags before command.
- Default private root: `~/forge/referneces/ui-taste-lab`. Never assume its spelling is a typo.
- `pending-count` prints `{pending_count,queue_limit}`; `list` prints item records.
- Daily recurring invocation: `python /ABSOLUTE/APP/tastelab.py discover --online` at 09:00 America/Los_Angeles. Add at most 20 per Pacific day and stop at 100 pending. No deletion or automatic voting to make room.
- Web research may write JSON/JSONL records and call `import-candidates FILE`. Preserve original URL, title, provenance and placement/platform/component/style tags; never represent a link card as a local image. Search across menus, HUD, inventory, navigation, dashboards, forms, onboarding, settings, editors, data tables and mobile layouts.
- Prefer diverse sources; source restrictions are in `sources.json`. Never scrape restricted sources or mirror third-party images based on an assumed license.
- Read `exports/TASTE.md` and `exports/feedback.json` before proposing UI changes. Cite supporting IDs and source links. Separate explicit preferences from tentative correlations. A dislike is scoped to one reference unless the note explicitly generalizes it.
- Do not upload local images or taste data, run unrecognized downloaded demos, expose localhost externally, or commit private files.
- Original imports are untouched. Preserve provenance and feedback event history. SQLite locking and atomic export writes are required; do not replace these with concurrent JSON rewrites.
- Run the meaningful tests after storage, limits or feedback changes. Test artifacts must use temporary data, never real user votes.
