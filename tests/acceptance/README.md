# Explicit acceptance checks

Run these scripts from the repository root. They are not collected by ordinary pytest.

- `verify_polished_ui.cjs`: Chrome and Edge UI, keyboard, mobile layout and accessibility checks against the main stack.
- `verify_document_text.cjs`: checks presentation preserves all prepared document text.
- `verify_stack_ui.cjs`: main-stack import UI exercise; creates a repeat import.
- `verify_stack_redelivery.py`: message redelivery checks.
- `verify_stack_resilience.py`, `verify_ui_outages.cjs`, `verify_failed_job.py`: fault injection on the isolated cs-acceptance stack only.
- `verify_ui.cjs`: fixture-based UI checks, distinct from real-stack evidence.
- `smoke_test_db.py`: historical Competition/PostgreSQL smoke test.

See the root README and tools/README.md for environment variables and setup. Committed evidence is in docs/coursework/stages/stage12-summary; transient output is in artifacts/test-results. Fault checks must never target the main project's volumes.
