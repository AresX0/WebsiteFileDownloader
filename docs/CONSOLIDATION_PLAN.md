Consolidation Plan: download_files and download_files_threaded

Objective
- Reduce duplication and divergence between `download_files` and `download_files_threaded`.
- Provide a single, well-tested traversal and download pipeline with configurable sync/threaded execution.

High-level strategy
1. Analysis (current step)
   - Identify differences between the two functions: collection of hrefs, file discovery, pause/stop semantics, download retry/backoff, file hashing/conflict handling.
   - Note shared helpers and side effects (logging, progress updates, UI status updates).

2. Design a small API of pure helpers (no UI):
   - `collect_links_from_page(page, base_url, allowed_domains) -> list[hrefs]`
   - `class FileCandidate(abs_url, rel_path, local_path)` to represent a candidate
   - `discover_file_candidates(hrefs, base_dir, existing_files=None) -> list[FileCandidate]`
   - `download_files_concurrent(candidates, gui_context)` — performs downloads with concurrency and honors pause/stop via adaptor functions

3. Tests (next subtask)
   - Unit tests for `collect_links_from_page` (mock Playwright-like page with anchor objects)
   - Unit tests for `discover_file_candidates` (simulate urls and check sanitized paths)
   - Integration-like tests for `download_files_concurrent` with a fake HTTP server or patched `requests.get` to return predictable content; ensure pause/stop cooperation.

4. Incremental refactor
   - Extract `collect_links_from_page` and `discover_file_candidates`; update both `download_files` and `download_files_threaded` to call them.
   - Add `download_files_concurrent` and make `download_files_threaded` delegate to it.
   - Add tests and run CI after each step.

5. Consolidation & cleanup
   - Once behavior is identical for the public surface (same skipped sets, file_tree, all_files), remove duplicated logic or deprecate one function and keep a single canonical implementation.

Risks & mitigations
- Risk: subtle differences in pause/stop handling. Mitigation: add unit tests that simulate pause events and verify behavior.
- Risk: causing regression in file naming/conflict resolution. Mitigation: add tests with pre-populated `_existing_files` and existing files on disk.

Timeline (rough)
- Analysis & test skeleton: 1 day (done now)
- Extract helpers & adapt functions: 1-2 days (iterative with tests)
- Final consolidation & remove duplication: 0.5-1 day (after verification)

Notes
- Keep GUI-related side effects (status updates, logger) in the GUI layer; make helpers accept callbacks to perform status/logging so they remain testable.
- Prefer small, well-named functions rather than a single large refactor.
