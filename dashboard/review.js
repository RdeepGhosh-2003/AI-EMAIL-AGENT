// Review workspace: keyboard navigation, responsive controls, and writing tools.
$searchInput.setAttribute('aria-label', 'Search drafts by sender or subject');
window.dateFilterActive ||= false;
document.getElementById('sort-drafts')?.addEventListener('change', () => {
  renderDrafts();
  saveDashboardView?.();
});
$refreshBtn.setAttribute('aria-label', 'Refresh drafts');
document.getElementById('toast-container').setAttribute('role', 'status');
$btnReject.textContent = 'Discard draft';
window.selectedDraftIds = new Set();
const deleteSelected = document.createElement('button');
deleteSelected.type = 'button';
deleteSelected.className = 'delete-selected hidden';
deleteSelected.textContent = '🗑 Delete selected';
document.querySelector('.controls-right-tools').prepend(deleteSelected);
window.updateDeleteSelection = () => {
  const count = window.selectedDraftIds.size;
  deleteSelected.classList.toggle('hidden', count === 0);
  deleteSelected.textContent = `🗑 Delete selected${count ? ` (${count})` : ''}`;
};
deleteSelected.addEventListener('click', async () => {
  const ids = [...window.selectedDraftIds];
  if (!ids.length || !confirm(`Move ${ids.length} selected draft${ids.length === 1 ? '' : 's'} to Deleted?`)) return;
  deleteSelected.disabled = true;
  try {
    const response = await fetch(`${API}/drafts/bulk-delete`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not delete drafts');
    allDrafts.forEach(draft => { if (ids.includes(draft.id)) { draft.status = 'deleted'; draft.deleted_at = data.deleted_at; } });
    window.selectedDraftIds.clear();
    window.updateDeleteSelection();
    renderDrafts();
    fetchStatus();
    showToast(`${data.deleted} draft${data.deleted === 1 ? '' : 's'} moved to Deleted`, 'success');
    if (data.warning) showToast(data.warning, 'info');
  } catch (error) { showToast(error.message, 'error'); }
  finally { deleteSelected.disabled = false; }
});
document.querySelectorAll('.filter-btn').forEach(button => {
  if (button.querySelector('.filter-count')) return;
  const count = document.createElement('span');
  count.className = 'filter-count';
  button.appendChild(count);
});
const originalUpdateStats = updateStats;
updateStats = function(data) {
  originalUpdateStats(data);
  document.querySelectorAll('.filter-btn').forEach(button => {
    button.setAttribute('aria-pressed', !overviewFilter && button.dataset.filter === currentFilter);
  });
  updateFilterCounts(data);
};
const originalSetFilter = setFilter;
setFilter = function(filter) {
  window.selectedDraftIds.clear();
  window.updateDeleteSelection();
  originalSetFilter(filter);
  document.querySelectorAll('.filter-btn').forEach(button => button.setAttribute('aria-pressed', button.dataset.filter === filter));
};

$modal.setAttribute('aria-labelledby', 'modal-subject');
const settingsTitle = document.querySelector('#settings-modal h2');
settingsTitle.id = 'settings-title';
document.getElementById('settings-modal').setAttribute('aria-labelledby', 'settings-title');
let reviewTrigger;
window.restoreReviewFocus = () => {
  const replacement = [...document.querySelectorAll('.draft-card')].find(card => card.dataset.id === reviewTrigger?.dataset.id);
  (replacement || reviewTrigger || $searchInput).focus();
};
const recipientLine = document.createElement('div');
recipientLine.className = 'recipient-line';
$modalFrom.after(recipientLine);
const signatureLine = document.createElement('div');
signatureLine.className = 'signature-status';
signatureLine.setAttribute('role', 'status');
$modalReply.after(signatureLine);
async function refreshSignatureStatus() {
  signatureLine.textContent = 'Checking Outlook signature…';
  signatureLine.classList.remove('warning');
  try {
    const response = await fetch(`${API}/accounts/outlook/signature`);
    const status = await response.json();
    if (!response.ok) throw new Error(status.error || 'Unavailable');
    if (status.available) {
      signatureLine.textContent = `✓ Outlook signature for ${status.account} will be appended when saved or sent.`;
    } else {
      signatureLine.textContent = `⚠ No Classic Outlook reply signature matches ${status.account || 'the connected mailbox'}; this email will be sent without a footer.`;
      signatureLine.classList.add('warning');
    }
  } catch (_) {
    signatureLine.textContent = '⚠ Outlook signature status could not be checked.';
    signatureLine.classList.add('warning');
  }
}
const loadOriginal = document.createElement('button');
loadOriginal.type = 'button';
loadOriginal.textContent = 'Load full original';
$modal.querySelector('.panel-original .panel-header').append(loadOriginal);
loadOriginal.addEventListener('click', async () => {
  const id = openDraftId;
  loadOriginal.disabled = true;
  try {
    const response = await fetch(`${API}/drafts/${encodeURIComponent(id)}/original`, {method:'POST'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load original');
    const draft = allDrafts.find(item => item.id === id);
    if (draft) Object.assign(draft, data.draft);
    if (openDraftId === id) { $modalOriginal.textContent = data.draft.original_body || '(No body)'; loadOriginal.hidden = true; }
  } catch(error) { showToast(error.message, 'error'); }
  finally { loadOriginal.disabled = false; }
});
const reviewColumns = document.createElement('div');
reviewColumns.className = 'review-columns';
$modal.querySelector('.modal-body').appendChild(reviewColumns);
reviewColumns.append($modal.querySelector('.panel-original'), $modal.querySelector('.panel-reply'));
const writingTools = document.createElement('div');
writingTools.className = 'writing-tools';
writingTools.innerHTML = '<button type="button" data-rewrite="regenerate">↻ Regenerate</button><button type="button" data-rewrite="shorten">Shorten</button><label><span class="sr-only">Reply tone</span><select id="rewrite-tone"><option value="professional">Professional</option><option value="casual">Friendly</option><option value="formal">Formal</option></select></label><button type="button" data-rewrite="tone">Change tone</button><input class="sr-only" type="file" id="attachment-input" multiple><button type="button" class="tool-icon" id="attach-button" title="Attach files or media" aria-label="Attach files or media">📎</button><button type="button" class="tool-icon" data-link-kind="link" title="Add a web link" aria-label="Add a web link">🔗</button><button type="button" class="tool-icon drive-icon" data-link-kind="drive" title="Add from Google Drive" aria-label="Add from Google Drive">△</button>';
$modal.querySelector('.panel-reply .panel-header').after(writingTools);
const attachmentPanel = document.createElement('div');
attachmentPanel.className = 'attachment-panel';
attachmentPanel.innerHTML = '<div class="resource-composer hidden" id="resource-composer"><label for="resource-url">Link URL</label><input type="url" id="resource-url" placeholder="https://"><input type="text" id="resource-label" placeholder="Display name (optional)"><button type="button" id="save-resource">Add</button><button type="button" id="cancel-resource">Cancel</button></div><div class="attachment-list" id="attachment-list" aria-live="polite"></div>';
writingTools.after(attachmentPanel);
const attachmentInput = document.getElementById('attachment-input');
document.getElementById('attach-button').addEventListener('click', () => attachmentInput.click());
function renderAttachments(draft) {
  const list = document.getElementById('attachment-list');
  list.innerHTML = '';
  (draft.attachments || []).forEach(file => {
    const row = document.createElement('div');
    row.className = 'attachment-chip';
    row.innerHTML = `<span title="${escHtml(file.name)}">📄 ${escHtml(file.name)} <small>${Math.ceil(file.size / 1024)} KB</small></span><button type="button" aria-label="Remove ${escHtml(file.name)}">×</button>`;
    row.querySelector('button').hidden = draft.status !== 'pending';
    row.querySelector('button').addEventListener('click', async () => {
      try {
      const response = await fetch(`${API}/drafts/${encodeURIComponent(draft.id)}/attachments/${encodeURIComponent(file.id)}`, { method: 'DELETE' });
      const data = await response.json();
      if (!response.ok) return showToast(data.error || 'Could not remove attachment', 'error');
      draft.attachments = data.attachments;
      renderAttachments(draft);
      } catch(error) { showToast(error.message, 'error'); }
    });
    list.appendChild(row);
  });
  (draft.links || []).forEach(link => {
    const row = document.createElement('div');
    row.className = 'attachment-chip';
    row.innerHTML = `<span title="${escHtml(link.url)}">${link.kind === 'drive' ? '△' : '🔗'} ${escHtml(link.label)}</span><button type="button" aria-label="Remove ${escHtml(link.label)}">×</button>`;
    row.querySelector('button').hidden = draft.status !== 'pending';
    row.querySelector('button').addEventListener('click', async () => {
      try {
      const response = await fetch(`${API}/drafts/${encodeURIComponent(draft.id)}/links/${encodeURIComponent(link.id)}`, { method: 'DELETE' });
      const data = await response.json();
      if (!response.ok) return showToast(data.error || 'Could not remove link', 'error');
      draft.links = data.links;
      renderAttachments(draft);
      } catch(error) { showToast(error.message, 'error'); }
    });
    list.appendChild(row);
  });
}
attachmentInput.addEventListener('change', async () => {
  const draft = allDrafts.find(item => item.id === openDraftId);
  if (!draft || !attachmentInput.files.length) return;
  const form = new FormData();
  [...attachmentInput.files].forEach(file => form.append('files', file));
  const button = document.getElementById('attach-button');
  button.disabled = true;
    button.textContent = '…';
  try {
    const response = await fetch(`${API}/drafts/${encodeURIComponent(draft.id)}/attachments`, { method: 'POST', body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not attach files');
    draft.attachments = data.attachments;
    renderAttachments(draft);
    showToast(`${data.added} attachment${data.added === 1 ? '' : 's'} added`, 'success');
  } catch (error) { showToast(error.message, 'error'); }
  finally {
    attachmentInput.value = '';
    button.disabled = false;
    button.textContent = '📎';
  }
});
let pendingLinkKind = 'link';
const resourceComposer = document.getElementById('resource-composer');
writingTools.querySelectorAll('[data-link-kind]').forEach(button => button.addEventListener('click', () => {
  pendingLinkKind = button.dataset.linkKind;
  resourceComposer.querySelector('label').textContent = pendingLinkKind === 'drive' ? 'Google Drive share link' : 'Link URL';
  resourceComposer.classList.remove('hidden');
  document.getElementById('resource-url').focus();
}));
document.getElementById('cancel-resource').addEventListener('click', () => resourceComposer.classList.add('hidden'));
document.getElementById('save-resource').addEventListener('click', async () => {
  const draft = allDrafts.find(item => item.id === openDraftId);
  const url = document.getElementById('resource-url').value.trim();
  const label = document.getElementById('resource-label').value.trim();
  if (!draft || !url) return showToast('Enter a link first', 'error');
  const save = document.getElementById('save-resource');
  save.disabled = true;
  try {
  const response = await fetch(`${API}/drafts/${encodeURIComponent(draft.id)}/links`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, label, kind: pendingLinkKind })
  });
  const data = await response.json();
  if (!response.ok) return showToast(data.error || 'Could not add link', 'error');
  draft.links = data.links;
  document.getElementById('resource-url').value = '';
  document.getElementById('resource-label').value = '';
  resourceComposer.classList.add('hidden');
  renderAttachments(draft);
  showToast(pendingLinkKind === 'drive' ? 'Google Drive link added' : 'Link added', 'success');
  } catch(error) { showToast(error.message, 'error'); }
  finally { save.disabled = false; }
});
$modalEditor.setAttribute('aria-label', 'Edit proposed reply');
window.enhanceReview = draft => {
  loadOriginal.hidden = draft.original_body_complete !== false;
  reviewTrigger = document.activeElement;
  recipientLine.textContent = `Reply to: ${draft.sender || 'Unknown'} · Reply to sender only`;
  const safeLabel = [...$modalMeta.querySelectorAll('.chip-label-title')].find(el => el.textContent === 'Auto-Safe');
  safeLabel.textContent = 'Auto-send assessment';
  const assessment = safeLabel.nextElementSibling;
  assessment.textContent = draft.classification?.auto_reply_safe ? 'AI suggests safe' : 'Needs review';
  assessment.title = 'AI classification of this email. This is a suggestion, not a guarantee; check recipients, facts, and commitments before sending.';
  assessment.tabIndex = 0;
  const pending = draft.status === 'pending';
  $btnApprove.hidden = $btnReject.hidden = $editToggle.hidden = !pending;
  writingTools.hidden = !pending;
  attachmentPanel.hidden = !pending && !(draft.links?.length || draft.attachments?.length);
  resourceComposer.classList.add('hidden');
  renderAttachments(draft);
  refreshSignatureStatus();
  $modalClose.focus();
};
const undoRestoreButton = document.createElement('button');
undoRestoreButton.type = 'button';
undoRestoreButton.className = 'btn-undo-reject';
$modalClose.before(undoRestoreButton);
window.restoreDraft = async draft => {
  if (!draft) return;
  undoRestoreButton.disabled = true;
  try {
  const response = await fetch(`${API}/drafts/${encodeURIComponent(draft.id)}/restore`, { method: 'POST' });
  const data = await response.json();
  undoRestoreButton.disabled = false;
  if (!response.ok) return showToast(data.error || 'Could not restore draft', 'error');
  Object.assign(draft, data.draft);
  closeModal();
  setFilter('pending');
  fetchStatus();
  showToast(`${data.restored_from === 'deleted' ? 'Deleted' : 'Discarded'} draft restored to Pending`, 'success');
  } catch(error) { showToast(error.message, 'error'); }
  finally { undoRestoreButton.disabled = false; }
};
undoRestoreButton.addEventListener('click', () => {
  const draft = allDrafts.find(item => item.id === openDraftId);
  if (draft?.snoozed_until) window.undoSnooze?.(draft);
  else window.restoreDraft(draft);
});
const originalEnhanceReview = window.enhanceReview;
window.enhanceReview = draft => {
  originalEnhanceReview(draft);
  const snoozed = Boolean(draft.snoozed_until);
  undoRestoreButton.hidden = !snoozed && !['rejected', 'deleted'].includes(draft.status);
  undoRestoreButton.textContent = snoozed ? '↶ Undo snooze' : draft.status === 'deleted' ? '↶ Undo delete' : '↶ Undo rejection';
};
writingTools.addEventListener('click', async event => {
  const button = event.target.closest('[data-rewrite]');
  if (!button) return;
  const id = openDraftId;
  const label = button.textContent;
  writingTools.querySelectorAll('button').forEach(el => el.disabled = true);
  button.textContent = 'Writing…';
  try {
    const response = await fetch(`${API}/drafts/${encodeURIComponent(id)}/rewrite`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: button.dataset.rewrite, tone: document.getElementById('rewrite-tone').value, reply: editMode ? $modalEditor.value : $modalReply.textContent })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not rewrite reply');
    if (openDraftId !== id) return;
    editMode = true;
    $modalEditor.value = data.ai_reply;
    $modalReply.classList.add('hidden');
    $modalEditor.classList.remove('hidden');
    $editorActions.classList.remove('hidden');
    $editToggle.textContent = 'Editing';
    $modalEditor.focus();
    showToast('New version ready. Review and save your changes.');
  } catch (error) { showToast(error.message, 'error'); }
  finally { button.textContent = label; writingTools.querySelectorAll('button').forEach(el => el.disabled = false); }
});

// Organize settings by stable IDs so adding or removing a card cannot move it
// into every tab (or silently place it under the wrong heading).
const sections = [
  ['General', ['setting-theme-group']],
  ['AI & Writing', ['setting-ai-group', 'setting-tone-group', 'setting-instructions-group', 'setting-vip-group']],
  ['Accounts', ['setting-platforms-group']],
  ['Automation', ['setting-interval-group', 'setting-auto-approve-group']],
  ['Security & Sound', ['setting-security-group', 'setting-pin-group']]
];
const settingsNav = document.createElement('nav');
settingsNav.className = 'settings-nav';
settingsNav.setAttribute('aria-label', 'Settings sections');
$settingsForm.before(settingsNav);
sections.forEach(([name, indexes], index) => {
  const section = document.createElement('section');
  section.id = `settings-section-${index}`;
  section.className = 'settings-section';
  section.hidden = index !== 0;
  section.setAttribute('aria-label', name);
  indexes.forEach(id => section.appendChild(document.getElementById(id)));
  $settingsForm.insertBefore(section, $settingsForm.querySelector('.settings-actions'));
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = name;
  button.setAttribute('aria-controls', section.id);
  button.setAttribute('aria-pressed', index === 0);
  button.addEventListener('click', () => {
    $settingsForm.querySelectorAll('.settings-section').forEach(el => el.hidden = el !== section);
    settingsNav.querySelectorAll('button').forEach(el => el.setAttribute('aria-pressed', el === button));
  });
  settingsNav.appendChild(button);
});
const apiKeyGroup = document.createElement('div');
apiKeyGroup.className = 'setting-group api-key-group';
apiKeyGroup.innerHTML = '<label class="setting-label">🔑 AI Provider API Keys</label><p class="setting-help">Keys are stored locally in your .env file and are never shown again.</p><div class="api-key-row"><label for="setting-openrouter-key">OpenRouter</label><input type="password" id="setting-openrouter-key" class="setting-input" autocomplete="new-password" placeholder="Paste a new key"><span id="openrouter-key-status">Not configured</span></div><div class="api-key-row"><label for="setting-openai-key">OpenAI</label><input type="password" id="setting-openai-key" class="setting-input" autocomplete="new-password" placeholder="Paste a new key"><span id="openai-key-status">Not configured</span></div><div class="api-key-row"><label for="setting-gemini-key">Google Gemini</label><input type="password" id="setting-gemini-key" class="setting-input" autocomplete="new-password" placeholder="Paste a new key"><span id="gemini-key-status">Not configured</span></div><div class="api-key-row"><label for="setting-claude-key">Anthropic Claude</label><input type="password" id="setting-claude-key" class="setting-input" autocomplete="new-password" placeholder="Paste a new key"><span id="claude-key-status">Not configured</span></div>';
document.getElementById('settings-section-1').appendChild(apiKeyGroup);
const accountSetup = document.createElement('div');
accountSetup.className = 'account-setup';
accountSetup.innerHTML = `
  <div class="account-setup-header">
    <div><h3>Connect Microsoft Outlook</h3><p>Connect the Outlook mailbox this agent will monitor. Passwords are never stored by this app.</p></div>
    <a href="/setup-guide" class="setup-guide-link">Download setup guide</a>
  </div>
  <section class="account-card" data-provider="outlook">
    <div class="account-title"><strong>Microsoft Outlook</strong><span class="account-status" id="outlook-account-status">Checking…</span></div>
    <p>Enter the public Application client ID from Microsoft Entra. Use <strong>common</strong> unless your organization provides a tenant ID.</p>
    <div class="account-fields">
      <label>Client ID<input class="setting-input" id="outlook-client-id" autocomplete="off" placeholder="Application client ID"></label>
      <label>Tenant<input class="setting-input" id="outlook-tenant-id" autocomplete="off" value="common"></label>
    </div>
    <div class="account-actions">
      <button type="button" id="save-outlook-config">Save Microsoft details</button>
      <button type="button" id="connect-outlook">Connect Microsoft</button>
    </div>
  </section>`;
document.getElementById('settings-section-2').appendChild(accountSetup);

async function refreshAccountStatus() {
  const response = await fetch(`${API}/accounts/status`);
  const accounts = await response.json();
  ['outlook'].forEach(provider => {
    const account = accounts[provider];
    const status = document.getElementById(`${provider}-account-status`);
    const readyText = 'client ID needed';
    status.textContent = account.connected ? '✓ Connected'
      : account.state === 'connecting' ? 'Waiting for sign-in…'
      : account.state === 'error' ? account.message
      : account.credentials_ready ? 'Ready to connect' : readyText;
    status.className = `account-status ${account.connected ? 'connected' : account.state === 'error' ? 'error' : ''}`;
    document.getElementById(`connect-${provider}`).disabled = !account.credentials_ready || account.state === 'connecting';
    if (provider === 'outlook') {
      document.getElementById('outlook-tenant-id').value = account.tenant || 'common';
      document.getElementById('outlook-client-id').placeholder = account.credentials_ready ? 'Configured — enter only to replace' : 'Application client ID';
    }
  });
  return accounts;
}

document.getElementById('save-outlook-config').addEventListener('click', async () => {
  const clientId = document.getElementById('outlook-client-id').value.trim();
  if (!clientId) return showToast('Enter the Microsoft Application client ID first.', 'error');
  try {
    const response = await fetch(`${API}/accounts/outlook/config`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, tenant_id: document.getElementById('outlook-tenant-id').value.trim() || 'common' })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not save Microsoft details');
    document.getElementById('outlook-client-id').value = '';
    showToast(data.message, 'success');
    await refreshAccountStatus();
  } catch (error) { showToast(error.message, 'error'); }
});

