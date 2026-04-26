/* ── IIT Hyderabad — SPA Logic ──────────────────────────────────────── */

const API = '';
let token = null;
let role = null;
let studentDid = null;
const adminState = {
  students: [],
  studentQuery: '',
  studentFilter: 'all',
  issued: [],
  issuedQuery: '',
  issuedFilterType: 'all',
  issuedFilterStatus: 'all',
  activity: [],
  issuerDoc: null,
  issuerExpanded: false,
  screen: 'composer',
  menuOpen: false,
  hideKpi: true,
  hideFilters: false,
};
const studentState = {
  credentials: [],
  screen: 'credentials',
  menuOpen: false,
  hideSummary: false,
  credentialFilter: 'pending',
  credentialSearch: '',
  claimedExpanded: false,
};
const verifierState = {
  screen: 'verify',
  menuOpen: false,
  showLegacy: false,
  targetMode: 'open',
  countdownInterval: null,
};

/* ── Helpers ───────────────────────────────────────────────────────────── */

async function api(method, path, body = null, auth = true) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (auth && token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API}${path}`, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function showView(id) {
  document.querySelectorAll('.app-container > .view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function toast(msg, type = 'info') {
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${msg}`;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
}

function fillLogin(u, p) {
  document.getElementById('login-username').value = u;
  document.getElementById('login-password').value = p;
}

function parseJwt(t) {
  try {
    return JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
  } catch { return {}; }
}

/* ── Auth tabs ────────────────────────────────────────────────────────── */

function switchAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('tab-login').classList.toggle('active', isLogin);
  document.getElementById('tab-register').classList.toggle('active', !isLogin);
  document.getElementById('tab-login').setAttribute('aria-selected', isLogin);
  document.getElementById('tab-register').setAttribute('aria-selected', !isLogin);
  document.getElementById('auth-login').style.display = isLogin ? 'block' : 'none';
  document.getElementById('auth-register').style.display = isLogin ? 'none' : 'block';
  const pill = document.getElementById('auth-toggle-pill');
  if (pill) pill.classList.toggle('at-register', !isLogin);
  const title = document.getElementById('login-card-title');
  if (title) title.textContent = isLogin ? 'Welcome back' : 'Create account';
}

function updatePasswordStrength(val) {
  const bar = document.getElementById('pw-strength-bar');
  if (!bar) return;
  let score = 0;
  if (val.length >= 6) score++;
  if (val.length >= 10) score++;
  if (/[A-Z]/.test(val)) score++;
  if (/[0-9]/.test(val)) score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;
  const widths  = ['0%', '20%', '40%', '65%', '85%', '100%'];
  const colors  = ['#E07B4F', '#E07B4F', '#F59E0B', '#10B981', '#1B4D3E', '#1B4D3E'];
  bar.style.width = widths[score];
  bar.style.backgroundColor = colors[score];
}

function selectRole(r) {
  document.querySelectorAll('.role-card').forEach(c => c.classList.toggle('active', c.dataset.role === r));
  document.getElementById('reg-role').value = r;
  updateRegFormLabels();
}

function togglePassword(inputId, btn) {
  const inp = document.getElementById(inputId);
  const isHidden = inp.type === 'password';
  inp.type = isHidden ? 'text' : 'password';
  btn.querySelector('.eye-icon').style.display = isHidden ? 'none' : '';
  btn.querySelector('.eye-off-icon').style.display = isHidden ? '' : 'none';
}

function setButtonLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.querySelector('.btn-label').style.display = loading ? 'none' : '';
  btn.querySelector('.btn-spinner').style.display = loading ? '' : 'none';
}

/* ── Auth: Login + Register ───────────────────────────────────────────── */

async function login() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value.trim();
  if (!username || !password) return toast('Enter both fields', 'error');

  setButtonLoading('btn-login', true);
  try {
    const data = await api('POST', '/auth/login', { username, password }, false);
    token = data.access_token;
    const payload = parseJwt(token);
    role = payload.role;

    localStorage.setItem('token', token);
    localStorage.setItem('role', role);
    localStorage.setItem('username', username);

    toast(`Welcome, ${username}!`, 'success');
    routeToView(username);
  } catch (e) {
    toast(e.message, 'error');
    setButtonLoading('btn-login', false);
  }
}

function updateRegFormLabels() {
  const r = document.getElementById('reg-role').value;
  const label = document.getElementById('reg-roll-label');
  label.textContent = r === 'student' ? 'Roll Number' : 'Username';
}

async function register() {
  const selectedRole = document.getElementById('reg-role').value;
  const rollNumber = document.getElementById('reg-roll').value.trim();
  const fullName = document.getElementById('reg-name').value.trim();
  const password = document.getElementById('reg-password').value.trim();

  if (!rollNumber || !fullName || !password) return toast('Fill all fields', 'error');
  if (password.length < 6) return toast('Password must be at least 6 characters', 'error');

  setButtonLoading('btn-register', true);
  try {
    const data = await api('POST', '/auth/register', {
      roll_number: rollNumber,
      password: password,
      full_name: fullName,
      role: selectedRole,
    }, false);

    toast(`${data.message} — ${data.username}`, 'success');
    switchAuthTab('login');
    document.getElementById('login-username').value = rollNumber;
    document.getElementById('login-password').value = password;
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    setButtonLoading('btn-register', false);
  }
}

function routeToView(username) {
  closeAdminMenu();
  closeStudentMenu();
  closeVerifierMenu();
  if (role === 'student') {
    updateStudentIdentity(username);
    showView('view-student');
    setStudentScreen('credentials');
    loadStudentData();
  } else if (role === 'admin') {
    updateAdminIdentity(username);
    showView('view-admin');
    updateAdminFields();
    setAdminScreen('composer');
    refreshAdminDashboard();
  } else if (role === 'verifier') {
    updateVerifierIdentity(username);
    showView('view-verifier');
    setVerifierScreen('verify');
    loadVerifierStudents();
    loadVwRecentSessions();
  }
}

function updateVerifierIdentity(usernameFallback = '') {
  const payload = token ? parseJwt(token) : {};
  const name = payload.full_name || localStorage.getItem('verifierFullName') || payload.username || usernameFallback || 'Verifier';
  const el = document.getElementById('vw-verifier-name');
  if (el) el.textContent = name;
}

function setVerifierTargetMode(mode) {
  verifierState.targetMode = mode;
  const studentRow = document.getElementById('vw-targeted-row');
  if (studentRow) studentRow.style.display = mode === 'targeted' ? '' : 'none';
  document.querySelectorAll('.vw-mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === `vw-mode-${mode}`);
  });
}

function startVerifierCountdown(seconds) {
  if (verifierState.countdownInterval) clearInterval(verifierState.countdownInterval);
  let remaining = seconds;
  const el = document.getElementById('vw-countdown');
  const update = () => {
    if (!el) return;
    if (remaining <= 0) {
      el.textContent = 'Expired';
      clearInterval(verifierState.countdownInterval);
      verifierState.countdownInterval = null;
      return;
    }
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
    remaining--;
  };
  update();
  verifierState.countdownInterval = setInterval(update, 1000);
}

async function loadVwRecentSessions() {
  try {
    const sessions = await api('GET', '/verifier/sessions');
    const host = document.getElementById('vw-recent-sessions-list');
    if (!host) return;
    const recent = sessions.slice(0, 6);
    if (!recent.length) {
      host.innerHTML = '<div class="vw-recent-empty">No sessions yet</div>';
      return;
    }
    host.innerHTML = recent.map(s => {
      const statusKey = (s.status || '').toLowerCase();
      return `
        <div class="vw-recent-row">
          <div class="vw-recent-row__info">
            <div class="vw-recent-row__name">${s.student_name || '—'}</div>
            <div class="vw-recent-row__type">${(s.vc_type || s.summary || '').replace('Credential', '').trim()}</div>
          </div>
          <div class="vw-recent-row__meta">
            <div class="vw-recent-row__time">${s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}</div>
            <span class="vw-recent-row__badge vw-recent-row__badge--${statusKey}">${s.status || '?'}</span>
          </div>
        </div>`;
    }).join('');
  } catch (_) {}
}

function updateAdminIdentity(usernameFallback = '') {
  const payload = token ? parseJwt(token) : {};
  const name = payload.full_name || localStorage.getItem('adminFullName') || payload.username || usernameFallback || 'Admin';
  const el = document.getElementById('admin-full-name');
  if (el) el.textContent = name;
}

function setAdminCredType(type) {
  const sel = document.getElementById('admin-vc-type');
  if (sel) { sel.value = type; }
  document.querySelectorAll('#aw-cred-type-tabs .aw-cred-type-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.type === type);
  });
  updateAdminFields();
}

function updateAdminStepState() {
  const studentSelected = !!document.getElementById('admin-student-did')?.value;
  const qrVisible = document.getElementById('qr-container')?.style.display !== 'none';
  const s1 = document.getElementById('aw-step-1');
  const s2 = document.getElementById('aw-step-2');
  const s3 = document.getElementById('aw-step-3');
  if (s1) s1.classList.toggle('aw-stepper__item--done', studentSelected);
  if (s2) {
    s2.classList.toggle('aw-stepper__item--active', studentSelected);
    s2.classList.toggle('aw-stepper__item--done', qrVisible);
  }
  if (s3) s3.classList.toggle('aw-stepper__item--active', qrVisible);
}

