# UI Taste Lab

A local-first visual taste notebook for building beautiful interfaces. Review images with love, like, dislike, skip, undo and short notes. Browse a searchable collection and export evidence for your agents. Python standard library only; no account, paid API or cloud database.

## Run

Python 3.11+ (with system timezone data):

```sh
python tastelab.py serve
# http://127.0.0.1:7841
```

Default private data: `~/forge/referneces/ui-taste-lab` (intentional spelling).
Use `python tastelab.py --data /your/private/folder serve` to override.

```sh
python tastelab.py ingest /folder/of/your/permitted/images
python tastelab.py import examples/candidates.jsonl
python tastelab.py list
python tastelab.py pending-count
python tastelab.py vote ITEM_ID love --note 'The layered panels make dense information feel calm.'
python tastelab.py preferences 'Explicit preference: rich, tactile interfaces for Proofanvil.'
python tastelab.py export
python tastelab.py profile
```

Images are copied without modifying originals into content-addressed `objects/ab/HASH.ext`. SHA-256 deduplicates identical images; source URL deduplicates link-only records. SQLite uses WAL and transactions. Exports use atomic replacement. Tags, voting history and notes remain local. `exports/feedback.json` and `exports/TASTE.md` are portable agent inputs. Do not commit these files.

### Review

Use Add reference to upload an image (up to 20 MB), save a link, or attach a source to an image. Edit placement, component, platform and style on any reference. Heart/love, thumbs up/like and thumbs down/dislike save the current note. Skip removes an item from the active queue; find it again in Collection and revise its reaction. Undo reverses the most recent non-undone vote. Keys: H/L/D/S/U. Search covers titles, notes and tag values. Filters include platform and reaction. Explicit global preferences are separate from reference notes; tag patterns are labeled tentative and cite reference IDs. Dislike notes apply only to that reference, not every tag it contains.

A link-only card deliberately displays no borrowed thumbnail. Open the original source to review; import a personally permitted image for an image-first card. Nothing embeds remote tracking images. The app never executes downloaded demo code.

## Discovery and daily limits

```sh
# Import queued local JSON or JSONL manifests; safe offline default:
python tastelab.py discover
# Fetch fresh official RSS metadata (One Page Love + Lapa Ninja + Smashing Magazine):
python tastelab.py discover --online
# Import records obtained by an agent's supported web search:
python tastelab.py import-candidates /path/to/candidates.jsonl
```

Discovery imports at most 20 unique candidates per America/Los_Angeles calendar day. All import paths enforce a hard cap of 100 unreviewed items under SQLite write locks. Reviewed references are retained without limit. Undo refuses an operation that would exceed the queue cap. Repeat imports are deduplicated; concurrent runs share the daily ledger. Existing references do not consume the daily budget. Limits mean *up to* 20, not a promise of 20 results.

Manifest records use `title`, `source` (or `url`), optional `tags` object, `snippet`, `provenance`, `discovered_at`; optionally `image` for a local file relative to the manifest. JSON is an array; JSONL is one record per line. `import-candidates` enforces the daily allowance; plain `import` is a manual import with queue limit only. Discovery reads `inbox/*.json` (JSONL supported via explicit file import).

`--online` fetches only allowlisted RSS metadata, interleaving sources for variety. It never downloads external images. Source policy is in `sources.json`: Game UI Database and Interface In Game are manual only; Mobbin stays link-only. Feed licensing does not imply screenshot licensing. Unavailable sources are reported in `exports/last-discovery.json` and discovery exits nonzero; local inbox imports still complete. There are no hidden retries or success claims for failed sources. Offline default works without network. Adding RSS or adapter sources requires a policy review.

Schedule the command at **09:00 America/Los_Angeles daily**, with a timezone-aware scheduler. This repository does not install a scheduler automatically. The desktop app service and discovery schedule are separate. A missed offline run may be retried safely; the same daily cap remains in force. The parent setup handles recurring task registration to avoid duplicate jobs.

## Agent interface

See [AGENTS.md](AGENTS.md). All CLI output for machine operations is JSON. `/api/items`, `/api/profile`, `/api/export` are GET endpoints. Mutation endpoints require the per-process `X-Taste-Token` returned by `/api/session`; see the bundled JS for request bodies. Server binds **127.0.0.1 only**, rejects foreign Host headers, has no CORS allowance, and escapes reference text through DOM text nodes. This is a trusted single-user local tool, not a multi-user service. Other local processes can access it.

## Linux desktop setup

Run `python install-local.py` to install a user systemd service and application launcher. It starts on login and binds localhost only. Stop with `systemctl --user disable --now ui-taste-lab.service`. The service points to this checkout, so keep the checkout in place. This installer does not create a discovery schedule.

## Check

```sh
python -m unittest discover -s tests -v
python -m py_compile tastelab.py
node --check web/app.js  # optional JS syntax check
```

MIT applies to this application's code. External references retain their owners' rights. Examples contain source links, not mirrored images. No user images, feedback, exports or credentials belong in the public repository.
