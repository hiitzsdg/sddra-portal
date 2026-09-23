// ==========================================================================
// South Dumdum Enclave Residents' Association (SDERA)
// Dual-Theme Interactive Visualizations & Analytics Engine (Chart.js)
// Multi-Month Filter & Cross-Analytics Engine (Expenses & Collections)
// ==========================================================================

// --- Expense Chart Instances & Cache ---
let categoryChartInstance = null;
let monthlyChartInstance = null;
let cachedChartData = null;

// Global Expense filter states (Support Multi-Month Selection)
let selectedMonthFilters = [];
let selectedCategoryFilter = null;

// Backward-compatibility getter for single-value inspections
Object.defineProperty(window, 'selectedMonthFilter', {
    get: () => selectedMonthFilters.length > 0 ? selectedMonthFilters[0] : null,
    set: (v) => {
        if (!v) selectedMonthFilters = [];
        else selectedMonthFilters = Array.isArray(v) ? v : [v];
    },
    configurable: true
});

// --- Collection Chart Instances & Cache ---
let collectionModeChartInstance = null;
let collectionMonthlyChartInstance = null;
let cachedCollectionChartData = null;

// Global Collection filter states (Support Multi-Month Selection)
let selectedCollectionMonthFilters = [];
let selectedCollectionModeFilter = null;

// Backward-compatibility getter for single-value inspections
Object.defineProperty(window, 'selectedCollectionMonthFilter', {
    get: () => selectedCollectionMonthFilters.length > 0 ? selectedCollectionMonthFilters[0] : null,
    set: (v) => {
        if (!v) selectedCollectionMonthFilters = [];
        else selectedCollectionMonthFilters = Array.isArray(v) ? v : [v];
    },
    configurable: true
});

document.addEventListener('DOMContentLoaded', async () => {
    // Check URL parameters for pre-selected months if present
    const urlParams = new URLSearchParams(window.location.search);
    const monthParam = urlParams.get('month');
    if (monthParam) {
        const parts = monthParam.split(',').map(s => s.trim()).filter(Boolean);
        if (parts.length > 0) {
            selectedMonthFilters = [...parts];
            selectedCollectionMonthFilters = [...parts];
        }
    }

    await renderAllCharts();

    window.addEventListener('themeChanged', (e) => {
        if (cachedChartData || cachedCollectionChartData) {
            renderAllCharts(cachedChartData, cachedCollectionChartData);
        }
    });
});