async function connectEmailAccount(provider) {
  const button = document.getElementById(`connect-${provider}`);
  button.disabled = true;
  try {
    const response = await fetch(`${API}/accounts/${provider}/connect`, { method: 'POST' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not start sign-in');
    showToast(data.message, 'info');
    for (let attempt = 0; attempt < 150; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const accounts = await refreshAccountStatus();
      if (accounts[provider].connected) {
        showToast('Microsoft connected', 'success');
        return;
      }
      if (accounts[provider].state === 'error') throw new Error(accounts[provider].message);
    }
    throw new Error('Sign-in timed out. You can click Connect again.');
  } catch (error) { showToast(error.message, 'error'); }
  finally { button.disabled = false; }
}
document.getElementById('connect-outlook').addEventListener('click', () => connectEmailAccount('outlook'));
document.querySelectorAll('.theme-option').forEach(old => {
  const button = document.createElement('button');
  [...old.attributes].forEach(attr => button.setAttribute(attr.name, attr.value));
  button.type = 'button';
  button.innerHTML = old.innerHTML;
  button.setAttribute('aria-pressed', old.classList.contains('active'));
  old.replaceWith(button);
});
const originalSelectTheme = selectDashboardTheme;
selectDashboardTheme = function(theme) {
  originalSelectTheme(theme);
  document.querySelectorAll('.theme-option').forEach(el => el.setAttribute('aria-pressed', el.dataset.theme === theme));
};
$settingsForm.querySelectorAll('input[type=checkbox]').forEach(el => el.setAttribute('role', 'switch'));
const autoSelect = document.getElementById('setting-auto-approve');
autoSelect.classList.add('hidden');
autoSelect.removeAttribute('id');
const autoSwitch = document.createElement('input');
autoSwitch.type = 'checkbox';
autoSwitch.setAttribute('role', 'switch');
autoSwitch.setAttribute('aria-label', 'Auto-send eligible replies');
autoSelect.after(autoSwitch);
// Keep the existing settings serializer's true/false values synchronized.
autoSelect.id = 'setting-auto-approve';
autoSwitch.addEventListener('change', () => autoSelect.value = String(autoSwitch.checked));
const autoHelp = document.createElement('p');
autoHelp.className = 'setting-help';
autoHelp.textContent = 'Off: every reply needs approval. On: only low or medium priority questions, follow-ups or information with a safe assessment and at least 85% AI confidence qualify. Confidence is an AI estimate, not a guarantee.';
autoSwitch.after(autoHelp);
const pin = document.getElementById('setting-pin-code');
pin.value = '';
pin.removeAttribute('value');
pin.autocomplete = 'new-password';
pin.placeholder = 'Unchanged';
pin.closest('.setting-group').querySelector('label').textContent = 'New PIN (leave blank to keep current)';
function syncPin() { pin.closest('.setting-group').hidden = !document.getElementById('setting-pin-security').checked; }
document.getElementById('setting-pin-security').addEventListener('change', syncPin);
window.enhanceSettings = async () => {
  syncPin(); autoSwitch.checked = autoSelect.value === 'true';
  try {
    const response = await fetch(`${API}/config`);
    const config = await response.json();
    ['openrouter', 'openai', 'gemini', 'claude'].forEach(provider => {
      const configured = Boolean(config.api_keys_configured?.[provider]);
      const status = document.getElementById(`${provider}-key-status`);
      status.textContent = configured ? '✓ Configured' : 'Not configured';
      status.classList.toggle('configured', configured);
      document.getElementById(`setting-${provider}-key`).value = '';
    });
    await refreshAccountStatus();
  } catch {}
  document.body.style.overflow = 'hidden';
  $settingsCloseBtn.focus();
};
document.addEventListener('keydown', event => {
  const overlay = !$settingsOverlay.classList.contains('hidden') ? $settingsOverlay : !$overlay.classList.contains('hidden') ? $overlay : null;
  if (!overlay) return;
  if (event.key === 'Escape' && overlay === $settingsOverlay) closeSettingsModal();
  if (event.key !== 'Tab') return;
  const elements = [...overlay.querySelectorAll('button, input, select, textarea, [tabindex="0"]')].filter(el => !el.disabled && el.getClientRects().length);
  const first = elements[0], last = elements[elements.length - 1];
  if (event.shiftKey && (document.activeElement === first || !overlay.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && (document.activeElement === last || !overlay.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
});
function startAutoRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(() => { if (!openDraftId && $settingsOverlay.classList.contains('hidden') && !document.querySelector('.draft-card:focus')) refreshAll(); }, AUTO_REFRESH_MS);
}
