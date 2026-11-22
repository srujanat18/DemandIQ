// DemandIQ Dashboard JavaScript & Chart.js Integration

document.addEventListener("DOMContentLoaded", function () {
    initMonthlyChart();
    initCategoryChart();
    initForecastChart();
});

function showAlert(message, type = "success") {
    const container = document.getElementById("alertContainer");
    if (!container) return;

    container.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show shadow-sm" role="alert">
            <i class="bi bi-info-circle-fill me-2"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
}

// ----------------- PIPELINE TRIGGERS ----------------- //

async function triggerFullPipeline() {
    const btn = document.getElementById("btnRunFull");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Executing ETL...`;
    }
    showAlert("Running Master ETL Pipeline (Extract -> Clean -> Transform -> Load -> Forecast)...", "info");

    try {
        const response = await fetch("/api/pipeline/run-full", { method: "POST" });
        const result = await response.json();
        if (result.success) {
            showAlert(`Master ETL Pipeline completed successfully! Processed ${result.data.records_processed} records. Reloading...`, "success");
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showAlert(`Pipeline execution failed: ${result.error}`, "danger");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-play-circle-fill me-1"></i> Run Master ETL`;
            }
        }
    } catch (err) {
        showAlert(`Error triggering pipeline: ${err}`, "danger");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-play-circle-fill me-1"></i> Run Master ETL`;
        }
    }
}

async function triggerIncrementalPipeline() {
    const btn = document.getElementById("btnRunIncremental");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Processing Delta...`;
    }
    showAlert("Checking high-watermark and processing incremental batch...", "info");

    try {
        const response = await fetch("/api/pipeline/run-incremental", { method: "POST" });
        const result = await response.json();
        if (result.success) {
            const data = result.data;
            if (data.status === "UP_TO_DATE") {
                showAlert("Database is already up to date! Watermark indicates no new records were detected.", "secondary");
            } else {
                showAlert(`Incremental load succeeded! Processed ${data.new_records_count} new records. New watermark: ${data.new_watermark.last_processed_sale_id}. Reloading...`, "success");
            }
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showAlert(`Incremental pipeline failed: ${result.error}`, "danger");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i> Run Incremental Load`;
            }
        }
    } catch (err) {
        showAlert(`Error triggering incremental pipeline: ${err}`, "danger");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i> Run Incremental Load`;
        }
    }
}

// ----------------- CHARTS INITIALIZATION ----------------- //

function initMonthlyChart() {
    const ctx = document.getElementById("monthlyTrendChart");
    if (!ctx) return;

    fetch("/api/charts/monthly")
        .then(r => r.json())
        .then(data => {
            new Chart(ctx, {
                type: "bar",
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: "Total Revenue ($)",
                            data: data.revenue,
                            backgroundColor: "rgba(37, 99, 235, 0.75)",
                            borderColor: "rgb(37, 99, 235)",
                            borderWidth: 1,
                            borderRadius: 6,
                            yAxisID: "y"
                        },
                        {
                            label: "Units Sold",
                            data: data.units,
                            type: "line",
                            borderColor: "rgb(16, 185, 129)",
                            backgroundColor: "rgba(16, 185, 129, 0.1)",
                            tension: 0.3,
                            fill: true,
                            yAxisID: "y1"
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    scales: {
                        y: {
                            type: "linear",
                            position: "left",
                            ticks: {
                                callback: val => "$" + val.toLocaleString()
                            },
                            grid: { color: "#f1f5f9" }
                        },
                        y1: {
                            type: "linear",
                            position: "right",
                            grid: { drawOnChartArea: false }
                        },
                        x: { grid: { display: false } }
                    }
                }
            });
        });
}

function initCategoryChart() {
    const ctx = document.getElementById("categoryChart");
    if (!ctx) return;

    fetch("/api/charts/categories")
        .then(r => r.json())
        .then(data => {
            new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.revenue,
                        backgroundColor: [
                            "#2563eb", "#06b6d4", "#10b981", "#f59e0b", "#8b5cf6"
                        ],
                        borderWidth: 2,
                        borderColor: "#ffffff"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom" },
                        tooltip: {
                            callbacks: {
                                label: ctx => ` ${ctx.label}: $${ctx.raw.toLocaleString()}`
                            }
                        }
                    }
                }
            });
        });
}

function initForecastChart() {
    const ctx = document.getElementById("forecastChart");
    if (!ctx) return;

    fetch("/api/charts/forecast")
        .then(r => r.json())
        .then(data => {
            new Chart(ctx, {
                type: "line",
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: "Predicted Total Daily Units",
                        data: data.values,
                        borderColor: "#2563eb",
                        backgroundColor: "rgba(37, 99, 235, 0.1)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            title: { display: true, text: "Projected Units Demanded" },
                            grid: { color: "#f1f5f9" }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { maxTicksLimit: 12 }
                        }
                    }
                }
            });
        });
}
