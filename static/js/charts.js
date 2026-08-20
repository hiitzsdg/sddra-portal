// ==========================================================================
// South Dumdum Enclave Residents' Association (SDDRA)
// Dual-Theme Interactive Visualizations & Analytics Engine (Chart.js)
// ==========================================================================

let categoryChartInstance = null;
let monthlyChartInstance = null;
let cachedChartData = null;

document.addEventListener('DOMContentLoaded', async () => {
    await renderAllCharts();

    window.addEventListener('themeChanged', (e) => {
        if (cachedChartData) {
            renderAllCharts(cachedChartData);
        }
    });
});

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
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
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
            
            monthlyChartInstance = new Chart(monthlyTrendCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Expenditure (₹)',
                        data: values,
                        backgroundColor: isLight ? 'rgba(37, 99, 235, 0.85)' : 'rgba(59, 130, 246, 0.85)',
                        hoverBackgroundColor: '#1d4ed8',
                        borderRadius: 6,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
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
                                    return ` Incurred: ₹ ${val.toLocaleString('en-IN')}`;
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
        }
    } catch (e) {
        console.warn('Note: Chart visualizer skipped or offline data mode active:', e);
    }
}
