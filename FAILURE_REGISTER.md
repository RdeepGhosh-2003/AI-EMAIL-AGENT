# AI Email Agent Failure Register

Updated 21 September 2026

This register records 24 findings from the dashboard audit and the repair work on 18 September 2026, with a current file and test review refreshed on 21 September 2026. It preserves symptoms, corrections and verification evidence for future maintenance. The updated app is configured for Outlook and Google Gemini, PIN protection is enabled, automatic sending remains off, and the limits below remain explicit.

## F01 Send falsely reported success

**Severity:** Critical | **Status:** Fixed

**Failure:** A failed provider call or missing provider draft ID returned success and moved the record to Sent.

**Correction:** Send now requires a provider ID, synchronizes the reviewed content, and marks Sent only after provider confirmation. Failures stay pending with an explicit error.

**Verification and limits:** Mocked outage, missing ID, successful send and repeated approval checks pass. Real delivery was not attempted. After an ambiguous network failure, check the provider Sent folder before retrying.

## F02 Edit falsely reported synchronization

**Severity:** High | **Status:** Fixed

**Failure:** Save Edit changed local text even when remote synchronization failed.

**Correction:** The edited candidate is committed only after provider synchronization succeeds. The UI shows a failure instead of claiming synchronization.

**Verification and limits:** Regression test injects an offline provider and confirms the previous saved reply remains intact.

## F03 Discard hid remote cleanup failures

**Severity:** High | **Status:** Fixed

**Failure:** Discard silently succeeded when the remote draft could not be removed; provider helpers swallowed errors.

**Correction:** Provider errors propagate. Local discard returns a warning and cleanup_pending state, supporting a truthful undo path.

**Verification and limits:** API audit and Gmail/Outlook helper tests cover outages and recovery. A warning means a remote draft can still exist.

## F04 Demonstration records mixed with real data

**Severity:** High | **Status:** Fixed

**Failure:** Three of five live records were unlabelled mock messages, included in counts and apparently sendable.

**Correction:** Normal queries and counts exclude demos. Sending demos is blocked. The worker no longer creates implicit demonstrations when credentials fail.

**Verification and limits:** Live restart shows two real records and three hidden demos. Existing sample records remain stored for traceability.

## F05 PIN switch provided no protection

**Severity:** High | **Status:** Fixed

**Failure:** The enabled setting did not protect data or mutation endpoints.

**Correction:** APIs require an expiring PIN-unlocked session. New PINs are hashed, secrets are omitted from configuration responses, and cross-origin access is rejected.

**Verification and limits:** Tests cover denial, unlock, incorrect credentials, hashing and session invalidation. Live locked status returns 401 and existing-PIN unlock returns 200.

## F06 Auto send switch had no behavior

**Severity:** High | **Status:** Fixed with limits

**Failure:** The worker ignored auto_approve and confidence settings and always left drafts pending.

**Correction:** Explicit enablement now permits only eligible simple replies with at least 85 percent estimated confidence, safe intent and allowed priority/category/sentiment. User edits prevent automatic sending.

**Verification and limits:** Eligibility and successful delivery pipeline tests pass. This is model-estimated confidence, not a correctness guarantee. Live auto-send remains OFF.

## F07 Sent history could be altered

**Severity:** High | **Status:** Fixed

**Failure:** API requests could edit or discard an already approved draft despite hidden UI controls.

**Correction:** Mutations require the appropriate pending state. Sent reply content and linked resources are read-only.

**Verification and limits:** Audit checks reject editing/discarding Sent records. A regression test also rejects removal of a sent link.

## F08 Today and Clear showed misleading dates

**Severity:** Medium | **Status:** Fixed

**Failure:** Today appeared selected while no filter was active; explicitly choosing today still showed other dates.

**Correction:** The date field starts empty. Every selected date filters; Clear removes the value and filter. Date help describes the selected status timestamp.

**Verification and limits:** Browser check: today excluded the older fixture; Clear restored it. The empty input and disabled Clear state matched the results.

## F09 Discard time missing until refresh

**Severity:** Medium | **Status:** Fixed

**Failure:** The frontend changed status without copying rejected_at, briefly displaying a dash and filtering on creation date.

**Correction:** Discard returns the full updated record; the frontend uses its server timestamp immediately.

