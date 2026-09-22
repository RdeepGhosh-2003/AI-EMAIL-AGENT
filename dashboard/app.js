/**
 * app.js — AI Email Agent Dashboard Logic
 * Handles API communication, rendering, search, filter,
 * modal, edit, approve, and reject actions.
 */

const API = `${window.location.origin}/api`;
const AUTO_REFRESH_MS = 30_000;

// ─── State ──────────────────────────────────────────────────────────────
let allDrafts     = [];
let currentFilter = 'pending';
let currentSearch = '';
let overviewFilter = null;
let dateFilterMode = 'single';
let openDraftId   = null;
let editMode      = false;
let refreshTimer  = null;
let actionBusy = false;
let soundEnabled = false;
let audioContext = null;
let savedDashboardTheme = 'dark';
let activityEvents = [];
document.addEventListener('pointerdown', () => {
  if (!soundEnabled) return;
  const Audio = window.AudioContext || window.webkitAudioContext;
  if (Audio) { audioContext ||= new Audio(); audioContext.resume().catch(() => {}); }
});

function setActionBusy(value) {
  actionBusy = value;
  [$btnApprove, $btnReject, $editToggle, $btnSaveEdit, $btnCancelEdit].forEach(button => button.disabled = value);
}

// ─── DOM References ─────────────────────────────────────────────────────
const $draftList    = document.getElementById('draft-list');
const $loadingState = document.getElementById('loading-state');
const $emptyState   = document.getElementById('empty-state');
const $inboxSub     = document.getElementById('inbox-subtitle');
const $searchInput  = document.getElementById('search-input');
const $refreshBtn   = document.getElementById('refresh-btn');
const $refreshBtnTop = document.getElementById('refresh-btn-top');
const $clearDate    = document.getElementById('clear-date');
const $themeToggleBtn = document.getElementById('theme-toggle-btn');
const $activeFilterRow = document.getElementById('active-filter-row');
const $selectAllDrafts = document.getElementById('select-all-drafts');
const $selectAllDraftsInput = document.getElementById('select-all-drafts-input');
const $mailboxAlert = document.getElementById('mailbox-alert');
const $savedViewNote = document.getElementById('saved-view-note');
let vipList = [];

if ($clearDate) {
  $clearDate.addEventListener('click', () => {
    clearDateFilter();
  });
}
if ($refreshBtnTop) {
  $refreshBtnTop.addEventListener('click', async () => {
    $refreshBtnTop.disabled = true;
    await refreshAll();
    $refreshBtnTop.disabled = false;
  });
}

// Email overview
const priorityCountEls = {
  high: document.getElementById('priority-high'),
  medium: document.getElementById('priority-medium'),
  low: document.getElementById('priority-low'),
};
const typeCountEls = {
  banking: document.getElementById('type-banking'),
  customerSupplier: document.getElementById('type-customer-supplier'),
  payments: document.getElementById('type-payments'),
  invoices: document.getElementById('type-invoices'),
  legal: document.getElementById('type-legal'),
  keyContacts: document.getElementById('type-key-contacts'),
};
const globalDraftCountEls = {
  pending: document.getElementById('total-pending'),
  approved: document.getElementById('total-approved'),
  rejected: document.getElementById('total-rejected'),
  deleted: document.getElementById('total-deleted'),
  total: document.getElementById('total-visible'),
};

// Status
const $statusPulse = document.getElementById('status-pulse');
const $statusText  = document.getElementById('status-text');
const $lastUpdated = document.getElementById('last-updated');
const $pageContext = document.getElementById('page-context');

// Modal
const $overlay       = document.getElementById('modal-overlay');
const $modal         = document.getElementById('modal');
const $modalClose    = document.getElementById('modal-close');
const $modalBadges   = document.getElementById('modal-badges');
const $modalSubject  = document.getElementById('modal-subject');
const $modalFrom     = document.getElementById('modal-from');
const $modalOriginal = document.getElementById('modal-original');
const $modalReply    = document.getElementById('modal-ai-reply');
const $modalEditor   = document.getElementById('modal-ai-editor');
const $modalMeta     = document.getElementById('modal-meta');
const $modalFooter   = document.getElementById('modal-footer');
const $editToggle    = document.getElementById('edit-toggle-btn');
const $editorActions = document.getElementById('editor-actions');
const $btnSaveEdit   = document.getElementById('btn-save-edit');
const $btnCancelEdit = document.getElementById('btn-cancel-edit');
const $btnApprove    = document.getElementById('btn-approve');
const $btnReject     = document.getElementById('btn-reject');

// ─── Utilities ──────────────────────────────────────────────────────────

