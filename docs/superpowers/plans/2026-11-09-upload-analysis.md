# Upload Analysis Implementation Plan

> For agentic workers: use superpowers:executing-plans; implement inline, then request one fresh review.

Goal: Turn approved Demo into a local persistent application with ChatGPT as the sole seeded provider.
Architecture: FastAPI serves a lightweight HTML/CSS/JS frontend at /app on 8503, reusing SQLite projects, parsed documents and historical runs. New /api/v2 routes own encrypted model settings, upload idempotency, parallel model jobs, persistent questions and PDF exports. Legacy routes remain available.
Tech Stack: Python, FastAPI, SQLAlchemy, SQLite, urllib, ReportLab, cryptography, vanilla JS.
Spec: docs/导航与上传分析改版设计.md (approved by user's instruction to build).

## Global Constraints

No paid calls without user operation; no seeded fake reports. Default one ChatGPT config using OpenAI Responses, editable model ID gpt-5-mini. Additional providers selectable through OpenAI-compatible Chat Completions. Keys never returned, logged or committed. All storage under ignored data/. Bind loopback only. Existing data untouched. This is a single-user local tool, not an authenticated internet service.

Implementation decision: replace Streamlit's main UI with the approved static visual layout, keep original Streamlit file for compatibility. Use native inline execution to reduce cost; existing independent clone on codex/upload-analysis, no additional worktree needed. No further design approval needed: user explicitly requested implementation.

## Review Focus

- Duplicate upload and duplicate submit should not create duplicate projects or paid requests.
- Changing model settings must not change an already queued request or disclose stored keys to a new endpoint.
- A failed/disabled/deleted provider must not affect other reports or history.
- Reports and chat must isolate project context, validate citation identifiers, and expose context truncation.
- Broken model output, interrupted tasks, long Chinese PDF output and old Mock reports remain readable.

## Task 1: Persistent API and contract tests

Files: tests/conftest.py, tests/test_workspace.py; backend/workspace_models.py, backend/workspace_api.py, backend/providers.py; modify database.py/main.py.
Interfaces: /api/v2/models CRUD (key_configured only); /imports multipart request_id; /projects and PATCH /projects/{id}; /projects/{id}/runs POST model_ids + request_id and GET; /reports list/detail; /projects/{id}/messages GET/POST report_id + model_id + question + request_id.
- [x] Write failing integration tests for singleton default, encrypted secret update, import reuse/content mismatch, invalid naming, project isolation, missing key and context rules.
- [x] Run pytest tests/test_workspace.py and observe missing routes before implementing.
- [x] Implement persistence, URL/secret validation, bounded parsing and request identities.
- [x] Run tests against disposable storage; preserve existing API tests.

## Task 2: Real provider jobs, chat and PDF

Files: backend/providers.py, backend/workspace_jobs.py, backend/report_pdf.py; tests/test_workspace.py, tests/test_providers.py.
Interfaces: generate(config, messages) -> text + usage; independent executor jobs with request snapshots and state recovery; PDF endpoint returns application/pdf attachment.
- [x] Add failing tests for parallel completion, independent failure, persistent chat, project boundaries, malformed replies, safe error messages, PDF content and citations.
- [x] Implement max 3 concurrent calls; no automatic paid retries; per-request timeout and input/output limits. Save input/config snapshots excluding decrypted keys. Persist message and report state. Encrypt secrets at rest using local master key file.
- [x] Verify mocked transport only (no live provider billing), PDF extraction and rendered layout.

## Task 3: Approved UI + launch + reconstruction docs

Files: frontend/web/index.html, app.js, style.css; launcher_web.py, start_web.bat; README and docs.
- [x] Connect upload/name/model selection/report list/task retry/chat/settings to real API.
- [x] Remove fixed sample content; explicit missing-key and error states; pending upload/analysis recovery, search and source display.
- [x] Build direct PDF download, retain report snapshot identity and runtime usage metadata.
- [x] Browser check upload/edit/settings/chat errors/report display with isolated fixtures; run full pytest and JS syntax checks.
- [x] Update main requirements/reconstruction appendix and launch new UI at 8503.
- [x] Fresh independent review, resolve important findings, record verification and remaining live-key limitation.