**Verification and limits:** Timestamp API assertion passes. The discarded fixture displayed its relative discard time in the browser.

## F10 Saved theme lost on reload

**Severity:** Medium | **Status:** Fixed

**Failure:** Theme selection saved but was applied only after reopening Settings.

**Correction:** Initialization loads saved appearance. Closing an unsaved preview restores the saved theme.

**Verification and limits:** Emerald was saved and retained after browser reload. All four theme buttons were exercised in the original audit.

## F11 Agent running badge inferred from a key

**Severity:** Medium | **Status:** Fixed

**Failure:** Any nonempty AI key made an API-only process claim the worker was running.

**Correction:** Status now reports actual worker-thread health, phase and mailbox state independently of key presence.

**Verification and limits:** Mock API-only server displays Worker not running. Live worker reports alive and Gmail connected. This badge does not certify AI answer accuracy.

## F12 Audio preference was inert

**Severity:** Medium | **Status:** Implemented

**Failure:** Audio Feedback Chimes saved a flag without producing sound.

**Correction:** A short Web Audio chime now follows notifications when enabled; the audio context initializes after a user gesture.

**Verification and limits:** Code and JavaScript syntax checks pass. Browser audio output was not independently listened to; browser/device mute settings can suppress it.

## F13 Platform switches needed restart

**Severity:** Medium | **Status:** Fixed

**Failure:** Provider clients and startup flags determined later polling, ignoring changed settings.

**Correction:** The worker reloads platform configuration during polling and obtains enabled provider connections without interactive sign-in.

**Verification and limits:** A regression test disables Gmail between two cycles and confirms no second fetch/connection. Changes take effect by the next polling cycle.

## F14 Original email and rewrite context truncated

**Severity:** High | **Status:** Fixed with legacy recovery

**Failure:** Stored bodies stopped at 1000 characters; both real legacy records had exactly that length.

**Correction:** New records retain the full original and RFC message ID. Legacy excerpts are labelled and can load the full original; rewriting retrieves it before generation.

**Verification and limits:** Full-body persistence and legacy hydration tests pass. Old records require access to the original provider message for recovery.

## F15 Category accessibility state stayed selected

**Severity:** Low | **Status:** Fixed

**Failure:** Returning to Pending removed visual selection but retained category aria-pressed=true.

**Correction:** Overview and status navigation consistently reset visual and accessibility state.

**Verification and limits:** Browser check selected Invoices then Pending and confirmed the category aria-pressed value became false.

## F16 Stop claimed success after request failure

**Severity:** Medium | **Status:** Fixed

**Failure:** The UI displayed Stopped even when the stop request failed.

**Correction:** Stop checks HTTP success and reports Shutdown requested; a failed request restores the button and displays an error.

**Verification and limits:** API shutdown dispatch is tested with process exit mocked. The real app was restarted separately; shutdown-button process termination was not used during QA.

## F17 Gmail mailbox appeared unavailable

**Severity:** Medium | **Status:** Resolved environment issue

**Failure:** The original audit could not load Gmail because its test environment restricted outbound network access.

**Correction:** Read-only verification outside that restriction succeeded. Mailbox error reporting now distinguishes sign-in, permissions and connectivity failures.

**Verification and limits:** Live updated Gmail inbox endpoint returns HTTP 200. This finding was environmental, not proof of a broken Gmail account.

## F18 Outlook mailbox cannot authenticate

**Severity:** High | **Status:** Account setup required

**Failure:** No saved Outlook sign-in is available; the old UI asserted administrator approval was required without sufficient evidence.

**Correction:** The app now provides sign-in guidance and reports the actual authentication condition. Background polling never opens sign-in automatically.

**Verification and limits:** Live endpoint returns 401. Run .venv\Scripts\python.exe connect_email.py outlook and complete the account flow. Administrator approval is needed only if the tenant requests it.

## F19 Worker could overwrite dashboard changes

**Severity:** High | **Status:** Fixed

**Failure:** Long-lived in-memory draft data could overwrite newer edits or sent states; concurrent writes could corrupt JSON.

**Correction:** Worker additions merge the latest stored state under a shared transaction lock. JSON writes replace the destination atomically.

**Verification and limits:** A regression test adds a new worker draft while preserving an existing approved record and its current data.

## F20 Attachment retries and undo lost integrity

**Severity:** High | **Status:** Fixed