function updateAdminPreview() {
  const host = document.getElementById('admin-preview-card');
  if (!host) return;

  const type = document.getElementById('admin-vc-type')?.value || 'UniversityDegreeCredential';
  const studentSelect = document.getElementById('admin-student-did');
  const studentLabel = studentSelect?.selectedIndex > 0
    ? (studentSelect.options[studentSelect.selectedIndex]?.textContent || '').split('—').pop()?.trim()
    : null;

  const TYPE_COLORS = {
    UniversityDegreeCredential: '#1A237E',
    InternshipCredential: '#064e3b',
    SkillBadgeCredential: '#92400e',
  };
  const TYPE_LABELS = {
    UniversityDegreeCredential: 'University Degree',
    InternshipCredential: 'Internship Certificate',
    SkillBadgeCredential: 'Skill Badge',
  };

  const color = TYPE_COLORS[type] || '#1A237E';
  const typeLabel = TYPE_LABELS[type] || type;
  const fields = [];

  if (type === 'UniversityDegreeCredential') {
    const degree = document.getElementById('admin-degree')?.value;
    const branch = document.getElementById('admin-branch')?.value;
    const cgpa = document.getElementById('admin-cgpa')?.value;
    const year = document.getElementById('admin-year')?.value;
    const spec = document.getElementById('admin-specialization')?.value;
    const honours = document.getElementById('admin-honours')?.value;
    if (degree) fields.push(['Degree', degree]);
    if (branch) fields.push(['Branch', branch]);
    if (spec) fields.push(['Specialization', spec]);
    if (cgpa) fields.push(['CGPA', cgpa]);
    if (year) fields.push(['Year', year]);
    if (honours) fields.push(['Honours', honours]);
  } else if (type === 'InternshipCredential') {
    const company = document.getElementById('admin-company')?.value;
    const roleVal = document.getElementById('admin-role')?.value;
    const duration = document.getElementById('admin-duration')?.value;
    if (company) fields.push(['Company', company]);
    if (roleVal) fields.push(['Role', roleVal]);
    if (duration) fields.push(['Duration', duration]);
  } else {
    const skill = document.getElementById('admin-skill')?.value;
    const prof = document.getElementById('admin-proficiency')?.value;
    if (skill) fields.push(['Skill', skill]);
    if (prof) fields.push(['Level', prof]);
  }

  if (!studentLabel && !fields.length) {
    host.innerHTML = `
      <div class="aw-preview-empty">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#9CA3AF; margin-bottom:0.5rem;"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="12" y2="16"/></svg>
        <div class="aw-preview-empty__text">Fill in the form to see a live preview</div>
      </div>`;
    return;
  }

  const fieldRows = fields.map(([k, v]) => `
    <div class="aw-cred-mock__field">
      <div class="aw-cred-mock__field-label">${k}</div>
      <div class="aw-cred-mock__field-value">${v}</div>
    </div>`).join('');

  host.innerHTML = `
    <div class="aw-cred-mock">
      <div class="aw-cred-mock__header" style="background:${color};">
        <div class="aw-cred-mock__header-badge">IIT Hyderabad</div>
        <div class="aw-cred-mock__header-type">${typeLabel}</div>
        ${studentLabel ? `<div class="aw-cred-mock__header-name">${studentLabel}</div>` : ''}
      </div>
      <div class="aw-cred-mock__body">
        ${fieldRows || '<div style="grid-column:1/-1;padding:1rem;text-align:center;color:#9CA3AF;font-size:0.75rem;">Fill in credential fields</div>'}
      </div>
      <div class="aw-cred-mock__footer">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        IIT Hyderabad · W3C VC 2.0
      </div>
    </div>`;
}

function updateStudentIdentity(usernameFallback = '') {
  const payload = token ? parseJwt(token) : {};
  const roll = payload.student_id || payload.username || usernameFallback || 'Student';
  const fullName = payload.full_name || localStorage.getItem('studentFullName') || roll;
  const nameEl = document.getElementById('student-full-name');
  const rollEl = document.getElementById('student-name');
  if (nameEl) nameEl.textContent = fullName;
  if (rollEl) rollEl.textContent = roll;
}

function logout() {
  if (verifierPollingInterval) {
    clearInterval(verifierPollingInterval);
    verifierPollingInterval = null;
  }

  token = null;
  role = null;
  studentDid = null;
  resetAdminState();
  resetStudentState();
  resetVerifierState();
  localStorage.clear();
  showView('view-login');
  switchAuthTab('login');
  setButtonLoading('btn-login', false);
  setButtonLoading('btn-register', false);
  toast('Signed out', 'info');
}

/* ── Student: Tabs ────────────────────────────────────────────────────── */

function switchStudentTab(tab) {
  setStudentScreen(tab);
}

function resetStudentState() {
  studentState.credentials = [];
  studentState.screen = 'credentials';
  studentState.menuOpen = false;
  studentState.hideSummary = false;
  studentState.credentialFilter = 'pending';
  studentState.credentialSearch = '';
  studentState.claimedExpanded = false;
  setStudentMenuOpen(false);
}

function setStudentMenuOpen(open) {
  studentState.menuOpen = !!open;
  const overlay = document.getElementById('student-menu-overlay');
  const drawer = document.getElementById('student-menu-drawer');
  if (overlay) overlay.classList.toggle('open', studentState.menuOpen);
  if (drawer) {
    drawer.classList.toggle('open', studentState.menuOpen);
    drawer.setAttribute('aria-hidden', studentState.menuOpen ? 'false' : 'true');
  }
  document.body.classList.toggle('student-no-scroll', studentState.menuOpen);
}

function toggleStudentMenu() {
  setStudentMenuOpen(!studentState.menuOpen);
}

function closeStudentMenu() {
  setStudentMenuOpen(false);
}

function applyStudentVisibility() {
  const setHidden = (id, hidden) => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.toggle('student-hidden', !!hidden);
      el.classList.toggle('active', !hidden);
    }
  };

  const map = {
    overview: { credentials: true, challenges: true, identity: true, history: true },
    credentials: { credentials: true, challenges: false, identity: false, history: false },
    challenges: { credentials: false, challenges: true, identity: false, history: false },
    identity: { credentials: false, challenges: false, identity: true, history: false },
    history: { credentials: false, challenges: false, identity: false, history: true },
  };
  const view = map[studentState.screen] || map.credentials;

  setHidden('student-summary-strip', studentState.hideSummary);
  setHidden('student-tab-credentials', !view.credentials);
  setHidden('student-tab-challenges', !view.challenges);
  setHidden('student-tab-identity', !view.identity);
  setHidden('student-tab-history', !view.history);

  const summaryToggle = document.getElementById('sw-toggle-summary');
  if (summaryToggle) {
    summaryToggle.classList.toggle('is-off', studentState.hideSummary);
    summaryToggle.setAttribute('aria-checked', studentState.hideSummary ? 'false' : 'true');
  }

  const menuBtn = document.querySelector('.student-hamburger-btn');
  if (menuBtn) {
    const labels = {
      overview: 'Menu · Overview',
      credentials: 'Menu · Credentials',
      challenges: 'Menu · Challenges',
      identity: 'Menu · Identity',
      history: 'Menu · History',
    };
    menuBtn.textContent = `☰ ${labels[studentState.screen] || 'Menu'}`;
  }
}

function setTextIfPresent(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function updateStudentCredentialCounts(all = studentState.credentials || []) {
  const pendingTotal = all.filter(v => v.status === 'PENDING').length;
  const claimedTotal = all.length - pendingTotal;
  setTextIfPresent('stat-vcs-pending', pendingTotal);
  setTextIfPresent('stat-vcs', claimedTotal);
  setTextIfPresent('sw-stat-pending-count', pendingTotal);
  setTextIfPresent('sw-stat-claimed-count', claimedTotal);
}

function setStudentScreen(screen) {
  studentState.screen = screen;
  applyStudentVisibility();
  if (screen === 'history') loadStudentHistory();
  if (screen === 'challenges') loadChallenges();
  if (screen === 'identity') loadDID();
}

function toggleStudentSection(section) {
  if (section === 'summary') {
    studentState.hideSummary = !studentState.hideSummary;
    applyStudentVisibility();
  }
  closeStudentMenu();
}

function setStudentCredentialFilter(filter) {
  studentState.credentialFilter = filter;
  if (filter === 'claimed') studentState.claimedExpanded = true;
  if (filter === 'pending') studentState.claimedExpanded = false;
  document.querySelectorAll('#student-cred-filters .student-cred-chip').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filter);
  });
  renderStudentCredentials();
}

function handleStudentCredentialSearch(value) {
  studentState.credentialSearch = String(value || '').trim().toLowerCase();
  if (studentState.credentialSearch) studentState.claimedExpanded = true;
  renderStudentCredentials();
}

function toggleStudentClaimedList(forceOpen = null) {
  if (typeof forceOpen === 'boolean') {
    studentState.claimedExpanded = forceOpen;
  } else {
    studentState.claimedExpanded = !studentState.claimedExpanded;
  }
  renderStudentCredentials();
}

function getFilteredStudentCredentials(vcs) {
  let rows = [...vcs];
  const f = studentState.credentialFilter;
  if (f === 'pending') rows = rows.filter(v => v.status === 'PENDING');
  else if (f === 'claimed') rows = rows.filter(v => v.status !== 'PENDING');
  else if (f !== 'all') rows = rows.filter(v => v.type === f);

  if (studentState.credentialSearch) {
    const q = studentState.credentialSearch;
    rows = rows.filter(v => {
      const d = v.details || {};
      return (
        String(v.type || '').toLowerCase().includes(q) ||
        String(d.degree || '').toLowerCase().includes(q) ||
        String(d.company || '').toLowerCase().includes(q) ||
        String(d.skill_name || '').toLowerCase().includes(q) ||
        String(d.student_id || '').toLowerCase().includes(q)
      );
    });
  }

  return rows;
}

function studentCredentialTypeLabel(type) {
  const labels = {
    UniversityDegreeCredential: 'University Degree',
    InternshipCredential: 'Internship',
    SkillBadgeCredential: 'Skill Badge',
  };
  return labels[type] || String(type || 'Credential').replace('Credential', '').trim() || 'Credential';
}

function studentCredentialSummary(vc) {
  const d = vc.details || {};
  if (vc.type === 'UniversityDegreeCredential') {
    return [d.degree, d.branch].filter(Boolean).join(' · ') || 'Degree credential';
  }
  if (vc.type === 'InternshipCredential') {
    return [d.company, d.role].filter(Boolean).join(' · ') || 'Internship credential';
  }
  if (vc.type === 'SkillBadgeCredential') {
    return [d.skill_name, d.proficiency].filter(Boolean).join(' · ') || 'Skill credential';
  }
  return d.degree || d.company || d.skill_name || 'Credential';
}

function studentCredentialOwner(vc) {
  const d = vc.details || {};
  return d.student_name || d.student_id || 'Student';
}

