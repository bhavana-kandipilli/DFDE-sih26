/**
 * Digital Field Drug Evidence System - Forensic Analyst Portal Logic
 * Real-Time, Zero-Mock Production Implementation
 * Matches Mockup Design: Screen 3 (Clean & Clear Analyst Dashboard)
 */

class ForensicAnalystApp {
  constructor() {
    this.currentView = 'viewLogin';
    this.previousView = 'viewDashboard';
    this.token = localStorage.getItem('dfde_analyst_token') || null;
    this.analyst = JSON.parse(localStorage.getItem('dfde_analyst_info') || 'null');
    
    this.allCases = [];
    this.allEvidence = [];
    this.activeCase = null;
    this.activeEvidence = null;
    this.currentCertificate = null;

    this.initElements();
    this.bindEvents();
    this.checkSession();
  }

  initElements() {
    this.appMainLayout = document.getElementById('appMainLayout');
    this.views = {
      viewLogin: document.getElementById('viewLogin'),
      viewDashboard: document.getElementById('viewDashboard'),
      viewCasesList: document.getElementById('viewCasesList'),
      viewEvidenceList: document.getElementById('viewEvidenceList'),
      viewProfile: document.getElementById('viewProfile'),
      viewCaseDetails: document.getElementById('viewCaseDetails'),
      viewEvidenceViewer: document.getElementById('viewEvidenceViewer')
    };

    this.navDashboard = document.getElementById('navDashboard');
    this.navCases = document.getElementById('navCases');
    this.navEvidence = document.getElementById('navEvidence');
    this.navProfile = document.getElementById('navProfile');

    this.analystDisplayName = document.getElementById('analystDisplayName');
    this.analystDeptDisplay = document.getElementById('analystDeptDisplay');
    this.userAvatarInitials = document.getElementById('userAvatarInitials');
    this.btnLogout = document.getElementById('btnLogout');
    
    this.inputSearch = document.getElementById('inputSearch');
    this.casesTbody = document.getElementById('casesTbody');
    this.casesEmptyState = document.getElementById('casesEmptyState');
    this.casesTable = document.getElementById('casesTable');

    // New views elements
    this.allCasesListTbody = document.getElementById('allCasesListTbody');
    this.allCasesEmptyState = document.getElementById('allCasesEmptyState');
    this.evidenceListTbody = document.getElementById('evidenceListTbody');
    this.evidenceEmptyState = document.getElementById('evidenceEmptyState');
    this.statTotalEvidence = document.getElementById('statTotalEvidence');
    this.statVerifiedDigests = document.getElementById('statVerifiedDigests');
    this.statReagentsTested = document.getElementById('statReagentsTested');

    this.statTotalCases = document.getElementById('statTotalCases');
    this.statPendingReview = document.getElementById('statPendingReview');
    this.statVerified = document.getElementById('statVerified');

    this.btnTogglePassword = document.getElementById('btnTogglePassword');
    this.pwdEyeIcon = document.getElementById('pwdEyeIcon');
    this.loginPasswordInput = document.getElementById('loginPassword');

    this.modalCertificate = document.getElementById('modalCertificate');
    this.btnVerifyNow = document.getElementById('btnVerifyNow');
    this.btnGenerateCert = document.getElementById('btnGenerateCert');
    this.btnDownloadCertJson = document.getElementById('btnDownloadCertJson');
  }

