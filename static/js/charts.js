// ==========================================================================
// South Dumdum Enclave Residents' Association (SDDRA)
// Interactive Visualizations & Dark-Mode Analytics Engine (Chart.js)
// ==========================================================================

document.addEventListener('DOMContentLoaded', async () => {
    const expenseChartCanvas = document.getElementById('expenseCategoryChart');
    const monthlyTrendCanvas = document.getElementById('expenseMonthlyChart');
    
    if (!expenseChartCanvas && !monthlyTrendCanvas) return;
    
    // Set Chart.js global typography and defaults
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif";
        Chart.defaults.color = '#94a3b8';
    }
    
    try {
        const response = await fetch('/api/expenses/chart-data');
        if (!response.ok) return;
        const data = await response.json();
        
        // 1. Doughnut Chart: Category Outlays Breakdown
        if (expenseChartCanvas && data.categories && data.categories.length > 0) {
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
            
            new Chart(expenseChartCanvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: vibrantPalette.slice(0, labels.length),
                        borderWidth: 3,
                        borderColor: '#0f172a',
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
                                color: '#cbd5e1',
                                font: { size: 12, weight: 600 }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleColor: '#ffffff',
                            bodyColor: '#60a5fa',
                            borderColor: 'rgba(59, 130, 246, 0.4)',
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
            const labels = data.monthly.map(m => m.month);
            const values = data.monthly.map(m => m.total);
            
            new Chart(monthlyTrendCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Expenditure (₹)',
                        data: values,
                        backgroundColor: 'rgba(59, 130, 246, 0.85)',
                        hoverBackgroundColor: '#2563eb',
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
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleColor: '#ffffff',
                            bodyColor: '#34d399',
                            borderColor: 'rgba(16, 185, 129, 0.4)',
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
                                color: 'rgba(255, 255, 255, 0.07)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: { size: 11 },
                                callback: function(val) {
                                    return '₹' + (val / 1000) + 'k';
                                }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#cbd5e1',
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
});
