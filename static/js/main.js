// ==========================================================================
// South Dumdum Enclave Residents' Association (SDDRA)
// Master Interactivity, Real-time Live Search & Dynamic Component Handlers
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Light / Dark Theme Switcher
    initThemeSwitcher();

    // 2. Initialize Mobile Navigation Menu Toggle
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const mobileDrawer = document.getElementById('mobileNavDrawer');
    const mobileIcon = document.getElementById('mobileMenuIcon');

    if (mobileBtn && mobileDrawer) {
        mobileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = mobileDrawer.classList.toggle('active');
            if (mobileIcon) {
                mobileIcon.textContent = isOpen ? '✕' : '☰';
            }
        });

        // Close mobile drawer when clicking outside
        document.addEventListener('click', (e) => {
            if (!mobileDrawer.contains(e.target) && !mobileBtn.contains(e.target)) {
                if (mobileDrawer.classList.contains('active')) {
                    mobileDrawer.classList.remove('active');
                    if (mobileIcon) mobileIcon.textContent = '☰';
                }
            }
        });
    }

    // 3. Auto-dismiss flash alerts after 6 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 400);
        }, 6000);
    });

    // 4. Escape key listener for Modals & Drawers
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-backdrop.active').forEach(m => {
                m.classList.remove('active');
            });
            if (mobileDrawer && mobileDrawer.classList.contains('active')) {
                mobileDrawer.classList.remove('active');
                if (mobileIcon) mobileIcon.textContent = '☰';
            }
            document.body.style.overflow = 'auto';
        }
    });

    // 5. Initialize Live Instant Tables Search if present
    initGenericLiveSearch();
});

// ================= Theme Switcher (Light / Dark Mode) =================
function initThemeSwitcher() {
    const savedTheme = localStorage.getItem('sddra_theme') || 
        (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    
    applyTheme(savedTheme);

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
            const icon = btn.querySelector('.theme-toggle-icon') || btn.querySelector('span') || btn;
            if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
            btn.title = theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode';
        });
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    }

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-toggle-btn');
        if (btn) {
            e.preventDefault();
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
            try {
                localStorage.setItem('sddra_theme', newTheme);
            } catch (err) {}
        }
    });
}

// ================= Modal Dialog Controller =================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}

window.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-backdrop')) {
        e.target.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
});

// ================= Client-Side Live Instant Search Engine =================
function initGenericLiveSearch() {
    const searchInputs = document.querySelectorAll('[data-live-search]');
    searchInputs.forEach(input => {
        const targetTableSelector = input.getAttribute('data-live-search');
        const counterTarget = input.getAttribute('data-search-counter');
        const clearBtnId = input.getAttribute('data-clear-btn');
        const clearBtn = clearBtnId ? document.getElementById(clearBtnId) : null;
        const table = document.querySelector(targetTableSelector);

        if (!table) return;

        function performFilter() {
            if (typeof window.applyExpenditureFilters === 'function' && 
                (targetTableSelector === '#adminRecentExpensesTable' || 
                 targetTableSelector === '#expensesTable' || 
                 targetTableSelector === '#memberExpensesTable')) {
                const rawQuery = input.value.trim();
                if (clearBtn) {
                    clearBtn.style.display = rawQuery.length > 0 ? 'block' : 'none';
                }
                window.applyExpenditureFilters(false);
                return;
            }

            const rawQuery = input.value.trim().toLowerCase();
            const cleanQuery = rawQuery.replace(/[\/\-\s_,\.]/g, '');
            const tokens = rawQuery.split(/\s+/).filter(t => t.length > 0);

            const rows = table.querySelectorAll('tbody tr');
            let matchCount = 0;
            let totalRows = 0;

            if (clearBtn) {
                clearBtn.style.display = rawQuery.length > 0 ? 'block' : 'none';
            }

            rows.forEach(row => {
                // Ignore empty-state rows
                if (row.children.length === 1 && row.children[0].getAttribute('colspan')) {
                    return;
                }
                totalRows++;

                if (!rawQuery) {
                    row.style.display = '';
                    matchCount++;
                    return;
                }

                const rowRawText = row.textContent.toLowerCase();
                const rowCleanText = rowRawText.replace(/[\/\-\s_,\.]/g, '');

                // Match 1: Exact substring in raw text
                const rawSubstringMatch = rowRawText.includes(rawQuery);

                // Match 2: Punctuation-agnostic match (e.g. 'A4C' or 'A 4 C' matches 'Flat A/4-C')
                const cleanMatch = cleanQuery.length > 0 && rowCleanText.includes(cleanQuery);

                // Match 3: All search tokens appear anywhere in row
                const allTokensMatch = tokens.length > 0 && tokens.every(token => {
                    const cleanToken = token.replace(/[\/\-\s_,\.]/g, '');
                    return rowRawText.includes(token) || (cleanToken.length > 0 && rowCleanText.includes(cleanToken));
                });

                if (rawSubstringMatch || cleanMatch || allTokensMatch) {
                    row.style.display = '';
                    matchCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            if (counterTarget) {
                const counterEl = document.querySelector(counterTarget);
                if (counterEl) {
                    if (rawQuery) {
                        counterEl.textContent = `${matchCount} of ${totalRows} Shown`;
                    } else {
                        counterEl.textContent = `${totalRows} Records`;
                    }
                }
            }
        }

        // Attach listeners across all input events
        input.addEventListener('input', performFilter);
        input.addEventListener('keyup', performFilter);
        input.addEventListener('change', performFilter);
        input.addEventListener('search', performFilter);

        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                input.value = '';
                performFilter();
                input.focus();
            });
        }

        // Run immediately if input has pre-filled value
        if (input.value) {
            performFilter();
        }
    });
}

