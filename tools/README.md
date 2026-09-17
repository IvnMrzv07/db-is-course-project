# Maintenance tools

These tools maintain documentation and diagrams. They do not generate or overwrite service implementations. Run commands from the repository root.

## Python tools

`python tools/update_code_documentation.py` rebuilds `docs/service-structure.md`, `docs/code-inventory.md`, and `docs/diagrams.md` from current Python files and Mermaid sources. Edit the source files or generator when changing generated content.

`python tools/enrich_class_diagrams.py` refreshes representative class fields in `diagrams/*-classes.mmd` from Python declarations. It selects a subset of fields and may replace manual field selections. Review its diff before committing, then run the documentation updater.

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
node tools/export_diagrams.cjs
```

The exporter reads `diagrams/*.mmd`, writes eight PNGs and `diagrams/images/manifest.json`, and uses a temporary localhost server that closes after rendering. It does not export SVG files. `.diagram-renderer/` is local tooling and is ignored by Git.

By default it uses the locally installed Playwright and its Chromium browser. Optional environment variables `PLAYWRIGHT_MODULE` and `CHROME_PATH` select an alternative Playwright installation and browser executable. No personal filesystem paths are required.

After changing diagrams, inspect the exported PNGs and commit the sources, images, and updated documentation together. Changes made only in the generated Markdown diagrams will be replaced by the next documentation update.