**Failure:** Outlook send retries could upload duplicate attachments; undo and sent history could lose attachment resources.

**Correction:** Remote attachment IDs are tracked, retries reuse uploaded files, and soft deletion/discard retain resources for undo. Sent resources remain visible and read-only.

**Verification and limits:** Retry test confirms one upload over two failed send attempts. Discard retains attachment metadata and bytes. Native file chooser interaction remains unverified.

## F21 Gemini generation used an unavailable model

**Severity:** High | **Status:** Fixed

**Failure:** The configured Gemini 1.5 model returned 404. A 2.5 replacement was also unavailable to this account.

**Correction:** The deprecated SDK path was replaced with a requests-based generateContent adapter and gemini-3.6-flash, as identified by the provider error. Empty or incomplete output fails clearly.

**Verification and limits:** Live synthetic text and JSON generation both succeeded. Mock tests cover JSON configuration and rejection of truncated/empty replies. No private email was used for this connectivity check.

## F22 Async actions lacked failure and busy handling

**Severity:** Medium | **Status:** Fixed

**Failure:** Some resource and restore operations lacked network-error feedback; repeated main-action clicks could race.

**Correction:** Mutation controls handle errors, capture the target draft ID and restore state in finally blocks. Send/edit/discard prevent repeated in-flight actions.

**Verification and limits:** JavaScript syntax checks and isolated API flows pass. No browser console errors were recorded in the rechecked fixture.

## F23 Fallback classification looked authoritative

**Severity:** Medium | **Status:** Fixed with historical caveat

**Failure:** Two real records contained default classification after AI failures, but normal priority/category badges still looked authoritative.

**Correction:** Fallback records now carry an explicit Classification needs review warning. Fallback confidence is zero and automatic sending is ineligible.

**Verification and limits:** Legacy fallback summaries are detected without rewriting historical records. Their priorities still require manual review; the repair does not retroactively certify classifications.

## F24 Classifier ignored the end of messages

**Severity:** High | **Status:** Fixed

**Failure:** Classification saw only the first 500 characters, potentially missing later instructions or urgency.

**Correction:** Classification now receives the full original body, matching the information available to reply generation.

**Verification and limits:** A regression test places an important request after character 1500 and verifies it is present in the prompt. Model judgments still require user review.

## Verification and future use

### Current automated verification

On 21 September 2026, .venv\Scripts\python.exe -m unittest discover -s tests -v ran 22 tests successfully. JavaScript and dashboard checks should be rerun when frontend behavior changes. Provider sends, deletes and AI rewrites in tests use mocks and temporary data.

### Historical dashboard verification

The earlier repair record reported 27 isolated diagnostic API checks passing after an audit baseline of 21 passes and six failures. The generated dashboard-fix-results.json file is not present in the current workspace, so that evidence is retained as historical rather than current rerun evidence.

### Current configuration review

config.yaml currently enables Outlook, selects Google Gemini with gemini-3.6-flash, enables PIN security, enables sound and snooze behavior, keeps automatic sending disabled, and listens on 127.0.0.1:5001.

### Live verification still required

Outlook mailbox polling, provider draft synchronization against a real mailbox, native file chooser behavior and audible chimes still need live-account verification after sign-in. Passing tests verify the exercised behavior, not every possible provider or message.

### Browser verification

Rechecked PIN entry, saved-theme reload, today/Clear filtering, category accessibility reset, worker status and discarded timestamps. The original audit covered navigation, search, sort, review, edit, rewrite, links, delete/undo, discard/undo, settings and a mocked send.

### Remaining limits

No real email was sent or deleted for QA. Outlook delivery and mailbox pagination require authenticated access. Native file selection and audible chimes were not independently verified. AI factual correctness cannot be established by a connection test. Check ambiguous send failures in the provider Sent folder before retrying.

### Repeatable checks

Run .venv\Scripts\python.exe -m unittest discover -s tests -v. If the dashboard diagnostic script is restored or available in the workspace, run it after frontend changes and keep the generated JSON with the audit record.

### Evidence and maintenance

Keep DASHBOARD_AUDIT.md and dashboard-audit-results.json as the original baseline. Use FAILURE_REGISTER.md and this document as the repair record. Future entries should retain an ID, severity, reproduction, expected/actual behavior, fix, verification and remaining limitation.
