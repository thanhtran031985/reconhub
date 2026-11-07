# Progress Task UI-06 — Batch & Run Wizards

## Status
DONE ✅

## Summary of Accomplishments
1. **New Run Wizard (`/runs/new`, `app/ui/pages/new_run.py`)**:
   - Modernized header using compact `page_header` with UAT/PROD badge.
   - Bounded viewport container (`calc(100vh - 48px)`) with `overflow: hidden`, guaranteeing zero desktop page scroll.
   - Middle body container with independent scroll (`flex: 1, minHeight: 0, overflowY: "auto"`), containing file drop section, parameter inputs, execution card, and SQL query preview.
   - Preserved all contracts: file upload store, progress interval, PROD confirmation modal, execution callback.

2. **Batch Run Wizard (`/batch-runs`, `app/ui/pages/batch_run_wizard.py`)**:
   - Bounded viewport container (`calc(100vh - 48px)`) for both new batch run selection and 5-step batch run workflow.
   - Structured step workflow with fixed top header & stepper, scrollable body for file assignment & prechecks, and fixed 48px bottom navigation footer.
   - Preserved PROD confirmation modal, interval polling, and rerun triggers.

## Test Results
- `tests/unit/test_page_new_run.py`: 12 passed
- `tests/unit/test_page_new_run_extra_params.py`: 6 passed
- `tests/unit/test_batch_run_pages.py`: 26 passed
- `tests/e2e/test_batch_run.py`: 6 passed
- Total: 50/50 passed (100%)
- Lint: `ruff check` passed with zero errors.