  bindEvents() {
    // Login
    document.getElementById('formLogin').addEventListener('submit', (e) => {
      e.preventDefault();
      const user = document.getElementById('loginAnalystId').value.trim();
      const pass = document.getElementById('loginPassword').value;
      this.handleLogin(user, pass);
    });

    // Password Visibility Toggle
    if (this.btnTogglePassword) {
      this.btnTogglePassword.addEventListener('click', () => {
        if (this.loginPasswordInput.type === 'password') {
          this.loginPasswordInput.type = 'text';
          this.pwdEyeIcon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
        } else {
          this.loginPasswordInput.type = 'password';
          this.pwdEyeIcon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
        }
      });
    }

    // Logout
    this.btnLogout.addEventListener('click', () => this.handleLogout());

    // Search filter
    let searchTimer;
    this.inputSearch.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => this.filterCases(), 200);
    });

    // Verification & Cert Actions
    this.btnVerifyNow.addEventListener('click', () => {
      if (this.activeEvidence) this.executeCryptographicVerification(this.activeEvidence.id);
    });

    this.btnGenerateCert.addEventListener('click', () => {
      if (this.currentCertificate) this.openCertificateModal();
    });

    this.btnDownloadCertJson.addEventListener('click', () => {
      if (this.currentCertificate) this.downloadCertificateJson();
    });
  }

  fillCredentials(user, pass) {
    document.getElementById('loginAnalystId').value = user;
    document.getElementById('loginPassword').value = pass;
  }

  navTo(viewId) {
    if (viewId === 'viewLogin') {
      if (this.appMainLayout) this.appMainLayout.classList.add('hidden');
      if (this.views.viewLogin) this.views.viewLogin.classList.remove('hidden');
      this.currentView = 'viewLogin';
      window.scrollTo(0, 0);
      return;
    }

    if (this.currentView && this.currentView !== 'viewLogin') {
      this.previousView = this.currentView;
    }

    if (this.views.viewLogin) this.views.viewLogin.classList.add('hidden');
    if (this.appMainLayout) this.appMainLayout.classList.remove('hidden');

    Object.keys(this.views).forEach(k => {
      if (k !== 'viewLogin' && this.views[k]) {
        this.views[k].classList.add('hidden');
        this.views[k].classList.remove('active');
      }
    });

    if (this.views[viewId]) {
      this.views[viewId].classList.remove('hidden');
      this.views[viewId].classList.add('active');
      this.currentView = viewId;
    }

    // Update active nav item in sidebar
    if (this.navDashboard && this.navCases && this.navEvidence && this.navProfile) {
      this.navDashboard.classList.remove('active');
      this.navCases.classList.remove('active');
      this.navEvidence.classList.remove('active');
      this.navProfile.classList.remove('active');
      
      if (viewId === 'viewDashboard') {
        this.navDashboard.classList.add('active');
      } else if (viewId === 'viewCasesList' || viewId === 'viewCaseDetails') {
        this.navCases.classList.add('active');
      } else if (viewId === 'viewEvidenceList' || viewId === 'viewEvidenceViewer') {
        this.navEvidence.classList.add('active');
      } else if (viewId === 'viewProfile') {
        this.navProfile.classList.add('active');
      }
    }

    // Trigger view-specific renderers
    if (viewId === 'viewCasesList') {
      this.renderCasesList(this.allCases);
    } else if (viewId === 'viewEvidenceList') {
      this.renderEvidenceList();
    } else if (viewId === 'viewProfile') {
      this.renderProfile();
    }

    window.scrollTo(0, 0);
  }

  backFromEvidenceViewer() {
    if (this.previousView && (this.previousView === 'viewEvidenceList' || this.previousView === 'viewCasesList')) {
      this.navTo(this.previousView);
    } else if (this.activeCase) {
      this.navTo('viewCaseDetails');
    } else {
      this.navTo('viewEvidenceList');
    }
  }

  viewActiveEvidenceShortcut() {
    this.navTo('viewEvidenceList');
  }

  showProfileModal() {
    this.navTo('viewProfile');
  }

  async checkSession() {
    if (this.token) {
      try {
        const res = await fetch('/dashboard/summary', {
          headers: { 'Authorization': `Bearer ${this.token}` }
        });
        if (res.ok) {
          this.updateUserBadge();
          this.navTo('viewDashboard');
          this.loadCases();
          return;
        }
      } catch (e) {
        console.warn('Analyst session check error:', e);
      }
    }
    this.navTo('viewLogin');
  }

  async handleLogin(username, password) {
    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Login failed');
      }

      const data = await res.json();
      if (data.role === 'FIELD_OFFICER') {
        throw new Error('Access denied. Field officers must use the Field Evidence Capture application.');
      }

      this.token = data.access_token;
      this.analyst = {
        name: data.full_name || data.name || data.username,
        badge: data.badge_number || '--',
        role: data.role,
        department: data.department || '--'
      };

      localStorage.setItem('dfde_analyst_token', this.token);
      localStorage.setItem('dfde_analyst_info', JSON.stringify(this.analyst));

      this.updateUserBadge();
      this.navTo('viewDashboard');
      this.loadCases();
    } catch (err) {
      alert(`Analyst Authentication Error: ${err.message}`);
    }
  }

  handleLogout() {
    this.token = null;
    this.analyst = null;
    localStorage.removeItem('dfde_analyst_token');
    localStorage.removeItem('dfde_analyst_info');
    this.navTo('viewLogin');
  }

  updateUserBadge() {
    if (this.analyst) {
      if (this.analystDisplayName) this.analystDisplayName.textContent = this.analyst.name;
      if (this.analystDeptDisplay) this.analystDeptDisplay.textContent = this.analyst.department;
      if (this.userAvatarInitials) {
        this.userAvatarInitials.textContent = 'FA';
      }
    }
  }

  // ---------------- Dashboard & Cases ----------------

  async loadCases() {
    if (!this.token) return;
    try {
      // 1. Fetch real summary
      const sumRes = await fetch('/dashboard/summary', {
        headers: { 'Authorization': `Bearer ${this.token}` }
      });
      if (sumRes.ok) {
        const sumData = await sumRes.json();
        const total = sumData.total_cases || 0;
        const pending = sumData.pending_sync || 0;
        const verified = Math.max(0, (sumData.total_tests || 0) - (sumData.integrity_warnings_count || 0));

        if (this.statTotalCases) this.statTotalCases.textContent = total;
        if (this.statPendingReview) this.statPendingReview.textContent = pending;
        if (this.statVerified) this.statVerified.textContent = verified;
      }

      // 2. Fetch real cases
      const casesRes = await fetch('/cases', {
        headers: { 'Authorization': `Bearer ${this.token}` }
      });

      if (!casesRes.ok) throw new Error(`HTTP ${casesRes.status}`);

      this.allCases = await casesRes.json();
      this.renderCasesTable(this.allCases);
      if (this.currentView === 'viewCasesList') {
        this.renderCasesList(this.allCases);
      }
      this.loadAllEvidence();

    } catch (err) {
      console.error('Error loading cases:', err);
    }
  }

  filterCases() {
    const q = this.inputSearch.value.trim().toLowerCase();
    if (!q) {
      this.renderCasesTable(this.allCases);
      return;
    }
    const filtered = this.allCases.filter(c => 
      c.case_number.toLowerCase().includes(q) ||
      (c.incident_location && c.incident_location.toLowerCase().includes(q)) ||
      (c.notes && c.notes.toLowerCase().includes(q))
    );
    this.renderCasesTable(filtered);
  }

  renderCasesTable(cases) {
    this.casesTbody.innerHTML = '';

    if (cases.length === 0) {
      this.casesTable.classList.add('hidden');
      this.casesEmptyState.classList.remove('hidden');
      return;
    }

    this.casesTable.classList.remove('hidden');
    this.casesEmptyState.classList.add('hidden');

    cases.forEach(c => {
      const tr = document.createElement('tr');
      const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Today';
      
      // Determine presumptive result label
      let resultText = 'Pending Test';
      if (c.result_summary) {
        resultText = c.result_summary;
      } else if (c.tests && c.tests.length > 0 && c.tests[0].ai_result) {
        resultText = c.tests[0].ai_result.classification;
      }
      const cleanResult = resultText.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());

      // Integrity score
      const score = (c.integrity_score !== undefined && c.integrity_score !== null)
        ? c.integrity_score
        : (c.tests && c.tests[0] && c.tests[0].evidence && c.tests[0].evidence.integrity_score !== undefined
          ? c.tests[0].evidence.integrity_score
          : '--');

      // Status badge: Synced, Review, or Verified
      const statusStr = (c.status || 'Active').toLowerCase();
      let badgeClass = 'synced';
      let statusDisplay = 'Synced';
      if (statusStr === 'verified' || c.is_verified) {
        badgeClass = 'verified';
        statusDisplay = 'Verified';
      } else if (statusStr === 'review' || statusStr === 'pending' || statusStr === 'active') {
        badgeClass = 'review';
        statusDisplay = 'Review';
      }

      tr.style.cursor = 'pointer';
      tr.innerHTML = `
        <td style="font-weight: 700; color: var(--color-primary); font-family: var(--font-mono);">${this.escapeHtml(c.case_number)}</td>
        <td style="color: var(--text-muted); font-size: 0.85rem;">${dateStr}</td>
        <td style="font-weight: 600;">${cleanResult}</td>
        <td style="font-weight: 700;">${score !== '--' ? score + ' / 100' : '--'}</td>
        <td><span class="status-pill-badge ${badgeClass}">${statusDisplay}</span></td>
      `;
      tr.addEventListener('click', () => {
        this.openCaseDetails(c.id);
      });
      this.casesTbody.appendChild(tr);
    });
  }

  // ---------------- Cases Repository ----------------

  renderCasesList(cases) {
    if (!this.allCasesListTbody) return;
    this.allCasesListTbody.innerHTML = '';

    const list = cases || this.allCases || [];
    if (list.length === 0) {
      if (this.allCasesEmptyState) this.allCasesEmptyState.classList.remove('hidden');
      return;
    }
    if (this.allCasesEmptyState) this.allCasesEmptyState.classList.add('hidden');

    list.forEach(c => {
      const tr = document.createElement('tr');
      const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Today';
      let resultText = c.result_summary || (c.tests && c.tests.length > 0 && c.tests[0].ai_result ? c.tests[0].ai_result.classification : 'Pending Test');
      const cleanResult = resultText.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
      const score = (c.integrity_score !== undefined && c.integrity_score !== null)
        ? c.integrity_score
        : (c.tests && c.tests[0] && c.tests[0].evidence && c.tests[0].evidence.integrity_score !== undefined
          ? c.tests[0].evidence.integrity_score
          : '--');
      const statusStr = (c.status || 'Active').toLowerCase();
      let badgeClass = 'synced';
      let statusDisplay = 'Synced';
      if (statusStr === 'verified' || c.is_verified) {
        badgeClass = 'verified';
        statusDisplay = 'Verified';
      } else if (statusStr === 'review' || statusStr === 'pending' || statusStr === 'active') {
        badgeClass = 'review';
        statusDisplay = 'Review';
      }

      tr.innerHTML = `
        <td style="font-weight: 700; color: var(--color-primary); font-family: var(--font-mono);">${this.escapeHtml(c.case_number)}</td>
        <td style="color: var(--text-muted); font-size: 0.85rem;">${dateStr}</td>
        <td style="font-size: 0.85rem;">${this.escapeHtml(c.incident_location || '--')}</td>
        <td style="font-weight: 600;">${cleanResult}</td>
        <td style="font-weight: 700; color: var(--status-positive-text);">${score !== '--' ? score + ' / 100' : '--'}</td>
        <td><span class="status-pill-badge ${badgeClass}">${statusDisplay}</span></td>
        <td>
          <button class="btn btn-primary btn-sm" type="button">Review Case →</button>
        </td>
      `;
      tr.querySelector('button').addEventListener('click', (e) => {
        e.stopPropagation();
        this.openCaseDetails(c.id);
      });
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', () => {
        this.openCaseDetails(c.id);
      });
      this.allCasesListTbody.appendChild(tr);
    });
  }

  filterCasesList(query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) {
      this.renderCasesList(this.allCases);
      return;
    }
    const filtered = (this.allCases || []).filter(c =>
      (c.case_number && c.case_number.toLowerCase().includes(q)) ||
      (c.incident_location && c.incident_location.toLowerCase().includes(q)) ||
      (c.notes && c.notes.toLowerCase().includes(q))
    );
    this.renderCasesList(filtered);
  }

  // ---------------- Optical Evidence Repository ----------------

  async loadAllEvidence() {
    if (!this.allCases || this.allCases.length === 0) return;
    try {
      const evidenceRecords = [];
      const reagentsSet = new Set();
      let verifiedCount = 0;

      const detailPromises = this.allCases.map(c => 
        fetch(`/cases/${c.id}/details`, {
          headers: { 'Authorization': `Bearer ${this.token}` }
        }).then(r => r.ok ? r.json() : null).catch(() => null)
      );

      const results = await Promise.all(detailPromises);
      results.forEach(res => {
        if (!res || !res.tests) return;
        const c = res.case || {};
        res.tests.forEach(t => {
          if (t.evidence) {
            const ev = t.evidence;
            const ai = t.ai_result;
            if (t.reagent_name) reagentsSet.add(t.reagent_name);
            if (ev.integrity_score >= 80) verifiedCount++;

            evidenceRecords.push({
              id: ev.id,
              caseId: c.id,
              caseNumber: c.case_number || '--',
              reagentName: t.reagent_name || '--',
              classification: ai ? ai.classification : 'PENDING_ANALYSIS',
              confidence: ai ? ai.confidence_score : null,
              integrityScore: ev.integrity_score !== undefined ? ev.integrity_score : '--',
              payloadHash: ev.payload_hash,
              createdAt: t.created_at || c.created_at
            });
          }
        });
      });

      this.allEvidence = evidenceRecords;
      if (this.statTotalEvidence) this.statTotalEvidence.textContent = evidenceRecords.length;
      if (this.statVerifiedDigests) this.statVerifiedDigests.textContent = verifiedCount;
      if (this.statReagentsTested) this.statReagentsTested.textContent = reagentsSet.size || (evidenceRecords.length > 0 ? 1 : 0);

      if (this.currentView === 'viewEvidenceList') {
        this.renderEvidenceList();
      }
    } catch (e) {
      console.warn('Could not preload all evidence:', e);
    }
  }

  renderEvidenceList() {
    if (!this.evidenceListTbody) return;
    this.evidenceListTbody.innerHTML = '';

    const list = this.allEvidence || [];
    if (list.length === 0) {
      if (this.evidenceEmptyState) this.evidenceEmptyState.classList.remove('hidden');
      return;
    }
    if (this.evidenceEmptyState) this.evidenceEmptyState.classList.add('hidden');

    list.forEach(ev => {
      const tr = document.createElement('tr');
      const cleanResult = (ev.classification || 'Pending').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
      const confPct = ev.confidence !== null && ev.confidence !== undefined ? Math.round(ev.confidence * 100) + '%' : '--';

      tr.innerHTML = `
        <td style="font-weight: 700; color: var(--color-primary); font-family: var(--font-mono);">${this.escapeHtml(ev.id.substring(0, 10))}...</td>
        <td style="font-weight: 600; font-family: var(--font-mono);">${this.escapeHtml(ev.caseNumber)}</td>
        <td style="font-size: 0.85rem;">${this.escapeHtml(ev.reagentName)}</td>
        <td><span class="status-pill-badge verified">${cleanResult}</span></td>
        <td style="font-weight: 700;">${confPct}</td>
        <td style="font-weight: 700; color: var(--status-positive-text);">${ev.integrityScore !== '--' ? ev.integrityScore + ' / 100' : '--'}</td>
        <td>
          <button class="btn btn-primary btn-sm" type="button">Inspect Evidence →</button>
        </td>
      `;

      tr.querySelector('button').addEventListener('click', (e) => {
        e.stopPropagation();
        this.openEvidenceViewer(ev.id);
      });
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', () => {
        this.openEvidenceViewer(ev.id);
      });
      this.evidenceListTbody.appendChild(tr);
    });
  }

  // ---------------- Analyst Profile ----------------

  renderProfile() {
    const name = this.analyst ? this.analyst.name : '--';
    const badge = this.analyst ? this.analyst.badge : '--';
    const dept = this.analyst && this.analyst.department ? this.analyst.department : '--';

    const pName = document.getElementById('profName');
    const pBadge = document.getElementById('profBadge');
    const pAgency = document.getElementById('profAgency');
    const pAvatar = document.getElementById('profAvatarInitials');

    if (pName) pName.textContent = name;
    if (pBadge) pBadge.textContent = badge;
    if (pAgency) pAgency.textContent = dept;
    if (pAvatar) {
      const initials = name && name !== '--' ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'FA';
      pAvatar.textContent = initials;
    }
  }

  // ---------------- Case View ----------------

  async openCaseDetails(caseId) {
    try {
      const res = await fetch(`/cases/${caseId}/details`, {
        headers: { 'Authorization': `Bearer ${this.token}` }
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      this.activeCase = data.case;

      document.getElementById('caseDetailsTitle').textContent = `CASE ${this.activeCase.case_number}`;
      document.getElementById('detOfficer').textContent = `${data.officer_name} (${data.officer_badge})`;
      document.getElementById('detDate').textContent = new Date(this.activeCase.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
      document.getElementById('detLocation').textContent = this.activeCase.incident_location || '--';
      let statusClass = 'synced';
      const st = (this.activeCase.status || '').toUpperCase();
      if (st === 'VERIFIED') statusClass = 'verified';
      else if (st === 'REVIEW') statusClass = 'review';
      document.getElementById('detStatus').innerHTML = `<span class="status-pill-badge ${statusClass}">${this.escapeHtml(this.activeCase.status || 'Active')}</span>`;

      const evContainer = document.getElementById('detEvidenceContainer');
      evContainer.innerHTML = '';

      const tests = data.tests || [];
      let foundEvidence = false;

      tests.forEach((t, idx) => {
        const ev = t.evidence;
        const ai = t.ai_result;

        if (ev) {
          foundEvidence = true;
          const card = document.createElement('div');
          card.style.background = '#ffffff';
          card.style.border = '1px solid var(--border-color)';
          card.style.borderRadius = 'var(--radius-md)';
          card.style.padding = '1rem 1.25rem';
          card.style.display = 'flex';
          card.style.justifyContent = 'space-between';
          card.style.alignItems = 'center';
          card.style.marginBottom = '0.5rem';

          const classText = ai ? ai.classification.replace(/_/g, ' ') : 'Pending AI Analysis';
          const integ = ev.integrity_score !== undefined && ev.integrity_score !== null ? ev.integrity_score : '--';

          card.innerHTML = `
            <div>
              <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-main);">Evidence 0${idx + 1}: ${this.escapeHtml(t.reagent_name)}</div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                Result: <strong style="color: var(--color-primary);">${classText}</strong> | Integrity: <strong>${integ} / 100</strong> | Hash: <span class="font-mono">${ev.payload_hash.substring(0, 12)}...</span>
              </div>
            </div>
            <div>
              <button class="btn btn-primary btn-sm" type="button">Review Evidence →</button>
            </div>
          `;

          card.querySelector('button').addEventListener('click', () => {
            this.openEvidenceViewer(ev.id);
          });
          evContainer.appendChild(card);
        }
      });

      if (!foundEvidence) {
        evContainer.innerHTML = `
          <div class="clean-empty-state" style="padding: 2rem;">
            <p style="color: var(--text-muted);">No finalized evidence records submitted for this case yet.</p>
          </div>
        `;
      }

      this.navTo('viewCaseDetails');
    } catch (err) {
      alert(`Could not load case details: ${err.message}`);
    }
  }

  // ---------------- Evidence Viewer ----------------

  async openEvidenceViewer(evidenceId) {
    try {
      const res = await fetch(`/evidence/${evidenceId}/certificate`, {
        headers: { 'Authorization': `Bearer ${this.token}` }
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const cert = await res.json();
      this.currentCertificate = cert;
      this.activeEvidence = { id: evidenceId, ...cert };

      document.getElementById('evViewerSubtitle').textContent = `Evidence ID: ${evidenceId}`;

      // Images (Raw, Calibrated, Reaction Patch)
      const rawUrl = cert.original_image_path ? (cert.original_image_path.startsWith('/') ? cert.original_image_path : `/static/${cert.original_image_path}`) : '';
      const calibUrl = cert.calibrated_image_path ? (cert.calibrated_image_path.startsWith('/') ? cert.calibrated_image_path : `/static/${cert.calibrated_image_path}`) : rawUrl;
      const patchUrl = cert.patch_image_path ? (cert.patch_image_path.startsWith('/') ? cert.patch_image_path : `/static/${cert.patch_image_path}`) : rawUrl;

      document.getElementById('evImgRaw').src = rawUrl;
      document.getElementById('evImgCalib').src = calibUrl;
      document.getElementById('evImgPatch').src = patchUrl;

      // AI Analysis
      const resObj = cert.result || {};
      const classStr = resObj.classification ? resObj.classification.replace(/_/g, ' ') : 'PRESUMPTIVE RESULT';
      document.getElementById('evClassification').textContent = classStr;
      document.getElementById('evSubstanceName').textContent = cert.test_type || 'Presumptive Test';
      
      const confVal = resObj.confidence !== undefined ? resObj.confidence : (resObj.confidence_score !== undefined ? resObj.confidence_score : null);
      document.getElementById('evConfidence').textContent = confVal !== null ? `${Math.round(confVal * 100)}%` : '--%';

      // Integrity
      const integScore = cert.evidence_integrity ? cert.evidence_integrity.score : (cert.integrity_score !== undefined ? cert.integrity_score : null);
      document.getElementById('evIntegrityScore').textContent = integScore !== null ? `${integScore} / 100` : '--';

      // SHA-256 Hash
      const hashes = cert.cryptographic_hashes || {};
      const rawSha = hashes.raw_image_sha256 || cert.payload_hash || '--';
      document.getElementById('evSha256Box').textContent = rawSha;
      document.getElementById('evHashVerificationNotice').classList.add('hidden');

      this.navTo('viewEvidenceViewer');
    } catch (err) {
      alert(`Evidence retrieval error: ${err.message}`);
    }
  }

  async executeCryptographicVerification(evidenceId) {
    try {
      const res = await fetch(`/evidence/${evidenceId}/verify`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${this.token}` }
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      document.getElementById('evSha256Box').textContent = data.stored_payload_hash;

      const notice = document.getElementById('evHashVerificationNotice');
      if (!data.is_tampered && data.image_intact) {
        notice.textContent = '✓ HASH MATCH: Cryptographic integrity confirmed against original upload digest.';
        notice.style.color = 'var(--status-positive-text)';
        notice.classList.remove('hidden');
      } else {
        notice.textContent = '⚠️ HASH MISMATCH: File alteration or byte tampering detected!';
        notice.style.color = 'var(--color-danger)';
        notice.classList.remove('hidden');
      }
    } catch (err) {
      alert(`Verification check error: ${err.message}`);
    }
  }

  // ---------------- Digital Certificate ----------------

  openCertificateModal() {
    const cert = this.currentCertificate;
    if (!cert) return;

    document.getElementById('certId').textContent = cert.certificate_id || '--';
    document.getElementById('certDate').textContent = cert.timestamp ? new Date(cert.timestamp).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Today';
    document.getElementById('certCaseRef').textContent = cert.case_id || (this.activeCase ? this.activeCase.case_number : '--');
    document.getElementById('certOfficer').textContent = cert.officer ? `${cert.officer.name} (${cert.officer.badge_number})` : 'Officer';
    document.getElementById('certLocation').textContent = this.activeCase ? this.activeCase.incident_location : 'Field Operation';
    document.getElementById('certReagent').textContent = cert.test_type || 'Presumptive Test';

    const resObj = cert.result || {};
    const classStr = resObj.classification ? resObj.classification.replace(/_/g, ' ') : 'PRESUMPTIVE RESULT';
    document.getElementById('certResultText').textContent = classStr;
    const certConf = resObj.confidence !== undefined ? resObj.confidence : (resObj.confidence_score !== undefined ? resObj.confidence_score : null);
    document.getElementById('certConfidence').textContent = certConf !== null ? `${Math.round(certConf * 100)}%` : '--%';

    const hashes = cert.cryptographic_hashes || {};
    document.getElementById('certSha256').textContent = hashes.raw_image_sha256 || cert.payload_hash || '--';

    const integScore = cert.evidence_integrity ? cert.evidence_integrity.score : (cert.integrity_score !== undefined ? cert.integrity_score : null);
    document.getElementById('certIntegrityScore').textContent = integScore !== null ? integScore : '--';

    this.modalCertificate.classList.add('active');
  }

  closeCertificateModal() {
    this.modalCertificate.classList.remove('active');
  }

  downloadCertificateJson() {
    if (!this.currentCertificate) return;
    const str = JSON.stringify(this.currentCertificate, null, 2);
    const blob = new Blob([str], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.currentCertificate.certificate_id || 'evidence_certificate'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Global initialization
let analystApp;
document.addEventListener('DOMContentLoaded', () => {
  analystApp = new ForensicAnalystApp();
});
