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
    const themeBtn = document.getElementById('themeToggleBtn');
    const themeIcon = document.getElementById('themeToggleIcon');
    const savedTheme = localStorage.getItem('sddra_theme') || 
        (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    
    applyTheme(savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
            localStorage.setItem('sddra_theme', newTheme);
        });
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (themeIcon) {
            themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
        if (themeBtn) {
            themeBtn.title = theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode';
        }
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    }
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
