// ==========================================================================
// South Dumdum Enclave Residents' Association (SDDRA)
// Dual-Theme Interactive Visualizations & Analytics Engine (Chart.js)
// ==========================================================================

let categoryChartInstance = null;
let monthlyChartInstance = null;
let cachedChartData = null;

// Global filter states
let selectedMonthFilter = null;
let selectedCategoryFilter = null;

document.addEventListener('DOMContentLoaded', async () => {
    await renderAllCharts();

    window.addEventListener('themeChanged', (e) => {
        if (cachedChartData) {
            renderAllCharts(cachedChartData);
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

// Generate bar dataset colors based on current active selection
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

// Update chart visual styles when a filter is toggled
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

// Render or update interactive month filter pills below chart
function updateMonthPillsVisual() {
    const containers = document.querySelectorAll('#expenseMonthlyPills');
    if (!containers || containers.length === 0 || !cachedChartData || !cachedChartData.monthly) return;

    containers.forEach(container => {
        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
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

// Toggle month filter when bar or pill is clicked
function toggleMonthExpenditureFilter(clickedMonth) {
    if (selectedMonthFilter === clickedMonth) {
        selectedMonthFilter = null;
    } else {
        selectedMonthFilter = clickedMonth;
    }
    updateChartVisualSelection();
    applyExpenditureFilters(true);
}

// Clear active month filter
function clearMonthlyChartFilter() {
    selectedMonthFilter = null;
    updateChartVisualSelection();
    applyExpenditureFilters(false);
}

// Toggle category filter when doughnut slice is clicked
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

        // Double fail-safe: If totalAmount is 0 but we matched rows and have pre-calculated chartMonthTotal
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

// Expose globally for HTML onclick handlers
window.toggleMonthExpenditureFilter = toggleMonthExpenditureFilter;
window.clearMonthlyChartFilter = clearMonthlyChartFilter;
window.toggleCategoryExpenditureFilter = toggleCategoryExpenditureFilter;
window.applyExpenditureFilters = applyExpenditureFilters;

async function renderAllCharts(existingData = null) {
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
        
        // 1. Doughnut Chart: Category Outlays Breakdown
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

            // Native DOM click & touch event listener for fail-safe trigger
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

        // Render interactive month pills below chart
        updateMonthPillsVisual();

        // Re-apply any active filters
        if (selectedMonthFilter || selectedCategoryFilter) {
            applyExpenditureFilters(false);
        }
    } catch (e) {
        console.warn('Note: Chart visualizer skipped or offline data mode active:', e);
    }
}