function studentCredentialDate(vc) {
  const d = vc.details || {};
  const raw = d.issued_on || vc.issued_at;
  if (!raw) return '—';
  const dt = new Date(raw);
  if (Number.isNaN(dt.getTime())) return String(raw);
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function compactVcId(id) {
  const txt = String(id || '');
  if (!txt) return '—';
  if (txt.length <= 20) return txt;
  return `${txt.slice(0, 12)}...${txt.slice(-5)}`;
}

function renderStudentCredentials() {
  const host = document.getElementById('vc-list');
  if (!host) return;

  const all = studentState.credentials || [];
  const vcs = getFilteredStudentCredentials(all);

  const pendingTotal = all.filter(v => v.status === 'PENDING').length;
  const claimedTotal = all.length - pendingTotal;
  updateStudentCredentialCounts(all);

  const pending = vcs.filter(v => v.status === 'PENDING');
  const claimed = vcs.filter(v => v.status !== 'PENDING');

  if (!vcs.length) {
    const quickAction = studentState.credentialFilter === 'pending' && claimedTotal > 0
      ? `<button class="student-cred-empty__cta" type="button" onclick="setStudentCredentialFilter('claimed')">View Claimed Credentials</button>`
      : `<button class="student-cred-empty__cta" type="button" onclick="toast('Credential requests are routed through the Academic Records Office.', 'info')">Request Credential</button>`;
    const emptyTitle = all.length ? 'No credentials match this view' : 'No credentials yet';
    const emptyText = all.length
      ? 'Try another filter or clear the search to see the rest of your wallet.'
      : 'Your institution will issue credentials here';

    host.innerHTML = `
      <div class="student-cred-empty">
        <div class="student-cred-empty__art" aria-hidden="true">
          <div class="student-cred-empty__dots"></div>
          <div class="student-cred-empty__card"></div>
        </div>
        <h3 class="student-cred-empty__title">${emptyTitle}</h3>
        <p class="student-cred-empty__text">${emptyText}</p>
        ${quickAction}
      </div>`;
    return;
  }

  const pendingHtml = pending.length ? `
    <div class="student-list-block">
      <div class="student-list-header">
        <div class="student-list-title">Claim Queue</div>
        <span class="badge badge-warning">${pending.length} Pending</span>
      </div>
      <div class="student-table-wrap">
        <table class="data-table student-cred-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Summary</th>
              <th>Offer ID</th>
              <th>Issued</th>
              <th style="text-align:right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${pending.map(vc => {
              const offerUrl = encodeURIComponent(vc.offer_url || '');
              return `<tr>
                <td><span class="admin-type-pill">${studentCredentialTypeLabel(vc.type)}</span></td>
                <td>
                  <div class="student-vc-main">${studentCredentialSummary(vc)}</div>
                  <div class="student-vc-sub">${studentCredentialOwner(vc)}</div>
                </td>
                <td class="mono student-vc-id">${compactVcId(vc.vc_id)}</td>
                <td>${studentCredentialDate(vc)}</td>
                <td style="text-align:right;">
                  <div class="student-inline-actions">
                    <button class="btn btn-outline btn-sm" type="button" onclick="showOfferQr('${offerUrl}', '${vc.vc_id}')">QR</button>
                    <button class="btn btn-outline btn-sm" type="button" onclick="openCredentialOffer('${offerUrl}')">Open</button>
                  </div>
                </td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>` : '';

  const showClaimedTable = studentState.claimedExpanded || studentState.credentialFilter === 'claimed' || !!studentState.credentialSearch;
  const claimedHtml = claimed.length ? `
    <div class="student-list-block">
      <div class="student-list-header">
        <div class="student-list-title">Claimed Credentials</div>
        <button class="btn btn-outline btn-sm" type="button" onclick="toggleStudentClaimedList()">${showClaimedTable ? 'Hide list' : `Show list (${claimed.length})`}</button>
      </div>
      ${showClaimedTable ? `
      <div class="student-table-wrap">
        <table class="data-table student-cred-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Summary</th>
              <th>Credential ID</th>
              <th>Issued</th>
              <th style="text-align:right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${claimed.map(vc => `<tr>
              <td><span class="admin-type-pill">${studentCredentialTypeLabel(vc.type)}</span></td>
              <td>
                <div class="student-vc-main">${studentCredentialSummary(vc)}</div>
                <div class="student-vc-sub">${studentCredentialOwner(vc)}</div>
              </td>
              <td class="mono student-vc-id">${compactVcId(vc.vc_id)}</td>
              <td>${studentCredentialDate(vc)}</td>
              <td style="text-align:right;">
                <div class="student-inline-actions">
                  <button class="btn btn-primary btn-sm" type="button" onclick="viewCertificate('${vc.vc_id}')">View</button>
                  <button class="btn btn-outline btn-sm" type="button" onclick="downloadVC('${vc.vc_id}')">Copy JWT</button>
                </div>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>` : `<p class="student-collapsed-note">Claimed records are hidden by default to keep this view compact.</p>`}
    </div>` : '';

  host.innerHTML = `${pendingHtml}${claimedHtml}`;
}

/* ── Student: Load Data ───────────────────────────────────────────────── */

async function loadStudentData() {
  await loadDID();
  await loadVCs();
  await loadChallenges();
  await refreshStudentVerifiedCount();
  applyStudentVisibility();
}

async function refreshStudentVerifiedCount() {
  try {
    const sessions = await api('GET', '/students/verification-history');
    setTextIfPresent('sw-stat-verified-count', sessions.filter(s => s.status === 'VERIFIED').length);
  } catch {
    setTextIfPresent('sw-stat-verified-count', '0');
  }
}

async function loadDID() {
  try {
    const payload = parseJwt(token);
    const sid = payload.student_id;
    const doc = await api('GET', `/students/${sid}/did.json`, null, false);
    studentDid = doc.id;

    document.getElementById('stat-did').textContent = '✓';
    document.getElementById('stat-did').style.color = 'var(--success)';

    document.getElementById('did-content').innerHTML = `
      <div class="did-display">
        <span class="did-text">${doc.id}</span>
        <button class="btn-copy" onclick="navigator.clipboard.writeText('${doc.id}');toast('Copied!','success');" title="Copy DID">📋</button>
      </div>
      <div style="margin-top:0.75rem;display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">
        <span class="badge badge-success">✓ Registered</span>
        <span class="badge badge-info" style="font-size:0.65rem;">🔗 Wallet-Bound</span>
        ${doc.verificationMethod && doc.verificationMethod[0] ? `<span class="badge badge-info" style="font-size:0.65rem;">🔑 ${doc.verificationMethod[0].id.split('#').pop()}</span>` : ''}
      </div>
      <p style="margin-top:0.75rem;font-size:0.8rem;color:var(--text-secondary);">
        Your DID is bound to your wallet's key. Use your wallet (e.g. Altme) to manage credentials and respond to verification requests.
      </p>
    `;
  } catch {
    document.getElementById('stat-did').textContent = '—';
    document.getElementById('did-content').innerHTML = `
      <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem;">
        No DID created yet. Your DID will be <strong>automatically created</strong> when you accept a credential offer with your wallet.
      </p>
      <div style="padding:1rem;background:rgba(59,130,246,0.08);border-radius:8px;border:1px solid rgba(59,130,246,0.2);">
        <strong style="font-size:0.85rem;">📱 How it works:</strong>
        <ol style="margin:0.5rem 0 0 1.25rem;font-size:0.82rem;color:var(--text-secondary);line-height:1.6;">
          <li>Admin issues a credential for you</li>
          <li>Open your <strong>Altme</strong> wallet and scan the QR code</li>
          <li>Your wallet's key is automatically linked to your DID</li>
          <li>The credential is stored securely in your wallet</li>
        </ol>
      </div>
    `;
  }
}

async function createDID() {
  // In the wallet-based flow, DIDs are created automatically when the
  // student's wallet claims a credential offer via OID4VCI.
  toast('Your DID will be created automatically when you scan a credential QR with your wallet (e.g. Altme)', 'info');
}

async function rotateKey() {
  // Key rotation now happens automatically when your wallet presents a new
  // key during credential claim.  The issuer portal updates your DID document.
  toast('Key rotation happens automatically when your wallet claims a credential with a new key', 'info');
}

/* ── Student: VCs ─────────────────────────────────────────────────────── */

async function loadVCs() {
  try {
    const vcs = await api('GET', '/students/vcs');
    studentState.credentials = Array.isArray(vcs) ? vcs : [];
    renderStudentCredentials();
  } catch (e) {
    studentState.credentials = [];
    updateStudentCredentialCounts([]);
    document.getElementById('vc-list').innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
  }
}

function openCredentialOffer(encodedUrl) {
  const url = decodeURIComponent(encodedUrl || '');
  if (!url) return toast('Offer URL unavailable', 'error');
  window.open(url, '_blank', 'noopener');
}

function studentOfferEscHandler(e) {
  if (e.key === 'Escape') closeStudentOfferQr();
}

function closeStudentOfferQr() {
  const overlay = document.getElementById('student-offer-overlay');
  if (overlay) overlay.remove();
  document.removeEventListener('keydown', studentOfferEscHandler);
}

function showOfferQr(encodedUrl, vcId) {
  const url = decodeURIComponent(encodedUrl || '');
  if (!url) return toast('Offer URL unavailable', 'error');

  closeStudentOfferQr();
  const overlay = document.createElement('div');
  overlay.id = 'student-offer-overlay';
  overlay.className = 'student-offer-overlay';
  overlay.innerHTML = `
    <div class="student-offer-modal">
      <div class="student-offer-head">
        <div>
          <div class="student-offer-title">Claim Credential</div>
          <div class="student-offer-sub mono">${vcId}</div>
        </div>
        <button class="btn btn-outline btn-sm" type="button" onclick="closeStudentOfferQr()">Close</button>
      </div>
      <div class="student-offer-body">
        <div id="student-offer-qrcode" class="student-offer-qrcode"></div>
        <p class="student-offer-help">Open your wallet app, scan this QR, then accept the offer to claim the credential.</p>
      </div>
      <div class="student-offer-actions">
        <button class="btn btn-outline btn-sm" type="button" onclick="openCredentialOffer('${encodeURIComponent(url)}')">Open Offer Link</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  const qrHost = document.getElementById('student-offer-qrcode');
  if (qrHost) {
    qrHost.innerHTML = '';
    new QRCode(qrHost, {
      text: url,
      width: 220,
      height: 220,
      colorDark: '#000000',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.L,
    });
  }

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeStudentOfferQr();
  });
  document.addEventListener('keydown', studentOfferEscHandler);
}

async function downloadVC(vcId) {
  try {
    const data = await api('GET', `/students/vcs/${vcId}`);
    await navigator.clipboard.writeText(data.verifiable_credential);
    toast('VC JWT copied to clipboard!', 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ── Certificate Diploma View ─────────────────────────────────────────── */

const CORNER_SVG = `<svg viewBox="0 0 60 60" fill="none"><path d="M5 5 C5 5 15 5 20 10 C25 15 20 20 25 25 C30 30 25 35 30 40 C35 45 45 40 50 45 C55 50 55 55 55 55" stroke="#b8963e" stroke-width="1" fill="none"/><path d="M10 5 C10 5 18 8 22 14 C26 20 22 24 27 28" stroke="#b8963e" stroke-width="0.5" fill="none" opacity="0.5"/></svg>`;

async function viewAdminCertificate(id) {
  try {
    const data = await api('GET', `/admin/vcs/${id}`);
    
    // We can't use the standard jwt parsing for PENDING offers which lack a JWT,
    // so we provide a fake minimal payload if it's missing.
    let payload = { vc: { type: ['VerifiableCredential', data.certificate.vc_type], credentialSubject: data.certificate } };
    if (data.verifiable_credential) {
      payload = JSON.parse(atob(data.verifiable_credential.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    }
    
    renderCertificate(data.certificate, payload, id, data.verifiable_credential ? true : false);
  } catch (e) { toast(e.message, 'error'); }
}

async function viewCertificate(vcId) {
  try {
    const data = await api('GET', `/students/vcs/${vcId}`);
    const payload = JSON.parse(atob(data.verifiable_credential.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    renderCertificate(data.certificate, payload, vcId, true);
  } catch (e) { toast(e.message, 'error'); }
}

function renderCertificate(c, payload, id, showDownloadVCButton) {
    const dateStr = c.issuance_date
      ? new Date(c.issuance_date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
      : 'N/A';

    const overlay = document.createElement('div');
    overlay.className = 'cert-overlay';
    overlay.id = 'cert-overlay';

    const vcType = payload.vc.type.find(t => t !== 'VerifiableCredential');
    let template = '';

    if (vcType === 'InternshipCredential') {
      const cs = payload.vc.credentialSubject || {};
      const intn = cs.internship || {};
      const company = intn.company || cs.company || 'Private Organization';
      const duration = intn.duration || cs.duration || 'N/A';
      const role = intn.role || cs.role || '';
      template = `
        <div class="diploma internship-cert">
          <div class="diploma-inner">
            <div class="diploma-university">Certificate of Internship</div>
            <div class="diploma-certifies">Awarded To</div>
            <div class="diploma-name">${c.student_name}</div>
            <div class="diploma-body">for successfully completing an internship at</div>
            <div class="diploma-degree" style="font-family:'Space Grotesk', sans-serif; color:var(--accent);">${company}</div>
            ${role ? `<div class="diploma-body">Role: <strong>${role}</strong></div>` : ''}
            <div class="diploma-body">Duration: <strong>${duration}</strong></div>
            <div class="diploma-date">Issued on ${dateStr}</div>
            <div class="diploma-did-badge"><span class="dot"></span> Verified · ${c.student_did}</div>
          </div>
        </div>
      `;
    } else if (vcType === 'SkillBadgeCredential') {
      const cs = payload.vc.credentialSubject || {};
      const badge = cs.badge || cs.skill || {};
      const skillName = badge.name || cs.skill_name || 'Professional Skill';
      const level = badge.level || badge.proficiency || cs.proficiency || 'Advanced';
      template = `
        <div class="diploma skill-badge-cert">
          <div class="diploma-inner">
             <div class="diploma-crest"><img src="/static/logo.svg" style="width:50px"></div>
             <div class="diploma-university">Skill Badge</div>
             <div class="diploma-certifies">This acknowledges that</div>
             <div class="diploma-name">${c.student_name}</div>
             <div class="diploma-body">has achieved the proficiency level of <strong>${level}</strong> in</div>
             <div class="diploma-degree" style="color:#4a148c">${skillName}</div>
             <div class="diploma-date">Issued on ${dateStr}</div>
             <div class="diploma-did-badge">${c.student_did}</div>
          </div>
        </div>
       `;
    } else {
      // Default Degree Template
      template = `
        <div class="diploma">
          <div class="diploma-bg"> ${CORNER_SVG} </div>
          <div class="diploma-inner" style="border: 2px solid #b8963e; padding: 2rem 2rem 6rem;">
            <div class="diploma-crest"><img src="/static/logo.svg" alt="" style="width:100%;height:100%"></div>
            <div class="diploma-university">IIT Hyderabad</div>
            <div class="diploma-sub">Verifiable Credentials</div>
            <div class="diploma-line"></div>
            <div class="diploma-certifies">This is to certify that</div>
            <div class="diploma-name">${c.student_name}</div>
            <div class="diploma-rollno">Roll No. ${c.student_id}</div>
            <div class="diploma-body">has successfully completed all requirements and is hereby conferred the degree of</div>
            <div class="diploma-degree">${c.degree || c.degree_name || '—'}</div>
            <div class="diploma-body">in the year <strong>${c.graduation_year || c.year || '—'}</strong></div>
            <div class="diploma-date">Issued on ${dateStr}</div>
            <div class="diploma-did-badge"><span class="dot"></span> Cryptographically Verified · ${c.student_did}</div>

            <div class="diploma-signatures">
              <div class="diploma-sig">
                <div class="diploma-sig-line"></div>
                <div class="diploma-sig-name">Dr. R. K. Sharma</div>
                <div class="diploma-sig-title">Vice-Chancellor</div>
              </div>
              <div class="diploma-sig">
                <div class="diploma-sig-line"></div>
                <div class="diploma-sig-name">Prof. A. Mehta</div>
                <div class="diploma-sig-title">Dean of Studies</div>
              </div>
            </div>
          </div>

          <div class="diploma-seal">
            <span class="diploma-seal-icon">✦</span>
            <span class="diploma-seal-text">Verified</span>
          </div>
        </div>
      `;
    }

    overlay.innerHTML = `
      <button class="cert-close" onclick="closeCertificate()">&times;</button>
      ${template}
      <div class="cert-actions">
        <button class="btn btn-primary btn-sm" onclick="downloadCertificateImage()">⬇ Download PNG</button>
        ${showDownloadVCButton ? `<button class="btn btn-outline btn-sm" onclick="downloadVC('${id}')">📋 Copy JWT</button>` : ''}
      </div>
    `;

    document.body.appendChild(overlay);

    // Close on backdrop click
    overlay.addEventListener('click', e => { if (e.target === overlay) closeCertificate(); });
    // Close on Escape
    document.addEventListener('keydown', certEscHandler);
}

function certEscHandler(e) {
  if (e.key === 'Escape') closeCertificate();
}

function closeCertificate() {
  const overlay = document.getElementById('cert-overlay');
  if (overlay) {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 200);
  }
  document.removeEventListener('keydown', certEscHandler);
}

function openCertPreviewFromVerification(cert, verificationId) {
  const s = cert.subject_data || {};
  const c = {
    student_name: s.student_name || s.name || '—',
    student_id: s.student_id || '—',
    degree: s.degree || '—',
    graduation_year: s.graduation_year || s.year || '—',
    student_did: cert.holder_did || '—',
    issuance_date: s.issued_on || null,
  };
  const payload = {
    vc: {
      type: ['VerifiableCredential', cert.vc_type || 'UniversityDegreeCredential'],
      credentialSubject: {
        ...s,
        internship: { company: s.company, role: s.role, duration: s.duration },
        badge: { name: s.skill_name, level: s.proficiency },
        skill: { name: s.skill_name, level: s.proficiency },
      },
    },
  };
  renderCertificate(c, payload, verificationId, false);
}

async function previewVerifierCert(vId) {
  try {
    const data = await api('GET', `/verifications/${vId}`);
    if (data.data) openCertPreviewFromVerification(data.data, vId);
    else toast('No credential data for this session', 'error');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function downloadCertificateImage() {
  const diploma = document.querySelector('#cert-overlay .diploma');
  if (!diploma) return;
  try {
    const canvas = await html2canvas(diploma, {
      scale: 2,
      useCORS: true,
      backgroundColor: null,
      logging: false,
    });
    const link = document.createElement('a');
    link.download = 'IIT_Hyderabad_Certificate.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
    toast('Certificate downloaded!', 'success');
  } catch (e) {
    toast('Download failed: ' + e.message, 'error');
  }
}

/* ── Student: Challenges ──────────────────────────────────────────────── */

async function loadChallenges() {
  try {
    const challenges = await api('GET', '/students/challenges');
    setTextIfPresent('stat-challenges', challenges.length);
    setTextIfPresent('sw-stat-verified-count', '0');

    if (challenges.length === 0) {
      document.getElementById('challenge-list').innerHTML = `
        <div class="empty-state">
          <div class="icon">⚡</div>
          <p>No pending verification requests</p>
        </div>`;
      return;
    }

    const itemsHtml = challenges.map(c => {
      const qrId = `challenge-qr-${c.verification_id}`;
      return `
        <li class="data-item" style="flex-direction:column; align-items:stretch; gap:1rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
            <div>
              <span class="data-item-title">Verification Request</span>
              <span class="data-item-sub">${c.verification_id} · Expires: ${new Date(c.expires_at).toLocaleString()}</span>
            </div>
            <span class="badge badge-warning">⏳ Pending</span>
          </div>
          <div style="display:flex; gap:1.5rem; align-items:center; flex-wrap:wrap; padding:0.75rem; background:var(--bg-card); border-radius:8px; border:1px solid var(--border);">
            <div id="${qrId}" style="background:#fff; padding:8px; border-radius:8px;"></div>
            <div style="font-size:0.82rem; color:var(--text-secondary); line-height:1.6;">
              <strong>Scan to prove your credential:</strong><br>
              1. Open <strong>Altme</strong> wallet on your phone<br>
              2. Tap <em>Scan QR</em><br>
              3. Select the credential to share<br>
              4. Tap <em>Confirm</em>
            </div>
          </div>
        </li>`;
    }).join('');

    document.getElementById('challenge-list').innerHTML = `<ul class="data-list">${itemsHtml}</ul>`;

    // Render QR codes
    challenges.forEach(c => {
      const qrDiv = document.getElementById(`challenge-qr-${c.verification_id}`);
      if (qrDiv && c.qr_content) {
        new QRCode(qrDiv, {
          text: c.qr_content,
          width: 180,
          height: 180,
          colorDark: "#000000",
          colorLight: "#ffffff",
          correctLevel: QRCode.CorrectLevel.L
        });
      }
    });
  } catch (e) {
    document.getElementById('challenge-list').innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
  }
}

async function respondToChallenge(verificationId, nonce) {
  // In the wallet-based flow, challenges are handled by scanning the
  // QR code with the wallet.  Server-side VP signing is no longer used.
  toast('Use your wallet (e.g. Altme) to scan the QR code and respond to the challenge', 'info');
}

/* ── Student: Verification History ────────────────────────────────────── */

async function loadStudentHistory() {
  try {
    const sessions = await api('GET', '/students/verification-history');
    setTextIfPresent('sw-stat-verified-count', sessions.filter(s => s.status === 'VERIFIED').length);
    if (sessions.length === 0) {
      document.getElementById('student-history-list').innerHTML = `
        <div class="empty-state"><div class="icon">📋</div><p>No verification history yet</p></div>`;
      return;
    }

    const statusBadge = (s) => {
      if (s === 'VERIFIED') return '<span class="badge badge-success">✓ Verified</span>';
      if (s === 'EXPIRED') return '<span class="badge badge-warning">Expired</span>';
      return '<span class="badge badge-info">Pending</span>';
    };

    document.getElementById('student-history-list').innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Verification ID</th>
            <th>Verified By</th>
            <th>Degree</th>
            <th>Status</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          ${sessions.map(s => `
            <tr>
              <td><span class="mono" style="font-size:0.7rem;">${s.verification_id}</span></td>
              <td><strong>${s.verifier_name || '—'}</strong></td>
              <td>${s.degree_name || '—'}${s.year ? ' (' + s.year + ')' : ''}</td>
              <td>${statusBadge(s.status)}</td>
              <td style="font-size:0.75rem;">${s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (e) {
    document.getElementById('student-history-list').innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
  }
}

/* ── Admin: Operations Dashboard ─────────────────────────────────────── */

function resetAdminState() {
  adminState.students = [];
  adminState.studentQuery = '';
  adminState.studentFilter = 'all';
  adminState.issued = [];
  adminState.issuedQuery = '';
  adminState.issuedFilterType = 'all';
  adminState.issuedFilterStatus = 'all';
  adminState.activity = [];
  adminState.issuerDoc = null;
  adminState.issuerExpanded = false;
  adminState.screen = 'composer';
  adminState.menuOpen = false;
  adminState.hideKpi = true;
  adminState.hideFilters = false;
  setAdminMenuOpen(false);
}

function switchAdminTab(tab) {
  // Legacy compatibility shim from old tabbed layout.
  if (tab === 'students') {
    setAdminScreen('directory');
    loadAdminStudents();
    document.getElementById('admin-directory-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  if (tab === 'issue') {
    setAdminScreen('composer');
    loadStudentDIDDropdown();
    updateAdminFields();
    document.getElementById('admin-composer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  if (tab === 'issued') {
    setAdminScreen('ledger');
    loadAdminIssuedVCs();
    document.getElementById('admin-issued-list')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function prettyVcType(vcType) {
  const map = {
    UniversityDegreeCredential: 'University Degree',
    InternshipCredential: 'Internship Certificate',
    SkillBadgeCredential: 'Skill Badge',
  };
  return map[vcType] || String(vcType || 'Credential').replace('Credential', '').trim();
}

function getAdminStudentReference(student) {
  return student.has_did ? student.did_uri : (student.username || student.student_id);
}

function truncateDid(value) {
  if (!value) return '';
  if (value.length <= 34) return value;
  return `${value.slice(0, 22)}...${value.slice(-8)}`;
}

function setAdminMenuOpen(open) {
  adminState.menuOpen = !!open;
  const overlay = document.getElementById('admin-menu-overlay');
  const drawer = document.getElementById('admin-menu-drawer');

  if (overlay) overlay.classList.toggle('open', adminState.menuOpen);
  if (drawer) {
    drawer.classList.toggle('open', adminState.menuOpen);
    drawer.setAttribute('aria-hidden', adminState.menuOpen ? 'false' : 'true');
  }
  document.body.classList.toggle('admin-no-scroll', adminState.menuOpen);
}

function toggleAdminMenu() {
  setAdminMenuOpen(!adminState.menuOpen);
}

function closeAdminMenu() {
  setAdminMenuOpen(false);
}

function setAdminScreen(screen) {
  adminState.screen = screen;
  if (screen === 'overview') {
    adminState.hideKpi = false;
  }
  applyAdminVisibility();
}

function applyAdminVisibility() {
  const setHidden = (id, hidden) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('admin-hidden', !!hidden);
  };

  const screenMap = {
    overview: { kpi: true, directory: true, composer: true, ledger: true, advanced: true },
    composer: { kpi: false, directory: false, composer: true, ledger: false, advanced: false },
    directory: { kpi: false, directory: true, composer: false, ledger: false, advanced: false },
    ledger: { kpi: false, directory: false, composer: false, ledger: true, advanced: false },
    advanced: { kpi: false, directory: false, composer: false, ledger: false, advanced: true },
  };
  const view = screenMap[adminState.screen] || screenMap.composer;

  setHidden('admin-kpi-strip', !view.kpi || adminState.hideKpi);
  setHidden('admin-directory-panel', !view.directory);
  setHidden('admin-composer-card', !view.composer);
  setHidden('admin-preview-panel', !view.composer);
  setHidden('admin-ledger-section', !view.ledger);
  setHidden('admin-advanced-tools', !view.advanced);

  const filtersHidden = adminState.hideFilters;
  setHidden('admin-directory-controls', !view.directory || filtersHidden);
  setHidden('admin-ledger-toolbar', !view.ledger || filtersHidden);
  setHidden('admin-issued-summary-chips', !view.ledger || filtersHidden);

  const grid = document.getElementById('admin-main-grid');
  if (grid) grid.classList.toggle('admin-hidden', !view.composer);

  if (view.advanced) {
    const adv = document.getElementById('admin-advanced-tools');
    if (adv) adv.open = true;
  }

  const breadcrumb = document.getElementById('aw-breadcrumb-screen');
  if (breadcrumb) {
    const labels = {
      overview: 'Overview', composer: 'Credential Composer',
      directory: 'Student Directory', ledger: 'Issued Ledger', advanced: 'Advanced Tools',
    };
    breadcrumb.textContent = labels[adminState.screen] || 'Credential Composer';
  }

  const kpiToggle = document.getElementById('aw-toggle-kpi');
  if (kpiToggle) {
    kpiToggle.classList.toggle('is-off', adminState.hideKpi);
    kpiToggle.setAttribute('aria-checked', adminState.hideKpi ? 'false' : 'true');
  }
  const filtersToggle = document.getElementById('aw-toggle-filters');
  if (filtersToggle) {
    filtersToggle.classList.toggle('is-off', adminState.hideFilters);
    filtersToggle.setAttribute('aria-checked', adminState.hideFilters ? 'false' : 'true');
  }
}

function toggleAdminSection(section) {
  if (section === 'kpi') {
    adminState.hideKpi = !adminState.hideKpi;
    applyAdminVisibility();
  } else if (section === 'filters') {
    adminState.hideFilters = !adminState.hideFilters;
    applyAdminVisibility();
  } else if (section === 'advanced') {
    setAdminScreen(adminState.screen === 'advanced' ? 'composer' : 'advanced');
  }
  closeAdminMenu();
}

function adminQuickNav(id) {
  const map = {
    'admin-directory-panel': 'directory',
    'admin-composer-card': 'composer',
    'admin-issued-list': 'ledger',
    'admin-ledger-section': 'ledger',
  };
  if (map[id]) setAdminScreen(map[id]);
  closeAdminMenu();
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function seedAdminActivity() {
  if (adminState.activity.length > 0) return;
  adminState.activity = [{
    action: 'Session started',
    detail: 'Admin workspace initialized',
    at: new Date().toISOString(),
  }];
  renderAdminActivity();
}

function addAdminActivity(action, detail = '') {
  adminState.activity.unshift({ action, detail, at: new Date().toISOString() });
  adminState.activity = adminState.activity.slice(0, 20);
  renderAdminActivity();
}

function renderAdminActivity() {
  const host = document.getElementById('admin-activity-log');
  if (!host) return;

  if (!adminState.activity.length) {
    host.innerHTML = '<div class="empty-state"><p>No activity yet</p></div>';
    return;
  }

  host.innerHTML = adminState.activity.map(item => {
    const t = new Date(item.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `<div class="admin-activity-item">
      <div>
        <div class="admin-activity-action">${item.action}</div>
        ${item.detail ? `<div class="admin-activity-detail">${item.detail}</div>` : ''}
      </div>
      <div class="admin-activity-time">${t}</div>
    </div>`;
  }).join('');
}

async function refreshAdminDashboard(showToast = false) {
  seedAdminActivity();
  await Promise.all([loadAdminStudents(), loadIssuerInfo(), loadAdminIssuedVCs()]);
  applyAdminVisibility();
  if (showToast) {
    addAdminActivity('Dashboard refreshed');
    toast('Admin data refreshed', 'success');
  }
}

function renderAdminKPIs() {
  const students = adminState.students || [];
  const issued = adminState.issued || [];
  const didReady = students.filter(s => s.has_did).length;
  const pending = issued.filter(v => (v.status || '').toUpperCase() !== 'ISSUED').length;
  const today = new Date().toDateString();
  const issuedToday = issued.filter(v => {
    if ((v.status || '').toUpperCase() !== 'ISSUED' || !v.issued_at) return false;
    return new Date(v.issued_at).toDateString() === today;
  }).length;

  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  };

  set('admin-kpi-students', students.length);
  set('admin-kpi-did', didReady);
  set('admin-kpi-pending', pending);
  set('admin-kpi-today', issuedToday);

  const claimedTotal = issued.filter(v => (v.status || '').toUpperCase() === 'ISSUED').length;
  set('aw-stat-issued-today', issuedToday);
  set('aw-stat-pending', pending);
  set('aw-stat-claimed', claimedTotal);
}

function setAdminStudentFilter(filter) {
  adminState.studentFilter = filter;
  document.querySelectorAll('#admin-student-filters .admin-filter-chip').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filter);
  });
  renderAdminStudentDirectory();
}

function handleAdminStudentSearch(value) {
  adminState.studentQuery = String(value || '').trim().toLowerCase();
  renderAdminStudentDirectory();
}

function renderAdminStudentDirectory() {
  const host = document.getElementById('admin-student-list');
  if (!host) return;

  let rows = [...(adminState.students || [])];
  if (adminState.studentFilter === 'did') rows = rows.filter(s => s.has_did);
  if (adminState.studentFilter === 'no-did') rows = rows.filter(s => !s.has_did);
  if (adminState.studentFilter === 'with-vc') rows = rows.filter(s => (s.vc_count || 0) > 0);
  if (adminState.studentFilter === 'no-vc') rows = rows.filter(s => (s.vc_count || 0) === 0);

  if (adminState.studentQuery) {
    const q = adminState.studentQuery;
    rows = rows.filter(s =>
      String(s.student_id || '').toLowerCase().includes(q) ||
      String(s.full_name || '').toLowerCase().includes(q) ||
      String(s.username || '').toLowerCase().includes(q) ||
      String(s.did_uri || '').toLowerCase().includes(q)
    );
  }

  if (!rows.length) {
    host.innerHTML = '<div class="empty-state"><p>No students match this filter</p></div>';
    return;
  }

  const selectedRef = document.getElementById('admin-student-did')?.value || '';
  host.innerHTML = `<table class="data-table admin-student-table">
    <thead>
      <tr>
        <th>Student</th>
        <th>DID</th>
        <th>VCs</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      ${rows.map(s => {
    const ref = getAdminStudentReference(s);
    const isSelected = selectedRef && selectedRef === ref;
    const didCell = s.has_did
      ? `<span class="badge badge-success">DID Ready</span><span class="mono admin-student-did-text">${truncateDid(s.did_uri)}</span>`
      : '<span class="badge badge-warning">No DID yet</span>';
    return `<tr class="${isSelected ? 'is-selected' : ''}">
      <td>
        <div class="admin-student-name">${s.full_name || s.username || 'Unknown'}</div>
        <div class="admin-student-meta">${s.student_id || '—'} · ${s.username || '—'}</div>
      </td>
      <td><div class="admin-student-did">${didCell}</div></td>
      <td><span class="badge badge-info">${s.vc_count || 0}</span></td>
      <td style="text-align:right;"><button class="btn btn-outline btn-sm" type="button" onclick="selectAdminStudent('${encodeURIComponent(ref)}')">Issue</button></td>
    </tr>`;
  }).join('')}
    </tbody>
  </table>`;
}

function selectAdminStudent(encodedRef) {
  const ref = decodeURIComponent(encodedRef);
  const select = document.getElementById('admin-student-did');
  if (!select) return;
  select.value = ref;
  setAdminScreen('composer');
  updateAdminSelectionSummary();
  renderAdminStudentDirectory();
  document.getElementById('admin-composer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('Student preselected in composer', 'success');
}

async function loadAdminStudents() {
  try {
    const students = await api('GET', '/admin/students');
    adminState.students = Array.isArray(students) ? students : [];
    renderAdminStudentDirectory();
    await loadStudentDIDDropdown();
    renderAdminKPIs();
    seedAdminActivity();
  } catch (e) {
    adminState.students = [];
    renderAdminStudentDirectory();
    renderAdminKPIs();
    document.getElementById('admin-student-list').innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
  }
}

async function loadStudentDIDDropdown() {
  try {
    if (!adminState.students.length) {
      const students = await api('GET', '/admin/students');
      adminState.students = Array.isArray(students) ? students : [];
    }
    const select = document.getElementById('admin-student-did');
    if (!select) return;

    const previous = select.value;
    select.innerHTML = '<option value="">Select a student…</option>';
    adminState.students.forEach(s => {
      const val = getAdminStudentReference(s);
      const label = s.has_did ? '' : ' (No DID yet)';
      select.innerHTML += `<option value="${val}">${s.student_id} — ${s.full_name}${label}</option>`;
    });

    if (previous) select.value = previous;
    updateAdminSelectionSummary();
  } catch {
    // Keep UI usable even when directory refresh fails.
  }
}

function updateAdminSelectionSummary() {
  const summary = document.getElementById('admin-selection-summary');
  const select = document.getElementById('admin-student-did');
  const typeSelect = document.getElementById('admin-vc-type');
  if (!summary || !select || !typeSelect) return;

  if (!select.value) {
    summary.textContent = 'No student selected yet.';
    return;
  }

  const label = select.options[select.selectedIndex]?.textContent || select.value;
  summary.innerHTML = `<strong>Selected:</strong> ${label} <span class="admin-selection-dot">•</span> <strong>Type:</strong> ${prettyVcType(typeSelect.value)}`;
}

/* ── Admin: Credential Form ─────────────────────────────────────────── */

function updateAdminFields() {
  const type = document.getElementById('admin-vc-type').value;
  document.querySelectorAll('.vc-fields').forEach(el => el.style.display = 'none');
  if (type === 'UniversityDegreeCredential') document.getElementById('fields-degree').style.display = 'grid';
  if (type === 'InternshipCredential') document.getElementById('fields-internship').style.display = 'grid';
  if (type === 'SkillBadgeCredential') document.getElementById('fields-skill').style.display = 'grid';
  updateAdminSelectionSummary();
  updateAdminPreview();
}

function copyOfferUrl() {
  const offer = document.getElementById('admin-offer-url')?.textContent?.trim() || '';
  if (!offer || offer === '—') return toast('No offer URL available', 'error');
  navigator.clipboard.writeText(offer);
  toast('Offer URL copied', 'success');
}

async function issueVC() {
  const studentDidRef = document.getElementById('admin-student-did').value;
  const vc_type = document.getElementById('admin-vc-type').value;

  const payload = {
    student_did: studentDidRef,
    vc_type: vc_type,
  };

  if (vc_type === 'UniversityDegreeCredential') {
    payload.degree = document.getElementById('admin-degree').value.trim();
    payload.branch = document.getElementById('admin-branch').value.trim();
    payload.specialization = document.getElementById('admin-specialization').value.trim();
    payload.cgpa = document.getElementById('admin-cgpa').value.trim();
    payload.graduation_year = parseInt(document.getElementById('admin-year').value, 10);
    payload.honours = document.getElementById('admin-honours').value.trim();
    if (!payload.degree || !payload.branch || !payload.cgpa || !payload.graduation_year) {
      return toast('Fill required fields: Degree, Branch, CGPA, Year', 'error');
    }
  } else if (vc_type === 'InternshipCredential') {
    payload.company = document.getElementById('admin-company').value.trim();
    payload.role = document.getElementById('admin-role').value.trim();
    payload.duration = document.getElementById('admin-duration').value.trim();
    if (!payload.company || !payload.role || !payload.duration) {
      return toast('Fill required fields: Company, Role, Duration', 'error');
    }
  } else if (vc_type === 'SkillBadgeCredential') {
    payload.skill_name = document.getElementById('admin-skill').value.trim();
    payload.proficiency = document.getElementById('admin-proficiency').value.trim();
    if (!payload.skill_name || !payload.proficiency) {
      return toast('Fill required fields: Skill, Proficiency', 'error');
    }
  }

  if (!studentDidRef) return toast('Select a student reference', 'error');

  const btn = document.getElementById('btn-issue-vc');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating Offer...';

  try {
    const response = await api('POST', '/admin/issue-vc', payload);
    const offerUrl = response.offer_url;

    document.getElementById('qr-container').style.display = 'block';
    document.getElementById('admin-offer-url').textContent = offerUrl;

    const qrDiv = document.getElementById('qrcode');
    qrDiv.innerHTML = '';
    new QRCode(qrDiv, {
      text: offerUrl,
      width: 220,
      height: 220,
      colorDark: '#000000',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.L,
    });

    const selectedLabel = document.getElementById('admin-student-did').options[
      document.getElementById('admin-student-did').selectedIndex
    ]?.textContent || studentDidRef;

    addAdminActivity('Credential offer generated', `${prettyVcType(vc_type)} for ${selectedLabel}`);
    toast('Credential offer generated successfully', 'success');
    updateAdminStepState();
    loadAdminIssuedVCs();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Issue Credential';
  }
}

function renderIssuerDidPreview() {
  const host = document.getElementById('issuer-did-info');
  if (!host) return;

  if (!adminState.issuerDoc) {
    host.textContent = 'Unable to load issuer DID document.';
    return;
  }

  const fullText = JSON.stringify(adminState.issuerDoc, null, 2);
  if (adminState.issuerExpanded) {
    host.textContent = fullText;
  } else {
    const lines = fullText.split('\n');
    host.textContent = lines.slice(0, 16).join('\n') + (lines.length > 16 ? '\n...' : '');
  }

  const btn = document.getElementById('btn-issuer-toggle');
  if (btn) btn.textContent = adminState.issuerExpanded ? 'Collapse' : 'Expand';
}

function toggleIssuerDidPreview() {
  adminState.issuerExpanded = !adminState.issuerExpanded;
  renderIssuerDidPreview();
}

function copyIssuerDid(mode = 'id') {
  if (!adminState.issuerDoc) return toast('Issuer DID not loaded', 'error');
  const text = mode === 'json'
    ? JSON.stringify(adminState.issuerDoc, null, 2)
    : String(adminState.issuerDoc.id || '');
  if (!text) return toast('Issuer DID unavailable', 'error');
  navigator.clipboard.writeText(text);
  toast(mode === 'json' ? 'Issuer document copied' : 'Issuer DID copied', 'success');
}

async function loadIssuerInfo() {
  try {
    const doc = await api('GET', '/admin/issuer/did.json', null, false);
    adminState.issuerDoc = doc;
    renderIssuerDidPreview();
  } catch {
    adminState.issuerDoc = null;
    renderIssuerDidPreview();
  }
}

/* ── Admin: Issued Ledger ────────────────────────────────────────────── */

function handleAdminIssuedSearch(value) {
  adminState.issuedQuery = String(value || '').trim().toLowerCase();
  renderAdminIssuedLedger();
}

function handleAdminIssuedFilter() {
  adminState.issuedFilterType = document.getElementById('admin-issued-filter-type')?.value || 'all';
  adminState.issuedFilterStatus = document.getElementById('admin-issued-filter-status')?.value || 'all';
  renderAdminIssuedLedger();
}

function renderAdminIssuedLedger() {
  const host = document.getElementById('admin-issued-list');
  const summaryHost = document.getElementById('admin-issued-summary-chips');
  if (!host) return;

  const all = [...(adminState.issued || [])];
  const issuedCount = all.filter(v => (v.status || '').toUpperCase() === 'ISSUED').length;
  const pendingCount = all.length - issuedCount;
  const degreeCount = all.filter(v => v.vc_type === 'UniversityDegreeCredential').length;
  const internshipCount = all.filter(v => v.vc_type === 'InternshipCredential').length;
  const skillCount = all.filter(v => v.vc_type === 'SkillBadgeCredential').length;

  if (summaryHost) {
    summaryHost.innerHTML = `
      <span class="admin-summary-chip">Total ${all.length}</span>
      <span class="admin-summary-chip">Issued ${issuedCount}</span>
      <span class="admin-summary-chip">Pending ${pendingCount}</span>
      <span class="admin-summary-chip">Degree ${degreeCount} · Internship ${internshipCount} · Skill ${skillCount}</span>
    `;
  }

  let rows = all;
  if (adminState.issuedFilterType !== 'all') {
    rows = rows.filter(v => v.vc_type === adminState.issuedFilterType);
  }
  if (adminState.issuedFilterStatus !== 'all') {
    rows = rows.filter(v => (v.status || '').toUpperCase() === adminState.issuedFilterStatus);
  }
  if (adminState.issuedQuery) {
    const q = adminState.issuedQuery;
    rows = rows.filter(v =>
      String(v.student_name || '').toLowerCase().includes(q) ||
      String(v.student_id || '').toLowerCase().includes(q) ||
      String(v.summary || '').toLowerCase().includes(q) ||
      String(prettyVcType(v.vc_type) || '').toLowerCase().includes(q)
    );
  }

  rows.sort((a, b) => new Date(b.issued_at || 0) - new Date(a.issued_at || 0));

  if (!rows.length) {
    host.innerHTML = '<div class="empty-state"><p>No credentials match these filters</p></div>';
    return;
  }

  const tableRows = rows.map(vc => {
    const isIssued = (vc.status || '').toUpperCase() === 'ISSUED';
    const statusCls = isIssued ? 'badge-success' : 'badge-warning';
    const statusLabel = isIssued ? 'Issued' : 'Pending';
    const dateStr = vc.issued_at
      ? new Date(vc.issued_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      : '—';

    return `<tr>
      <td><span class="admin-type-pill">${prettyVcType(vc.vc_type)}</span></td>
      <td>
        <div class="admin-student-name">${vc.student_name || '—'}</div>
        <div class="admin-student-meta">${vc.student_id || '—'}</div>
      </td>
      <td>${vc.summary || 'No summary available'}</td>
      <td><span class="badge ${statusCls}">${statusLabel}</span></td>
      <td>${dateStr}</td>
      <td style="text-align:right;"><button class="btn btn-outline btn-sm" onclick="viewAdminCertificate('${vc.vc_id}')">Preview</button></td>
    </tr>`;
  }).join('');

  host.innerHTML = `<table class="data-table admin-issued-table">
    <thead>
      <tr>
        <th>Type</th>
        <th>Student</th>
        <th>Summary</th>
        <th>Status</th>
        <th>Date</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      ${tableRows}
    </tbody>
  </table>`;
}

async function loadAdminIssuedVCs() {
  const host = document.getElementById('admin-issued-list');
  if (host) {
    host.innerHTML = '<div class="empty-state"><span class="spinner"></span> Loading...</div>';
  }

  try {
    const vcs = await api('GET', '/admin/issued-vcs');
    adminState.issued = Array.isArray(vcs) ? vcs : [];
    renderAdminKPIs();
    renderAdminIssuedLedger();
  } catch (e) {
    adminState.issued = [];
    renderAdminKPIs();
    if (host) host.innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
  }
}

/* ── Verifier ─────────────────────────────────────────────────────────── */

function resetVerifierState() {
  verifierState.screen = 'verify';
  verifierState.menuOpen = false;
  verifierState.showLegacy = false;
  verifierState.targetMode = 'open';
  if (verifierState.countdownInterval) {
    clearInterval(verifierState.countdownInterval);
    verifierState.countdownInterval = null;
  }
  setVerifierMenuOpen(false);
}

function setVerifierMenuOpen(open) {
  verifierState.menuOpen = !!open;
  const overlay = document.getElementById('verifier-menu-overlay');
  const drawer = document.getElementById('verifier-menu-drawer');
  if (overlay) overlay.classList.toggle('open', verifierState.menuOpen);
  if (drawer) {
    drawer.classList.toggle('open', verifierState.menuOpen);
    drawer.setAttribute('aria-hidden', verifierState.menuOpen ? 'false' : 'true');
  }
  // vw-drawer-overlay uses display:none toggle via .open, no body scroll lock needed
}

function toggleVerifierMenu() {
  setVerifierMenuOpen(!verifierState.menuOpen);
}

function closeVerifierMenu() {
  setVerifierMenuOpen(false);
}

function applyVerifierVisibility() {
  const setHidden = (id, hidden) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('verifier-hidden', !!hidden);
  };

  const map = {
    overview: { verify: true, history: true },
    verify:   { verify: true, history: false },
    history:  { verify: false, history: true },
  };
  const view = map[verifierState.screen] || map.verify;

  setHidden('verifier-tab-verify', !view.verify);
  setHidden('verifier-tab-history', !view.history);

  // Manual panel uses display style, not class
  const legacyPanel = document.getElementById('verifier-legacy-panel');
  if (legacyPanel) legacyPanel.style.display = (view.verify && verifierState.showLegacy) ? '' : 'none';

  // Breadcrumb
  const labels = { verify: 'Proof Request', history: 'History', overview: 'All Sections' };
  const breadcrumb = document.getElementById('vw-breadcrumb-screen');
  if (breadcrumb) breadcrumb.textContent = labels[verifierState.screen] || 'Proof Request';

  // Manual tool toggle sync
  const manualToggle = document.getElementById('vw-toggle-manual');
  if (manualToggle) {
    manualToggle.classList.toggle('is-off', !verifierState.showLegacy);
    manualToggle.setAttribute('aria-checked', verifierState.showLegacy ? 'true' : 'false');
  }
}

function setVerifierScreen(screen) {
  verifierState.screen = screen;
  applyVerifierVisibility();
  if (screen === 'history' || screen === 'overview') loadVerifierHistory();
}

function toggleVerifierSection(section) {
  if (section === 'legacy') {
    verifierState.showLegacy = !verifierState.showLegacy;
    if (verifierState.showLegacy) verifierState.screen = 'verify';
    applyVerifierVisibility();
  }
  closeVerifierMenu();
}

function switchVerifierTab(tab) {
  setVerifierScreen(tab === 'history' ? 'history' : 'verify');
}

let verifierPollingInterval = null;

async function loadVerifierStudents() {
  try {
    const students = await api('GET', '/admin/students');
    const select = document.getElementById('verifier-student-select');
    if (!select) return;

    const previous = select.value;
    select.innerHTML = '<option value="">Any student (open verification)</option>';
    students.forEach(s => {
      const did = s.did_uri || s.did;
      if (!did) return;
      const name = s.full_name || s.username || 'Student';
      select.innerHTML += `<option value="${did}">${name} (${s.student_id || '—'})</option>`;
    });

    if (previous) select.value = previous;
  } catch (e) {
    console.log('Could not load students for verifier:', e);
  }
}

async function initiateOID4VP() {
  const btn = document.getElementById('btn-request-vp');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating...';

  try {
    setVerifierScreen('verify');

    const select = document.getElementById('verifier-student-select');
    const targetDid = (verifierState.targetMode === 'targeted' && select) ? select.value : '';
    const body = targetDid ? { target_student_did: targetDid } : {};

    const data = await api('POST', '/verify/init', body);

    // Show QR block
    const qrContainer = document.getElementById('verifier-qr-container');
    const qrDiv = document.getElementById('verifier-qrcode');
    const scanStatus = document.getElementById('verifier-scan-status');
    if (qrContainer) qrContainer.style.display = 'flex';
    if (scanStatus) scanStatus.innerHTML = '<span class="spinner"></span> Waiting for student scan...';

    if (!qrDiv) throw new Error('QR container not available');
    qrDiv.innerHTML = '';
    new QRCode(qrDiv, {
      text: data.qr_content,
      width: 220,
      height: 220,
      colorDark: '#000000',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.L,
    });

    // Update session chip and start countdown
    const sessionIdEl = document.getElementById('vw-session-id');
    if (sessionIdEl) sessionIdEl.textContent = (data.verification_id || '').slice(0, 8).toUpperCase();
    startVerifierCountdown(300);

    // Right panel: reset to awaiting state
    const awaitingEl = document.getElementById('vw-awaiting-state');
    const resultCard = document.getElementById('verifier-result-card');
    if (awaitingEl) awaitingEl.style.display = '';
    if (resultCard) { resultCard.style.display = 'none'; resultCard.innerHTML = ''; }

    // Pulsing dot → active
    const dot = document.getElementById('vw-session-dot');
    if (dot) { dot.className = 'vw-session-dot active'; }

    // Start polling
    if (verifierPollingInterval) clearInterval(verifierPollingInterval);
    verifierPollingInterval = setInterval(() => pollVerificationStatus(data.verification_id), 3000);

    toast('Verification QR generated!', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Generate Verification QR';
  }
}

// Helper: render a labelled field cell for the verification result card
function _vf(label, value) {
  if (value === undefined || value === null || value === '') return '';
  return `<div style="padding:0.8rem 1rem; border-right:1px solid var(--border); border-bottom:1px solid var(--border);">
    <div style="font-size:0.6rem; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:var(--text-muted); margin-bottom:0.2rem;">${label}</div>
    <div style="font-size:0.88rem; font-weight:500; color:var(--text-primary);">${value}</div>
  </div>`;
}

async function pollVerificationStatus(verificationId) {
  try {
    const data = await api('GET', `/verifications/${verificationId}`);
    
    if (data.status === 'verified') {
      clearInterval(verifierPollingInterval);
      verifierPollingInterval = null;
      if (verifierState.countdownInterval) {
        clearInterval(verifierState.countdownInterval);
        verifierState.countdownInterval = null;
      }

      setVerifierScreen('verify');

      // Update scan status in left panel (keep QR visible)
      const scanStatus = document.getElementById('verifier-scan-status');
      if (scanStatus) scanStatus.innerHTML = '✓ Wallet scan received';

      // Dot → verified
      const dot = document.getElementById('vw-session-dot');
      if (dot) dot.className = 'vw-session-dot verified';

      // Right panel: hide awaiting, show result
      const awaitingEl = document.getElementById('vw-awaiting-state');
      if (awaitingEl) awaitingEl.style.display = 'none';
      const resultCard = document.getElementById('verifier-result-card');
      if (!resultCard) return;
      resultCard.style.display = 'block';
      
      const cert = data.data || {};
      const s = cert.subject_data || {};
      const vcType = cert.vc_type || '';

      // Build credential-specific fields grid
      let credFields = '';
      if (vcType === 'UniversityDegreeCredential') {
        credFields = `
          ${_vf('Graduate',       s.student_name)}
          ${_vf('Roll No',        s.student_id)}
          ${_vf('Degree',         s.degree)}
          ${_vf('Branch',         s.branch)}
          ${s.specialization ? _vf('Specialization', s.specialization) : ''}
          ${_vf('CGPA',           s.cgpa)}
          ${_vf('Year of Passing',s.graduation_year)}
          ${s.honours ? _vf('Honours', s.honours) : ''}
          ${_vf('Issued on',      s.issued_on)}`;
      } else if (vcType === 'InternshipCredential') {
        credFields = `
          ${_vf('Student',  s.student_name)}
          ${_vf('Roll No',  s.student_id)}
          ${_vf('Company',  s.company)}
          ${_vf('Role',     s.role)}
          ${_vf('Duration', s.duration)}
          ${_vf('Issued on',s.issued_on)}`;
      } else if (vcType === 'SkillBadgeCredential') {
        credFields = `
          ${_vf('Recipient',  s.student_name)}
          ${_vf('Roll No',    s.student_id)}
          ${_vf('Skill',      s.skill_name)}
          ${_vf('Level',      s.proficiency)}
          ${_vf('Issued on',  s.issued_on)}`;
      } else {
        // Fallback: dump all keys
        credFields = Object.entries(s).filter(([k]) => k !== 'id')
          .map(([k, v]) => _vf(k.replace(/_/g,' '), v)).join('');
      }

      const TYPE_COLORS = {
        'UniversityDegreeCredential': '#1A237E',
        'InternshipCredential':        '#064e3b',
        'SkillBadgeCredential':        '#92400e',
      };
      const bannerColor = TYPE_COLORS[vcType] || '#1A237E';

      verifierState.lastVerifiedId = verificationId;

      resultCard.innerHTML = `
        <div style="border-radius:12px; overflow:hidden; border:1px solid var(--border); box-shadow:0 4px 20px rgba(0,0,0,0.08);">
          <!-- Banner -->
          <div style="background:${bannerColor}; padding:1rem 1.25rem; display:flex; align-items:center; justify-content:space-between; gap:0.75rem;">
            <div style="display:flex; align-items:center; gap:0.75rem;">
              <div style="font-size:1.5rem;">✅</div>
              <div>
                <div style="font-weight:700; color:#fff; font-size:1.05rem;">Verification Successful</div>
                <div style="font-size:0.78rem; color:rgba(255,255,255,0.7);">Proof received and cryptographically verified</div>
              </div>
            </div>
            <button class="btn btn-sm" onclick="previewVerifierCert('${verificationId}')" style="background:rgba(255,255,255,0.18); color:#fff; border:1px solid rgba(255,255,255,0.35); white-space:nowrap;">🎓 View Certificate</button>
          </div>
          <!-- Fields grid -->
          <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); background:var(--bg-card);">
            ${credFields}
          </div>
          <!-- Footer: issuer + holder DID -->
          <div style="display:grid; grid-template-columns:1fr 2fr; border-top:1px solid var(--border); background:var(--bg-secondary);">
            <div style="padding:0.75rem 1rem; border-right:1px solid var(--border);">
              <div style="font-size:0.6rem; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:var(--text-muted); margin-bottom:0.2rem;">Issuer</div>
              <div style="font-size:0.85rem; font-weight:600;">IIT Hyderabad</div>
            </div>
            <div style="padding:0.75rem 1rem;">
              <div style="font-size:0.6rem; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:var(--text-muted); margin-bottom:0.2rem;">Holder DID</div>
              <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; overflow-wrap:anywhere; color:var(--text-secondary);">${cert.holder_did || '—'}</div>
            </div>
          </div>
        </div>
      `;
      toast('Verification Completed!', 'success');
      resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      loadVerifierHistory();
      loadVwRecentSessions();
      updateVerifierHeroStats();
    } else if (data.status === 'expired') {
      clearInterval(verifierPollingInterval);
      verifierPollingInterval = null;
      if (verifierState.countdownInterval) {
        clearInterval(verifierState.countdownInterval);
        verifierState.countdownInterval = null;
      }
      const scanStatus = document.getElementById('verifier-scan-status');
      if (scanStatus) scanStatus.innerHTML = '<span style="color:var(--error);">QR expired. Generate a new request.</span>';
      const countdown = document.getElementById('vw-countdown');
      if (countdown) countdown.textContent = 'Expired';
      const dot = document.getElementById('vw-session-dot');
      if (dot) dot.className = 'vw-session-dot';
    }
  } catch (e) {
    console.error("Polling error:", e);
  }
}

async function verifyManual() {
  const vcJwt = document.getElementById('verify-vc-jwt').value.trim();
  if (!vcJwt) return toast('Paste a VC JWT', 'error');

  try {
    // Legacy endpoint still works if we keep it, but OID4VP is preferred.
    // For now, let's just decode it locally to show we can see the data.
    const payload = JSON.parse(atob(vcJwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    document.getElementById('verify-result').innerHTML = `
      <div style="padding:0.75rem;background:var(--success-bg);border:1px solid rgba(16,185,129,0.3);border-radius:var(--radius-sm);">
        <span style="color:var(--success);font-weight:600;">✓ JWT Decoded (Local Preview)</span>
        <pre style="font-size:0.7rem; margin-top:0.5rem; overflow:auto;">${JSON.stringify(payload, null, 2)}</pre>
      </div>`;
    toast('Manual check complete', 'success');
  } catch (e) {
    toast('Invalid JWT format', 'error');
  }
}

async function updateVerifierHeroStats() {
  try {
    const sessions = await api('GET', '/verifier/sessions');
    const today = new Date().toDateString();
    const todaySessions = sessions.filter(s => s.created_at && new Date(s.created_at).toDateString() === today);
    const verified = todaySessions.filter(s => s.status === 'VERIFIED').length;
    const rejected = todaySessions.filter(s => s.status === 'EXPIRED' || s.status === 'REJECTED').length;
    const el = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    el('vw-stat-sessions', todaySessions.length);
    el('vw-stat-verified', verified);
    el('vw-stat-rejected', rejected);
  } catch (_) {}
}

/* ── Verifier: History ────────────────────────────────────────────────── */

async function loadVerifierHistory() {
  try {
    const sessions = await api('GET', '/verifier/sessions');
    if (sessions.length === 0) {
      document.getElementById('verifier-history-list').innerHTML = `
        <div class="empty-state"><div class="icon">📋</div><p>No verification sessions yet</p></div>`;
      return;
    }

    const statusBadge = (s) => {
      if (s === 'VERIFIED') return '<span class="badge badge-success">✓ Verified</span>';
      if (s === 'EXPIRED') return '<span class="badge badge-warning">Expired</span>';
      return '<span class="badge badge-info">Pending</span>';
    };

    document.getElementById('verifier-history-list').innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Verification ID</th>
            <th>Student</th>
            <th>Summary</th>
            <th>Status</th>
            <th>Date</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${sessions.map(s => `
            <tr>
              <td><a href="#" onclick="viewVerificationDetail('${s.verification_id}', this);return false;" style="color:var(--accent);text-decoration:none;cursor:pointer;"><span class="mono" style="font-size:0.75rem;">${s.verification_id}</span></a></td>
              <td><strong>${s.student_name || '—'}</strong><br><span style="font-size:0.65rem;color:var(--text-secondary);overflow-wrap:anywhere;">${s.holder_did || '—'}</span></td>
              <td style="font-size:0.85rem;">${s.summary || '—'}</td>
              <td>${statusBadge(s.status)}</td>
              <td style="font-size:0.75rem;">${s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}</td>
              <td>${s.status === 'VERIFIED' ? `<button class="btn btn-outline btn-sm" onclick="previewVerifierCert('${s.verification_id}')">🎓 Preview</button>` : ''}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (e) {
    document.getElementById('verifier-history-list').innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
  }
}

/* ── Verifier: View detail from history ───────────────────────────────── */

async function viewVerificationDetail(vId, el) {
  const existing = document.getElementById('verification-detail-panel');
  if (existing && existing.dataset.vId === vId) {
    existing.remove();
    return;
  }
  if (existing) existing.remove();

  try {
    const data = await api('GET', `/verifications/${vId}`);
    const isVerified = data.status === 'verified';
    
    const panel = document.createElement('div');
    panel.id = 'verification-detail-panel';
    panel.dataset.vId = vId;
    panel.className = 'card';
    panel.style.cssText = 'margin-top:1rem;animation:fadeIn 0.2s ease; border: 1px solid var(--border);';
    
    if (!isVerified) {
      panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:600; color:var(--text-secondary);">Session: ${vId} (${data.status.toUpperCase()})</span>
          <button class="btn btn-outline btn-sm" onclick="this.closest('#verification-detail-panel').remove()">✕ Close</button>
        </div>
        <div style="margin-top:1rem; text-align:center; padding:1.5rem; color:var(--text-muted);">
           No verified data available for this session.
        </div>
      `;
    } else {
      const cert = data.data || {};
      const subject = cert.subject_data || {};
      
      panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem; border-bottom:1px solid var(--border); padding-bottom:0.75rem;">
          <div>
            <span style="font-weight:700; color:var(--success); font-size:1.1rem;">✅ Verified Proof</span>
            <span class="mono" style="font-size:0.7rem; color:var(--text-muted); margin-left:1rem;">ID: ${vId}</span>
          </div>
          <div style="display:flex;gap:0.5rem;">
            <button class="btn btn-primary btn-sm" onclick="previewVerifierCert('${vId}')">🎓 View Certificate</button>
            <button class="btn btn-outline btn-sm" onclick="this.closest('#verification-detail-panel').remove()">✕ Close</button>
          </div>
        </div>
        
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:1.25rem;">
          <div>
            <label class="form-label" style="font-size:0.65rem;">Credential Type</label>
            <div style="font-weight:600;">${cert.vc_type}</div>
          </div>
          <div>
            <label class="form-label" style="font-size:0.65rem;">Issuer</label>
            <div style="font-weight:600;">IIT Hyderabad</div>
          </div>
          <div style="grid-column: 1 / -1;">
            <label class="form-label" style="font-size:0.65rem;">Holder DID</label>
            <div class="mono" style="font-size:0.7rem; background:var(--bg-secondary); padding:0.6rem; border-radius:6px; overflow-wrap:anywhere;">${cert.holder_did}</div>
          </div>
        </div>

        <div style="margin-top:1.25rem; padding:1.25rem; background:white; border:1px solid var(--border); border-radius:10px;">
           <div style="font-weight:700; margin-bottom:0.75rem; color:var(--primary); font-size:0.9rem;">Decoded Subject Information</div>
           <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem; font-size:0.85rem;">
              ${Object.entries(subject).map(([k, v]) => {
                if (typeof v === 'object') return ''; 
                return `<div><span style="color:var(--text-muted);">${k}:</span> <strong style="color:var(--text-main);">${v}</strong></div>`;
              }).join('')}
           </div>
        </div>
      `;
    }
    
    // Insert after the history list card
    const historyCard = document.getElementById('verifier-history-list').closest('.card');
    historyCard.parentNode.insertBefore(panel, historyCard.nextSibling);
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ── Event listeners ──────────────────────────────────────────────────── */

document.getElementById('btn-login').addEventListener('click', login);
document.getElementById('btn-register').addEventListener('click', register);
document.getElementById('login-username').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('login-password').focus(); });
document.getElementById('login-password').addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
document.getElementById('reg-password').addEventListener('keydown', e => { if (e.key === 'Enter') register(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeAdminMenu(); closeStudentMenu(); closeVerifierMenu(); closeStudentOfferQr(); } });
if (document.getElementById('btn-issue-vc')) {
  document.getElementById('btn-issue-vc').addEventListener('click', issueVC);
}

/* ── Session restore ──────────────────────────────────────────────────── */

(function init() {
  const savedToken = localStorage.getItem('token');
  const savedRole = localStorage.getItem('role');
  const savedUsername = localStorage.getItem('username');

  if (savedToken && savedRole) {
    token = savedToken;
    role = savedRole;
    routeToView(savedUsername || 'User');
  }
})();
