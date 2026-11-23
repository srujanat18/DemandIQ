// DemandIQ Interactive Dashboard & Manufacturing Intelligence Engine

let currentDetailChart = null;

document.addEventListener("DOMContentLoaded", function () {
    // Initialize Perspective (Manufacturer vs Data Engineer)
    initPerspective();

    // Initialize Global Charts
    initMonthlyChart();
    initCategoryChart();
    initForecastChart();

    // Initialize Interactive Manufacturer Tools
    loadProductDropdowns();

    // Initialize Drag & Drop File Upload
    setupDropZone();
});

function showAlert(message, type = "success") {
    const container = document.getElementById("alertContainer");
    if (!container) return;

    container.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show shadow-sm rounded-3" role="alert">
            <i class="bi bi-info-circle-fill me-2"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ----------------- PERSPECTIVE TOGGLE (MANUFACTURER VS ENGINEER) ----------------- //

function initPerspective() {
    const saved = localStorage.getItem("demandiq_perspective") || "manufacturer";
    setPerspective(saved, false);
}

function setPerspective(mode, save = true) {
    if (save) localStorage.setItem("demandiq_perspective", mode);

    const btnMfg = document.getElementById("btnModeManufacturer");
    const btnEng = document.getElementById("btnModeEngineer");

    if (mode === "manufacturer") {
        if (btnMfg) {
            btnMfg.className = "btn btn-sm btn-primary py-1 px-2 text-nowrap fw-medium";
        }
        if (btnEng) {
            btnEng.className = "btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap text-light";
        }
        // Hide complex engineering-only buttons in top header if in factory mode
        document.querySelectorAll(".eng-only-btn").forEach(el => el.classList.add("d-none"));
    } else {
        if (btnMfg) {
            btnMfg.className = "btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap text-light";
        }
        if (btnEng) {
            btnEng.className = "btn btn-sm btn-primary py-1 px-2 text-nowrap fw-medium";
        }
        document.querySelectorAll(".eng-only-btn").forEach(el => el.classList.remove("d-none"));
    }
}

// ----------------- INTERACTIVE PRODUCT INSPECTOR ----------------- //

async function loadProductDropdowns() {
    const selector = document.getElementById("productSelector");
    const simSelector = document.getElementById("simProductSelect");
    if (!selector && !simSelector) return;

    try {
        const resp = await fetch("/api/products/list");
        const data = await resp.json();
        if (data.success && data.products.length > 0) {
            let optionsHtml = "";
            data.products.forEach(p => {
                optionsHtml += `<option value="${p.product_id}">${p.product_name} (Stock: ${p.stock_quantity})</option>`;
            });

            if (selector) {
                selector.innerHTML = optionsHtml;
                // Auto-load first product
                loadProductDetails(data.products[0].product_id);
            }
            if (simSelector) {
                simSelector.innerHTML = optionsHtml;
                runSimulation();
            }
        }
    } catch (err) {
        console.error("Error loading products:", err);
    }
}

function selectProductInInspector(productId) {
    const selector = document.getElementById("productSelector");
    if (selector) {
        selector.value = productId;
        loadProductDetails(productId);
        selector.scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

async function loadProductDetails(productId) {
    if (!productId) return;
    const loader = document.getElementById("inspectorLoading");
    const content = document.getElementById("inspectorContent");
    if (loader) loader.classList.remove("d-none");

    try {
        const resp = await fetch(`/api/products/details/${productId}`);
        const data = await resp.json();
        if (loader) loader.classList.add("d-none");

        if (data.success) {
            const p = data.product;
            document.getElementById("prodStock").innerText = p.stock;
            document.getElementById("prodReorder").innerText = `Min alert level: ${p.reorder_level}`;
            document.getElementById("prodDemand").innerText = `${p.forecast_30d} units`;
            
            const daysEl = document.getElementById("prodDaysLeft");
            daysEl.innerText = `${p.days_remaining} Days`;
            if (p.days_remaining <= 10) {
                daysEl.className = "fw-bold my-1 text-danger";
            } else if (p.days_remaining <= 20) {
                daysEl.className = "fw-bold my-1 text-warning";
            } else {
                daysEl.className = "fw-bold my-1 text-success";
            }

            const recEl = document.getElementById("prodRecommend");
            if (p.recommended_build > 0) {
                recEl.innerText = `+${p.recommended_build} Units`;
            } else {
                recEl.innerText = `0 Needed`;
            }

            // Coverage percentage calculation
            const coverage = Math.min(200, Math.round((p.stock / (p.forecast_30d || 1)) * 100));
            document.getElementById("stockCoveragePct").innerText = `${coverage}% of monthly demand in stock`;
            const bar = document.getElementById("stockProgressBar");
            bar.style.width = `${Math.min(100, coverage)}%`;
            if (coverage < 50) {
                bar.className = "progress-bar bg-danger";
            } else if (coverage < 90) {
                bar.className = "progress-bar bg-warning";
            } else {
                bar.className = "progress-bar bg-success";
            }

            // Update Chart
            renderProductDetailChart(data.history, data.forecast);
        }
    } catch (err) {
        if (loader) loader.classList.add("d-none");
        console.error("Error loading product details:", err);
    }
}

function renderProductDetailChart(history, forecast) {
    const ctx = document.getElementById("productDetailChart");
    if (!ctx) return;

    if (currentDetailChart) {
        currentDetailChart.destroy();
    }

    // Combine historical dates and forecast dates
    const labels = [...history.dates.slice(-14), ...forecast.dates.slice(0, 14)];
    const histData = [...history.values.slice(-14), ...new Array(forecast.dates.slice(0, 14).length).fill(null)];
    const fcData = [...new Array(history.dates.slice(-14).length).fill(null), ...forecast.values.slice(0, 14)];

    currentDetailChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Historical Daily Sales",
                    data: histData,
                    borderColor: "#64748b",
                    backgroundColor: "rgba(100, 116, 139, 0.1)",
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 3
                },
                {
                    label: "Predicted Future Demand",
                    data: fcData,
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37, 99, 235, 0.15)",
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: { beginAtZero: true, grid: { color: "#f8fafc" } },
                x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }
            },
            plugins: {
                legend: { position: "top", labels: { boxWidth: 12 } }
            }
        }
    });
}

