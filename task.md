# Implementation Tasks — 10 Demo Improvements

## Phase 1: Dashboard Frontend
- [x] `style.css` — Add sidebar-w var (315px), topbar-header-row, stats-strip, controls-row, filter, badge, snooze, confidence, diff, light-theme styles
- [x] `index.html` — Sidebar width, all-drafts 2×2 grid, activity log, retry queue, topbar restructure (header row + stats strip + controls row), remove banner text, dark/light toggle
- [x] `app.js` — renderDrafts() with confidence bar + snooze + VIP/conflict badges, renderActivityLog(), updateHeaderStats(), toggleThemeMode(), toggleSnooze(), doSnooze(), init theme from localStorage

## Phase 2: Python Backend
- [x] `config.yaml` — Add vip_contacts, retry_max_attempts, snooze_enabled
- [x] `storage.py` — get/save retry_queue, get/save style_memory, snooze_draft, is_snoozed helpers
- [x] `classifier.py` — VIP allowlist check: flag is_vip: true in draft
- [x] `ai_engine.py` — Style diff memory: save diff after approval, use patterns in future drafts
- [x] `agent.py` — Retry queue on send fail, thread conflict detection before generating draft
- [x] `api/server.py` — Record style diff on edit, clean compile & verified

## Phase 3: Verification
- [x] Run python -c "import agent, classifier, ai_engine, storage" to check no import errors
- [x] Ran 40 unit and regression tests in test suite (100% OK)
- [x] Ran full QA dashboard audit (100% PASS on all 27 checks)
