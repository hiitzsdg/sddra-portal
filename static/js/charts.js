// ==========================================================================
// South Dumdum Enclave Residents' Association (SDERA)
// Dual-Theme Interactive Visualizations & Analytics Engine (Chart.js)
// Comprehensive Expense Reporting & Maintenance Collection Analytics
// ==========================================================================

// --- Expense Chart Instances & Cache ---
let categoryChartInstance = null;
let monthlyChartInstance = null;
let cachedChartData = null;

// Global Expense filter states
let selectedMonthFilter = null;
let selectedCategoryFilter = null;

// --- Collection Chart Instances & Cache ---
let collectionModeChartInstance = null;
let collectionMonthlyChartInstance = null;
let cachedCollectionChartData = null;

// Global Collection filter states
let selectedCollectionMonthFilter = null;
let selectedCollectionModeFilter = null;

document.addEventListener('DOMContentLoaded', async () => {
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

// ==========================================================================
// 1. EXPENSE REPORTING ANALYTICS & FILTERING ENGINE
// ==========================================================================

// Generate expense bar dataset colors based on current active selection
function getBarColors(labels, isLight) {
    const defaultColor = isLight ? 'rgba(37, 99, 235, 0.85)' : 'rgba(59, 130, 246, 0.85)';
    const dimmedColor = isLight ? 'rgba(37, 99, 235, 0.22)' : 'rgba(59, 130, 246, 0.20)';
    const activeColor = isLight ? '#1d4ed8' : '#38bdf8';
    const activeBorder = isLight ? '#1e3a8a' : '#ffffff';

    if (!selectedMonthFilter) {
        return {
            bg: labels.map(() => defaultColor),
            border: labels.map(() => 'transparent'),
            borderWidth: labels.map(() => 0)
        };
    }

    return {
        bg: labels.map(label => label === selectedMonthFilter ? activeColor : dimmedColor),
        border: labels.map(label => label === selectedMonthFilter ? activeBorder : 'transparent'),
        borderWidth: labels.map(label => label === selectedMonthFilter ? 2.5 : 0)
    };
}

// Update expense chart visual styles when a filter is toggled
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

// Render or update interactive month filter pills below expense chart
function updateMonthPillsVisual() {
    const containers = document.querySelectorAll('#expenseMonthlyPills');
    if (!containers || containers.length === 0 || !cachedChartData || !cachedChartData.monthly) return;

    containers.forEach(container => {
        const months = cachedChartData.monthly;
        
        let html = `
            <button type="button" onclick="clearMonthlyChartFilter()" class="btn btn-sm ${!selectedMonthFilter ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px;">
                ✨ All Months
            </button>
        `;

        months.forEach(m => {
            const isSelected = selectedMonthFilter === m.month;
            const activeStyle = isSelected 
                ? 'background: #3b82f6; color: #ffffff; border-color: #60a5fa; font-weight: 700;' 
                : '';
            html += `
                <button type="button" onclick="toggleMonthExpenditureFilter('${m.month}')" class="btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px; ${activeStyle}">
                    📅 ${m.month}
                </button>
            `;
        });

        container.innerHTML = html;
    });
}

// Toggle month filter when expense bar or pill is clicked
function toggleMonthExpenditureFilter(clickedMonth) {
    if (selectedMonthFilter === clickedMonth) {
        selectedMonthFilter = null;
    } else {
        selectedMonthFilter = clickedMonth;
    }
    updateChartVisualSelection();
    applyExpenditureFilters(true);
}

// Clear active expense month filter
function clearMonthlyChartFilter() {
    selectedMonthFilter = null;
    updateChartVisualSelection();
    applyExpenditureFilters(false);
}

// Toggle category filter when expense doughnut slice is clicked
function toggleCategoryExpenditureFilter(clickedCategory) {
    if (selectedCategoryFilter === clickedCategory) {
        selectedCategoryFilter = null;
    } else {
        selectedCategoryFilter = clickedCategory;
    }
    applyExpenditureFilters(true);
}

// Apply active filters across all expense tables
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
            bannerId: null,
            labelId: null,
            statId: null,
            counterId: null,
            totalBadgeId: null,
            searchId: '#memberExpSearch',
            cardId: null,
            defaultSuffix: 'Records'
        }
    ];

    const filterInfo = selectedMonthFilter ? parseVoucherMonthYear(selectedMonthFilter) : null;

    // Pre-aggregated month total lookup from chart API
    let chartMonthTotal = null;
    if (selectedMonthFilter && cachedChartData && cachedChartData.monthly) {
        const foundMonth = cachedChartData.monthly.find(m => {
            const mInfo = parseVoucherMonthYear(m.month);
            return (filterInfo && mInfo.ym && filterInfo.ym && mInfo.ym === filterInfo.ym) ||
                   (m.month.toLowerCase() === selectedMonthFilter.toLowerCase());
        });
        if (foundMonth && typeof foundMonth.total === 'number') {
            chartMonthTotal = foundMonth.total;
        }
    }

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

            // 1. Month match
            let matchesMonth = true;
            if (selectedMonthFilter && filterInfo) {
                const rowYm = row.getAttribute('data-voucher-ym');
                const dateVal = row.getAttribute('data-voucher-date') || '';
                const myInfo = parseVoucherMonthYear(dateVal);

                matchesMonth = (
                    (rowYm && filterInfo.ym && rowYm === filterInfo.ym) ||
                    (myInfo.ym && filterInfo.ym && myInfo.ym === filterInfo.ym) ||
                    (myInfo.short && filterInfo.short && myInfo.short.toLowerCase() === filterInfo.short.toLowerCase()) ||
                    (filterInfo.ym && dateVal.includes(filterInfo.ym)) ||
                    (filterInfo.short && dateVal.toLowerCase().includes(filterInfo.short.toLowerCase())) ||
                    (filterInfo.short && row.textContent.toLowerCase().includes(filterInfo.short.toLowerCase()))
                );
            }

            // 2. Category match
            let matchesCategory = true;
            if (selectedCategoryFilter) {
                const partVal = (row.getAttribute('data-particulars') || row.textContent).toLowerCase();
                matchesCategory = partVal.includes(selectedCategoryFilter.toLowerCase());
            }

            // 3. Search query match
            let matchesSearch = true;
            if (rawSearch) {
                const rowRawText = row.textContent.toLowerCase();
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

        // Fail-safe: If totalAmount is 0 but we matched rows and have pre-calculated chartMonthTotal
        if (totalAmount === 0 && matchCount > 0 && chartMonthTotal !== null && !rawSearch && !selectedCategoryFilter) {
            totalAmount = chartMonthTotal;
        }

        lastActiveTotalAmount = totalAmount;
        lastActiveMatchCount = matchCount;

        // Update dynamic aggregated total alongside table
        if (cfg.totalBadgeId) {
            const totalBadge = document.querySelector(cfg.totalBadgeId);
            if (totalBadge) {
                if (!totalBadge.getAttribute('data-original')) {
                    totalBadge.setAttribute('data-original', totalBadge.textContent.trim());
                }
                if (selectedMonthFilter || rawSearch || selectedCategoryFilter) {
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
                if (selectedMonthFilter) {
                    banner.style.display = 'block';
                    if (label) label.textContent = selectedMonthFilter;
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
                if (selectedMonthFilter || rawSearch) {
                    counter.textContent = `${matchCount} of ${totalRows} Shown`;
                } else {
                    counter.textContent = `${totalRows} ${cfg.defaultSuffix}`;
                }
            }
        }

        // Pulse animation feedback on card
        if (shouldAnimateCard && cfg.cardId && selectedMonthFilter) {
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

        if (selectedMonthFilter || selectedCategoryFilter) {
            dashOutlayVal.textContent = `₹ ${lastActiveTotalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (dashOutlaySub) {
                dashOutlaySub.textContent = `${lastActiveMatchCount} vouchers (${selectedMonthFilter || 'Filtered'})`;
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
// 2. MAINTENANCE COLLECTION ANALYTICS & FILTERING ENGINE
// ==========================================================================

// Generate collection bar dataset colors based on current active selection (Emerald Green theme)
function getCollectionBarColors(labels, isLight) {
    const defaultColor = isLight ? 'rgba(16, 185, 129, 0.85)' : 'rgba(52, 211, 153, 0.85)';
    const dimmedColor = isLight ? 'rgba(16, 185, 129, 0.22)' : 'rgba(52, 211, 153, 0.20)';
    const activeColor = isLight ? '#059669' : '#10b981';
    const activeBorder = isLight ? '#047857' : '#ffffff';

    if (!selectedCollectionMonthFilter) {
        return {
            bg: labels.map(() => defaultColor),
            border: labels.map(() => 'transparent'),
            borderWidth: labels.map(() => 0)
        };
    }

    return {
        bg: labels.map(label => label === selectedCollectionMonthFilter ? activeColor : dimmedColor),
        border: labels.map(label => label === selectedCollectionMonthFilter ? activeBorder : 'transparent'),
        borderWidth: labels.map(label => label === selectedCollectionMonthFilter ? 2.5 : 0)
    };
}

// Update collection chart visual styles when a filter is toggled
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

// Render or update interactive month filter pills below collection chart
function updateCollectionMonthPillsVisual() {
    const containers = document.querySelectorAll('#collectionMonthlyPills');
    if (!containers || containers.length === 0 || !cachedCollectionChartData || !cachedCollectionChartData.monthly) return;

    containers.forEach(container => {
        const months = cachedCollectionChartData.monthly;
        
        let html = `
            <button type="button" onclick="clearMonthlyCollectionFilter()" class="btn btn-sm ${!selectedCollectionMonthFilter ? 'btn-success' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px;">
                ✨ All Months
            </button>
        `;

        months.forEach(m => {
            const isSelected = selectedCollectionMonthFilter === m.month;
            const activeStyle = isSelected 
                ? 'background: #10b981; color: #ffffff; border-color: #34d399; font-weight: 700;' 
                : '';
            html += `
                <button type="button" onclick="toggleMonthCollectionFilter('${m.month}')" class="btn btn-sm ${isSelected ? 'btn-success' : 'btn-secondary'}" style="padding: 0.2rem 0.65rem; font-size: 0.78rem; border-radius: 20px; margin: 2px; ${activeStyle}">
                    📅 ${m.month}
                </button>
            `;
        });

        container.innerHTML = html;
    });
}

// Toggle month filter when collection bar or pill is clicked
function toggleMonthCollectionFilter(clickedMonth) {
    if (selectedCollectionMonthFilter === clickedMonth) {
        selectedCollectionMonthFilter = null;
    } else {
        selectedCollectionMonthFilter = clickedMonth;
    }
    updateCollectionChartVisualSelection();
    applyCollectionFilters(true);
}

// Clear active collection month filter
function clearMonthlyCollectionFilter() {
    selectedCollectionMonthFilter = null;
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

// Apply active filters across all collection tables
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
            defaultSuffix: 'Receipts'
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

    const filterInfo = selectedCollectionMonthFilter ? parseVoucherMonthYear(selectedCollectionMonthFilter) : null;

    // Pre-aggregated month total lookup from chart API
    let chartMonthTotal = null;
    if (selectedCollectionMonthFilter && cachedCollectionChartData && cachedCollectionChartData.monthly) {
        const foundMonth = cachedCollectionChartData.monthly.find(m => {
            const mInfo = parseVoucherMonthYear(m.month);
            return (filterInfo && mInfo.ym && filterInfo.ym && mInfo.ym === filterInfo.ym) ||
                   (m.month.toLowerCase() === selectedCollectionMonthFilter.toLowerCase());
        });
        if (foundMonth && typeof foundMonth.total === 'number') {
            chartMonthTotal = foundMonth.total;
        }
    }

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

            // 1. Month match
            let matchesMonth = true;
            if (selectedCollectionMonthFilter && filterInfo) {
                const rowYm = row.getAttribute('data-payment-ym') || row.getAttribute('data-voucher-ym');
                const dateVal = row.getAttribute('data-payment-date') || row.getAttribute('data-voucher-date') || '';
                const remarksVal = row.getAttribute('data-remarks') || '';
                const myInfo = parseVoucherMonthYear(dateVal || remarksVal);

                matchesMonth = (
                    (rowYm && filterInfo.ym && rowYm === filterInfo.ym) ||
                    (myInfo.ym && filterInfo.ym && myInfo.ym === filterInfo.ym) ||
                    (myInfo.short && filterInfo.short && myInfo.short.toLowerCase() === filterInfo.short.toLowerCase()) ||
                    (filterInfo.ym && dateVal.includes(filterInfo.ym)) ||
                    (filterInfo.short && dateVal.toLowerCase().includes(filterInfo.short.toLowerCase())) ||
                    (filterInfo.short && remarksVal.toLowerCase().includes(filterInfo.short.toLowerCase())) ||
                    (filterInfo.short && row.textContent.toLowerCase().includes(filterInfo.short.toLowerCase()))
                );
            }

            // 2. Payment Mode match
            let matchesMode = true;
            if (selectedCollectionModeFilter) {
                const modeVal = (row.getAttribute('data-pymnt-mode') || row.textContent).toLowerCase();
                matchesMode = modeVal.includes(selectedCollectionModeFilter.toLowerCase());
            }

            // 3. Search query match
            let matchesSearch = true;
            if (rawSearch) {
                const rowRawText = row.textContent.toLowerCase();
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

        // Fail-safe: If totalAmount is 0 but we matched rows and have pre-calculated chartMonthTotal
        if (totalAmount === 0 && matchCount > 0 && chartMonthTotal !== null && !rawSearch && !selectedCollectionModeFilter) {
            totalAmount = chartMonthTotal;
        }

        lastActiveTotalAmount = totalAmount;
        lastActiveMatchCount = matchCount;

        // Update dynamic aggregated total alongside table
        if (cfg.totalBadgeId) {
            const totalBadge = document.querySelector(cfg.totalBadgeId);
            if (totalBadge) {
                if (!totalBadge.getAttribute('data-original')) {
                    totalBadge.setAttribute('data-original', totalBadge.textContent.trim());
                }
                if (selectedCollectionMonthFilter || rawSearch || selectedCollectionModeFilter) {
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
                if (selectedCollectionMonthFilter) {
                    banner.style.display = 'block';
                    if (label) label.textContent = selectedCollectionMonthFilter;
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
                if (selectedCollectionMonthFilter || rawSearch) {
                    counter.textContent = `${matchCount} of ${totalRows} Shown`;
                } else {
                    counter.textContent = `${totalRows} ${cfg.defaultSuffix}`;
                }
            }
        }

        // Pulse animation feedback on card
        if (shouldAnimateCard && cfg.cardId && selectedCollectionMonthFilter) {
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

        if (selectedCollectionMonthFilter || selectedCollectionModeFilter) {
            dashCollectedVal.textContent = `₹ ${lastActiveTotalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (dashCollectedSub) {
                dashCollectedSub.textContent = `${lastActiveMatchCount} receipts (${selectedCollectionMonthFilter || 'Filtered'})`;
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
        
        // 1. Doughnut Chart: Expense Category Outlays Breakdown
        if (expenseChartCanvas && data.categories && data.categories.length > 0) {
            if (categoryChartInstance) {
                categoryChartInstance.destroy();
            }

            const labels = data.categories.map(c => c.category);
            const values = data.categories.map(c => c.total);
            
            const vibrantPalette = [
                '#3b82f6', // Electric Blue
                '#10b981', // Emerald Green
                '#f59e0b', // Amber Orange
                '#f43f5e', // Rose / Red
                '#8b5cf6', // Violet
                '#06b6d4', // Cyan
                '#ec4899', // Pink
                '#64748b'  // Slate
            ];
            
            categoryChartInstance = new Chart(expenseChartCanvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: vibrantPalette.slice(0, labels.length),
                        borderWidth: 3,
                        borderColor: chartCardBg,
                        hoverOffset: 8
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
                                padding: 14,
                                color: textColor,
                                font: { size: 12, weight: 600 }
                            }
                        },
                        tooltip: {
                            backgroundColor: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(15, 23, 42, 0.95)',
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
                                    return ` ₹ ${val.toLocaleString('en-IN')}`;
                                }
                            }
                        }
                    },
                    cutout: '68%'
                }
            });
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
                                    const isSelected = labels[context.dataIndex] === selectedMonthFilter;
                                    return ` Incurred: ₹ ${val.toLocaleString('en-IN')}${isSelected ? ' (Active Filter)' : ' • Click to filter'}`;
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

        if (selectedMonthFilter || selectedCategoryFilter) {
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
                                    const isSelected = labels[context.dataIndex] === selectedCollectionMonthFilter;
                                    return ` Collected: ₹ ${val.toLocaleString('en-IN')}${isSelected ? ' (Active Filter)' : ' • Click to filter'}`;
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

        if (selectedCollectionMonthFilter || selectedCollectionModeFilter) {
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

// Expose functions globally for HTML onclick handlers and cross-script integration
window.parseVoucherMonthYear = parseVoucherMonthYear;
window.getBarColors = getBarColors;
window.getCollectionBarColors = getCollectionBarColors;

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
