"""Build a retained-template Word register and a maintainable Markdown copy."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import zipfile
from lxml import etree as E

ROOT = Path(__file__).resolve().parent.parent
REF = Path(r'C:\Users\bhagyaraj\.codex\plugins\cache\openai-curated-remote\openai-templates\0.1.1\skills\artifact-template-strategy-memorandum\assets\reference.docx')
OUT = ROOT / 'AI_Email_Agent_Failure_Register.docx'
issues = [
('Send falsely reported success','Critical','Fixed',
'A failed provider call or missing provider draft ID returned success and moved the record to Sent.',
'Send now requires a provider ID, synchronizes the reviewed content, and marks Sent only after provider confirmation. Failures stay pending with an explicit error.',
'Mocked outage, missing ID, successful send and repeated approval checks pass. Real delivery was not attempted. After an ambiguous network failure, check the provider Sent folder before retrying.'),
('Edit falsely reported synchronization','High','Fixed',
'Save Edit changed local text even when remote synchronization failed.',
'The edited candidate is committed only after provider synchronization succeeds. The UI shows a failure instead of claiming synchronization.',
'Regression test injects an offline provider and confirms the previous saved reply remains intact.'),
('Discard hid remote cleanup failures','High','Fixed',
'Discard silently succeeded when the remote draft could not be removed; provider helpers swallowed errors.',
'Provider errors propagate. Local discard returns a warning and cleanup_pending state, supporting a truthful undo path.',
'API audit and Gmail/Outlook helper tests cover outages and recovery. A warning means a remote draft can still exist.'),
('Demonstration records mixed with real data','High','Fixed',
'Three of five live records were unlabelled mock messages, included in counts and apparently sendable.',
'Normal queries and counts exclude demos. Sending demos is blocked. The worker no longer creates implicit demonstrations when credentials fail.',
'Live restart shows two real records and three hidden demos. Existing sample records remain stored for traceability.'),
('PIN switch provided no protection','High','Fixed',
'The enabled setting did not protect data or mutation endpoints.',
'APIs require an expiring PIN-unlocked session. New PINs are hashed, secrets are omitted from configuration responses, and cross-origin access is rejected.',
'Tests cover denial, unlock, incorrect credentials, hashing and session invalidation. Live locked status returns 401 and existing-PIN unlock returns 200.'),
('Auto send switch had no behavior','High','Fixed with limits',
'The worker ignored auto_approve and confidence settings and always left drafts pending.',
'Explicit enablement now permits only eligible simple replies with at least 85 percent estimated confidence, safe intent and allowed priority/category/sentiment. User edits prevent automatic sending.',
'Eligibility and successful delivery pipeline tests pass. This is model-estimated confidence, not a correctness guarantee. Live auto-send remains OFF.'),
('Sent history could be altered','High','Fixed',
'API requests could edit or discard an already approved draft despite hidden UI controls.',
'Mutations require the appropriate pending state. Sent reply content and linked resources are read-only.',
'Audit checks reject editing/discarding Sent records. A regression test also rejects removal of a sent link.'),
('Today and Clear showed misleading dates','Medium','Fixed',
'Today appeared selected while no filter was active; explicitly choosing today still showed other dates.',
'The date field starts empty. Every selected date filters; Clear removes the value and filter. Date help describes the selected status timestamp.',
'Browser check: today excluded the older fixture; Clear restored it. The empty input and disabled Clear state matched the results.'),
('Discard time missing until refresh','Medium','Fixed',
'The frontend changed status without copying rejected_at, briefly displaying a dash and filtering on creation date.',
'Discard returns the full updated record; the frontend uses its server timestamp immediately.',
'Timestamp API assertion passes. The discarded fixture displayed its relative discard time in the browser.'),
('Saved theme lost on reload','Medium','Fixed',
'Theme selection saved but was applied only after reopening Settings.',
'Initialization loads saved appearance. Closing an unsaved preview restores the saved theme.',
'Emerald was saved and retained after browser reload. All four theme buttons were exercised in the original audit.'),
('Agent running badge inferred from a key','Medium','Fixed',
'Any nonempty AI key made an API-only process claim the worker was running.',
'Status now reports actual worker-thread health, phase and mailbox state independently of key presence.',
'Mock API-only server displays Worker not running. Live worker reports alive and Gmail connected. This badge does not certify AI answer accuracy.'),
('Audio preference was inert','Medium','Implemented',
'Audio Feedback Chimes saved a flag without producing sound.',
'A short Web Audio chime now follows notifications when enabled; the audio context initializes after a user gesture.',
'Code and JavaScript syntax checks pass. Browser audio output was not independently listened to; browser/device mute settings can suppress it.'),
('Platform switches needed restart','Medium','Fixed',
'Provider clients and startup flags determined later polling, ignoring changed settings.',
'The worker reloads platform configuration during polling and obtains enabled provider connections without interactive sign-in.',
'A regression test disables Gmail between two cycles and confirms no second fetch/connection. Changes take effect by the next polling cycle.'),
('Original email and rewrite context truncated','High','Fixed with legacy recovery',
'Stored bodies stopped at 1000 characters; both real legacy records had exactly that length.',
'New records retain the full original and RFC message ID. Legacy excerpts are labelled and can load the full original; rewriting retrieves it before generation.',
'Full-body persistence and legacy hydration tests pass. Old records require access to the original provider message for recovery.'),
('Category accessibility state stayed selected','Low','Fixed',
'Returning to Pending removed visual selection but retained category aria-pressed=true.',
'Overview and status navigation consistently reset visual and accessibility state.',
'Browser check selected Invoices then Pending and confirmed the category aria-pressed value became false.'),
('Stop claimed success after request failure','Medium','Fixed',
'The UI displayed Stopped even when the stop request failed.',
'Stop checks HTTP success and reports Shutdown requested; a failed request restores the button and displays an error.',
'API shutdown dispatch is tested with process exit mocked. The real app was restarted separately; shutdown-button process termination was not used during QA.'),
('Gmail mailbox appeared unavailable','Medium','Resolved environment issue',
'The original audit could not load Gmail because its test environment restricted outbound network access.',
'Read-only verification outside that restriction succeeded. Mailbox error reporting now distinguishes sign-in, permissions and connectivity failures.',
'Live updated Gmail inbox endpoint returns HTTP 200. This finding was environmental, not proof of a broken Gmail account.'),
('Outlook mailbox cannot authenticate','High','Account setup required',
'No saved Outlook sign-in is available; the old UI asserted administrator approval was required without sufficient evidence.',
'The app now provides sign-in guidance and reports the actual authentication condition. Background polling never opens sign-in automatically.',
'Live endpoint returns 401. Run .venv\\Scripts\\python.exe connect_email.py outlook and complete the account flow. Administrator approval is needed only if the tenant requests it.'),
('Worker could overwrite dashboard changes','High','Fixed',
'Long-lived in-memory draft data could overwrite newer edits or sent states; concurrent writes could corrupt JSON.',
'Worker additions merge the latest stored state under a shared transaction lock. JSON writes replace the destination atomically.',
'A regression test adds a new worker draft while preserving an existing approved record and its current data.'),
('Attachment retries and undo lost integrity','High','Fixed',
'Outlook send retries could upload duplicate attachments; undo and sent history could lose attachment resources.',
'Remote attachment IDs are tracked, retries reuse uploaded files, and soft deletion/discard retain resources for undo. Sent resources remain visible and read-only.',
'Retry test confirms one upload over two failed send attempts. Discard retains attachment metadata and bytes. Native file chooser interaction remains unverified.'),
('Gemini generation used an unavailable model','High','Fixed',
'The configured Gemini 1.5 model returned 404. A 2.5 replacement was also unavailable to this account.',
'The deprecated SDK path was replaced with a requests-based generateContent adapter and gemini-3.6-flash, as identified by the provider error. Empty or incomplete output fails clearly.',
'Live synthetic text and JSON generation both succeeded. Mock tests cover JSON configuration and rejection of truncated/empty replies. No private email was used for this connectivity check.'),
('Async actions lacked failure and busy handling','Medium','Fixed',
'Some resource and restore operations lacked network-error feedback; repeated main-action clicks could race.',
'Mutation controls handle errors, capture the target draft ID and restore state in finally blocks. Send/edit/discard prevent repeated in-flight actions.',
'JavaScript syntax checks and isolated API flows pass. No browser console errors were recorded in the rechecked fixture.'),
('Fallback classification looked authoritative','Medium','Fixed with historical caveat',
'Two real records contained default classification after AI failures, but normal priority/category badges still looked authoritative.',
'Fallback records now carry an explicit Classification needs review warning. Fallback confidence is zero and automatic sending is ineligible.',
'Legacy fallback summaries are detected without rewriting historical records. Their priorities still require manual review; the repair does not retroactively certify classifications.'),
('Classifier ignored the end of messages','High','Fixed',
'Classification saw only the first 500 characters, potentially missing later instructions or urgency.',
'Classification now receives the full original body, matching the information available to reply generation.',
'A regression test places an important request after character 1500 and verifies it is present in the prompt. Model judgments still require user review.')
]

summary = 'This register records 24 findings from the dashboard audit and the repair work on 18 September 2026, with a current file and test review refreshed on 21 September 2026. It preserves symptoms, corrections and verification evidence for future maintenance. The updated app is configured for Outlook and Google Gemini, PIN protection is enabled, automatic sending remains off, and the limits below remain explicit.'
verification = [
('Current automated verification','On 21 September 2026, .venv\\Scripts\\python.exe -m unittest discover -s tests -v ran 22 tests successfully. JavaScript and dashboard checks should be rerun when frontend behavior changes. Provider sends, deletes and AI rewrites in tests use mocks and temporary data.'),
('Historical dashboard verification','The earlier repair record reported 27 isolated diagnostic API checks passing after an audit baseline of 21 passes and six failures. The generated dashboard-fix-results.json file is not present in the current workspace, so that evidence is retained as historical rather than current rerun evidence.'),
('Current configuration review','config.yaml currently enables Outlook, selects Google Gemini with gemini-3.6-flash, enables PIN security, enables sound and snooze behavior, keeps automatic sending disabled, and listens on 127.0.0.1:5001.'),
('Live verification still required','Outlook mailbox polling, provider draft synchronization against a real mailbox, native file chooser behavior and audible chimes still need live-account verification after sign-in. Passing tests verify the exercised behavior, not every possible provider or message.'),
('Browser verification','Rechecked PIN entry, saved-theme reload, today/Clear filtering, category accessibility reset, worker status and discarded timestamps. The original audit covered navigation, search, sort, review, edit, rewrite, links, delete/undo, discard/undo, settings and a mocked send.'),
('Remaining limits','No real email was sent or deleted for QA. Outlook delivery and mailbox pagination require authenticated access. Native file selection and audible chimes were not independently verified. AI factual correctness cannot be established by a connection test. Check ambiguous send failures in the provider Sent folder before retrying.'),
('Repeatable checks','Run .venv\\Scripts\\python.exe -m unittest discover -s tests -v. If the dashboard diagnostic script is restored or available in the workspace, run it after frontend changes and keep the generated JSON with the audit record.'),
('Evidence and maintenance','Keep DASHBOARD_AUDIT.md and dashboard-audit-results.json as the original baseline. Use FAILURE_REGISTER.md and this document as the repair record. Future entries should retain an ID, severity, reproduction, expected/actual behavior, fix, verification and remaining limitation.')
]

md = ['# AI Email Agent Failure Register','', 'Updated 21 September 2026','',summary,'']
for i,(title,severity,status,symptom,fix,verify) in enumerate(issues,1):
    md += [f'## F{i:02d} {title}', '', f'**Severity:** {severity} | **Status:** {status}', '', f'**Failure:** {symptom}', '', f'**Correction:** {fix}', '', f'**Verification and limits:** {verify}', '']
md += ['## Verification and future use','']
for title, text in verification: md += [f'### {title}', '', text, '']
(ROOT/'FAILURE_REGISTER.md').write_text('\n'.join(md),encoding='utf-8')

ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+ns['w']+'}'
with zipfile.ZipFile(REF) as z:
    parts={name:z.read(name) for name in z.namelist()}
doc=E.fromstring(parts['word/document.xml'])
body=doc.find(W+'body')
paras=body.findall(W+'p')
templates={name:deepcopy(paras[index]) for name,index in [('title',3),('h1',31),('h2',43),('body',32)]}
section=deepcopy(body.find(W+'sectPr'))
for child in list(body): body.remove(child)

def paragraph(text,kind='body',newpage=False):
    p=deepcopy(templates[kind]); prop=p.find(W+'pPr')
    if prop is None: prop=E.Element(W+'pPr');p.insert(0,prop)
    for child in list(p):
        if child is not prop: p.remove(child)
    for name in ('numPr','pageBreakBefore','sectPr'):
        for child in prop.findall(W+name): prop.remove(child)
    if newpage: E.SubElement(prop,W+'pageBreakBefore')
    # Keep complete issue paragraphs together; headings retain template styles.
    E.SubElement(prop,W+'keepLines')
    run=E.SubElement(p,W+'r');t=E.SubElement(run,W+'t');t.text=text
    body.append(p)

paragraph('AI Email Agent Failure Register','title')
paragraph('Audit findings and repair evidence','h1')
paragraph('Prepared for Bhagyaraj by Codex   |   Updated 21 September 2026')
paragraph(summary)
paragraph('Current verification','h2')
for title,text in verification[:3]: paragraph(f'{title}: {text}')
paragraph('What still needs attention','h2')
paragraph('Complete Outlook sign-in and repeat live mailbox checks. Review older drafts marked as excerpts or failed classifications. Keep automatic sending disabled until you are satisfied with the replies. Passing checks verify the exercised behavior, not every possible provider or message.')
for start in range(0,len(issues),4):
    paragraph(f'Failure records {start+1} to {min(start+4,len(issues))}','h1',True)
    for i, (title,severity,status,symptom,fix,verify) in enumerate(issues[start:start+4],start+1):
        paragraph(f'F{i:02d} {title}','h2')
        paragraph(f'{severity} | {status}. Failure: {symptom}')
        paragraph('Correction: '+fix)
        paragraph('Verification: '+verify)
paragraph('Verification and future use','h1',True)
for title,text in verification[3:]: paragraph(title,'h2');paragraph(text)
paragraph('Account setup','h2')
paragraph('From the project directory, run .venv\\Scripts\\python.exe connect_email.py outlook and follow the Microsoft sign-in instructions. Then refresh the Outlook mailbox. This document does not contain passwords, PINs, API keys or email contents.')
paragraph('Technical sources','h2')
paragraph('Gemini REST request format: https://ai.google.dev/api/generate-content. Model availability was established from the authenticated provider response and successful synthetic generation on the verification date.')
body.append(section)
parts['word/document.xml']=E.tostring(doc,xml_declaration=True,encoding='UTF-8',standalone=True)
for name in list(parts):
    if name.startswith('word/header') or name.startswith('word/footer'):
        if name.endswith('.xml'):
            xml=E.fromstring(parts[name])
            for t in xml.findall('.//'+W+'t'):
                if t.text: t.text=t.text.replace('Strategy Memo','AI Email Agent Failure Register').replace('[Confidentiality]','Project maintenance record')
            parts[name]=E.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True)
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in parts.items(): z.writestr(name,data)
contract = f'''# Template fidelity contract
Reference: {REF}
SHA256: {hashlib.sha256(REF.read_bytes()).hexdigest()}
Reference render: 10 pages, all visually inspected.
Retained: all package parts, section geometry (US Letter, one-inch margins), theme, styles, numbering, fonts, relationships, header rule and page-number fields.
Editable slots: document body, running header label, footer confidentiality placeholder.
Body uses cloned Title, Heading 1, Heading 2 and Normal paragraph patterns. Optional charts and comparison tables have no corresponding evidence and are omitted from body; their package parts remain retained. Placeholder/blank reference pages were not reproduced. Added page breaks organize four findings per section.
Rendering: packaged LibreOffice unavailable on this Windows host; Microsoft Word ExportAsFixedFormat creates the PDF. Packaged render_docx.rasterize generates final PNGs through render_word_export.py. No reference mutation.
Output: {OUT.name}
'''
(ROOT/'doc_qa'/'artifact.md').write_text(contract,encoding='utf-8')
print(OUT)
print('Findings:',len(issues))
