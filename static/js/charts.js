/*
  SmartSpend Dashboard Charts Renderer
  Configures Chart.js canvas elements with premium gradients and styled tooltips
*/

document.addEventListener("DOMContentLoaded", () => {
    const canvas = document.getElementById('dashboardChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Prepare values from initialChartValues defined in HTML
    const labels = Object.keys(initialChartValues);
    const dataValues = Object.values(initialChartValues);
    
    // Filter categories with values > 0. If all are 0, display a dummy dataset representing empty state
    const hasData = dataValues.some(val => val > 0);
    
    let displayLabels = labels;
    let displayValues = dataValues;
    let backgroundColors = chartColors;
    let hoverBackgroundColors = chartColors;
    
    if (!hasData) {
        displayLabels = ['No Data Yet'];
        displayValues = [1];
        backgroundColors = ['rgba(255, 255, 255, 0.05)'];
        hoverBackgroundColors = ['rgba(255, 255, 255, 0.08)'];
    } else {
        // Match colors to categories
        backgroundColors = labels.map((_, i) => chartColors[i % chartColors.length]);
    }
    
    // Render Doughnut Chart
    const dashboardChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: displayLabels,
            datasets: [{
                data: displayValues,
                backgroundColor: backgroundColors,
                hoverBackgroundColor: hoverBackgroundColors,
                borderWidth: 2,
                borderColor: 'var(--bg-secondary)',
                hoverOffset: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            radius: '90%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: 'var(--text-secondary)',
                        padding: 16,
                        font: {
                            family: 'Plus Jakarta Sans',
                            size: 12,
                            weight: '500'
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#fff',
                    bodyColor: 'var(--text-secondary)',
                    borderColor: 'var(--border-color)',
                    borderWidth: 1,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true,
                    callbacks: {
                        label: function(context) {
                            if (!hasData) return 'Speak or add expenses to populate';
                            let label = context.label || '';
                            let value = context.parsed;
                            return ` Spent: ${currencySymbol}${value.toFixed(2)}`;
                        }
                    }
                }
            },
            layout: {
                padding: {
                    bottom: 10
                }
            }
        }
    });
});