// ================= AJAX Receipt Dispatcher =================
async function emailReceiptAjax(receiptId, btnElement) {
    if (!btnElement) return;
    
    const originalText = btnElement.innerHTML;
    btnElement.disabled = true;
    btnElement.innerHTML = '✉️ Sending...';
    
    try {
        const response = await fetch(`/receipts/${receiptId}/email`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
        
        let data;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        } else {
            const text = await response.text();
            data = {
                success: response.ok,
                message: response.ok ? 'Receipt processed successfully.' : `Server returned error (${response.status})`
            };
        }
        
        if (data && data.success) {
            btnElement.innerHTML = '✓ Sent!';
            btnElement.classList.remove('btn-outline-primary', 'btn-secondary');
            btnElement.classList.add('btn-success');
            showToast(data.message || `Receipt #${receiptId} dispatched.`, 'success');
            setTimeout(() => {
                btnElement.innerHTML = originalText;
                btnElement.disabled = false;
                btnElement.classList.remove('btn-success');
            }, 3000);
        } else {
            btnElement.innerHTML = originalText;
            btnElement.disabled = false;
            showToast(data.message || 'Could not complete receipt email dispatch.', 'danger');
        }
    } catch (err) {
        btnElement.innerHTML = originalText;
        btnElement.disabled = false;
        showToast(`Request failed: ${err.message || 'Unable to connect to server.'}`, 'danger');
    }
}