// ----------------- WHAT-IF PRODUCTION SIMULATOR ----------------- //

function updateSimUnits(val) {
    document.getElementById("simUnitsLabel").innerText = `+${val} units`;
    runSimulation();
}

function updateSimDemand(val) {
    const sign = val > 0 ? "+" : "";
    document.getElementById("simDemandLabel").innerText = `${sign}${val}%`;
    runSimulation();
}

async function runSimulation() {
    const productSelect = document.getElementById("simProductSelect");
    const unitsRange = document.getElementById("simUnitsRange");
    const demandRange = document.getElementById("simDemandRange");
    if (!productSelect || !unitsRange || !demandRange) return;

    const payload = {
        product_id: parseInt(productSelect.value) || 101,
        additional_production: parseInt(unitsRange.value) || 0,
        demand_change_pct: parseFloat(demandRange.value) || 0.0
    };

    try {
        const resp = await fetch("/api/simulator/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById("simDaysText").innerText = `Stock will last ~${data.days_remaining} days`;
            document.getElementById("simAdviceText").innerText = data.message;
            document.getElementById("simTotalAvail").innerText = `${data.total_available} units`;
            document.getElementById("simAdjDemand").innerText = `${data.adjusted_demand} units`;

            const badge = document.getElementById("simStatusBadge");
            badge.innerText = data.status;
            badge.className = `badge bg-${data.status_class}`;
        }
    } catch (err) {
        console.error("Simulation error:", err);
    }
}

// ----------------- DRAG & DROP CSV UPLOAD ----------------- //

function setupDropZone() {
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener("click", () => fileInput.click());

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("border-primary", "bg-primary-subtle");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("border-primary", "bg-primary-subtle");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("border-primary", "bg-primary-subtle");
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });
}

function handleFileSelect(file) {
    const feedback = document.getElementById("uploadFeedback");
    if (feedback) {
        feedback.innerHTML = `
            <div class="alert alert-info py-2 mb-0">
                <i class="bi bi-filetype-csv me-1"></i> Selected: <strong>${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)
            </div>
        `;
    }
}

