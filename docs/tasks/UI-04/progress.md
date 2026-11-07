# Progress Task UI-04 — Configuration Master–Detail

## Status
DONE ✅

## Summary of Accomplishments
1. **Data Sources & Storage (`/data-sources`, `app/ui/pages/data_sources.py`)**:
   - Converted layout to bounded viewport (`calc(100vh - 48px)`) with zero desktop page-scroll.
   - Standardized header using compact `page_header`.
   - Refactored `render_data_sources_table` by removing 65 repetitive inline styles, adopting shared `td_style` and sticky headers.
   - Passed 5/5 tests in `test_page_data_sources.py`.

2. **Batch Definition Detail (`/batches/<def_id>`, `app/ui/pages/batch_def_edit.py`)**:
   - Transformed template child list into Master–Detail: Left (Master flex: 1) list with internal scroll and sticky headers; Right (Detail ~380px) trial period & parameter preview panel.
   - Bounded viewport with zero desktop page-scroll (`calc(100vh - 48px)`).
   - Passed 5/5 tests in `test_batch_def_pages.py`.

3. **Bounded Template Diagram (`/templates/<id>/diagram`, `app/ui/pages/template_diagram.py`)**:
   - Bounded viewport to `calc(100vh - 48px)` with internal scroll for diagram cards.
   - In `render_diagram_card`, bounded Mermaid preview containers with `maxHeight: "420px"` and `overflow: "auto"`, completely eliminating 4132px unconstrained vertical page sprawl.
   - Passed 2/2 tests in `test_page_template_diagram.py`.

4. **Report Admin (`/report-admin`, `app/ui/pages/report_admin.py`)**:
   - Replaced unconstrained layout with `page_header` and bounded viewport `calc(100vh - 48px)`.
   - Enforced internal flex scroll for both `admin-list-container` and `admin-wizard-container` in `handle_mode_display` callback.
   - Passed 31/31 tests in `test_page_report_admin.py`.

## Test Results
- `tests/unit/test_page_data_sources.py`: 5 passed
- `tests/unit/test_batch_def_pages.py`: 5 passed
- `tests/unit/test_page_template_diagram.py`: 2 passed
- `tests/unit/test_page_report_admin.py`: 31 passed
- Total: 43/43 passed (100%)
- Lint: `ruff check` passed with zero errors.
