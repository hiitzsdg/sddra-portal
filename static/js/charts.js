// Charts initialization using Chart.js for Association Expenses & Breakdown

document.addEventListener('DOMContentLoaded', async () => {
    const expenseChartCanvas = document.getElementById('expenseCategoryChart');
    const monthlyTrendCanvas = document.getElementById('expenseMonthlyChart');
    
    if (!expenseChartCanvas && !monthlyTrendCanvas) return;
    
    try {
        const response = await fetch('/api/expenses/chart-data');
        const data = await response.json();
        
        if (expenseChartCanvas && data.categories) {
            const labels = data.categories.map(c => c.category);
            const values = data.categories.map(c => c.total);
            
            const palette = [
                '#2563eb', '#10b981', '#f59e0b', '#ef4444', 
                '#8b5cf6', '#06b6d4', '#ec4899', '#64748b'
            ];
            
            new Chart(expenseChartCanvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: palette.slice(0, labels.length),
                        borderWidth: 2,
                        borderColor: '#ffffff'
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
                                font: { family: 'Plus Jakarta Sans', size: 12 }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const val = context.raw || 0;
                                    return ` ₹ ${val.toLocaleString('en-IN')}`;
                                }
                            }
                        }
                    },
                    cutout: '65%'
                }
            });
        }
        
        if (monthlyTrendCanvas && data.monthly) {
            const labels = data.monthly.map(m => m.month);
            const values = data.monthly.map(m => m.total);
            
            new Chart(monthlyTrendCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Expenditure (₹)',
                        data: values,
                        backgroundColor: 'rgba(37, 99, 235, 0.85)',
                        hoverBackgroundColor: '#1d4ed8',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
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
                            grid: { color: '#f1f5f9' },
                            ticks: {
                                callback: function(val) {
                                    return '₹' + (val / 1000) + 'k';
                                }
                            }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }
    } catch (e) {
        console.error('Error loading chart data:', e);
    }
});
