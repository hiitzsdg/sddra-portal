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

    // 6. Modern Web App Elevations: Command Palette, Visualizer, Helpdesk & WhatsApp
    initCommandPalette();
    initBuildingVisualizer();
    initHelpdesk();
    initWhatsAppHelpdeskWidget();
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

// ==========================================================================
// 7. Global Floating Toast Notification System
// ==========================================================================
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('globalToastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    
    const icons = {
        success: '✅',
        danger: '🚨',
        warning: '⚠️',
        info: 'ℹ️'
    };

    toast.innerHTML = `
        <span style="font-size: 1.15rem;">${icons[type] || 'ℹ️'}</span>
        <div style="flex: 1; font-size: 0.86rem; font-weight: 500; color: var(--text-main); line-height: 1.35;">${message}</div>
        <button type="button" style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 1.1rem; line-height: 1;" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideToastOut 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards';
        setTimeout(() => toast.remove(), 250);
    }, duration);
}
window.showToast = showToast;

// ==========================================================================
// 8. Global Omnisearch Command Palette (Ctrl + K / Cmd + K)
// ==========================================================================
let commandPaletteDataCache = null;
let selectedCommandIndex = 0;

function initCommandPalette() {
    const modal = document.getElementById('commandPaletteModal');
    const input = document.getElementById('commandPaletteInput');
    const resultsContainer = document.getElementById('commandPaletteResults');
    const openBtn = document.getElementById('openCommandPaletteBtn');
    const closeBtn = document.getElementById('closeCommandPaletteBtn');

    if (!modal || !input || !resultsContainer) return;

    function openPalette() {
        modal.classList.add('active');
        input.value = '';
        selectedCommandIndex = 0;
        document.body.style.overflow = 'hidden';
        setTimeout(() => input.focus(), 50);

        if (!commandPaletteDataCache) {
            fetchCommandData();
        } else {
            renderCommandResults(commandPaletteDataCache, '');
        }
    }

    function closePalette() {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }

    window.openCommandPalette = openPalette;
    window.closeCommandPalette = closePalette;

    if (openBtn) openBtn.addEventListener('click', openPalette);
    if (closeBtn) closeBtn.addEventListener('click', closePalette);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closePalette();
    });

    // Keyboard shortcuts: Ctrl+K / Cmd+K
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
            e.preventDefault();
            if (modal.classList.contains('active')) {
                closePalette();
            } else {
                openPalette();
            }
        } else if (e.key === 'Escape' && modal.classList.contains('active')) {
            closePalette();
        }
    });

    // Fetch searchable items from server API
    async function fetchCommandData() {
        resultsContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Indexing portal resources...</div>';
        try {
            const resp = await fetch('/api/command-palette-data');
            if (resp.ok) {
                commandPaletteDataCache = await resp.json();
                renderCommandResults(commandPaletteDataCache, input.value.trim());
            } else {
                resultsContainer.innerHTML = '<div class="cmd-empty-state"><p>Could not load index.</p></div>';
            }
        } catch (err) {
            resultsContainer.innerHTML = '<div class="cmd-empty-state"><p>Index network error.</p></div>';
        }
    }

    input.addEventListener('input', () => {
        selectedCommandIndex = 0;
        if (commandPaletteDataCache) {
            renderCommandResults(commandPaletteDataCache, input.value.trim());
        }
    });

    // Keydown navigation (ArrowUp, ArrowDown, Enter)
    input.addEventListener('keydown', (e) => {
        const items = resultsContainer.querySelectorAll('.cmd-item');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedCommandIndex = (selectedCommandIndex + 1) % items.length;
            updateItemSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedCommandIndex = (selectedCommandIndex - 1 + items.length) % items.length;
            updateItemSelection(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            const activeItem = items[selectedCommandIndex];
            if (activeItem) activeItem.click();
        }
    });

    function updateItemSelection(items) {
        items.forEach((item, idx) => {
            if (idx === selectedCommandIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    function renderCommandResults(data, query) {
        const q = query.toLowerCase().replace(/[\/\-\s]/g, '');
        let html = '';
        let totalRendered = 0;

        const sections = [
            { key: 'actions', title: '⚡ Quick Actions' },
            { key: 'navigation', title: '📍 Navigation' },
            { key: 'residents', title: '👥 Residents & Flats' },
            { key: 'notices', title: '📢 Announcements' }
        ];

        sections.forEach(sec => {
            const list = data[sec.key] || [];
            const filtered = list.filter(item => {
                if (!q) return true;
                const titleNorm = (item.title || '').toLowerCase().replace(/[\/\-\s]/g, '');
                const descNorm = (item.desc || '').toLowerCase().replace(/[\/\-\s]/g, '');
                return titleNorm.includes(q) || descNorm.includes(q);
            });

            if (filtered.length) {
                html += `<div class="cmd-group-title">${sec.title}</div>`;
                filtered.forEach(item => {
                    const isSelected = totalRendered === selectedCommandIndex ? 'selected' : '';
                    html += `
                        <div class="cmd-item ${isSelected}" data-index="${totalRendered}" data-url="${item.url || ''}" data-action="${item.action || ''}">
                            <div class="cmd-item-left">
                                <div class="cmd-item-icon">${item.icon || '🔹'}</div>
                                <div>
                                    <div class="cmd-item-title">${item.title}</div>
                                    <div class="cmd-item-desc">${item.desc}</div>
                                </div>
                            </div>
                            <span class="cmd-item-badge">${item.category || 'Quick'}</span>
                        </div>
                    `;
                    totalRendered++;
                });
            }
        });

        if (totalRendered === 0) {
            html = `
                <div class="cmd-empty-state">
                    <span style="font-size: 2rem;">🔍</span>
                    <p>No results found matching "<strong>${query}</strong>"</p>
                </div>
            `;
        }

        resultsContainer.innerHTML = html;

        // Add click events to rendered items
        resultsContainer.querySelectorAll('.cmd-item').forEach(item => {
            item.addEventListener('click', () => {
                const url = item.getAttribute('data-url');
                const action = item.getAttribute('data-action');
                closePalette();

                if (action === 'toggle_theme') {
                    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
                    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
                    document.documentElement.setAttribute('data-theme', nextTheme);
                    localStorage.setItem('sddra_theme', nextTheme);
                    showToast(`Theme switched to ${nextTheme === 'dark' ? 'Dark Mode 🌙' : 'Light Mode ☀️'}`, 'info');
                } else if (url) {
                    window.location.href = url;
                }
            });
        });
    }
}

// ==========================================================================
// 9. Interactive 2D Building Matrix Visualizer
// ==========================================================================
function initBuildingVisualizer() {
    const popover = document.getElementById('matrixUnitPopover');
    const filterPills = document.querySelectorAll('.matrix-filter-pill');
    const unitBtns = document.querySelectorAll('.unit-cell-btn');

    if (!unitBtns.length) return;

    let hideTimeout = null;

    if (popover) {
        popover.addEventListener('mouseenter', () => {
            if (hideTimeout) {
                clearTimeout(hideTimeout);
                hideTimeout = null;
            }
        });

        popover.addEventListener('mouseleave', () => {
            hideTimeout = setTimeout(() => {
                popover.classList.remove('visible');
            }, 300);
        });
    }

    // Filter by Block or Status
    filterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            filterPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            const filterType = pill.getAttribute('data-filter');

            unitBtns.forEach(btn => {
                const status = btn.getAttribute('data-status');
                const block = btn.getAttribute('data-block');

                if (filterType === 'all') {
                    btn.style.display = 'flex';
                } else if (filterType === 'paid') {
                    btn.style.display = (status === 'paid') ? 'flex' : 'none';
                } else if (filterType === 'overdue') {
                    btn.style.display = (status === 'due' || status === 'critical') ? 'flex' : 'none';
                } else if (filterType === 'block_a') {
                    btn.style.display = (block === 'Block A') ? 'flex' : 'none';
                } else if (filterType === 'block_b') {
                    btn.style.display = (block === 'Block B') ? 'flex' : 'none';
                } else if (filterType === 'block_c') {
                    btn.style.display = (block === 'Block C') ? 'flex' : 'none';
                }
            });
        });
    });

    // Helper function to populate and open flat modal
    function openVisualizerModalForUnit(btn) {
        const flat = btn.getAttribute('data-flat') || '';
        const name = btn.getAttribute('data-name') || '';
        const status = btn.getAttribute('data-status') || 'paid';
        const block = btn.getAttribute('data-block') || '';
        const overdue = btn.getAttribute('data-overdue') || '0';
        const rate = btn.getAttribute('data-rate') || '0';
        const sqft = btn.getAttribute('data-sqft') || '1200';
        const totalDue = btn.getAttribute('data-total-due') || '0';
        const coverage = btn.getAttribute('data-coverage') || 'Up to date';

        const modal = document.getElementById('flatVisualizerModal');
        if (!modal) return;

        const titleEl = document.getElementById('visModalFlatTitle');
        const memberEl = document.getElementById('visModalMemberName');
        const badgeEl = document.getElementById('visModalStatusBadge');
        const blockEl = document.getElementById('visModalBlock');
        const sqftEl = document.getElementById('visModalSqft');
        const rateEl = document.getElementById('visModalRate');
        const covEl = document.getElementById('visModalCoverage');
        const dueEl = document.getElementById('visModalTotalDue');
        const ledgerLink = document.getElementById('visModalLedgerLink');
        const rcptLink = document.getElementById('visModalReceiptsLink');
        const newRcptLink = document.getElementById('visModalNewReceiptLink');

        if (titleEl) titleEl.textContent = `Flat ${flat} (${block})`;
        if (memberEl) memberEl.textContent = name;
        if (blockEl) blockEl.textContent = block;
        if (sqftEl) sqftEl.textContent = `${sqft} Sq. Ft.`;
        if (rateEl) rateEl.textContent = `₹ ${Number(rate).toLocaleString('en-IN')} / month`;
        if (covEl) covEl.textContent = coverage;
        if (dueEl) {
            dueEl.textContent = (Number(totalDue) > 0) ? `₹ ${Number(totalDue).toLocaleString('en-IN')}` : '₹ 0.00 (All Cleared)';
            dueEl.className = (Number(totalDue) > 0) ? 'text-amount-danger' : 'text-amount-success';
        }

        if (badgeEl) {
            if (status === 'paid') {
                badgeEl.innerHTML = '<span class="badge badge-success" style="font-size: 0.82rem; padding: 0.35rem 0.75rem;">✓ Paid Up to Date &bull; Advance Account</span>';
            } else {
                badgeEl.innerHTML = `<span class="badge badge-danger" style="font-size: 0.82rem; padding: 0.35rem 0.75rem;">⚠️ Overdue: ${overdue} Unpaid Month(s) (Total ₹${Number(totalDue).toLocaleString('en-IN')})</span>`;
            }
        }

        if (ledgerLink) ledgerLink.href = `/admin/penalties?q=${encodeURIComponent(flat)}`;
        if (rcptLink) rcptLink.href = `/admin/receipts?flat=${encodeURIComponent(flat)}`;
        if (newRcptLink) newRcptLink.href = `/admin/receipts?action=new&flat=${encodeURIComponent(flat)}`;

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    // Popover hover & positioning
    unitBtns.forEach(btn => {
        btn.addEventListener('mouseenter', (e) => {
            if (!popover) return;
            if (hideTimeout) {
                clearTimeout(hideTimeout);
                hideTimeout = null;
            }

            const flat = btn.getAttribute('data-flat');
            const name = btn.getAttribute('data-name');
            const status = btn.getAttribute('data-status');
            const overdue = btn.getAttribute('data-overdue') || '0';
            const rate = btn.getAttribute('data-rate') || '0';
            const sqft = btn.getAttribute('data-sqft') || '1200';
            const totalDue = btn.getAttribute('data-total-due') || '0';
            const coverage = btn.getAttribute('data-coverage') || 'Up to date';

            const statusBadge = (status === 'paid')
                ? '<span class="badge badge-success" style="font-size: 0.72rem;">✓ Paid Up to Date</span>'
                : `<span class="badge badge-danger" style="font-size: 0.72rem;">⚠️ ${overdue} Mo. Overdue (₹${Number(totalDue).toLocaleString('en-IN')})</span>`;

            popover.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                    <div>
                        <strong style="font-size: 1.05rem; color: var(--text-main); font-family: var(--font-heading);">Flat ${flat}</strong>
                        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 2px;">${name}</div>
                    </div>
                    ${statusBadge}
                </div>
                <div style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.5; border-top: 1px dashed var(--surface-border); padding-top: 0.45rem; margin-top: 0.45rem;">
                    <div>📏 Unit Size: <strong class="text-main">${sqft} sq.ft.</strong></div>
                    <div>💰 Rate: <strong class="text-main">₹${Number(rate).toLocaleString('en-IN')}/mo</strong></div>
                    <div>📅 Last Covered: <strong class="text-highlight-blue">${coverage}</strong></div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.35rem; margin-top: 0.75rem;">
                    <a href="/admin/penalties?q=${encodeURIComponent(flat)}" class="btn btn-sm btn-outline-primary" style="font-size: 0.72rem; padding: 0.3rem 0.2rem; text-align: center; justify-content: center;" title="View Overdue & Penalty Ledger">📊 Ledger</a>
                    <a href="/admin/receipts?flat=${encodeURIComponent(flat)}" class="btn btn-sm btn-outline-success" style="font-size: 0.72rem; padding: 0.3rem 0.2rem; text-align: center; justify-content: center;" title="View Receipts History">🧾 Receipts</a>
                    <a href="/admin/receipts?action=new&flat=${encodeURIComponent(flat)}" class="btn btn-sm btn-primary" style="font-size: 0.72rem; padding: 0.3rem 0.2rem; text-align: center; justify-content: center;" title="Issue New Receipt">+ Receipt</a>
                </div>
            `;

            // Position popover near target button safely within viewport
            const rect = btn.getBoundingClientRect();
            let top = rect.bottom + 8;
            let left = rect.left - 40;
            const popWidth = Math.min(290, window.innerWidth - 20);
            popover.style.width = `${popWidth}px`;

            if (left + popWidth > window.innerWidth - 10) left = window.innerWidth - popWidth - 10;
            if (left < 10) left = 10;
            if (top + 210 > window.innerHeight) top = Math.max(10, rect.top - 210);

            popover.style.top = `${top}px`;
            popover.style.left = `${left}px`;
            popover.classList.add('visible');
        });

        btn.addEventListener('mouseleave', () => {
            if (popover) {
                hideTimeout = setTimeout(() => {
                    popover.classList.remove('visible');
                }, 300);
            }
        });

        // Click handler to open full inspector modal
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (popover) popover.classList.remove('visible');
            openVisualizerModalForUnit(btn);
        });
    });
}

