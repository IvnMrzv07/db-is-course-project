# Maintenance tools

Documentation scripts live in `tools/documentation/`. Browser and Docker checks live in `tests/acceptance/`; run all commands from the repository root. The `update_stage_report.py` and `polish_stage_report.py` scripts are historical migrations, not a pipeline to rerun. `refresh_verified_report.py` is the current evidence-based report updater; always render and inspect afterwards.

# Maintenance tools

These tools maintain documentation and diagrams. They do not generate or overwrite service implementations. Run commands from the repository root.

## Python tools

`python tools/documentation/update_code_documentation.py` rebuilds `docs/service-structure.md`, `docs/code-inventory.md`, and `docs/diagrams.md` from current Python files and Mermaid sources. Edit the source files or generator when changing generated content.

`python tools/documentation/enrich_class_diagrams.py` refreshes representative class fields in `docs/diagrams/*-classes.mmd` from Python declarations. It selects a subset of fields and may replace manual field selections. Review its diff before committing, then run the documentation updater.

Both scripts use the Python standard library.

## PNG exporter

Install a current Node.js LTS release, then install optional rendering dependencies locally:

```sh
npm install --prefix .diagram-renderer --save-exact mermaid@12.0.0 playwright@1.58.2
```

Install Playwright's Chromium browser from the dependency directory:

```sh
cd .diagram-renderer
npx playwright install chromium
cd ..
node tools/documentation/export_diagrams.cjs
```

The exporter reads `docs/diagrams/*.mmd`, writes eight PNGs and `docs/diagrams/images/manifest.json`, and uses a temporary localhost server that closes after rendering. It does not export SVG files. `.diagram-renderer/` is local tooling and is ignored by Git.

By default it uses the locally installed Playwright and its Chromium browser. Optional environment variables `PLAYWRIGHT_MODULE` and `CHROME_PATH` select an alternative Playwright installation and browser executable. No personal filesystem paths are required.

After changing docs/diagrams, inspect the exported PNGs and commit the sources, images, and updated documentation together. Changes made only in the generated Markdown docs/diagrams will be replaced by the next documentation update.

## Stage 9–12 checks and report maintenance

- `verify_ui.cjs` exercises the React UI using explicit HTTP fixtures. Supply `PLAYWRIGHT_MODULE` and optionally `CHROME_PATH`; run Vite first. Screenshots go to ignored `artifacts/test-results/`.
- `verify_stack_ui.cjs` exercises the running Compose UI without HTTP interception. Supply `OPERATOR_TOKEN`, `PLAYWRIGHT_MODULE` and optionally `CHROME_PATH`; the default URL is `http://127.0.0.1:8080` (`UI_BASE_URL` overrides it). Run after the first corpus import. It creates a repeat import through the UI, pauses/resumes it and changes the rate from 10 to 500. Evidence and screenshots go to `docs/coursework/stages/stage12-summary/`.
- `verify_stack_redelivery.py` verifies repeated AMQP delivery after imports finish. Run inside `ingestion_api` with its existing environment (for example `Get-Content -Raw tests/acceptance/verify_stack_redelivery.py | docker compose exec -T ingestion_api python` in PowerShell). It republishes one existing batch and completion twice, waits for queues to drain, and asserts unchanged document, receipt and job counts. It prints JSON evidence; it does not remove data.
- `update_stage_report.py` is the guarded one-time report migration for stages 9–12. It refuses to append the same sections twice. Run it only against the pre-stage report with the bundled document runtime.
- `polish_stage_report.py` repairs layout spacing and the cached automatic TOC; pass a rendered PDF path to refresh the cached page numbers. Always render and inspect the DOCX after edits.
- `update_query_catalog.py` rebuilds the exact SQL/MongoDB query listing after repository changes.

The current frontend screenshots under `docs/coursework/stages/stage12-summary/` come from the real Compose stack, not from the UI fixture script. Earlier native database checks remain separately identified in their JSON files. Top-level dependencies are declared in `requirements.txt`; `requirements.lock` pins the tested transitive backend environment. Rebuild the lock deliberately when upgrading dependencies.

## Extended verification

- `verify_polished_ui.cjs`: live Chrome and Edge, keyboard focus, mobile dialog, translated errors, integer rate controls and axe-core checks. Install `axe-core` in `.diagram-renderer`; requires `OPERATOR_TOKEN` and Playwright environment as above.
- `verify_document_text.cjs`: confirms presentation preserves all prepared document text, ignoring whitespace between paragraphs. Uses the frontend TypeScript dependency.
- `verify_stack_resilience.py`: isolated `cs-acceptance` faults, concurrent imports, poison messages and real completion redrive. See the root README for its 1,000-document fixture and clean-volume prerequisite.
- `verify_ui_outages.cjs`: real MongoDB/PostgreSQL outages and import history pagination on port 8081. Never targets the main demo.
- `refresh_verified_report.py`: updates the existing stage report only when its JSON evidence exists; preserves a pre-edit backup in `artifacts/report-work`. Render and inspect after running, and update the Word contents fields.

Backups used for the acceptance run are retained under ignored `artifacts/test-results/`; restored copies live in the isolated project's `restore_acceptance` databases. They are not published with the repository.

- `verify_failed_job.py`: on the isolated stack, injects one invalid correlated batch and verifies failed-job reporting followed by successful fresh replay. Its retained dead letter is intentional evidence, not a main-demo error.

## High load

- `tools/ops/cs_ops.py`: operator console of a Compose stand (start, shard outage, verify, purge, reset). Standard library only.
- `tools/load/`: scenario runner, report generator and host probe. See `tools/load/README.md`.