// Comprehensive date string parser for all SQLite & MySQL date formats
function parseVoucherMonthYear(dateStr) {
    if (!dateStr) return { short: '', full: '', ym: '' };
    let str = String(dateStr).trim().replace(/['"’`]/g, '');
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const fullNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    // 1. Check if string contains month name (e.g. "May 2026", "May 26", "May'2026", "May")
    const lowerStr = str.toLowerCase();
    for (let i = 0; i < 12; i++) {
        const shortName = monthNames[i].toLowerCase();
        const fullName = fullNames[i].toLowerCase();
        if (lowerStr.includes(shortName) || lowerStr.includes(fullName)) {
            let year = '2026';
            const y4Match = str.match(/(20\d{2})/);
            const y2Match = str.match(/(\d{2})$/);
            if (y4Match) {
                year = y4Match[1];
            } else if (y2Match && parseInt(y2Match[1], 10) >= 20 && parseInt(y2Match[1], 10) <= 40) {
                year = '20' + y2Match[1];
            }
            return {
                short: `${monthNames[i]} ${year}`,
                full: `${fullNames[i]} ${year}`,
                ym: `${year}-${String(i + 1).padStart(2, '0')}`
            };
        }
    }

    // 2. Format: YYYY-MM-DD or YYYY/MM/DD or YYYY-MM
    let m = str.match(/^(\d{4})[-\/](\d{1,2})/);
    if (m) {
        const year = m[1];
        const mIdx = parseInt(m[2], 10) - 1;
        if (mIdx >= 0 && mIdx < 12) {
            return {
                short: `${monthNames[mIdx]} ${year}`,
                full: `${fullNames[mIdx]} ${year}`,
                ym: `${year}-${String(mIdx + 1).padStart(2, '0')}`
            };
        }
    }

    // 3. Format: DD-MM-YYYY or DD/MM/YYYY
    m = str.match(/^(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})/);
    if (m) {
        const year = m[3];
        const mIdx = parseInt(m[2], 10) - 1;
        if (mIdx >= 0 && mIdx < 12) {
            return {
                short: `${monthNames[mIdx]} ${year}`,
                full: `${fullNames[mIdx]} ${year}`,
                ym: `${year}-${String(mIdx + 1).padStart(2, '0')}`
            };
        }
    }

    // 4. Native JS Date parsing fallback
    const d = new Date(str);
    if (!isNaN(d.getTime())) {
        const mIdx = d.getMonth();
        const year = d.getFullYear();
        return {
            short: `${monthNames[mIdx]} ${year}`,
            full: `${fullNames[mIdx]} ${year}`,
            ym: `${year}-${String(mIdx + 1).padStart(2, '0')}`
        };
    }

    return { short: '', full: '', ym: '' };
}

// Check if a row's date / ym matches any month in the active multi-month filter list
function isRowMatchingMultiMonth(rowDate, rowYm, rowRemarks, rowText, filterMonths) {
    if (!filterMonths || filterMonths.length === 0) return true;

    return filterMonths.some(filterMonthStr => {
        const filterInfo = parseVoucherMonthYear(filterMonthStr);
        if (!filterInfo || !filterInfo.ym) {
            return rowText.toLowerCase().includes(filterMonthStr.toLowerCase());
        }

        const myInfo = parseVoucherMonthYear(rowDate || rowRemarks);
        return (
            (rowYm && filterInfo.ym && rowYm === filterInfo.ym) ||
            (myInfo.ym && filterInfo.ym && myInfo.ym === filterInfo.ym) ||
            (myInfo.short && filterInfo.short && myInfo.short.toLowerCase() === filterInfo.short.toLowerCase()) ||
            (filterInfo.ym && rowDate && rowDate.includes(filterInfo.ym)) ||
            (filterInfo.short && rowDate && rowDate.toLowerCase().includes(filterInfo.short.toLowerCase())) ||
            (filterInfo.short && rowRemarks && rowRemarks.toLowerCase().includes(filterInfo.short.toLowerCase())) ||
            (filterInfo.short && rowText && rowText.toLowerCase().includes(filterInfo.short.toLowerCase()))
        );
    });
}

// ==========================================================================
// 1. EXPENSE REPORTING ANALYTICS & MULTI-MONTH FILTERING ENGINE
// ==========================================================================

// Generate expense bar dataset colors based on active multi-month selection
function getBarColors(labels, isLight) {
    const defaultColor = isLight ? 'rgba(37, 99, 235, 0.85)' : 'rgba(59, 130, 246, 0.85)';
    const dimmedColor = isLight ? 'rgba(37, 99, 235, 0.22)' : 'rgba(59, 130, 246, 0.20)';
    const activeColor = isLight ? '#1d4ed8' : '#38bdf8';
    const activeBorder = isLight ? '#1e3a8a' : '#ffffff';

    if (!selectedMonthFilters || selectedMonthFilters.length === 0) {
        return {
            bg: labels.map(() => defaultColor),
            border: labels.map(() => 'transparent'),
            borderWidth: labels.map(() => 0)
        };
    }

    return {
        bg: labels.map(label => selectedMonthFilters.includes(label) ? activeColor : dimmedColor),
        border: labels.map(label => selectedMonthFilters.includes(label) ? activeBorder : 'transparent'),
        borderWidth: labels.map(label => selectedMonthFilters.includes(label) ? 2.5 : 0)
    };
}

// Update expense chart visual styles when multi-month filter is toggled
function updateChartVisualSelection() {
    if (!monthlyChartInstance) return;
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const labels = monthlyChartInstance.data.labels;
    const colors = getBarColors(labels, isLight);

    monthlyChartInstance.data.datasets[0].backgroundColor = colors.bg;
    monthlyChartInstance.data.datasets[0].borderColor = colors.border;
    monthlyChartInstance.data.datasets[0].borderWidth = colors.borderWidth;
    monthlyChartInstance.update('none');

    updateMonthPillsVisual();
}

// Render or update interactive multi-month filter pills below expense chart
function updateMonthPillsVisual() {
    const containers = document.querySelectorAll('#expenseMonthlyPills');
    if (!containers || containers.length === 0 || !cachedChartData || !cachedChartData.monthly) return;

    containers.forEach(container => {
        const months = cachedChartData.monthly;
        const hasSelection = selectedMonthFilters && selectedMonthFilters.length > 0;
        
        let html = `
            <button type="button" onclick="clearMonthlyChartFilter()" class="btn btn-sm ${!hasSelection ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px;">
                ✨ All Months (${months.length})
            </button>
        `;

        months.forEach(m => {
            const isSelected = selectedMonthFilters.includes(m.month);
            const activeStyle = isSelected 
                ? 'background: #3b82f6; color: #ffffff; border-color: #60a5fa; font-weight: 700; box-shadow: 0 0 8px rgba(59,130,246,0.4);' 
                : '';
            html += `
                <button type="button" onclick="toggleMonthExpenditureFilter('${m.month}')" class="btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px; ${activeStyle}" title="${isSelected ? 'Click to deselect' : 'Click to add month to filter'}">
                    ${isSelected ? '✓' : '📅'} ${m.month}
                </button>
            `;
        });

        container.innerHTML = html;
    });
}

// Toggle a month in/out of the multi-month expense filter
function toggleMonthExpenditureFilter(clickedMonth) {
    const idx = selectedMonthFilters.indexOf(clickedMonth);
    if (idx > -1) {
        selectedMonthFilters.splice(idx, 1);
    } else {
        selectedMonthFilters.push(clickedMonth);
    }
    updateChartVisualSelection();
    applyExpenditureFilters(true);
}

// Clear all active expense month filters
function clearMonthlyChartFilter() {
    selectedMonthFilters = [];
    updateChartVisualSelection();
    applyExpenditureFilters(false);
}

// Curated Vibrant 20+ Color Palette for all Society Expense Heads
const EXPENSE_PALETTE = [
    '#2563eb', // Royal Blue (Service Charges)
    '#059669', // Emerald Green (Repair & Maintenance)
    '#d97706', // Amber Gold (Electricity Charges)
    '#7c3aed', // Rich Violet (Accounting Charges)
    '#e11d48', // Rose Crimson (AGM)
    '#0891b2', // Teal Cyan (AMC Lift)
    '#db2777', // Magenta Pink (Cultural Program & Milonotsav)
    '#0d9488', // Dark Cyan (Stationary)
    '#4f46e5', // Indigo (Misc & Other Expenses)
    '#ea580c', // Bright Flame Orange (Two Wheeler Security Deposit Refund)
    '#65a30d', // Lime (Capital Fund Refund)
    '#dc2626', // Bright Red (Fire Extinguisher)
    '#9333ea', // Purple Orchid (Painting)
    '#0284c7', // Sky Blue
    '#ca8a04', // Yellow Gold
    '#475569', // Slate Grey
    '#16a34a', // Forest Green
    '#c026d3', // Fuchsia
    '#b45309', // Rust
    '#334155'  // Charcoal Slate
];

// Helper to get consistent color for a category index
function getExpenseCategoryColor(index) {
    return EXPENSE_PALETTE[index % EXPENSE_PALETTE.length];
}

// Render or update interactive category filter pills below expense chart
function updateCategoryPillsVisual(categories = null, totalSpend = null) {
    const containers = document.querySelectorAll('#expenseCategoryPills');
    if (!containers || containers.length === 0) return;

    const cats = categories || (cachedChartData ? cachedChartData.categories : []);
    if (!cats || cats.length === 0) return;

    const total = totalSpend || (cachedChartData ? cachedChartData.total_spend : null) || cats.reduce((acc, c) => acc + (c.total || 0), 0) || 1;

    containers.forEach(container => {
        const hasCatSelection = Boolean(selectedCategoryFilter);

        let html = `
            <div style="display: flex; gap: 0.35rem; justify-content: center; align-items: center; flex-wrap: wrap; margin-top: 0.65rem; padding-top: 0.5rem; border-top: 1px dashed rgba(255, 255, 255, 0.1);">
                <button type="button" onclick="clearCategoryChartFilter()" class="btn btn-sm ${!hasCatSelection ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px;">
                    ✨ All Heads (${cats.length})
                </button>
        `;

        cats.forEach((c, idx) => {
            const isSelected = selectedCategoryFilter === c.category;
            const color = getExpenseCategoryColor(idx);
            const pct = c.percentage !== undefined ? c.percentage : Math.round(((c.total || 0) / total) * 1000) / 10;
            const activeStyle = isSelected 
                ? `background: ${color}; color: #ffffff; border-color: #ffffff; font-weight: 700; box-shadow: 0 0 10px ${color}88;` 
                : '';
            
            html += `
                <button type="button" onclick="toggleCategoryExpenditureFilter('${c.category.replace(/'/g, "\\'")}')" class="btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px; display: inline-flex; align-items: center; gap: 5px; ${activeStyle}" title="₹ ${(c.total || 0).toLocaleString('en-IN')} (${pct}% of total outlays) • Click to filter">
                    <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${isSelected ? '#ffffff' : color};"></span>
                    <span>${c.category}</span>
                    <span style="font-size: 0.72rem; opacity: 0.85; margin-left: 2px;">₹ ${Math.round(c.total).toLocaleString('en-IN')}</span>
                    <span class="badge" style="font-size: 0.68rem; padding: 1px 5px; background: rgba(0,0,0,0.18); border-radius: 10px;">${pct}%</span>
                </button>
            `;
        });

        html += `</div>`;
        container.innerHTML = html;
    });
}

// Clear active category filter
function clearCategoryChartFilter() {
    selectedCategoryFilter = null;
    updateCategoryPillsVisual();
    applyExpenditureFilters(false);
}

// Toggle category filter when expense doughnut slice or pill is clicked
function toggleCategoryExpenditureFilter(clickedCategory) {
    if (selectedCategoryFilter === clickedCategory) {
        selectedCategoryFilter = null;
    } else {
        selectedCategoryFilter = clickedCategory;
    }
    updateCategoryPillsVisual();
    applyExpenditureFilters(true);
}

// Apply active filters across all expense tables (Multi-Month Aware)
function applyExpenditureFilters(shouldAnimateCard = false) {
    const tableConfigs = [
        {
            tableId: '#adminRecentExpensesTable',
            bannerId: '#adminExpFilterBanner',
            labelId: '#adminExpFilterLabel',
            statId: '#adminExpFilterStat',
            counterId: '#adminExpCountBadge',
            totalBadgeId: '#adminExpTotalBadge',
            searchId: '#adminExpSearch',
            cardId: '#societyExpenditureOutlaysCard',
            defaultSuffix: 'Vouchers'
        },
        {
            tableId: '#expensesTable',
            bannerId: '#expensesFilterBanner',
            labelId: '#expensesFilterLabel',
            statId: '#expensesFilterStat',
            counterId: '#expensesCountBadge',
            totalBadgeId: '#expensesTotalBadge',
            searchId: '#q',
            cardId: null,
            defaultSuffix: 'Records'
        },
        {
            tableId: '#memberExpensesTable',
            bannerId: '#memberExpFilterBanner',
            labelId: '#memberExpFilterLabel',
            statId: '#memberExpFilterStat',
            counterId: '#memberExpCountBadge',
            totalBadgeId: '#memberExpTotalBadge',
            searchId: '#memberExpSearch',
            cardId: '#memberExpenditureCard',
            defaultSuffix: 'Vouchers'
        }
    ];

    const hasMonthFilter = selectedMonthFilters && selectedMonthFilters.length > 0;

    let lastActiveTotalAmount = 0;
    let lastActiveMatchCount = 0;

    tableConfigs.forEach(cfg => {
        const table = document.querySelector(cfg.tableId);
        if (!table) return;

        const searchInput = cfg.searchId ? document.querySelector(cfg.searchId) : null;
        const rawSearch = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const cleanSearch = rawSearch.replace(/[\/\-\s_,\.]/g, '');
        const tokens = rawSearch.split(/\s+/).filter(t => t.length > 0);

        const rows = table.querySelectorAll('tbody tr');
        let matchCount = 0;
        let totalRows = 0;
        let totalAmount = 0;

        rows.forEach(row => {
            if (row.children.length === 1 && row.children[0].getAttribute('colspan')) {
                return;
            }
            totalRows++;

            // 1. Multi-Month match
            const rowYm = row.getAttribute('data-voucher-ym');
            const dateVal = row.getAttribute('data-voucher-date') || '';
            const rowText = row.textContent;
            const matchesMonth = !hasMonthFilter || isRowMatchingMultiMonth(dateVal, rowYm, '', rowText, selectedMonthFilters);

            // 2. Category match
            let matchesCategory = true;
            if (selectedCategoryFilter) {
                const partVal = (row.getAttribute('data-particulars') || rowText).toLowerCase();
                matchesCategory = partVal.includes(selectedCategoryFilter.toLowerCase());
            }

            // 3. Search query match
            let matchesSearch = true;
            if (rawSearch) {
                const rowRawText = rowText.toLowerCase();
                const rowCleanText = rowRawText.replace(/[\/\-\s_,\.]/g, '');

                const rawSubstringMatch = rowRawText.includes(rawSearch);
                const cleanMatch = cleanSearch.length > 0 && rowCleanText.includes(cleanSearch);
                const allTokensMatch = tokens.length > 0 && tokens.every(token => {
                    const cleanToken = token.replace(/[\/\-\s_,\.]/g, '');
                    return rowRawText.includes(token) || (cleanToken.length > 0 && rowCleanText.includes(cleanToken));
                });

                matchesSearch = rawSubstringMatch || cleanMatch || allTokensMatch;
            }

            if (matchesMonth && matchesCategory && matchesSearch) {
                row.style.display = '';
                matchCount++;

                // Sum up amounts directly from data-amount attribute or formatted cells
                let rowAmt = 0;
                const dataAmt = row.getAttribute('data-amount');
                if (dataAmt !== null && dataAmt !== '' && !isNaN(parseFloat(dataAmt))) {
                    rowAmt = parseFloat(dataAmt);
                } else {
                    const tds = row.querySelectorAll('td');
                    for (let td of tds) {
                        const text = td.textContent.trim();
                        if (text.includes('₹') || text.includes('INR') || td.querySelector('.text-amount-danger') || td.classList.contains('text-amount-danger')) {
                            const cleaned = text.replace(/[^0-9.]/g, '');
                            const parsed = parseFloat(cleaned);
                            if (!isNaN(parsed) && parsed > 0) {
                                rowAmt = parsed;
                                break;
                            }
                        }
                    }
                }
                if (rowAmt > 0) {
                    totalAmount += rowAmt;
                }
            } else {
                row.style.display = 'none';
            }
        });

        lastActiveTotalAmount = totalAmount;
        lastActiveMatchCount = matchCount;

        // Update dynamic aggregated total alongside table
        if (cfg.totalBadgeId) {
            const totalBadge = document.querySelector(cfg.totalBadgeId);
            if (totalBadge) {
                if (!totalBadge.getAttribute('data-original')) {
                    totalBadge.setAttribute('data-original', totalBadge.textContent.trim());
                }
                if (hasMonthFilter || rawSearch || selectedCategoryFilter) {
                    totalBadge.textContent = `Total: ₹ ${totalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                } else {
                    totalBadge.textContent = totalBadge.getAttribute('data-original');
                }
            }
        }

        // Update active filter banner
        if (cfg.bannerId) {
            const banner = document.querySelector(cfg.bannerId);
            const label = document.querySelector(cfg.labelId);
            const stat = document.querySelector(cfg.statId);

            if (banner) {
                if (hasMonthFilter) {
                    banner.style.display = 'block';
                    const monthSummaryText = selectedMonthFilters.length === 1 
                        ? selectedMonthFilters[0] 
                        : `${selectedMonthFilters.length} Months (${selectedMonthFilters.join(', ')})`;
                    if (label) label.textContent = monthSummaryText;
                    if (stat) stat.textContent = `${matchCount} Vouchers • ₹ ${totalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                } else {
                    banner.style.display = 'none';
                }
            }
        }

        // Update counter badge
        if (cfg.counterId) {
            const counter = document.querySelector(cfg.counterId);
            if (counter) {
                if (hasMonthFilter || rawSearch) {
                    counter.textContent = `${matchCount} of ${totalRows} Shown`;
                } else {
                    counter.textContent = `${totalRows} ${cfg.defaultSuffix}`;
                }
            }
        }

        // Pulse animation feedback on card
        if (shouldAnimateCard && cfg.cardId && hasMonthFilter) {
            const card = document.querySelector(cfg.cardId);
            if (card) {
                card.classList.remove('card-highlight-pulse');
                void card.offsetWidth;
                card.classList.add('card-highlight-pulse');
            }
        }
    });

    // Update Dashboard Top KPI Stat Card for Society Outlays
    const dashOutlayVal = document.getElementById('dashboardSocietyOutlaysValue');
    const dashOutlaySub = document.getElementById('dashboardSocietyOutlaysSub');
    if (dashOutlayVal) {
        if (!dashOutlayVal.getAttribute('data-original')) {
            dashOutlayVal.setAttribute('data-original', dashOutlayVal.textContent.trim());
        }
        if (dashOutlaySub && !dashOutlaySub.getAttribute('data-original')) {
            dashOutlaySub.setAttribute('data-original', dashOutlaySub.textContent.trim());
        }

        if (hasMonthFilter || selectedCategoryFilter) {
            dashOutlayVal.textContent = `₹ ${lastActiveTotalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (dashOutlaySub) {
                const subMonthText = selectedMonthFilters.length === 1 
                    ? selectedMonthFilters[0] 
                    : `${selectedMonthFilters.length} Months Selected`;
                dashOutlaySub.textContent = `${lastActiveMatchCount} vouchers (${subMonthText})`;
            }
        } else {
            dashOutlayVal.textContent = dashOutlayVal.getAttribute('data-original');
            if (dashOutlaySub) {
                dashOutlaySub.textContent = dashOutlaySub.getAttribute('data-original');
            }
        }
    }
}

// ==========================================================================
// 2. MAINTENANCE COLLECTION ANALYTICS & MULTI-MONTH FILTERING ENGINE
// ==========================================================================

// Generate collection bar dataset colors based on active multi-month selection (Emerald Green theme)
function getCollectionBarColors(labels, isLight) {
    const defaultColor = isLight ? 'rgba(16, 185, 129, 0.85)' : 'rgba(52, 211, 153, 0.85)';
    const dimmedColor = isLight ? 'rgba(16, 185, 129, 0.22)' : 'rgba(52, 211, 153, 0.20)';
    const activeColor = isLight ? '#059669' : '#10b981';
    const activeBorder = isLight ? '#047857' : '#ffffff';

    if (!selectedCollectionMonthFilters || selectedCollectionMonthFilters.length === 0) {
        return {
            bg: labels.map(() => defaultColor),
            border: labels.map(() => 'transparent'),
            borderWidth: labels.map(() => 0)
        };
    }

    return {
        bg: labels.map(label => selectedCollectionMonthFilters.includes(label) ? activeColor : dimmedColor),
        border: labels.map(label => selectedCollectionMonthFilters.includes(label) ? activeBorder : 'transparent'),
        borderWidth: labels.map(label => selectedCollectionMonthFilters.includes(label) ? 2.5 : 0)
    };
}

// Update collection chart visual styles when multi-month filter is toggled
function updateCollectionChartVisualSelection() {
    if (!collectionMonthlyChartInstance) return;
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const labels = collectionMonthlyChartInstance.data.labels;
    const colors = getCollectionBarColors(labels, isLight);

    collectionMonthlyChartInstance.data.datasets[0].backgroundColor = colors.bg;
    collectionMonthlyChartInstance.data.datasets[0].borderColor = colors.border;
    collectionMonthlyChartInstance.data.datasets[0].borderWidth = colors.borderWidth;
    collectionMonthlyChartInstance.update('none');

    updateCollectionMonthPillsVisual();
}

// Render or update interactive multi-month filter pills below collection chart
function updateCollectionMonthPillsVisual() {
    const containers = document.querySelectorAll('#collectionMonthlyPills');
    if (!containers || containers.length === 0 || !cachedCollectionChartData || !cachedCollectionChartData.monthly) return;

    containers.forEach(container => {
        const months = cachedCollectionChartData.monthly;
        const hasSelection = selectedCollectionMonthFilters && selectedCollectionMonthFilters.length > 0;
        
        let html = `
            <button type="button" onclick="clearMonthlyCollectionFilter()" class="btn btn-sm ${!hasSelection ? 'btn-success' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px;">
                ✨ All Months (${months.length})
            </button>
        `;

        months.forEach(m => {
            const isSelected = selectedCollectionMonthFilters.includes(m.month);
            const activeStyle = isSelected 
                ? 'background: #10b981; color: #ffffff; border-color: #34d399; font-weight: 700; box-shadow: 0 0 8px rgba(16,185,129,0.4);' 
                : '';
            html += `
                <button type="button" onclick="toggleMonthCollectionFilter('${m.month}')" class="btn btn-sm ${isSelected ? 'btn-success' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px; ${activeStyle}" title="${isSelected ? 'Click to deselect' : 'Click to add month to filter'}">
                    ${isSelected ? '✓' : '📅'} ${m.month}
                </button>
            `;
        });

        container.innerHTML = html;
    });
}

// Toggle a month in/out of the multi-month collection filter
function toggleMonthCollectionFilter(clickedMonth) {
    const idx = selectedCollectionMonthFilters.indexOf(clickedMonth);
    if (idx > -1) {
        selectedCollectionMonthFilters.splice(idx, 1);
    } else {
        selectedCollectionMonthFilters.push(clickedMonth);
    }
    updateCollectionChartVisualSelection();
    applyCollectionFilters(true);
}

// Clear all active collection month filters
function clearMonthlyCollectionFilter() {
    selectedCollectionMonthFilters = [];
    updateCollectionChartVisualSelection();
    applyCollectionFilters(false);
}

// Toggle payment mode filter when collection doughnut slice is clicked
function togglePaymentModeCollectionFilter(clickedMode) {
    if (selectedCollectionModeFilter === clickedMode) {
        selectedCollectionModeFilter = null;
    } else {
        selectedCollectionModeFilter = clickedMode;
    }
    applyCollectionFilters(true);
}

// Apply active filters across all collection tables (Multi-Month Aware)
function applyCollectionFilters(shouldAnimateCard = false) {
    const tableConfigs = [
        {
            tableId: '#adminRecentReceiptsTable',
            bannerId: '#adminRcptFilterBanner',
            labelId: '#adminRcptFilterLabel',
            statId: '#adminRcptFilterStat',
            counterId: '#adminRcptCountBadge',
            totalBadgeId: '#adminRcptTotalBadge',
            searchId: '#adminRcptSearch',
            cardId: '#societyCollectionsInflowCard',
            defaultSuffix: 'Receipts'
        },
        {
            tableId: '#adminReceiptsTable',
            bannerId: '#receiptsFilterBanner',
            labelId: '#receiptsFilterLabel',
            statId: '#receiptsFilterStat',
            counterId: '#rcptCountBadge',
            totalBadgeId: '#rcptTotalBadge',
            searchId: '#liveReceiptSearch',
            cardId: null,
            defaultSuffix: 'Receipts Found'
        },
        {
            tableId: '#memberReceiptsTable',
            bannerId: null,
            labelId: null,
            statId: null,
            counterId: '#memberRcptCountBadge',
            totalBadgeId: null,
            searchId: '#memberRcptSearch',
            cardId: null,
            defaultSuffix: 'Receipts'
        }
    ];

    const hasMonthFilter = selectedCollectionMonthFilters && selectedCollectionMonthFilters.length > 0;

    let lastActiveTotalAmount = 0;
    let lastActiveMatchCount = 0;

    tableConfigs.forEach(cfg => {
        const table = document.querySelector(cfg.tableId);
        if (!table) return;

        const searchInput = cfg.searchId ? document.querySelector(cfg.searchId) : null;
        const rawSearch = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const cleanSearch = rawSearch.replace(/[\/\-\s_,\.]/g, '');
        const tokens = rawSearch.split(/\s+/).filter(t => t.length > 0);

        const rows = table.querySelectorAll('tbody tr');
        let matchCount = 0;
        let totalRows = 0;
        let totalAmount = 0;

        rows.forEach(row => {
            if (row.children.length === 1 && row.children[0].getAttribute('colspan')) {
                return;
            }
            totalRows++;

            // 1. Multi-Month match
            const rowYm = row.getAttribute('data-payment-ym') || row.getAttribute('data-voucher-ym');
            const dateVal = row.getAttribute('data-payment-date') || row.getAttribute('data-voucher-date') || '';
            const remarksVal = row.getAttribute('data-remarks') || '';
            const rowText = row.textContent;
            const matchesMonth = !hasMonthFilter || isRowMatchingMultiMonth(dateVal, rowYm, remarksVal, rowText, selectedCollectionMonthFilters);

            // 2. Payment Mode match
            let matchesMode = true;
            if (selectedCollectionModeFilter) {
                const modeVal = (row.getAttribute('data-pymnt-mode') || rowText).toLowerCase();
                matchesMode = modeVal.includes(selectedCollectionModeFilter.toLowerCase());
            }

            // 3. Search query match
            let matchesSearch = true;
            if (rawSearch) {
                const rowRawText = rowText.toLowerCase();
                const rowCleanText = rowRawText.replace(/[\/\-\s_,\.]/g, '');

                const rawSubstringMatch = rowRawText.includes(rawSearch);
                const cleanMatch = cleanSearch.length > 0 && rowCleanText.includes(cleanSearch);
                const allTokensMatch = tokens.length > 0 && tokens.every(token => {
                    const cleanToken = token.replace(/[\/\-\s_,\.]/g, '');
                    return rowRawText.includes(token) || (cleanToken.length > 0 && rowCleanText.includes(cleanToken));
                });

                matchesSearch = rawSubstringMatch || cleanMatch || allTokensMatch;
            }

            if (matchesMonth && matchesMode && matchesSearch) {
                row.style.display = '';
                matchCount++;

                // Sum up amounts directly from data-amount attribute or formatted cells
                let rowAmt = 0;
                const dataAmt = row.getAttribute('data-amount');
                if (dataAmt !== null && dataAmt !== '' && !isNaN(parseFloat(dataAmt))) {
                    rowAmt = parseFloat(dataAmt);
                } else {
                    const tds = row.querySelectorAll('td');
                    for (let td of tds) {
                        const text = td.textContent.trim();
                        if (text.includes('₹') || text.includes('INR') || td.querySelector('.text-amount-success') || td.classList.contains('text-amount-success')) {
                            const cleaned = text.replace(/[^0-9.]/g, '');
                            const parsed = parseFloat(cleaned);
                            if (!isNaN(parsed) && parsed > 0) {
                                rowAmt = parsed;
                                break;
                            }
                        }
                    }
                }
                if (rowAmt > 0) {
                    totalAmount += rowAmt;
                }
            } else {
                row.style.display = 'none';
            }
        });

        lastActiveTotalAmount = totalAmount;
        lastActiveMatchCount = matchCount;

        // Update dynamic aggregated total alongside table
        if (cfg.totalBadgeId) {
            const totalBadge = document.querySelector(cfg.totalBadgeId);
            if (totalBadge) {
                if (!totalBadge.getAttribute('data-original')) {
                    totalBadge.setAttribute('data-original', totalBadge.textContent.trim());
                }
                if (hasMonthFilter || rawSearch || selectedCollectionModeFilter) {
                    totalBadge.textContent = `Total: ₹ ${totalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                } else {
                    totalBadge.textContent = totalBadge.getAttribute('data-original');
                }
            }
        }

        // Update active filter banner
        if (cfg.bannerId) {
            const banner = document.querySelector(cfg.bannerId);
            const label = document.querySelector(cfg.labelId);
            const stat = document.querySelector(cfg.statId);

            if (banner) {
                if (hasMonthFilter) {
                    banner.style.display = 'block';
                    const monthSummaryText = selectedCollectionMonthFilters.length === 1 
                        ? selectedCollectionMonthFilters[0] 
                        : `${selectedCollectionMonthFilters.length} Months (${selectedCollectionMonthFilters.join(', ')})`;
                    if (label) label.textContent = monthSummaryText;
                    if (stat) stat.textContent = `${matchCount} Receipts • ₹ ${totalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                } else {
                    banner.style.display = 'none';
                }
            }
        }

        // Update counter badge
        if (cfg.counterId) {
            const counter = document.querySelector(cfg.counterId);
            if (counter) {
                if (hasMonthFilter || rawSearch) {
                    counter.textContent = `${matchCount} of ${totalRows} Shown`;
                } else {
                    counter.textContent = `${totalRows} ${cfg.defaultSuffix}`;
                }
            }
        }

        // Pulse animation feedback on card
        if (shouldAnimateCard && cfg.cardId && hasMonthFilter) {
            const card = document.querySelector(cfg.cardId);
            if (card) {
                card.classList.remove('card-highlight-pulse');
                void card.offsetWidth;
                card.classList.add('card-highlight-pulse');
            }
        }
    });

    // Update Dashboard Top KPI Stat Card for Total Maintenance Collected
    const dashCollectedVal = document.getElementById('dashboardTotalCollectedValue');
    const dashCollectedSub = document.getElementById('dashboardTotalCollectedSub');
    if (dashCollectedVal) {
        if (!dashCollectedVal.getAttribute('data-original')) {
            dashCollectedVal.setAttribute('data-original', dashCollectedVal.textContent.trim());
        }
        if (dashCollectedSub && !dashCollectedSub.getAttribute('data-original')) {
            dashCollectedSub.setAttribute('data-original', dashCollectedSub.textContent.trim());
        }

        if (hasMonthFilter || selectedCollectionModeFilter) {
            dashCollectedVal.textContent = `₹ ${lastActiveTotalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (dashCollectedSub) {
                const subMonthText = selectedCollectionMonthFilters.length === 1 
                    ? selectedCollectionMonthFilters[0] 
                    : `${selectedCollectionMonthFilters.length} Months Selected`;
                dashCollectedSub.textContent = `${lastActiveMatchCount} receipts (${subMonthText})`;
            }
        } else {
            dashCollectedVal.textContent = dashCollectedVal.getAttribute('data-original');
            if (dashCollectedSub) {
                dashCollectedSub.textContent = dashCollectedSub.getAttribute('data-original');
            }
        }
    }
}

// ==========================================================================
// 3. CHART INITIALIZATION & RENDERING PIPELINE
// ==========================================================================

async function renderExpenseCharts(existingData = null) {
    const expenseChartCanvas = document.getElementById('expenseCategoryChart');
    const monthlyTrendCanvas = document.getElementById('expenseMonthlyChart');
    
    if (!expenseChartCanvas && !monthlyTrendCanvas) return;
    
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const textColor = isLight ? '#475569' : '#cbd5e1';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.07)' : 'rgba(255, 255, 255, 0.08)';
    const chartCardBg = isLight ? '#ffffff' : '#0f172a';
    
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif";
        Chart.defaults.color = isLight ? '#64748b' : '#94a3b8';
    }
    
    try {
        let data = existingData;
        if (!data) {
            const response = await fetch('/api/expenses/chart-data');
            if (!response.ok) return;
            data = await response.json();
            cachedChartData = data;
        }
        
        // 1. Doughnut Chart: Expense Category Outlays Breakdown (All Particulars Showcase)
        if (expenseChartCanvas && data.categories && data.categories.length > 0) {
            if (categoryChartInstance) {
                categoryChartInstance.destroy();
            }

            const labels = data.categories.map(c => c.category);
            const values = data.categories.map(c => c.total);
            const totalOutlays = data.total_spend || values.reduce((a, b) => a + b, 0) || 1;
            
            const sliceColors = labels.map((_, i) => getExpenseCategoryColor(i));
            
            categoryChartInstance = new Chart(expenseChartCanvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: sliceColors,
                        borderWidth: 2.5,
                        borderColor: chartCardBg,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onHover: (event, chartElement) => {
                        const canvas = event.native ? event.native.target : (categoryChartInstance ? categoryChartInstance.canvas : null);
                        if (canvas) {
                            canvas.style.cursor = chartElement && chartElement.length ? 'pointer' : 'default';
                        }
                    },
                    onClick: (event, elements) => {
                        let targetElements = elements;
                        if ((!targetElements || targetElements.length === 0) && categoryChartInstance) {
                            targetElements = categoryChartInstance.getElementsAtEventForMode(
                                event.native || event,
                                'nearest',
                                { intersect: true },
                                false
                            );
                        }
                        if (!targetElements || targetElements.length === 0) return;
                        const index = targetElements[0].index;
                        if (categoryChartInstance && categoryChartInstance.data.labels[index]) {
                            const clickedCategory = categoryChartInstance.data.labels[index];
                            toggleCategoryExpenditureFilter(clickedCategory);
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                boxWidth: 12,
                                boxHeight: 12,
                                borderRadius: 3,
                                useBorderRadius: true,
                                padding: 12,
                                color: textColor,
                                font: { size: 11.5, weight: 600 }
                            }
                        },
                        tooltip: {
                            backgroundColor: isLight ? 'rgba(255, 255, 255, 0.98)' : 'rgba(15, 23, 42, 0.96)',
                            titleColor: isLight ? '#0f172a' : '#ffffff',
                            bodyColor: isLight ? '#2563eb' : '#60a5fa',
                            borderColor: isLight ? '#cbd5e1' : 'rgba(59, 130, 246, 0.4)',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 6,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    const val = context.raw || 0;
                                    const pct = Math.round((val / totalOutlays) * 1000) / 10;
                                    const isSel = selectedCategoryFilter === labels[context.dataIndex];
                                    return ` ₹ ${val.toLocaleString('en-IN')} (${pct}% of budget)${isSel ? ' (Active Filter)' : ' • Click to filter'}`;
                                }
                            }
                        }
                    },
                    cutout: '62%'
                }
            });

            // Update interactive category pills visual
            updateCategoryPillsVisual(data.categories, totalOutlays);
        }
        
        // 2. Bar Chart: Monthly Expenditure Trend
        if (monthlyTrendCanvas && data.monthly && data.monthly.length > 0) {
            if (monthlyChartInstance) {
                monthlyChartInstance.destroy();
            }

            const labels = data.monthly.map(m => m.month);
            const values = data.monthly.map(m => m.total);
            const barColors = getBarColors(labels, isLight);
            
            monthlyChartInstance = new Chart(monthlyTrendCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Expenditure (₹)',
                        data: values,
                        backgroundColor: barColors.bg,
                        borderColor: barColors.border,
                        borderWidth: barColors.borderWidth,
                        hoverBackgroundColor: '#1d4ed8',
                        borderRadius: 6,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    onHover: (event, chartElement) => {
                        const canvas = event.native ? event.native.target : (monthlyChartInstance ? monthlyChartInstance.canvas : null);
                        if (canvas) {
                            canvas.style.cursor = 'pointer';
                        }
                    },
                    onClick: (event, elements, chart) => {
                        let targetElements = elements;
                        const chartObj = chart || monthlyChartInstance;
                        if ((!targetElements || targetElements.length === 0) && chartObj) {
                            targetElements = chartObj.getElementsAtEventForMode(
                                event.native || event,
                                'index',
                                { intersect: false },
                                false
                            );
                        }
                        if (!targetElements || targetElements.length === 0) return;
                        const index = targetElements[0].index;
                        if (chartObj && chartObj.data.labels[index]) {
                            const clickedMonth = chartObj.data.labels[index];
                            toggleMonthExpenditureFilter(clickedMonth);
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(15, 23, 42, 0.95)',
                            titleColor: isLight ? '#0f172a' : '#ffffff',
                            bodyColor: isLight ? '#059669' : '#34d399',
                            borderColor: isLight ? '#cbd5e1' : 'rgba(16, 185, 129, 0.4)',
                            borderWidth: 1,
                            padding: 12,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    const val = context.raw || 0;
                                    const isSelected = selectedMonthFilters.includes(labels[context.dataIndex]);
                                    return ` Incurred: ₹ ${val.toLocaleString('en-IN')}${isSelected ? ' (Selected)' : ' • Click to toggle'}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: gridColor,
                                drawBorder: false
                            },
                            ticks: {
                                color: isLight ? '#64748b' : '#94a3b8',
                                font: { size: 11 },
                                callback: function(val) {
                                    return '₹' + (val / 1000) + 'k';
                                }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: textColor,
                                font: { size: 11, weight: 600 }
                            }
                        }
                    }
                }
            });

            monthlyTrendCanvas.style.cursor = 'pointer';
            monthlyTrendCanvas.onclick = (e) => {
                if (!monthlyChartInstance) return;
                const points = monthlyChartInstance.getElementsAtEventForMode(e, 'index', { intersect: false }, false);
                if (points && points.length > 0) {
                    const idx = points[0].index;
                    const clickedMonth = monthlyChartInstance.data.labels[idx];
                    if (clickedMonth) {
                        toggleMonthExpenditureFilter(clickedMonth);
                    }
                }
            };
        }

        updateMonthPillsVisual();

        if ((selectedMonthFilters && selectedMonthFilters.length > 0) || selectedCategoryFilter) {
            applyExpenditureFilters(false);
        }
    } catch (e) {
        console.warn('Note: Expense chart visualizer skipped or offline data mode active:', e);
    }
}

async function renderCollectionCharts(existingData = null) {
    const collectionModeCanvas = document.getElementById('collectionModeChart');
    const collectionMonthlyCanvas = document.getElementById('collectionMonthlyChart');
    
    if (!collectionModeCanvas && !collectionMonthlyCanvas) return;
    
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const textColor = isLight ? '#475569' : '#cbd5e1';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.07)' : 'rgba(255, 255, 255, 0.08)';
    const chartCardBg = isLight ? '#ffffff' : '#0f172a';
    
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif";
        Chart.defaults.color = isLight ? '#64748b' : '#94a3b8';
    }
    
    try {
        let data = existingData;
        if (!data) {
            const response = await fetch('/api/collections/chart-data');
            if (!response.ok) return;
            data = await response.json();
            cachedCollectionChartData = data;
        }
        
        // 1. Doughnut Chart: Payment Mode Distribution
        if (collectionModeCanvas && data.payment_modes && data.payment_modes.length > 0) {
            if (collectionModeChartInstance) {
                collectionModeChartInstance.destroy();
            }

            const labels = data.payment_modes.map(p => p.mode || p.category);
            const values = data.payment_modes.map(p => p.total);
            
            const emeraldPalette = [
                '#10b981', // Emerald Green (Primary)
                '#3b82f6', // Electric Blue
                '#f59e0b', // Amber Orange
                '#8b5cf6', // Violet
                '#06b6d4', // Cyan
                '#ec4899', // Pink
                '#64748b'  // Slate
            ];
            
            collectionModeChartInstance = new Chart(collectionModeCanvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: emeraldPalette.slice(0, labels.length),
                        borderWidth: 3,
                        borderColor: chartCardBg,
                        hoverOffset: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onHover: (event, chartElement) => {
                        const canvas = event.native ? event.native.target : (collectionModeChartInstance ? collectionModeChartInstance.canvas : null);
                        if (canvas) {
                            canvas.style.cursor = chartElement && chartElement.length ? 'pointer' : 'default';
                        }
                    },
                    onClick: (event, elements) => {
                        let targetElements = elements;
                        if ((!targetElements || targetElements.length === 0) && collectionModeChartInstance) {
                            targetElements = collectionModeChartInstance.getElementsAtEventForMode(
                                event.native || event,
                                'nearest',
                                { intersect: true },
                                false
                            );
                        }
                        if (!targetElements || targetElements.length === 0) return;
                        const index = targetElements[0].index;
                        if (collectionModeChartInstance && collectionModeChartInstance.data.labels[index]) {
                            const clickedMode = collectionModeChartInstance.data.labels[index];
                            togglePaymentModeCollectionFilter(clickedMode);
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                boxWidth: 12,
                                boxHeight: 12,
                                borderRadius: 3,
                                useBorderRadius: true,
                                padding: 14,
                                color: textColor,
                                font: { size: 12, weight: 600 }
                            }
                        },
                        tooltip: {
                            backgroundColor: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(15, 23, 42, 0.95)',
                            titleColor: isLight ? '#0f172a' : '#ffffff',
                            bodyColor: isLight ? '#059669' : '#34d399',
                            borderColor: isLight ? '#cbd5e1' : 'rgba(16, 185, 129, 0.4)',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 6,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    const val = context.raw || 0;
                                    return ` ₹ ${val.toLocaleString('en-IN')}`;
                                }
                            }
                        }
                    },
                    cutout: '68%'
                }
            });
        }
        
        // 2. Bar Chart: Monthly Maintenance Inflow Trend
        if (collectionMonthlyCanvas && data.monthly && data.monthly.length > 0) {
            if (collectionMonthlyChartInstance) {
                collectionMonthlyChartInstance.destroy();
            }

            const labels = data.monthly.map(m => m.month);
            const values = data.monthly.map(m => m.total);
            const barColors = getCollectionBarColors(labels, isLight);
            
            collectionMonthlyChartInstance = new Chart(collectionMonthlyCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Maintenance Inflow (₹)',
                        data: values,
                        backgroundColor: barColors.bg,
                        borderColor: barColors.border,
                        borderWidth: barColors.borderWidth,
                        hoverBackgroundColor: '#059669',
                        borderRadius: 6,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    onHover: (event, chartElement) => {
                        const canvas = event.native ? event.native.target : (collectionMonthlyChartInstance ? collectionMonthlyChartInstance.canvas : null);
                        if (canvas) {
                            canvas.style.cursor = 'pointer';
                        }
                    },
                    onClick: (event, elements, chart) => {
                        let targetElements = elements;
                        const chartObj = chart || collectionMonthlyChartInstance;
                        if ((!targetElements || targetElements.length === 0) && chartObj) {
                            targetElements = chartObj.getElementsAtEventForMode(
                                event.native || event,
                                'index',
                                { intersect: false },
                                false
                            );
                        }
                        if (!targetElements || targetElements.length === 0) return;
                        const index = targetElements[0].index;
                        if (chartObj && chartObj.data.labels[index]) {
                            const clickedMonth = chartObj.data.labels[index];
                            toggleMonthCollectionFilter(clickedMonth);
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(15, 23, 42, 0.95)',
                            titleColor: isLight ? '#0f172a' : '#ffffff',
                            bodyColor: isLight ? '#059669' : '#34d399',
                            borderColor: isLight ? '#cbd5e1' : 'rgba(16, 185, 129, 0.4)',
                            borderWidth: 1,
                            padding: 12,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    const val = context.raw || 0;
                                    const isSelected = selectedCollectionMonthFilters.includes(labels[context.dataIndex]);
                                    return ` Collected: ₹ ${val.toLocaleString('en-IN')}${isSelected ? ' (Selected)' : ' • Click to toggle'}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: gridColor,
                                drawBorder: false
                            },
                            ticks: {
                                color: isLight ? '#64748b' : '#94a3b8',
                                font: { size: 11 },
                                callback: function(val) {
                                    return '₹' + (val / 1000) + 'k';
                                }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: textColor,
                                font: { size: 11, weight: 600 }
                            }
                        }
                    }
                }
            });

            collectionMonthlyCanvas.style.cursor = 'pointer';
            collectionMonthlyCanvas.onclick = (e) => {
                if (!collectionMonthlyChartInstance) return;
                const points = collectionMonthlyChartInstance.getElementsAtEventForMode(e, 'index', { intersect: false }, false);
                if (points && points.length > 0) {
                    const idx = points[0].index;
                    const clickedMonth = collectionMonthlyChartInstance.data.labels[idx];
                    if (clickedMonth) {
                        toggleMonthCollectionFilter(clickedMonth);
                    }
                }
            };
        }

        updateCollectionMonthPillsVisual();

        if ((selectedCollectionMonthFilters && selectedCollectionMonthFilters.length > 0) || selectedCollectionModeFilter) {
            applyCollectionFilters(false);
        }
    } catch (e) {
        console.warn('Note: Collection chart visualizer skipped or offline data mode active:', e);
    }
}