// ==========================================================================
// 10. Resident Helpdesk & Maintenance Ticketing Module
// ==========================================================================
function initHelpdesk() {
    const helpdeskModal = document.getElementById('helpdeskModal');
    const openBtn = document.getElementById('openHelpdeskBtn');
    const ticketForm = document.getElementById('helpdeskTicketForm');

    if (openBtn && helpdeskModal) {
        openBtn.addEventListener('click', (e) => {
            e.preventDefault();
            helpdeskModal.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    }

    if (ticketForm) {
        ticketForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const category = document.getElementById('ticketCategory')?.value || 'Plumbing';
            const description = document.getElementById('ticketDescription')?.value || 'Maintenance request';

            if (helpdeskModal) helpdeskModal.classList.remove('active');
            document.body.style.overflow = '';
            showToast(`Ticket #${Math.floor(1000 + Math.random() * 9000)} registered successfully (${category}). Caretaker dispatched!`, 'success', 5000);
            ticketForm.reset();
        });
    }
}

// ==========================================================================
// 12. WhatsApp Society Helpdesk & Instant Share Controller
// ==========================================================================
function initWhatsAppHelpdeskWidget() {
    const launcherBtn = document.getElementById('toggleWaFloatingBtn');
    const floatingCard = document.getElementById('waFloatingCard');
    const closeBtn = document.getElementById('closeWaFloatingCard');

    if (launcherBtn && floatingCard) {
        launcherBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            floatingCard.classList.toggle('active');
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                floatingCard.classList.remove('active');
            });
        }

        // Close on click outside
        document.addEventListener('click', (e) => {
            if (!floatingCard.contains(e.target) && !launcherBtn.contains(e.target)) {
                floatingCard.classList.remove('active');
            }
        });
    }
}