// ================= Toast Notifications =================
function showToast(message, type = 'info') {
    let container = document.querySelector('.alerts-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'alerts-container';
        const wrapper = document.querySelector('.main-wrapper');
        if (wrapper) {
            wrapper.insertBefore(container, wrapper.firstChild);
        }
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button type="button" class="close-btn" onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(alert);
    
    setTimeout(() => {
        alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        setTimeout(() => alert.remove(), 400);
    }, 5000);
}

// ================= Modal Edit Member Helper =================
function populateEditMember(id, name, email, phone, role, sqFeet) {
    const form = document.getElementById('editMemberForm');
    if (form) {
        form.action = `/admin/members/${id}/edit`;
        if (document.getElementById('edit_name')) document.getElementById('edit_name').value = name;
        if (document.getElementById('edit_email')) document.getElementById('edit_email').value = email;
        if (document.getElementById('edit_phone')) document.getElementById('edit_phone').value = phone;
        if (document.getElementById('edit_role')) document.getElementById('edit_role').value = role;
        if (document.getElementById('edit_sq_feet')) document.getElementById('edit_sq_feet').value = sqFeet;
        openModal('editMemberModal');
    }
}

// ================= In-Panel Member Receipts Modal =================
function getOrCreateMemberReceiptsModal() {
    let modal = document.getElementById('memberReceiptsModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'memberReceiptsModal';
        modal.className = 'modal-overlay';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="modal-container">
                <div class="modal-header">
                    <div>
                        <h3 class="card-title" id="modalFlatTitle" style="margin: 0; font-size: 1.2rem;">📄 Flat Maintenance Receipts</h3>
                        <p id="modalFlatSubtitle" class="text-muted" style="margin: 0.25rem 0 0; font-size: 0.85rem;"></p>
                    </div>
                    <button type="button" class="btn btn-sm btn-secondary" onclick="closeMemberReceiptsModal()" style="font-size: 1.2rem; padding: 0.2rem 0.6rem; line-height: 1;">&times;</button>
                </div>
                <div class="modal-body" id="modalReceiptsBody">
                    <div style="text-align: center; padding: 2.5rem;" class="text-muted">
                        <div class="spinner" style="display: inline-block; width: 2rem; height: 2rem; border: 3px solid rgba(59, 130, 246, 0.2); border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                        <p style="margin-top: 0.75rem;">Loading member receipts...</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <span id="modalTotalPaidBadge" class="badge badge-success" style="font-size: 0.9rem;"></span>
                    <div style="display: flex; gap: 0.5rem;">
                        <a id="modalFullLedgerLink" href="#" class="btn btn-sm btn-outline-primary">Open in Full Ledger &rarr;</a>
                        <button type="button" class="btn btn-sm btn-secondary" onclick="closeMemberReceiptsModal()">Close</button>
                    </div>
                </div>
            </div>
        `;
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeMemberReceiptsModal();
        });
        document.body.appendChild(modal);
    }
    return modal;
}

async function openMemberReceiptsModal(flatNo, memberName) {
    if (!flatNo) return;
    const modal = getOrCreateMemberReceiptsModal();

    document.getElementById('modalFlatTitle').innerHTML = `📄 Maintenance Receipts: <strong class="text-highlight-blue">Flat ${flatNo}</strong>`;
    document.getElementById('modalFlatSubtitle').textContent = `Official Registered Member: ${memberName || 'Resident'}`;
    document.getElementById('modalFullLedgerLink').href = `/admin/receipts?flat=${encodeURIComponent(flatNo)}`;
    document.getElementById('modalTotalPaidBadge').textContent = 'Calculating...';
    
    const bodyEl = document.getElementById('modalReceiptsBody');
    bodyEl.innerHTML = `
        <div style="text-align: center; padding: 2.5rem;" class="text-muted">
            <div class="spinner" style="display: inline-block; width: 2rem; height: 2rem; border: 3px solid rgba(59, 130, 246, 0.2); border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
            <p style="margin-top: 0.75rem;">Fetching official receipts for Flat ${flatNo} from database...</p>
        </div>
    `;
    
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    try {
        const res = await fetch(`/api/member-receipts?flat=${encodeURIComponent(flatNo)}`);
        const data = await res.json();

        if (!data.success || !data.receipts || data.receipts.length === 0) {
            bodyEl.innerHTML = `
                <div style="text-align: center; padding: 2.5rem;" class="text-muted">
                    <p style="font-size: 1.05rem; margin-bottom: 0.5rem;">No payment receipts recorded yet for Flat ${flatNo}.</p>
                    <a href="/admin/receipts?flat=${encodeURIComponent(flatNo)}" class="btn btn-sm btn-primary">➕ Issue First Receipt</a>
                </div>
            `;
            document.getElementById('modalTotalPaidBadge').textContent = '₹ 0.00 Total Paid';
            return;
        }

        document.getElementById('modalTotalPaidBadge').textContent = `Total Paid: ₹ ${Number(data.total_paid || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

        let rowsHtml = data.receipts.map(r => `
            <tr>
                <td><strong class="text-highlight-blue">#${r.receipt_no}</strong></td>
                <td class="text-secondary">${r.payment_date || r.receipt_date || '-'}</td>
                <td><span class="badge badge-warning">${r.remarks || 'Monthly'}</span></td>
                <td><span class="badge badge-info">${r.pymnt_mode || 'Online'}</span></td>
                <td><strong class="text-amount-success">₹ ${parseFloat(r.amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
                <td>
                    <div style="display: flex; gap: 0.35rem;">
                        <a href="/receipts/${r.receipt_no}" class="btn btn-sm btn-secondary" title="View & Print Official Voucher">📄 View</a>
                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="emailReceiptAjax(${r.receipt_no}, this)" title="Email Receipt">✉️</button>
                    </div>
                </td>
            </tr>
        `).join('');

        bodyEl.innerHTML = `
            <div class="table-container" style="max-height: 420px; overflow-y: auto;">
                <table class="custom-table">
                    <thead>
                        <tr>
                            <th>Receipt #</th>
                            <th>Date</th>
                            <th>Coverage / Period</th>
                            <th>Mode</th>
                            <th>Amount</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        bodyEl.innerHTML = `
            <div class="alert alert-danger" style="margin: 1rem 0;">
                Failed to load receipts: ${err.message}. <a href="/admin/receipts?flat=${encodeURIComponent(flatNo)}" class="text-highlight-blue">Open in Ledger instead &rarr;</a>
            </div>
        `;
    }
}

function closeMemberReceiptsModal() {
    const modal = document.getElementById('memberReceiptsModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
}

// Global click event delegation for member receipt buttons
document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.btn-view-member-receipts');
    if (trigger) {
        e.preventDefault();
        const flatNo = trigger.getAttribute('data-flat-no');
        const memberName = trigger.getAttribute('data-member-name');
        openMemberReceiptsModal(flatNo, memberName);
    }
});

// Escape key closes modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeMemberReceiptsModal();
        if (typeof window.closeBreakdownModal === 'function') window.closeBreakdownModal();
        if (typeof window.closePenaltySimulatorModal === 'function') window.closePenaltySimulatorModal();
    }
});

// ================= Penalty Breakdown Modal Controller =================
function getOrCreateBreakdownModal() {
    let modal = document.getElementById('breakdownModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'breakdownModal';
        modal.className = 'modal-overlay';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="modal-container">
                <div class="modal-header">
                    <div>
                        <h3 class="card-title" id="bdFlatTitle" style="margin: 0; font-size: 1.2rem;">🧮 Penalty Calculation Breakdown</h3>
                        <p id="bdFlatSubtitle" class="text-muted" style="margin: 0.25rem 0 0; font-size: 0.85rem;"></p>
                    </div>
                    <button type="button" class="btn btn-sm btn-secondary" onclick="closeBreakdownModal()" style="font-size: 1.2rem; padding: 0.2rem 0.6rem; line-height: 1;">&times;</button>
                </div>
                <div class="modal-body" id="bdModalBody"></div>
                <div class="modal-footer">
                    <a id="bdReceiptLink" href="#" class="btn btn-sm btn-primary">➕ Issue Receipt with Penalty &rarr;</a>
                    <button type="button" class="btn btn-sm btn-secondary" onclick="closeBreakdownModal()">Close</button>
                </div>
            </div>
        `;
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeBreakdownModal();
        });
        document.body.appendChild(modal);
    }
    return modal;
}

window.openBreakdownModal = function(flatNo, memberName, monthlyRate, lastCovered, overdueMonths, baseDue, penaltyAmount, totalDue) {
    const modal = getOrCreateBreakdownModal();
    if (!modal) return;

    flatNo = flatNo || '-';
    memberName = memberName || 'Resident';
    monthlyRate = parseFloat(monthlyRate) || 0;
    lastCovered = lastCovered || 'None';
    overdueMonths = parseInt(overdueMonths) || 0;
    baseDue = parseFloat(baseDue) || 0;
    penaltyAmount = parseFloat(penaltyAmount) || 0;
    totalDue = parseFloat(totalDue) || 0;

    const titleEl = document.getElementById('bdFlatTitle');
    if (titleEl) titleEl.innerHTML = `🧮 Penalty Breakdown: <strong class="text-highlight-blue">Flat ${flatNo}</strong>`;
    
    const subEl = document.getElementById('bdFlatSubtitle');
    if (subEl) subEl.textContent = `Member: ${memberName} • Monthly Rate: ₹ ${Number(monthlyRate).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    
    const rcptLink = document.getElementById('bdReceiptLink');
    if (rcptLink) rcptLink.href = `/admin/receipts?flat=${encodeURIComponent(flatNo)}`;

    let ladderHtml = '';
    let cumPen = 0;
    let runningTotal = 0;

    for (let i = 1; i <= overdueMonths; i++) {
        const mPen = i * 100;
        cumPen += mPen;
        runningTotal = (i * monthlyRate) + cumPen;
        ladderHtml += `
            <tr>
                <td><strong>Month ${i}</strong></td>
                <td>₹ ${Number(monthlyRate).toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                <td><span class="badge badge-warning">+ ₹ ${mPen}</span></td>
                <td><strong class="text-amount-danger">₹ ${cumPen.toLocaleString('en-IN')}</strong></td>
                <td><strong class="text-main">₹ ${runningTotal.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
            </tr>
        `;
    }

    if (overdueMonths === 0) {
        ladderHtml = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 2rem;" class="text-muted">
                    🟢 This flat is currently fully up to date or in advance. No overdue penalties accrued.
                </td>
            </tr>
        `;
    }

    const bodyEl = document.getElementById('bdModalBody');
    if (bodyEl) {
        bodyEl.innerHTML = `
            <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; background: var(--surface-hover); padding: 1rem 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--surface-border);">
                <div style="flex: 1; min-width: 140px;">
                    <span class="text-muted" style="font-size: 0.75rem;">Last Covered Month</span>
                    <strong class="text-main" style="display: block; font-size: 1rem;">${lastCovered}</strong>
                </div>
                <div style="flex: 1; min-width: 140px; border-left: 1px solid var(--surface-border); padding-left: 1rem;">
                    <span class="text-muted" style="font-size: 0.75rem;">Overdue Months (N)</span>
                    <strong class="text-warning" style="display: block; font-size: 1.1rem; color: #f59e0b;">${overdueMonths} Months</strong>
                </div>
                <div style="flex: 1; min-width: 140px; border-left: 1px solid var(--surface-border); padding-left: 1rem;">
                    <span class="text-muted" style="font-size: 0.75rem;">Base Maintenance</span>
                    <strong class="text-main" style="display: block; font-size: 1rem;">₹ ${Number(baseDue).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
                </div>
                <div style="flex: 1; min-width: 140px; border-left: 1px solid var(--surface-border); padding-left: 1rem;">
                    <span class="text-muted" style="font-size: 0.75rem;">Cumulative Penalty</span>
                    <strong class="text-amount-danger" style="display: block; font-size: 1.1rem;">+ ₹ ${Number(penaltyAmount).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
                </div>
                <div style="flex: 1; min-width: 140px; border-left: 1px solid var(--surface-border); padding-left: 1rem;">
                    <span class="text-muted" style="font-size: 0.75rem;">Total Payable Dues</span>
                    <strong class="text-amount-danger" style="display: block; font-size: 1.25rem; font-weight: 800;">₹ ${Number(totalDue).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
                </div>
            </div>

            <h4 class="text-main" style="font-size: 1rem; margin-bottom: 0.75rem;">🪜 Step-by-Step Penalty Accrual Schedule</h4>
            <div class="table-container" style="max-height: 250px; overflow-y: auto;">
                <table class="custom-table">
                    <thead>
                        <tr>
                            <th>Overdue Step</th>
                            <th>Base Rate</th>
                            <th>Month Penalty</th>
                            <th>Cumulative Penalty</th>
                            <th>Running Total Due</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${ladderHtml}
                    </tbody>
                </table>
            </div>
        `;
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
};

window.closeBreakdownModal = function() {
    const modal = document.getElementById('breakdownModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
};

// Global click event delegation for breakdown buttons
document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.btn-breakdown-modal');
    if (trigger) {
        e.preventDefault();
        window.openBreakdownModal(
            trigger.getAttribute('data-flat'),
            trigger.getAttribute('data-name'),
            trigger.getAttribute('data-rate'),
            trigger.getAttribute('data-last-covered'),
            trigger.getAttribute('data-overdue'),
            trigger.getAttribute('data-base-due'),
            trigger.getAttribute('data-penalty'),
            trigger.getAttribute('data-total-due')
        );
    }
});

// ==========================================================================
// 6. Password Visibility Toggle Functionality (Show / Hide Password)
// ==========================================================================
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';

    if (btn) {
        btn.setAttribute('aria-pressed', isPassword ? 'true' : 'false');
        btn.setAttribute('title', isPassword ? 'Hide password' : 'Show password');
        btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');

        const eyeIcon = btn.querySelector('.eye-icon') || btn;
        if (eyeIcon) {
            eyeIcon.textContent = isPassword ? '🙈' : '👁️';
        }
    }
}
window.togglePasswordVisibility = togglePasswordVisibility;