async function renderAllCharts(existingExpenseData = null, existingCollectionData = null) {
    await Promise.allSettled([
        renderExpenseCharts(existingExpenseData),
        renderCollectionCharts(existingCollectionData)
    ]);
}

// Expose functions and filter states globally
window.parseVoucherMonthYear = parseVoucherMonthYear;
window.isRowMatchingMultiMonth = isRowMatchingMultiMonth;
window.getBarColors = getBarColors;
window.getCollectionBarColors = getCollectionBarColors;

window.selectedMonthFilters = selectedMonthFilters;
window.selectedCollectionMonthFilters = selectedCollectionMonthFilters;

window.toggleMonthExpenditureFilter = toggleMonthExpenditureFilter;
window.clearMonthlyChartFilter = clearMonthlyChartFilter;
window.toggleCategoryExpenditureFilter = toggleCategoryExpenditureFilter;
window.applyExpenditureFilters = applyExpenditureFilters;
window.renderExpenseCharts = renderExpenseCharts;

window.toggleMonthCollectionFilter = toggleMonthCollectionFilter;
window.clearMonthlyCollectionFilter = clearMonthlyCollectionFilter;
window.togglePaymentModeCollectionFilter = togglePaymentModeCollectionFilter;
window.applyCollectionFilters = applyCollectionFilters;
window.renderCollectionCharts = renderCollectionCharts;

window.renderAllCharts = renderAllCharts;