async function submitFileUpload() {
    const fileInput = document.getElementById("fileInput");
    const btn = document.getElementById("btnUploadSubmit");
    const feedback = document.getElementById("uploadFeedback");

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        if (feedback) {
            feedback.innerHTML = `<div class="alert alert-danger py-2 mb-0">Please select a CSV file first.</div>`;
        }
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Cleaning & Processing...`;
    }

    try {
        const resp = await fetch("/api/upload/sales-data", {
            method: "POST",
            body: formData
        });
        const result = await resp.json();

        if (result.success) {
            if (feedback) {
                feedback.innerHTML = `
                    <div class="alert alert-success py-2 mb-0">
                        <i class="bi bi-check-circle-fill me-1"></i> ${result.message}<br/>
                        <small>Duplicates removed: ${result.duplicates_removed} | Acceptance rate: ${result.acceptance_rate}</small>
                    </div>
                `;
            }
            setTimeout(() => window.location.reload(), 1500);
        } else {
            if (feedback) {
                feedback.innerHTML = `<div class="alert alert-danger py-2 mb-0">${result.error}</div>`;
            }
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-check2-circle me-1"></i> Clean & Ingest Data`;
            }
        }
    } catch (err) {
        if (feedback) {
            feedback.innerHTML = `<div class="alert alert-danger py-2 mb-0">Upload failed: ${err}</div>`;
        }
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-check2-circle me-1"></i> Clean & Ingest Data`;
        }
    }
}

// ----------------- PIPELINE TRIGGERS ----------------- //

async function triggerFullPipeline() {
    const btn = document.getElementById("btnRunFull");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Rebuilding...`;
    }
    showAlert("Rebuilding entire warehouse (Extract -> Clean -> Star Schema -> Forecast)...", "info");

    try {
        const response = await fetch("/api/pipeline/run-full", { method: "POST" });
        const result = await response.json();
        if (result.success) {
            showAlert(`Warehouse refreshed! Processed ${result.data.records_processed} records. Reloading...`, "success");
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showAlert(`Pipeline failed: ${result.error}`, "danger");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-play-circle-fill me-1"></i> Rebuild Warehouse`;
            }
        }
    } catch (err) {
        showAlert(`Error: ${err}`, "danger");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-play-circle-fill me-1"></i> Rebuild Warehouse`;
        }
    }
}

async function triggerIncrementalPipeline() {
    const btn = document.getElementById("btnRefreshPipeline");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Syncing...`;
    }
    showAlert("Syncing latest data updates and refreshing forecasts...", "info");

    try {
        const response = await fetch("/api/pipeline/run-incremental", { method: "POST" });
        const result = await response.json();
        if (result.success) {
            const data = result.data;
            if (data.status === "UP_TO_DATE") {
                showAlert("Your inventory and demand data is already completely up to date!", "info");
            } else {
                showAlert(`Synced ${data.new_records_count} new transactions! Schedule updated. Reloading...`, "success");
            }
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showAlert(`Sync failed: ${result.error}`, "danger");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i> Sync Latest Data`;
            }
        }
    } catch (err) {
        showAlert(`Error: ${err}`, "danger");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i> Sync Latest Data`;
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
                            label: "Total Sales Revenue ($)",
                            data: data.revenue,
                            backgroundColor: "rgba(37, 99, 235, 0.8)",
                            borderColor: "rgb(37, 99, 235)",
                            borderRadius: 6,
                            yAxisID: "y"
                        },
                        {
                            label: "Units Delivered",
                            data: data.units,
                            type: "line",
                            borderColor: "rgb(16, 185, 129)",
                            backgroundColor: "rgba(16, 185, 129, 0.15)",
                            tension: 0.35,
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
                            ticks: { callback: val => "$" + val.toLocaleString() },
                            grid: { color: "#f8fafc" }
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
                        backgroundColor: ["#2563eb", "#06b6d4", "#10b981", "#f59e0b", "#8b5cf6"],
                        borderWidth: 3,
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
                        label: "Projected Units to Fulfill",
                        data: data.values,
                        borderColor: "#2563eb",
                        backgroundColor: "rgba(37, 99, 235, 0.12)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { title: { display: true, text: "Total Projected Daily Units" }, grid: { color: "#f8fafc" } },
                        x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } }
                    }
                }
            });
        });
}