// Global Receipt WhatsApp Handlers
window.openReceiptWhatsAppModal = function(receiptNo) {
    window._activeRcptNo = receiptNo;
    const modal = document.getElementById('receiptWhatsAppModal');
    const previewBox = document.getElementById('receiptWaPreview');
    const phoneInput = document.getElementById('receiptWaPhone');

    if (previewBox) previewBox.innerHTML = '<em>Generating official WhatsApp receipt slip for SDERA_' + receiptNo + '...</em>';
    if (modal) modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    fetch('/api/whatsapp/preview?type=receipt&id=' + receiptNo)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                if (previewBox) previewBox.innerText = data.message_text;
                if (phoneInput && data.phone && !phoneInput.value) phoneInput.value = data.phone;
                window._activeRcptMsg = data.message_text;
                window._activeRcptUrl = data.direct_url;
            } else {
                if (previewBox) previewBox.innerHTML = '<span class="text-danger">Failed to generate preview: ' + (data.message || 'Error') + '</span>';
            }
        })
        .catch(err => {
            if (previewBox) previewBox.innerHTML = '<span class="text-danger">Error loading receipt preview: ' + err.message + '</span>';
        });
};

window.copyReceiptWaText = function() {
    const text = window._activeRcptMsg || document.getElementById('receiptWaPreview')?.innerText;
    if (text) {
        navigator.clipboard.writeText(text).then(() => {
            if (window.showToast) showToast('Copied WhatsApp receipt voucher to clipboard!', 'success');
            else alert('Copied to clipboard!');
        });
    }
};

window.launchReceiptWhatsApp = function(receiptNo) {
    const rNo = receiptNo || window._activeRcptNo;
    const phone = document.getElementById('receiptWaPhone')?.value || '';

    fetch('/receipts/' + rNo + '/whatsapp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: phone })
    })
    .then(res => res.json())
    .then(data => {
        if (data.direct_url) {
            window.open(data.direct_url, '_blank');
            closeModal('receiptWhatsAppModal');
            if (window.showToast) showToast('Opened WhatsApp receipt for SDERA_' + rNo + '!', 'success');
        } else if (data.success) {
            closeModal('receiptWhatsAppModal');
            if (window.showToast) showToast(data.message || 'WhatsApp message sent!', 'success');
        }
    })
    .catch(err => {
        if (window._activeRcptUrl) {
            window.open(window._activeRcptUrl, '_blank');
            closeModal('receiptWhatsAppModal');
        }
    });
};