function timeAgo(isoString) {
  if (!isoString) return '—';
  const diff = Date.now() - new Date(isoString).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function formatDateTime(isoString) {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function isDraftSnoozed(draft) {
  if (!draft?.snoozed_until || draft.status !== 'pending') return false;
  const until = new Date(draft.snoozed_until).getTime();
  return Number.isFinite(until) && until > Date.now();
}

function visibleDrafts() {
  return allDrafts.filter(draft => !isDraftSnoozed(draft));
}

function escHtml(str = '') {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Toast Notifications ─────────────────────────────────────────────────

function showToast(msg, type = 'info') {
  if (soundEnabled && audioContext?.state === 'running') {
    const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
    oscillator.frequency.value = type === 'error' ? 260 : 660;
    gain.gain.setValueAtTime(.04, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(.001, audioContext.currentTime + .15);
    oscillator.connect(gain); gain.connect(audioContext.destination);
    oscillator.start(); oscillator.stop(audioContext.currentTime + .15);
  }
  const icons = { success: '✅', error: '❌', info: '💬' };
  const $tc = document.getElementById('toast-container');
  const $t = document.createElement('div');
  $t.className = `toast toast-${type}`;
  $t.innerHTML = `<span>${icons[type]}</span> ${escHtml(msg)}`;
  $tc.appendChild($t);
  setTimeout(() => {
    $t.classList.add('toast-out');
    $t.addEventListener('animationend', () => $t.remove());
  }, 4000);
}

// ─── API Calls ────────────────────────────────────────────────────────────

async function fetchStatus() {
  try {
    const res = await fetch(`${API}/status`);
    if (!res.ok) throw new Error('Status unavailable');
    const data = await res.json();
    const phase = data.worker?.phase || 'not_running';
    const labels = {not_running:'Worker not running', starting:'Worker starting', checking:'Checking mail', idle:'Worker waiting', ai_key_required:'AI key required', ai_error:'AI provider needs attention', connection_error:'Mailbox needs attention'};
    if (phase === 'connection_error' && data.worker?.mailboxes) {
      const failed = Object.entries(data.worker.mailboxes)
        .filter(([, state]) => state && state !== 'connected')
        .map(([mailbox]) => mailbox.charAt(0).toUpperCase() + mailbox.slice(1));
      if (failed.length) labels.connection_error = `${failed.join(', ')} needs attention`;
    }
    $statusPulse.classList.toggle('offline', !data.worker?.alive || ['ai_key_required','ai_error','connection_error'].includes(phase));
    $statusText.textContent = labels[phase] || 'Worker status unavailable';
    if (data.worker?.ai_fallback_provider) {
      $statusText.textContent += ` · using ${data.worker.ai_fallback_provider}`;
    }
    if ($mailboxAlert) {
      const needsAttention = ['ai_key_required', 'ai_error', 'connection_error'].includes(phase);
      $mailboxAlert.classList.toggle('hidden', !needsAttention);
      $mailboxAlert.firstChild.textContent = needsAttention ? `${labels[phase] || 'Mailbox needs attention'} ` : 'Mailbox needs attention ';
    }
    if ($pageContext) {
      $pageContext.textContent = data.ai_configured
        ? 'Saved reply drafts appear here. Check each AI suggestion before sending. Open Mailboxes to read your inbox.'
        : 'Add an AI provider key in Agent Settings to create reply drafts. Open Mailboxes to read your inbox.';
      if (data.demo_hidden) $pageContext.textContent += ` ${data.demo_hidden} demo drafts are excluded from these counts.`;
    }
    renderRetryQueue(data.retry_queue || []);
    updateStats(data);
    $lastUpdated.textContent = `Updated ${formatDateTime(data.timestamp)}`;
  } catch {
    $statusPulse.classList.add('offline');
    $statusText.textContent = 'Disconnected';
  }
}

function renderRetryQueue(queue = []) {
  const title = document.getElementById('retry-queue-title');
  const count = document.getElementById('retry-queue-count');
  const feed = document.getElementById('sidebar-retry-feed');
  if (!title || !count || !feed) return;
  title.style.display = queue.length ? '' : 'none';
  feed.style.display = queue.length ? '' : 'none';
  count.textContent = `${queue.length} pending`;
  feed.innerHTML = queue.slice(0, 6).map(item => `
    <div class="retry-card">
      <div class="retry-card-info">
        <strong>${escHtml(item.subject || 'Auto-send retry')}</strong>
        <span>${escHtml(item.error || 'Waiting to retry')}</span>
      </div>
    </div>
  `).join('');
}

async function fetchDrafts() {
  try {
    $loadingState.classList.remove('hidden');
    $emptyState.classList.add('hidden');

    const res = await fetch(`${API}/drafts`);
    if (!res.ok) throw new Error('Drafts unavailable');
    allDrafts = await res.json();
    const eligible = new Set(visibleDrafts().filter(d => !['approved','deleted'].includes(d.status)).map(d => d.id));
    window.selectedDraftIds?.forEach(id => { if (!eligible.has(id)) window.selectedDraftIds.delete(id); });
    window.updateDeleteSelection?.();
    updateEmailOverview();
    updateGlobalDraftSummary();
    renderDrafts();
  } catch (e) {
    showToast('Could not fetch drafts. Is the server running?', 'error');
  } finally {
    $loadingState.classList.add('hidden');
  }
}

async function refreshAll() {
  await Promise.all([fetchStatus(), fetchDrafts(), fetchActivity()]);
}

// ─── Stats ────────────────────────────────────────────────────────────────

function isVipSender(sender = '', senderName = '') {
  const s = String(sender || '').toLowerCase();
  const n = String(senderName || '').toLowerCase();
  return vipList.some(v => {
    const target = v.trim().toLowerCase();
    if (!target) return false;
    if (target.startsWith('*@')) {
      const domain = target.slice(2);
      return s.endsWith('@' + domain) || s.endsWith('.' + domain);
    }
    return s.includes(target) || n.includes(target);
  });
}

function updateHeaderStats(data = {}) {
  // Weekly inflow and its real per-day distribution.
  const now = Date.now();
  const weekAgo = now - 7 * 86400 * 1000;
  const drafts = visibleDrafts();
  const weeklyDrafts = drafts.filter(d => {
    const created = new Date(d.created_at).getTime();
    return Number.isFinite(created) && created >= weekAgo && created <= now;
  });
  const weeklyCount = weeklyDrafts.length;
  const $statWeekly = document.getElementById('stat-weekly-val');
  if ($statWeekly) $statWeekly.textContent = weeklyCount;
  const dayCounts = Array(7).fill(0);
  weeklyDrafts.forEach(draft => {
    const age = Math.floor((now - new Date(draft.created_at).getTime()) / 86400000);
    if (age >= 0 && age < 7) dayCounts[6 - age] += 1;
  });
  const maxDay = Math.max(...dayCounts, 0);
  document.querySelectorAll('[data-week-bar]').forEach((bar, index) => {
    const height = maxDay ? Math.max(3, Math.round(dayCounts[index] / maxDay * 21)) : 1;
    bar.setAttribute('height', height);
    bar.setAttribute('y', 22 - height);
    bar.style.opacity = dayCounts[index] ? '1' : '.16';
  });

  // Sent total and share of all drafts.
  const sentCount = drafts.filter(d => d.status === 'approved').length;
  const $statSent = document.getElementById('stat-sent-val');
  if ($statSent) $statSent.textContent = sentCount;
  const sentProgress = drafts.length ? Math.round(sentCount / drafts.length * 82) : 0;
  const sentRing = document.getElementById('stat-sent-ring');
  if (sentRing) {
    sentRing.setAttribute('stroke-dasharray', `${sentProgress} 82`);
    sentRing.style.opacity = drafts.length ? '1' : '.18';
  }

  // Average only genuine classifier confidence values; never invent a fallback.
  const confScores = drafts.map(d => d.classification?.confidence ?? d.confidence)
    .filter(value => typeof value === 'number' && Number.isFinite(value))
    .map(value => value <= 1 ? value * 100 : value)
    .filter(value => value >= 0 && value <= 100);
  const avgConf = confScores.length ? Math.round(confScores.reduce((a, b) => a + b, 0) / confScores.length) : null;
  const $statConf = document.getElementById('stat-conf-val');
  if ($statConf) $statConf.textContent = avgConf == null ? '—' : `${avgConf}%`;
  const confRing = document.getElementById('stat-conf-ring');
  if (confRing) {
    confRing.setAttribute('stroke-dasharray', `${avgConf ?? 0} 100`);
    confRing.style.opacity = avgConf == null ? '.18' : '1';
  }

  // Edit rate is defined only when at least one draft has been sent.
  const approvedDrafts = drafts.filter(d => d.status === 'approved');
  const editedCount = approvedDrafts.filter(d => d.edited).length;
  const editRate = approvedDrafts.length ? Math.round((editedCount / approvedDrafts.length) * 100) : null;
  const $statEdits = document.getElementById('stat-edits-val');
  if ($statEdits) $statEdits.textContent = editRate == null ? '—' : `${editRate}%`;
  const editsBar = document.getElementById('stat-edits-bar');
  if (editsBar) {
    editsBar.setAttribute('width', editRate == null ? 0 : editRate * .4);
    editsBar.style.opacity = editRate == null ? '.18' : '1';
  }
}

function renderActivityLog() {
  const $feed = document.getElementById('sidebar-activity-feed');
  if (!$feed) return;
  if (activityEvents.length) {
    $feed.innerHTML = activityEvents.slice(0, 6).map(event => {
      const details = event.details || {};
      const label = activityLabel(event.event);
      const subject = details.subject ? ` · ${escHtml(details.subject)}` : '';
      const platform = details.platform ? ` · ${String(details.platform).toUpperCase()}` : '';
      return `
        <div class="feed-item">
          <span>${activityIcon(event.event)}</span>
          <div>
            <strong>${escHtml(label)}</strong>${subject}
            <div class="feed-time">${timeAgo(event.timestamp)}${platform}</div>
          </div>
        </div>
      `;
    }).join('');
    return;
  }
  const recentItems = [];
  allDrafts.forEach(d => {
    if (d.status === 'approved' && d.approved_at) {
      recentItems.push({ icon: '✅', action: 'Sent reply', who: d.sender_name || d.sender || 'Sender', time: d.approved_at, platform: d.platform });
    } else if (d.created_at) {
      recentItems.push({ icon: '📝', action: 'Draft created', who: d.sender_name || d.sender || 'Sender', time: d.created_at, platform: d.platform });
    }
  });
  recentItems.sort((a, b) => new Date(b.time) - new Date(a.time));
  const topItems = recentItems.slice(0, 4);
  if (!topItems.length) return;
  $feed.innerHTML = topItems.map(item => `
    <div class="feed-item">
      <span>${item.icon}</span>
      <div>
        <strong>${item.action}</strong> · ${escHtml(item.who)}
        <div class="feed-time">${timeAgo(item.time)} · ${item.platform ? item.platform.toUpperCase() : 'Mail'}</div>
      </div>
    </div>
  `).join('');
}

function activityLabel(event = '') {
  return ({
    app_start: 'Agent started',
    app_stop: 'Agent stopped',
    dashboard_login_success: 'Dashboard unlocked',
    dashboard_login_failed: 'PIN rejected',
    email_scan_started: 'Mail scan started',
    email_scan_completed: 'Mail scan completed',
    email_scan_failed: 'Mail scan failed',
    email_classified: 'Email classified',
    draft_generated: 'Draft generated',
    draft_saved: 'Draft saved',
    draft_edited: 'Draft edited',
    draft_approved_sent: 'Reply sent',
    draft_rejected: 'Draft rejected',
    draft_restored: 'Draft restored',
    settings_changed: 'Settings changed',
    mailbox_connection_started: 'Mailbox sign-in started',
    mailbox_connection_completed: 'Mailbox connected',
    mailbox_connection_failed: 'Mailbox sign-in failed',
  })[event] || event.replaceAll('_', ' ');
}

function activityIcon(event = '') {
  if (event.includes('failed') || event.includes('error')) return '!';
  if (event.includes('approved') || event.includes('sent')) return '✓';
  if (event.includes('login')) return '#';
  if (event.includes('scan')) return '↻';
  if (event.includes('settings')) return '*';
  return '•';
}

async function fetchActivity() {
  try {
    const res = await fetch(`${API}/activity?limit=20`);
    if (!res.ok) throw new Error('Activity unavailable');
    const data = await res.json();
    activityEvents = data.events || [];
    renderActivityLog();
  } catch {
    activityEvents = [];
  }
}

function updateStats(data) {
  updateEmailOverview();
  updateGlobalDraftSummary(data);
  updateFilterCounts(data);
  updateHeaderStats(data);
  renderActivityLog();
}

function updateEmailOverview() {
  const emails = visibleDrafts().filter(draft => draft.status !== 'deleted');
  const priorities = { high: 0, medium: 0, low: 0 };
  const types = { banking: 0, customerSupplier: 0, payments: 0, invoices: 0, legal: 0, keyContacts: 0 };

  emails.forEach(draft => {
    priorities[getPriorityGroup(draft)]++;
    const type = getEmailType(draft);
    if (type) types[type]++;
  });

  Object.entries(priorities).forEach(([key, count]) => { priorityCountEls[key].textContent = count; });
  Object.entries(types).forEach(([key, count]) => { typeCountEls[key].textContent = count; });
}

function updateGlobalDraftSummary(data = {}) {
  const counts = { pending: 0, approved: 0, rejected: 0, deleted: 0 };
  visibleDrafts().forEach(draft => {
    const status = draft.status || 'pending';
    counts[status] = (counts[status] || 0) + 1;
  });
  Object.entries(counts).forEach(([key, count]) => {
    if (globalDraftCountEls[key]) globalDraftCountEls[key].textContent = count;
  });
  if (globalDraftCountEls.total) globalDraftCountEls.total.textContent = visibleDrafts().length || data.total || 0;
}

function getPriorityGroup(draft) {
  const priority = (draft.classification?.priority || 'medium').toLowerCase();
  return priority === 'urgent' ? 'high' : ['high', 'medium', 'low'].includes(priority) ? priority : 'medium';
}

function getEmailType(draft) {
  const text = [draft.classification?.category, draft.classification?.summary, draft.subject, draft.sender_name, draft.original_body]
    .filter(Boolean).join(' ').toLowerCase();
  if (/\b(legal|lawyer|attorney|contract|compliance|court|notice|nda|agreement)\b/.test(text)) return 'legal';
  if (/\b(invoice|billing|bill due|purchase order|po number)\b/.test(text)) return 'invoices';
  if (/\b(payment|paid|payable|receivable|refund|transaction|gateway)\b/.test(text)) return 'payments';
  if (/\b(bank|banking|account statement|credit|debit|loan|interest|forex)\b/.test(text)) return 'banking';
  if (/\b(customer|client issue|supplier|vendor|complaint|service issue|support request)\b/.test(text)) return 'customerSupplier';
  if (/\b(ceo|cfo|cto|coo|founder|owner|president|vice president|vp|director|manager|lead|key contact|business partner)\b/.test(text)) return 'keyContacts';
  return null;
}

// ─── Filter & Search ─────────────────────────────────────────────────────

function draftDateKey(draft, statusForDate = draft.status) {
  const relevantTimestamp = statusForDate === 'approved' ? (draft.approved_at || draft.created_at)
    : statusForDate === 'rejected' ? (draft.rejected_at || draft.created_at)
    : statusForDate === 'deleted' ? (draft.deleted_at || draft.created_at) : draft.created_at;
  const created = new Date(relevantTimestamp);
  return `${created.getFullYear()}-${String(created.getMonth() + 1).padStart(2, '0')}-${String(created.getDate()).padStart(2, '0')}`;
}

function todayDateKey() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
}

function matchesSearch(draft) {
  const q = currentSearch.toLowerCase();
  return !q
    || draft.subject?.toLowerCase().includes(q)
    || draft.sender?.toLowerCase().includes(q)
    || draft.sender_name?.toLowerCase().includes(q);
}

function matchesSelectedDate(draft, statusForDate = draft.status) {
  if (!window.dateFilterActive) return true;
  const draftKey = draftDateKey(draft, statusForDate);
  if (dateFilterMode === 'today') return draftKey === todayDateKey();
  if (dateFilterMode === 'range') {
    const from = document.getElementById('filter-date-from')?.value || '';
    const to = document.getElementById('filter-date-to')?.value || '';
    return (!from || draftKey >= from) && (!to || draftKey <= to);
  }
  const selectedDate = document.getElementById('filter-date')?.value || '';
  return !selectedDate || draftKey === selectedDate;
}

function getDateFilterLabel() {
  if (!window.dateFilterActive) return '';
  if (dateFilterMode === 'today') return 'Today';
  if (dateFilterMode === 'range') {
    const from = document.getElementById('filter-date-from')?.value || '';
    const to = document.getElementById('filter-date-to')?.value || '';
    if (from && to) return `${from} to ${to}`;
    return from ? `From ${from}` : to ? `Until ${to}` : 'Date range';
  }
  return document.getElementById('filter-date')?.value || 'Date';
}

function updateDateFilterUi() {
  document.querySelectorAll('.date-mode-btn').forEach(button => {
    button.classList.toggle('active', button.dataset.dateMode === dateFilterMode);
  });
  const singleInput = document.getElementById('filter-date');
  const rangeInputs = document.getElementById('date-range-inputs');
  if (singleInput) singleInput.classList.toggle('hidden', dateFilterMode === 'range');
  if (rangeInputs) rangeInputs.classList.toggle('hidden', dateFilterMode !== 'range');
  const help = document.getElementById('date-filter-help');
  if (help) {
    const statusLabel = ({approved:'sent',rejected:'discarded',deleted:'deleted',snoozed:'snoozed'})[currentFilter] || 'created';
    help.textContent = dateFilterMode === 'today'
      ? `Today's ${statusLabel} drafts`
      : dateFilterMode === 'range'
        ? `Showing drafts ${statusLabel} between these dates`
        : `Showing drafts ${statusLabel} on this date`;
  }
}

function setDateMode(mode) {
  dateFilterMode = mode;
  window.dateFilterActive = true;
  if (mode === 'today') {
    const today = todayDateKey();
    const singleInput = document.getElementById('filter-date');
    if (singleInput) singleInput.value = today;
  }
  updateDateFilterUi();
  renderDrafts();
}

function saveDashboardView() {
  const view = {
    filter: currentFilter,
    overviewFilter,
    search: currentSearch,
    dateFilterMode,
    dateActive: Boolean(window.dateFilterActive),
    date: document.getElementById('filter-date')?.value || '',
    from: document.getElementById('filter-date-from')?.value || '',
    to: document.getElementById('filter-date-to')?.value || '',
    sort: document.getElementById('sort-drafts')?.value || 'priority',
  };
  localStorage.setItem('ai_agent_dashboard_view', JSON.stringify(view));
  if ($savedViewNote) {
    $savedViewNote.classList.remove('hidden');
    clearTimeout(window.savedViewNoteTimer);
    window.savedViewNoteTimer = setTimeout(() => $savedViewNote.classList.add('hidden'), 2200);
  }
}

function restoreDashboardView() {
  try {
    const view = JSON.parse(localStorage.getItem('ai_agent_dashboard_view') || '{}');
    if (!view || typeof view !== 'object') return;
    currentFilter = view.filter || 'pending';
    overviewFilter = view.overviewFilter || null;
    currentSearch = view.search || '';
    dateFilterMode = view.dateFilterMode || 'single';
    window.dateFilterActive = Boolean(view.dateActive);
    if ($searchInput) $searchInput.value = currentSearch;
    const sort = document.getElementById('sort-drafts');
    if (sort && view.sort) sort.value = view.sort;
    const date = document.getElementById('filter-date');
    const from = document.getElementById('filter-date-from');
    const to = document.getElementById('filter-date-to');
    if (date) date.value = view.date || '';
    if (from) from.value = view.from || '';
    if (to) to.value = view.to || '';
  } catch {}
}

function syncFilterUi() {
  document.querySelectorAll('.filter-btn').forEach(button => {
    const active = !overviewFilter && button.dataset.filter === currentFilter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('.overview-filter').forEach(button => {
    const active = overviewFilter && button.dataset.overviewKind === overviewFilter.kind && button.dataset.overviewValue === overviewFilter.value;
    button.classList.toggle('active', Boolean(active));
    button.setAttribute('aria-pressed', String(Boolean(active)));
  });
}

function clearDateFilter() {
  ['filter-date', 'filter-date-from', 'filter-date-to'].forEach(id => {
    const input = document.getElementById(id);
    if (input) input.value = '';
  });
  window.dateFilterActive = false;
  dateFilterMode = 'single';
  updateDateFilterUi();
  renderDrafts();
  saveDashboardView();
}

function updateFilterCounts(data = {}) {
  document.querySelectorAll('.filter-btn .filter-count').forEach(count => {
    const button = count.closest('.filter-btn');
    const filter = button.dataset.filter;
    const drafts = visibleDrafts();
    const value = filter === 'snoozed'
      ? allDrafts.filter(draft => isDraftSnoozed(draft) && matchesSearch(draft) && matchesSelectedDate(draft, 'pending')).length
      : filter === 'all'
      ? drafts.filter(draft => matchesSearch(draft) && matchesSelectedDate(draft)).length
      : drafts.filter(draft => draft.status === filter && matchesSearch(draft) && matchesSelectedDate(draft, filter)).length;
    count.textContent = Number.isFinite(value) ? value : (data[filter] ?? 0);
  });
}

function getFilteredDrafts() {
  const sourceDrafts = currentFilter === 'snoozed' ? allDrafts : visibleDrafts();
  return sourceDrafts.filter(d => {
    const matchFilter = currentFilter === 'snoozed'
      ? d.status === 'pending'
      : overviewFilter ? d.status !== 'deleted' : currentFilter === 'all' || d.status === currentFilter;
    const matchSnoozed = currentFilter === 'snoozed' ? isDraftSnoozed(d) : true;
    const matchOverview = !overviewFilter || (overviewFilter.kind === 'priority'
      ? getPriorityGroup(d) === overviewFilter.value
      : getEmailType(d) === overviewFilter.value);
    return matchFilter && matchSnoozed && matchOverview && matchesSearch(d) && matchesSelectedDate(d);
  });
}

function clearOverviewFilter() {
  overviewFilter = null;
  currentFilter = 'pending';
  document.querySelectorAll('.overview-filter').forEach(button => { button.classList.remove('active'); button.setAttribute('aria-pressed','false'); });
  document.querySelectorAll('.filter-btn').forEach(button => {
    const active = button.dataset.filter === currentFilter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  renderDrafts();
  saveDashboardView();
}

function clearAllFilters() {
  overviewFilter = null;
  currentFilter = 'pending';
  currentSearch = '';
  if ($searchInput) $searchInput.value = '';
  ['filter-date', 'filter-date-from', 'filter-date-to'].forEach(id => {
    const input = document.getElementById(id);
    if (input) input.value = '';
  });
  window.dateFilterActive = false;
  dateFilterMode = 'single';
  document.querySelectorAll('.overview-filter').forEach(button => { button.classList.remove('active'); button.setAttribute('aria-pressed','false'); });
  document.querySelectorAll('.filter-btn').forEach(button => {
    const active = button.dataset.filter === currentFilter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  updateDateFilterUi();
  renderDrafts();
  saveDashboardView();
}

function clearActiveFilter(type) {
  if (type === 'all') return clearAllFilters();
  if (type === 'date') return clearDateFilter();
  if (type === 'search') {
    currentSearch = '';
    if ($searchInput) $searchInput.value = '';
    renderDrafts();
    return saveDashboardView();
  }
  if (type === 'overview') return clearOverviewFilter();
  if (type === 'status') {
    currentFilter = 'pending';
    document.querySelectorAll('.filter-btn').forEach(button => {
      const active = button.dataset.filter === currentFilter;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    renderDrafts();
    return saveDashboardView();
  }
}

function renderActiveFilters(resultCount = 0, totalCount = 0) {
  if (!$activeFilterRow) return;
  const chips = [];
  const statusLabels = { pending: 'Pending', approved: 'Sent', rejected: 'Discarded', deleted: 'Deleted', snoozed: 'Snoozed', all: 'All' };
  if (!overviewFilter && currentFilter !== 'pending') chips.push({ type: 'status', label: statusLabels[currentFilter] || currentFilter });
  if (overviewFilter) {
    const overviewLabels = {
      high: 'High priority', medium: 'Medium priority', low: 'Low priority', banking: 'Banking',
      customerSupplier: 'Customer / supplier issues', payments: 'Payments', invoices: 'Invoices',
      legal: 'Legal matters', keyContacts: 'Key contacts',
    };
    chips.push({ type: 'overview', label: overviewLabels[overviewFilter.value] || overviewFilter.value });
  }
  if (window.dateFilterActive) chips.push({ type: 'date', label: getDateFilterLabel() });
  if (currentSearch) chips.push({ type: 'search', label: `Search: ${currentSearch}` });
  if (!chips.length) {
    $activeFilterRow.classList.remove('hidden');
    $activeFilterRow.innerHTML = `<span class="active-filter-label">Showing</span><span class="result-count-pill">${resultCount} of ${totalCount} drafts</span>`;
    return;
  }
  $activeFilterRow.classList.remove('hidden');
  $activeFilterRow.innerHTML = `
    <span class="active-filter-label">Showing</span>
    <span class="result-count-pill">${resultCount} of ${totalCount} drafts</span>
    <span class="active-filter-label">Active filters</span>
    ${chips.map(chip => `<button type="button" class="active-filter-chip" data-clear-filter="${escHtml(chip.type)}">${escHtml(chip.label)} <span aria-hidden="true">x</span></button>`).join('')}
    <button type="button" class="active-filter-clear" data-clear-filter="all">Clear all</button>
  `;
}

function updateSelectAllControl(drafts) {
  if (!$selectAllDrafts || !$selectAllDraftsInput) return;
  const selectableIds = drafts.filter(draft => !['approved', 'deleted'].includes(draft.status)).map(draft => draft.id);
  $selectAllDrafts.classList.toggle('hidden', selectableIds.length === 0);
  const selectedCount = selectableIds.filter(id => window.selectedDraftIds?.has(id)).length;
  $selectAllDraftsInput.checked = selectableIds.length > 0 && selectedCount === selectableIds.length;
  $selectAllDraftsInput.indeterminate = selectedCount > 0 && selectedCount < selectableIds.length;
}

function setFilter(filter) {
  overviewFilter = null;
  document.querySelectorAll('.overview-filter').forEach(button => { button.classList.remove('active'); button.setAttribute('aria-pressed','false'); });
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filter);
  });
  renderDrafts();
  saveDashboardView();
}

function setOverviewFilter(kind, value) {
  window.selectedDraftIds?.clear();
  window.updateDeleteSelection?.();
  const isSame = overviewFilter?.kind === kind && overviewFilter?.value === value;
  overviewFilter = isSame ? null : { kind, value };
  if (overviewFilter) currentFilter = 'all';
  else currentFilter = 'pending';
  document.querySelectorAll('.filter-btn').forEach(button => { const active = !overviewFilter && button.dataset.filter === currentFilter; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
  document.querySelectorAll('.overview-filter').forEach(button => {
    const active = overviewFilter && button.dataset.overviewKind === overviewFilter.kind && button.dataset.overviewValue === overviewFilter.value;
    button.classList.toggle('active', Boolean(active));
    button.setAttribute('aria-pressed', String(Boolean(active)));
  });
  renderDrafts();
  saveDashboardView();
}

// ─── Rendering ────────────────────────────────────────────────────────────

function makeBadge(label, cls) {
  return `<span class="badge ${cls}">${escHtml(label)}</span>`;
}

function platformBadge(platform) {
  const p = (platform || '').toLowerCase();
  if (p === 'outlook') return makeBadge('📧 Outlook', 'badge-platform-outlook');
  return makeBadge(p, 'badge-category');
}

function priorityBadge(priority) {
  const icons = { urgent: '🔴', high: '🔴', medium: '🟡', low: '🔵' };
  return makeBadge(`${icons[priority] || ''} ${priority}`, `badge-priority-${priority}`);
}

function statusBadge(status) {
  const labels = { pending: '⏳ Pending', approved: '✅ Sent', rejected: '🗑️ Rejected', deleted: '🗃️ Deleted' };
  return makeBadge(labels[status] || status, `badge-status-${status}`);
}

function renderDrafts() {
  updateFilterCounts();
  updateDateFilterUi();
  syncFilterUi();
  const ranks = { urgent: 0, high: 1, medium: 2, low: 3 };
  const order = document.getElementById('sort-drafts')?.value || 'priority';
  const drafts = getFilteredDrafts().sort((a, b) => {
    const timestamp = draft => currentFilter === 'approved' ? (draft.approved_at || draft.created_at) : draft.created_at;
    const date = new Date(timestamp(b)) - new Date(timestamp(a));
    return order === 'oldest' ? -date : order === 'newest' || currentFilter === 'approved' ? date :
      (ranks[a.classification?.priority] ?? 2) - (ranks[b.classification?.priority] ?? 2) || date;
  });

  // Remove existing cards (keep static elements)
  document.querySelectorAll('.draft-card, .date-group-heading').forEach(el => el.remove());

  const total = drafts.length;
  const totalAvailable = currentFilter === 'snoozed' ? allDrafts.filter(isDraftSnoozed).length : visibleDrafts().length;
  renderActiveFilters(total, totalAvailable);
  updateSelectAllControl(drafts);
  const overviewLabels = {
    high: 'High priority', medium: 'Medium priority', low: 'Low priority', banking: 'Banking',
    customerSupplier: 'Customer / supplier issues', payments: 'Payments', invoices: 'Invoices',
    legal: 'Legal matters', keyContacts: 'Key contacts',
  };
  const filterLabels = { pending: 'pending', approved: 'sent', rejected: 'discarded', deleted: 'deleted', snoozed: 'snoozed' };
  const activeLabel = overviewFilter ? overviewLabels[overviewFilter.value] : (filterLabels[currentFilter] || currentFilter);
  $inboxSub.textContent = `${total} draft${total !== 1 ? 's' : ''} · ${activeLabel}`;
  const selectedDate = getDateFilterLabel();
  const dateHelp = document.getElementById('date-filter-help');
  if (selectedDate) $inboxSub.textContent += ` · ${selectedDate}`;
  $emptyState.querySelector('p').textContent = selectedDate || currentSearch
    ? 'No drafts match your filters. Try another date or clear your search.'
    : 'The AI agent will populate drafts as new emails arrive.';

  if (total === 0) {
    $emptyState.classList.remove('hidden');
    return;
  }
  $emptyState.classList.add('hidden');

  let lastSentDate = '';
  drafts.forEach((draft, i) => {
    if (currentFilter === 'approved') {
      const date = new Date(draft.approved_at || draft.created_at);
      const dateKey = date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
      if (dateKey !== lastSentDate) {
        const heading = document.createElement('div');
        heading.className = 'date-group-heading';
        heading.textContent = dateKey;
        $draftList.appendChild(heading);
        lastSentDate = dateKey;
      }
    }
    const card = document.createElement('article');
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `Review ${draft.subject || 'untitled email'}`);
    card.className = [
      'draft-card',
      `priority-${draft.classification?.priority || 'medium'}`,
      `status-${draft.status}`,
    ].join(' ');
    card.style.animationDelay = `${i * 40}ms`;
    card.dataset.id = draft.id;

    const isVip = draft.is_vip || isVipSender(draft.sender, draft.sender_name);
    const hasConflict = Boolean(draft.thread_conflict);
    const confVal = draft.confidence ?? (draft.classification?.auto_reply_safe ? 92 : draft.classification?.priority === 'low' ? 88 : 58);
    const confLevel = confVal >= 85 ? 'high' : confVal >= 60 ? 'med' : 'low';

    const badgesHtml = [
      (draft.platform || '').toLowerCase() === 'outlook' ? '' : platformBadge(draft.platform),
      priorityBadge(draft.classification?.priority || 'medium'),
      statusBadge(draft.status),
      isVip ? '<span class="badge badge-vip">⭐ VIP</span>' : '',
      hasConflict ? '<span class="badge badge-thread-conflict">⚠️ Thread conflict</span>' : '',
      (draft.classification?.classification_failed || draft.classification?.summary?.startsWith('Could not classify')) ? makeBadge('⚠ Classification needs review', 'badge-priority-high') : '',
      draft.classification?.category
        ? makeBadge(draft.classification.category.replace('_', ' '), 'badge-category')
        : '',
      draft.edited ? makeBadge('✏️ edited', 'badge-edited') : '',
      draft.snoozed_until ? '<span class="badge badge-category">💤 Snoozed</span>' : '',
    ].filter(Boolean).join('');

    card.innerHTML = `
      <div class="card-top">
        <div class="card-leading">
          ${!['approved', 'deleted'].includes(draft.status) ? `<input type="checkbox" class="draft-select" aria-label="Select ${escHtml(draft.subject || 'draft')}" ${window.selectedDraftIds?.has(draft.id) ? 'checked' : ''}>` : ''}
          <div class="card-badges">${badgesHtml}</div>
        </div>
        <div class="card-top-actions">
          ${!isDraftSnoozed(draft) && !['approved', 'deleted'].includes(draft.status) ? `
          <div class="snooze-wrapper" onclick="event.stopPropagation()">
            <button type="button" class="snooze-btn" onclick="toggleSnooze('snooze-${draft.id}')">💤 Snooze</button>
            <div class="snooze-popover" id="snooze-${draft.id}">
              <label class="snooze-date-label" for="snooze-date-${draft.id}">Snooze until</label>
              <input type="datetime-local" id="snooze-date-${draft.id}" class="snooze-date-input" aria-label="Snooze date and time" required />
              <small class="snooze-time-hint">Your local date and time</small>
              <div class="snooze-date-actions">
                <button type="button" class="snooze-item" onclick="toggleSnooze('snooze-${draft.id}')">Cancel</button>
                <button type="button" class="snooze-btn" onclick="doSnooze('${draft.id}')">Snooze</button>
              </div>
            </div>
          </div>` : ''}
          ${isDraftSnoozed(draft) ? `<span class="card-undo" data-undo-action="snooze" role="button" tabindex="0">↶ Undo snooze</span>` : ''}
          ${['rejected', 'deleted'].includes(draft.status) ? `<span class="card-undo" data-undo-action="restore" role="button" tabindex="0">↶ ${draft.status === 'deleted' ? 'Undo delete' : 'Undo rejection'}</span>` : ''}
          <span class="review-link">Review reply →</span>
          <span class="card-time">${timeAgo(draft.status === 'approved' ? draft.approved_at : draft.status === 'rejected' ? draft.rejected_at : draft.status === 'deleted' ? draft.deleted_at : draft.created_at)}</span>
        </div>
      </div>
      <div class="card-subject">${escHtml(draft.subject || '(No Subject)')}</div>
      <div class="card-from">From: ${escHtml(draft.sender_name || draft.sender || 'Unknown')}</div>
      <div class="card-preview">
        <span class="preview-label">They need</span>
        ${escHtml(draft.classification?.summary || draft.original_body || '')}
      </div>
      <div class="card-preview">
        <span class="preview-label">AI proposes</span>
        ${escHtml(draft.ai_reply || '')}
      </div>
      <div class="card-confidence-bar">
        <span class="confidence-label-small">AI Confidence: ${confVal}%</span>
        <div class="confidence-track">
          <div class="confidence-fill ${confLevel}" style="width: ${confVal}%"></div>
        </div>
      </div>
    `;

    card.addEventListener('click', event => {
      const nestedControl = event.target.closest('input, button, a, [role="button"]');
      if (!nestedControl || nestedControl === card) openModal(draft.id);
    });
    card.addEventListener('keydown', event => { if ((event.key === 'Enter' || event.key === ' ') && event.target === card) { event.preventDefault(); openModal(draft.id); } });
    const select = card.querySelector('.draft-select');
    if (select) select.addEventListener('change', event => {
      event.stopPropagation();
      if (select.checked) window.selectedDraftIds.add(draft.id); else window.selectedDraftIds.delete(draft.id);
      card.classList.toggle('selected', select.checked);
      window.updateDeleteSelection?.();
    });
    const undo = card.querySelector('.card-undo');
    if (undo) {
      const restore = event => {
        event.stopPropagation();
        if (undo.dataset.undoAction === 'snooze') window.undoSnooze?.(draft);
        else window.restoreDraft?.(draft);
      };
      undo.addEventListener('click', restore);
      undo.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); restore(event); } });
    }
    $draftList.appendChild(card);
  });
}

// ─── Modal ────────────────────────────────────────────────────────────────

function openModal(draftId) {
  if (actionBusy) return;
  const draft = allDrafts.find(d => d.id === draftId);
  if (!draft) return;

  openDraftId = draftId;
  editMode = false;

  const cls = draft.classification || {};

  // Badges
  $modalBadges.innerHTML = [
    platformBadge(draft.platform),
    priorityBadge(cls.priority || 'medium'),
    statusBadge(draft.status),
    (cls.classification_failed || cls.summary?.startsWith('Could not classify')) ? makeBadge('⚠ Classification needs review', 'badge-priority-high') : '',
    cls.category ? makeBadge(cls.category.replace('_', ' '), 'badge-category') : '',
    draft.edited ? makeBadge('✏️ edited', 'badge-edited') : '',
  ].filter(Boolean).join('');

  $modalSubject.textContent = draft.subject || '(No Subject)';
  $modalFrom.textContent = `From: ${draft.sender_name ? draft.sender_name + ' ' : ''}<${draft.sender}>  ·  ${formatDateTime(draft.created_at)}`;

  $modalOriginal.textContent = (draft.original_body_complete === false ? '⚠ This older draft contains only an excerpt. Use Load full original before reviewing.\n\n' : '') + (draft.original_body || '(No body)');
  $modalReply.textContent    = draft.ai_reply || '(No reply generated)';
  $modalEditor.value         = draft.ai_reply || '';

  // Reset editor state
  $modalReply.classList.remove('hidden');
  $modalEditor.classList.add('hidden');
  $editorActions.classList.add('hidden');
  $editToggle.textContent = '✏️ Edit';

  // Compact AI Classification strip
  const priority = (cls.priority || 'medium').toLowerCase();
  const category = (cls.category || 'other').replace('_', ' ');
  const sentiment = (cls.sentiment || 'neutral').toLowerCase();
  const autoSafe = cls.auto_reply_safe ? 'Yes' : 'No';
  const summary = cls.summary || 'No summary available';

  $modalMeta.innerHTML = `
    <div class="meta-strip-summary">
      <span class="meta-strip-tag">💡 AI SUMMARY</span>
      <span class="meta-strip-text">${escHtml(summary)}</span>
    </div>
    <div class="meta-strip-chips">
      <div class="meta-chip-item">
        <span class="chip-label-title">Priority</span>
        <span class="badge badge-priority-${priority}">${escHtml(priority)}</span>
      </div>
      <div class="meta-chip-item">
        <span class="chip-label-title">Category</span>
        <span class="chip-pill pill-category">${escHtml(category)}</span>
      </div>
      <div class="meta-chip-item">
        <span class="chip-label-title">Sentiment</span>
        <span class="chip-pill pill-sentiment">${escHtml(sentiment)}</span>
      </div>
      <div class="meta-chip-item">
        <span class="chip-label-title">Auto-Safe</span>
        <span class="chip-pill pill-autosafe">${autoSafe}</span>
      </div>
    </div>
  `;

  // Header actions state
  $modalFooter.className = 'modal-header-actions';
  // Remove old actioned label if any
  const oldLabel = $modalFooter.querySelector('.actioned-label');
  if (oldLabel) oldLabel.remove();


  if (draft.status === 'approved') {
    $modalFooter.classList.add('actioned');
    const lbl = document.createElement('span');
    lbl.className = 'actioned-label actioned-approved';
    lbl.textContent = '✅ Reply sent';
    $modalFooter.prepend(lbl);
  } else if (draft.status === 'rejected') {
    $modalFooter.classList.add('actioned');
    const lbl = document.createElement('span');
    lbl.className = 'actioned-label actioned-rejected';
    lbl.textContent = '🗑️ Draft rejected';
    $modalFooter.prepend(lbl);
  }

  $overlay.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  window.enhanceReview?.(draft);
}

function closeModal() {
  if (actionBusy) return;
  if (editMode && $modalEditor.value !== allDrafts.find(d => d.id === openDraftId)?.ai_reply && !confirm('Discard your unsaved reply changes?')) return;
  $overlay.classList.add('hidden');
  document.body.style.overflow = '';
  openDraftId = null;
  editMode = false;
  window.restoreReviewFocus?.();
}

// ─── Edit Mode ────────────────────────────────────────────────────────────

$editToggle.addEventListener('click', () => {
  editMode = !editMode;
  if (editMode) {
    $modalReply.classList.add('hidden');
    $modalEditor.classList.remove('hidden');
    $editorActions.classList.remove('hidden');
    $editToggle.textContent = 'Editing';
  } else {
    editMode = true;
    $modalEditor.focus();
  }
});

$btnCancelEdit.addEventListener('click', () => {
  editMode = false;
  const draft = allDrafts.find(d => d.id === openDraftId);
  if (draft) $modalEditor.value = draft.ai_reply;
  $modalReply.classList.remove('hidden');
  $modalEditor.classList.add('hidden');
  $editorActions.classList.add('hidden');
  $editToggle.textContent = '✏️ Edit';
});

$btnSaveEdit.addEventListener('click', async () => {
  if (!openDraftId || actionBusy) return;
  const draftId = openDraftId;
  const newReply = $modalEditor.value.trim();
  if (!newReply) { showToast('Reply cannot be empty', 'error'); return; }

  $btnSaveEdit.textContent = '💾 Saving...';
  $btnSaveEdit.disabled = true;
  setActionBusy(true);

  try {
    const res = await fetch(`${API}/drafts/${draftId}/edit`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai_reply: newReply }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Edit failed');

    // Update local state
    const idx = allDrafts.findIndex(d => d.id === draftId);
    if (idx >= 0) allDrafts[idx] = data.draft;

    $modalReply.textContent = newReply;
    $modalReply.classList.remove('hidden');
    $modalEditor.classList.add('hidden');
    $editorActions.classList.add('hidden');
    $editToggle.textContent = '✏️ Edit';
    editMode = false;

    renderDrafts();
    showToast(data.message || 'Reply saved.', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    setActionBusy(false);
    $btnSaveEdit.textContent = '💾 Save Edit';
    $btnSaveEdit.disabled = false;
  }
});

// ─── Approve ──────────────────────────────────────────────────────────────

$btnApprove.addEventListener('click', async () => {
  if (!openDraftId || actionBusy) return;
  const draftId = openDraftId;
  const draft = allDrafts.find(d => d.id === openDraftId);
  if (!draft || draft.status !== 'pending') return;

  if (editMode) { showToast('Save or cancel your edits before sending.', 'info'); return; }
  const cls = draft.classification || {};
  if ((['urgent', 'high'].includes(cls.priority) || cls.sentiment === 'negative' || !cls.auto_reply_safe)
      && !confirm(`Review required: ${cls.priority || 'unrated'} priority · ${cls.sentiment || 'unrated'} sentiment.\n\nSend this reply to ${draft.sender}?`)) return;

  $btnApprove.classList.add('loading');
  setActionBusy(true);
  $btnApprove.querySelector('span:last-child').textContent = 'Sending...';

  try {
    const res = await fetch(`${API}/drafts/${draftId}/approve`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Approve failed');

    // Update local state
    const idx = allDrafts.findIndex(d => d.id === draftId);
    if (idx >= 0) {
      allDrafts[idx] = data.draft;
    }

    showToast(data.message || 'Reply sent!', 'success');
    setActionBusy(false);
    closeModal();
    renderDrafts();
    fetchStatus();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    setActionBusy(false);
    $btnApprove.classList.remove('loading');
    $btnApprove.querySelector('span:last-child').textContent = 'Send Reply';
  }
});

// ─── Reject ───────────────────────────────────────────────────────────────

$btnReject.addEventListener('click', async () => {
  if (!openDraftId || actionBusy) return;
  const draftId = openDraftId;
  const draft = allDrafts.find(d => d.id === openDraftId);
  if (!draft || draft.status !== 'pending') return;

  if (!confirm(`Reject AI draft for:\n"${draft.subject}"?\n\nThis will delete the draft from ${draft.platform}.`)) return;
  if (editMode) { showToast('Save or cancel edits before discarding.', 'info'); return; }
  setActionBusy(true);

  try {
    const res = await fetch(`${API}/drafts/${draftId}/reject`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Reject failed');

    const idx = allDrafts.findIndex(d => d.id === draftId);
    if (idx >= 0) allDrafts[idx] = data.draft;

    showToast(data.warning || 'Draft discarded', data.warning ? 'info' : 'success');
    setActionBusy(false);
    closeModal();
    renderDrafts();
    fetchStatus();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    setActionBusy(false);
  }
});

// ─── Modal Close ──────────────────────────────────────────────────────────

$modalClose.addEventListener('click', closeModal);
$overlay.addEventListener('click', e => { if (e.target === $overlay) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && openDraftId) closeModal(); });

// ─── Filter Buttons ───────────────────────────────────────────────────────

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => setFilter(btn.dataset.filter));
});
document.querySelectorAll('.overview-filter').forEach(button => {
  button.setAttribute('aria-pressed', 'false');
  button.addEventListener('click', () => setOverviewFilter(button.dataset.overviewKind, button.dataset.overviewValue));
});
document.querySelectorAll('.date-mode-btn').forEach(button => {
  button.addEventListener('click', () => {
    setDateMode(button.dataset.dateMode);
    saveDashboardView();
  });
});
['filter-date', 'filter-date-from', 'filter-date-to'].forEach(id => {
  const input = document.getElementById(id);
  if (!input) return;
  input.addEventListener('change', () => {
    window.dateFilterActive = Boolean(input.value) || dateFilterMode === 'today';
    if (id === 'filter-date' && input.value) dateFilterMode = 'single';
    if ((id === 'filter-date-from' || id === 'filter-date-to') && input.value) dateFilterMode = 'range';
    updateDateFilterUi();
    renderDrafts();
    saveDashboardView();
  });
});
if ($activeFilterRow) {
  $activeFilterRow.addEventListener('click', event => {
    const button = event.target.closest('[data-clear-filter]');
    if (!button) return;
    clearActiveFilter(button.dataset.clearFilter);
    saveDashboardView();
  });
}
if ($selectAllDraftsInput) {
  $selectAllDraftsInput.addEventListener('change', () => {
    const visibleDrafts = getFilteredDrafts().filter(draft => !['approved', 'deleted'].includes(draft.status));
    visibleDrafts.forEach(draft => {
      if ($selectAllDraftsInput.checked) window.selectedDraftIds.add(draft.id);
      else window.selectedDraftIds.delete(draft.id);
    });
    window.updateDeleteSelection?.();
    renderDrafts();
  });
}
if ($mailboxAlert) {
  $mailboxAlert.addEventListener('click', () => {
    window.location.href = 'inbox.html';
  });
}

// ─── Search ───────────────────────────────────────────────────────────────

$searchInput.addEventListener('input', e => {
  currentSearch = e.target.value;
  renderDrafts();
  saveDashboardView();
});

// ─── Refresh Button ───────────────────────────────────────────────────────

$refreshBtn.addEventListener('click', async () => {
  $refreshBtn.disabled = true;
  $refreshBtn.textContent = '↻ Refreshing...';
  await refreshAll();
  $refreshBtn.disabled = false;
  $refreshBtn.innerHTML = '<span>↻</span> Refresh';
});

// ─── Settings Modal & Theme Controls ────────────────────────────────────
const $settingsOverlay  = document.getElementById('settings-overlay');
const $settingsOpenBtn  = document.getElementById('settings-open-btn');
const $settingsCloseBtn = document.getElementById('settings-close-btn');
const $settingsForm     = document.getElementById('settings-form');

let activeDashboardTheme = 'dark';
function selectDashboardTheme(theme) {
  activeDashboardTheme = theme;
  document.querySelectorAll('.theme-option').forEach(el => {
    el.classList.toggle('active', el.dataset.theme === theme);
  });
  applyThemeStyles(theme);
}

function applyThemeStyles(theme) {
  const themes = {
    dark:    ['#6366f1', '#0b0f19', '#111827'],
    cyan:    ['#00e5ff', '#06090e', '#0e1622'],
    amber:   ['#ffb300', '#0d0a04', '#181308'],
    emerald: ['#10b981', '#040d07', '#0a1a10'],
    blue:    ['#3b82f6', '#050b16', '#0d1729'],
    violet:  ['#8b5cf6', '#0b0715', '#171126'],
    purple:  ['#a855f7', '#0d0615', '#1a0f26'],
    fuchsia: ['#d946ef', '#110512', '#210d24'],
    pink:    ['#ec4899', '#12060d', '#230f1b'],
    rose:    ['#f43f5e', '#140608', '#260f15'],
    red:     ['#ef4444', '#140606', '#260f0f'],
    orange:  ['#f97316', '#130904', '#241409'],
    yellow:  ['#eab308', '#100d03', '#211b08'],
    lime:    ['#84cc16', '#090e03', '#152008'],
    green:   ['#22c55e', '#040f08', '#0a2012'],
    teal:    ['#14b8a6', '#030f0e', '#09201d'],
    sky:     ['#0ea5e9', '#040d13', '#0a1c27'],
    slate:   ['#94a3b8', '#090c11', '#151a22'],
    copper:  ['#c26d3b', '#110906', '#21140e'],
    gold:    ['#d4af37', '#100d04', '#201b0a']
  };
  const [accent, deep, surface] = themes[theme] || themes.dark;
  document.documentElement.style.setProperty('--accent', accent);
  document.documentElement.style.setProperty('--bg-deep', deep);
  document.documentElement.style.setProperty('--bg-surface', surface);
}

async function openSettingsModal() {
  try {
    const res = await fetch(`${API}/config`);
    if (!res.ok) throw new Error('Could not load settings');
    const cfg = await res.json();
    if (cfg) {
      document.getElementById('setting-ai-model').value = cfg.ai?.model || 'openai';
      document.getElementById('setting-openrouter-model').value = cfg.ai?.openrouter_model || 'google/gemini-2.5-flash';
      document.getElementById('setting-tone').value = cfg.user_style?.tone || 'professional';
      document.getElementById('setting-instructions').value = cfg.user_style?.instructions || '';
      document.getElementById('setting-interval').value = cfg.agent?.check_interval_seconds || 120;
      document.getElementById('setting-auto-approve').value = cfg.agent?.auto_approve ? 'true' : 'false';
      document.getElementById('setting-sound-fx').checked = cfg.agent?.sound_fx !== false;
      document.getElementById('setting-pin-security').checked = Boolean(cfg.agent?.pin_security);
      document.getElementById('setting-pin-code').value = '';
      document.getElementById('setting-outlook').checked = cfg.platforms?.outlook !== false;

      if (cfg.agent?.vip_contacts) {
        vipList = Array.isArray(cfg.agent.vip_contacts) ? cfg.agent.vip_contacts : String(cfg.agent.vip_contacts).split(',').map(s => s.trim()).filter(Boolean);
        const vipEl = document.getElementById('setting-vip-contacts');
        if (vipEl) vipEl.value = vipList.join(', ');
      }

      if (cfg.agent?.theme) {
        savedDashboardTheme = cfg.agent.theme;
        selectDashboardTheme(cfg.agent.theme);
      }
    }
  } catch (e) { showToast(e.message, 'error'); return; }

  $settingsOverlay.classList.remove('hidden');
  window.enhanceSettings?.();
}

function closeSettingsModal() {
  selectDashboardTheme(savedDashboardTheme);
  $settingsOverlay.classList.add('hidden');
  document.body.style.overflow = '';
  $settingsOpenBtn.focus();
}

if ($settingsOpenBtn) $settingsOpenBtn.addEventListener('click', openSettingsModal);
if ($settingsCloseBtn) $settingsCloseBtn.addEventListener('click', closeSettingsModal);

if ($settingsForm) {
  $settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btnSave = document.getElementById('btn-save-settings');
    btnSave.textContent = '💾 Saving...';
    btnSave.disabled = true;

    const vipInput = document.getElementById('setting-vip-contacts');
    const parsedVips = vipInput ? vipInput.value.split(',').map(s => s.trim()).filter(Boolean) : [];

    const payload = {
      ai: {
        model: document.getElementById('setting-ai-model').value,
        openrouter_model: document.getElementById('setting-openrouter-model').value.trim()
      },
      user_style: {
        tone: document.getElementById('setting-tone').value,
        instructions: document.getElementById('setting-instructions').value
      },
      agent: {
        check_interval_seconds: parseInt(document.getElementById('setting-interval').value) || 120,
        auto_approve: document.getElementById('setting-auto-approve').value === 'true',
        sound_fx: document.getElementById('setting-sound-fx').checked,
        pin_security: document.getElementById('setting-pin-security').checked,
        pin_code: document.getElementById('setting-pin-code').value,
        theme: activeDashboardTheme,
        vip_contacts: parsedVips
      },
      platforms: {
        outlook: document.getElementById('setting-outlook').checked
      },
      api_keys: {
        openrouter: document.getElementById('setting-openrouter-key')?.value.trim() || '',
        openai: document.getElementById('setting-openai-key')?.value.trim() || '',
        gemini: document.getElementById('setting-gemini-key')?.value.trim() || '',
        claude: document.getElementById('setting-claude-key')?.value.trim() || ''
      }
    };

    if (!payload.agent.pin_code) delete payload.agent.pin_code;

    try {
      const res = await fetch(`${API}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Save failed');
      savedDashboardTheme = payload.agent.theme;
      soundEnabled = payload.agent.sound_fx;
      vipList = parsedVips;
      showToast('Agent Settings updated & saved! ⚙️', 'success');
      closeSettingsModal();
      renderDrafts();
      fetchStatus();
    } catch(err) {
      showToast(err.message, 'error');
    } finally {
      btnSave.textContent = '💾 Save Settings';
      btnSave.disabled = false;
    }
  });
}

// ─── Dark / Light Theme Mode ──────────────────────────────────────────────
let isLightTheme = localStorage.getItem('ai_agent_theme_mode') === 'light';
function applyThemeMode(light) {
  isLightTheme = light;
  document.body.classList.toggle('light-theme', light);
  const icon = document.getElementById('theme-toggle-icon');
  const text = document.getElementById('theme-toggle-text');
  if (icon) icon.textContent = light ? '☀️' : '🌙';
  if (text) text.textContent = light ? 'Light' : 'Dark';
  localStorage.setItem('ai_agent_theme_mode', light ? 'light' : 'dark');
}

function toggleThemeMode() {
  applyThemeMode(!isLightTheme);
  showToast(isLightTheme ? 'Switched to Light theme' : 'Switched to Dark theme', 'info');
}

if ($themeToggleBtn) {
  $themeToggleBtn.addEventListener('click', toggleThemeMode);
}

// ─── Snooze Popover ───────────────────────────────────────────────────────
function toggleSnooze(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const isVisible = el.classList.contains('open');
  document.querySelectorAll('.snooze-popover').forEach(d => d.classList.remove('open'));
  if (!isVisible) {
    const input = el.querySelector('input[type="datetime-local"]');
    const localValue = date => {
      const pad = value => String(value).padStart(2, '0');
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    };
    input.min = localValue(new Date(Math.ceil((Date.now() + 1) / 60000) * 60000));
    if (!input.value) input.value = localValue(new Date(Date.now() + 60 * 60000));
    input.setCustomValidity('');
    el.classList.add('open');
    input.focus();
  }
}

async function doSnooze(draftId) {
  const input = document.getElementById(`snooze-date-${draftId}`);
  if (!input) return;
  input.setCustomValidity('');
  const chosen = new Date(input.value);
  if (!input.value || !Number.isFinite(chosen.getTime()) || chosen.getTime() <= Date.now()) {
    input.setCustomValidity('Choose a date and time in the future.');
  }
  if (!input.reportValidity()) return;
  const draft = allDrafts.find(d => d.id === draftId);
  if (!draft) return;
  const until = chosen.toISOString();
  try {
    const res = await fetch(`${API}/drafts/${draftId}/snooze`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snoozed_until: until })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not snooze draft');
    const idx = allDrafts.findIndex(d => d.id === draftId);
    if (idx >= 0) allDrafts[idx] = data.draft;
    window.selectedDraftIds?.delete(draftId);
    window.updateDeleteSelection?.();
    showToast(`Draft snoozed until ${formatDateTime(data.draft.snoozed_until)}`, 'info');
    updateEmailOverview();
    updateGlobalDraftSummary();
    renderDrafts();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

window.toggleSnooze = toggleSnooze;
window.doSnooze = doSnooze;

async function undoSnooze(draft) {
  if (!draft?.id || actionBusy) return;
  setActionBusy(true);
  try {
    const res = await fetch(`${API}/drafts/${encodeURIComponent(draft.id)}/snooze`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not undo snooze');
    const idx = allDrafts.findIndex(item => item.id === draft.id);
    if (idx >= 0) allDrafts[idx] = data.draft;
    if (openDraftId === draft.id) closeModal();
    if (currentFilter === 'snoozed') setFilter('pending');
    else renderDrafts();
    fetchStatus();
    showToast('Snoozed draft restored to Pending', 'success');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    setActionBusy(false);
  }
}

window.undoSnooze = undoSnooze;

document.addEventListener('click', e => {
  if (!e.target.closest('.snooze-wrapper')) {
    document.querySelectorAll('.snooze-popover').forEach(d => d.classList.remove('open'));
  }
});

// ─── Stop Agent Action ───────────────────────────────────────────────────

const $stopAgentBtn = document.getElementById('stop-agent-btn');
if ($stopAgentBtn) {
  $stopAgentBtn.addEventListener('click', async () => {
    if (confirm('Are you sure you want to stop the AI Email Agent completely?')) {
      $stopAgentBtn.disabled = true;
      $stopAgentBtn.innerHTML = '<span>⏳</span> Stopping...';

      // Send shutdown request
      try {
        const response = await fetch(`${API}/stop`, { method: 'POST' });
        if (!response.ok) throw new Error('Stop request failed');
        clearInterval(refreshTimer);
      } catch (e) {
        $stopAgentBtn.disabled = false;
        $stopAgentBtn.innerHTML = '<span>🛑</span> Stop Agent';
        showToast('Could not confirm shutdown. The agent may still be running.', 'error');
        return;
      }

      // Show closing screen
      document.body.innerHTML = `
        <div style="height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #080c14; color: #f1f5f9; font-family: 'Inter', sans-serif; text-align: center; padding: 20px;">
          <div style="font-size: 64px; margin-bottom: 16px;">🛑</div>
          <h1 style="font-size: 28px; font-weight: 700; margin-bottom: 8px;">Shutdown requested</h1>
          <p style="color: #94a3b8; font-size: 16px; margin-bottom: 24px;">The server accepted the shutdown request. Reopen the launcher to start it again.</p>
        </div>
      `;

      // Attempt auto tab closure
      setTimeout(() => {
        try {
          window.open('', '_self', '');
          window.close();
          self.close();
        } catch (e) {}
      }, 400);
    }
  });
}

const $logoutBtn = document.getElementById('logout-btn');
if ($logoutBtn) {
  $logoutBtn.addEventListener('click', () => {
    if (window.logoutDashboard) window.logoutDashboard();
  });
}

function updateCompactLayoutMode() {
  const row = document.querySelector('.controls-unified-row');
  const main = document.querySelector('.main');
  const mainOverflowing = main ? main.scrollWidth > main.clientWidth + 2 : false;
  const crampedViewport = window.innerWidth <= 1120;
  document.body.classList.toggle('zoom-compact', crampedViewport || mainOverflowing);
}

window.addEventListener('resize', updateCompactLayoutMode);
window.visualViewport?.addEventListener('resize', updateCompactLayoutMode);
setTimeout(updateCompactLayoutMode, 0);
setTimeout(updateCompactLayoutMode, 250);

// ─── Init ─────────────────────────────────────────────────────────────────

(async function init() {
  try {
    const response = await fetch(`${API}/config`);
    if (!response.ok) throw new Error('Settings unavailable');
    const config = await response.json();
    savedDashboardTheme = config.agent?.theme || 'dark';
    selectDashboardTheme(savedDashboardTheme);
    soundEnabled = config.agent?.sound_fx !== false;
    if (config.agent?.vip_contacts) {
      vipList = Array.isArray(config.agent.vip_contacts) ? config.agent.vip_contacts : String(config.agent.vip_contacts).split(',').map(s => s.trim()).filter(Boolean);
    }
  } catch(error) { showToast(error.message, 'error'); }
  applyThemeMode(localStorage.getItem('ai_agent_theme_mode') === 'light');
  restoreDashboardView();
  await refreshAll();
  if (typeof startAutoRefresh === 'function') startAutoRefresh();
})();
