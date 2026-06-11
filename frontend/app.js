// /* ==========================================================================
//    COMPENSATION CALCULATOR WORKSTATION - FRONTEND DASHBOARD ENGINE
//    ========================================================================== */
// 
// // Global Error Handler to shield against silent crashes (Task 19)
// window.onerror = function(msg, src, line, col, err) {
//     console.error("GLOBAL ERROR DETECTED:", msg, "at", src, "line:", line, err);
// };
// 
// document.addEventListener("DOMContentLoaded", () => {
// 
//     // --- STATE VARIABLES ---
//     let activeTab = "calculator";
//     let fileQueue = []; // Local file tracker
//     let uploadedFileObjects = {}; // Maps filename -> File object for local blob previews
//     let isPolling = false;
//     let currentCalculationAmount = 0;
//     let currentOcrRawText = []; // Recover raw text from the last successful single OCR
// 
//     // Global Cache for Extracted Field Population (Part 5)
//     let lastExtractedFields = {};
//     let lastExtractedConfidences = {};
// 
//     // --- OCR LIVE TIMER STATE & HELPERS ---
//     let ocrTimerInterval = null;
//     let ocrSecondsElapsed = 0;
// 
//     function formatTimeMMSS(totalSeconds) {
//         const minutes = Math.floor(totalSeconds / 60);
//         const seconds = totalSeconds % 60;
//         return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
//     }
// 
//     function startOcrTimer() {
//         if (ocrTimerInterval) {
//             clearInterval(ocrTimerInterval);
//         }
//         ocrSecondsElapsed = 0;
// 
//         const timerContainer = document.getElementById("ocr-timer-container");
//         const statusIcon = document.getElementById("ocr-timer-status-icon");
//         const statusText = document.getElementById("ocr-timer-status-text");
//         const elapsedText = document.getElementById("ocr-timer-elapsed");
// 
//         const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
//         const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");
// 
//         if (timerContainer) {
//             timerContainer.classList.remove("hidden-section");
//             timerContainer.style.display = "flex";
//         }
//         if (statusIcon) {
//             statusIcon.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-glow" style="color: var(--color-primary);"></i>`;
//         }
//         if (statusText) {
//             statusText.textContent = "Processing PDF...";
//             statusText.style.color = "var(--text-primary)";
//         }
//         if (elapsedText) {
//             elapsedText.textContent = "00:00";
//             elapsedText.style.color = "var(--color-primary)";
//         }
// 
//         if (headerTimerContainer) {
//             headerTimerContainer.classList.remove("hidden-section");
//             headerTimerContainer.style.display = "inline-flex";
//             headerTimerContainer.style.color = "var(--color-primary)";
//             headerTimerContainer.style.borderColor = "rgba(11, 58, 114, 0.25)";
//             headerTimerContainer.style.background = "rgba(11, 58, 114, 0.06)";
//         }
//         if (headerElapsedText) {
//             headerElapsedText.textContent = "00:00";
//         }
// 
//         ocrTimerInterval = setInterval(() => {
//             ocrSecondsElapsed++;
//             const formattedTime = formatTimeMMSS(ocrSecondsElapsed);
//             if (elapsedText) {
//                 elapsedText.textContent = formattedTime;
//             }
//             if (headerElapsedText) {
//                 headerElapsedText.textContent = formattedTime;
//             }
//             const loaderTimer = document.getElementById("ocr-loader-timer");
//             if (loaderTimer) {
//                 loaderTimer.textContent = formattedTime;
//             }
//         }, 1000);
//     }
// 
//     function stopOcrTimerSuccess() {
//         if (ocrTimerInterval) {
//             clearInterval(ocrTimerInterval);
//             ocrTimerInterval = null;
//         }
//         const statusIcon = document.getElementById("ocr-timer-status-icon");
//         const statusText = document.getElementById("ocr-timer-status-text");
//         const elapsedText = document.getElementById("ocr-timer-elapsed");
// 
//         const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
//         const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");
// 
//         if (statusIcon) {
//             statusIcon.innerHTML = `<i class="fa-solid fa-circle-check" style="color: var(--color-success);"></i>`;
//         }
//         if (statusText) {
//             statusText.textContent = "✅ OCR Complete";
//             statusText.style.color = "var(--color-success)";
//         }
//         if (elapsedText) {
//             elapsedText.textContent = `Total Time: ${formatTimeMMSS(ocrSecondsElapsed)}`;
//             elapsedText.style.color = "var(--color-success)";
//         }
// 
//         if (headerElapsedText && headerTimerContainer) {
//             headerElapsedText.textContent = `✅ Complete: ${formatTimeMMSS(ocrSecondsElapsed)}`;
//             headerTimerContainer.style.color = "var(--color-success)";
//             headerTimerContainer.style.borderColor = "rgba(22, 163, 74, 0.3)";
//             headerTimerContainer.style.background = "rgba(22, 163, 74, 0.08)";
//         }
//     }
// 
//     function stopOcrTimerFailure() {
//         if (ocrTimerInterval) {
//             clearInterval(ocrTimerInterval);
//             ocrTimerInterval = null;
//         }
//         const statusIcon = document.getElementById("ocr-timer-status-icon");
//         const statusText = document.getElementById("ocr-timer-status-text");
//         const elapsedText = document.getElementById("ocr-timer-elapsed");
// 
//         const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
//         const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");
// 
//         if (statusIcon) {
//             statusIcon.innerHTML = `<i class="fa-solid fa-circle-xmark" style="color: var(--color-danger);"></i>`;
//         }
//         if (statusText) {
//             statusText.textContent = "❌ OCR Failed";
//             statusText.style.color = "var(--color-danger)";
//         }
//         if (elapsedText) {
//             elapsedText.textContent = `OCR Failed after ${formatTimeMMSS(ocrSecondsElapsed)}`;
//             elapsedText.style.color = "var(--color-danger)";
//         }
// 
//         if (headerElapsedText && headerTimerContainer) {
//             headerElapsedText.textContent = `❌ Failed: ${formatTimeMMSS(ocrSecondsElapsed)}`;
//             headerTimerContainer.style.color = "var(--color-danger)";
//             headerTimerContainer.style.borderColor = "rgba(220, 38, 38, 0.3)";
//             headerTimerContainer.style.background = "rgba(220, 38, 38, 0.08)";
//         }
//     }
// 
//     // Programmatically Inject Suggestion Badge CSS Styles
//     const styleEl = document.createElement("style");
//     styleEl.innerHTML = `
//         .suggested-badge {
//             display: inline-flex !important;
//             align-items: center !important;
//             gap: 6px !important;
//             margin-top: 6px !important;
//             background: #fef3c7 !important; /* warm amber background for high contrast */
//             color: #b45309 !important; /* dark amber text for readable AAA-level contrast */
//             border: 1px solid #fde68a !important;
//             padding: 5px 10px !important;
//             border-radius: 6px !important;
//             font-size: 0.75rem !important;
//             font-weight: 600 !important;
//             cursor: pointer !important;
//             transition: all 0.2s ease !important;
//             user-select: none !important;
//             width: fit-content !important;
//             box-shadow: 0 1px 2px rgba(180, 83, 9, 0.08) !important;
//         }
//         .suggested-badge:hover {
//             background: #fcd34d !important;
//             border-color: #fbbf24 !important;
//             color: #78350f !important;
//             transform: translateY(-1px) !important;
//             box-shadow: 0 2px 4px rgba(180, 83, 9, 0.15) !important;
//         }
//         .low-confidence-input {
//             border-color: #fbbf24 !important;
//             box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.15) !important;
//         }
//     `;
//     document.head.appendChild(styleEl);
// 
//     // Dynamically Inject Audit Log Card (Part 7)
//     const ocrQualityTab = document.getElementById("pane-tab-ocr-quality-content");
//     if (ocrQualityTab) {
//         let auditCard = document.getElementById("extraction-audit-log-card");
//         if (!auditCard) {
//             auditCard = document.createElement("div");
//             auditCard.id = "extraction-audit-log-card";
//             auditCard.className = "card";
//             auditCard.style.marginTop = "20px";
//             auditCard.innerHTML = `
//                 <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
//                     <h3><i class="fa-solid fa-clipboard-list text-glow" style="color: #f59e0b;"></i> Case Type &amp; Extraction Audit Log</h3>
//                     <span class="badge tech-badge" id="audit-log-badge" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);">Audit Log</span>
//                 </div>
//                 <div class="card-body" style="padding-top: 12px; display: flex; flex-direction: column; gap: 15px;">
//                     <div class="metrics-grid" style="grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));">
//                         <div class="metric-item">
//                             <span class="label">User Case Type</span>
//                             <span class="value" id="audit-val-user-case" style="color: #60a5fa; font-weight: 600;">—</span>
//                         </div>
//                         <div class="metric-item">
//                             <span class="label">LLM Case Type</span>
//                             <span class="value" id="audit-val-llm-case" style="color: #c084fc; font-weight: 600;">—</span>
//                         </div>
//                         <div class="metric-item">
//                             <span class="label">OCR Evidence</span>
//                             <span class="value" id="audit-val-ocr-evidence" style="color: #34d399; font-weight: 600;">—</span>
//                         </div>
//                         <div class="metric-item">
//                             <span class="label">Avg Confidence</span>
//                             <span class="value" id="audit-val-confidence" style="color: #f59e0b; font-weight: 600;">—</span>
//                         </div>
//                         <div class="metric-item">
//                             <span class="label">Overwrite Blocked</span>
//                             <span class="value" id="audit-val-overwrite-blocked" style="font-weight: 700;">—</span>
//                         </div>
//                     </div>
//                     <div style="background: rgba(10, 15, 30, 0.6); border: 1px solid var(--border-glass); border-radius: var(--radius-sm); padding: 12px; font-family: monospace; font-size: 0.8rem; max-height: 150px; overflow-y: auto; line-height: 1.4; color: #94a3b8;" id="audit-log-terminal">
//                         <span style="color: #64748b;">[SYSTEM] Ready. Awaiting document upload or LLM extraction...</span>
//                     </div>
//                 </div>
//             `;
//             const rawCard = document.getElementById("ocr-raw-text-card");
//             if (rawCard) {
//                 ocrQualityTab.insertBefore(auditCard, rawCard);
//             } else {
//                 ocrQualityTab.appendChild(auditCard);
//             }
//         }
//     }
// 
//     // --- LLM CASE TYPE SUGGESTION ENGINE (Issue 2) ---
//     async function checkCaseType(selectedType, rawText) {
//         const container = document.getElementById("case-type-suggestion");
//         if (!container) return;
// 
//         if (!rawText || !rawText.trim()) {
//             container.innerHTML = "";
//             container.classList.add("hidden-section");
//             return;
//         }
// 
//         container.classList.remove("hidden-section");
//         container.innerHTML = `<div class="suggestion-loading">Analyzing case type...</div>`;
// 
//         try {
//             const response = await fetch("/api/ocr/suggest-case-type", {
//                 method: "POST",
//                 headers: {
//                     "Content-Type": "application/json"
//                 },
//                 body: JSON.stringify({
//                     raw_text: rawText,
//                     selected_case_type: selectedType
//                 })
//             });
// 
//             if (!response.ok) {
//                 throw new Error("Failed to fetch case type suggestions");
//             }
// 
//             const data = await response.json();
//             const suggestions = data.suggestions || [];
// 
//             if (suggestions.length === 0) {
//                 container.innerHTML = "";
//                 container.classList.add("hidden-section");
//                 return;
//             }
// 
//             // First item is the top prediction (since it is sorted descending by the backend)
//             const topPrediction = suggestions[0];
//             const topCategory = topPrediction.case_type;
//             const topConfidence = topPrediction.confidence;
// 
//             const topIsDeath = (topCategory === "Death");
//             const selectedIsDeath = (selectedType === "death");
//             const isMismatch = (topConfidence > 0.50) && (topIsDeath !== selectedIsDeath);
// 
//             let warningHtml = "";
//             if (isMismatch) {
//                 warningHtml = `
//                     <div class="case-warning">
//                         <i class="fa-solid fa-triangle-exclamation"></i>
//                         <span>⚠️ Document suggests ${topCategory} — please verify</span>
//                     </div>
//                 `;
//             }
// 
//             let barsHtml = '<div class="case-type-bars">';
//             suggestions.forEach(item => {
//                 const isDeathItem = (item.case_type === "Death");
//                 const isSelectedCategory = (isDeathItem && selectedIsDeath) || (!isDeathItem && !selectedIsDeath);
//                 const confidencePct = Math.round(item.confidence * 100);
//                 const selectedClass = isSelectedCategory ? "selected" : "";
// 
//                 barsHtml += `
//                     <div class="case-bar-row ${selectedClass}">
//                         <span class="case-label" title="${item.case_type}">${item.case_type}</span>
//                         <div class="bar-track">
//                             <div class="bar-fill" style="width: ${confidencePct}%"></div>
//                         </div>
//                         <span class="case-pct">${confidencePct}%</span>
//                     </div>
//                 `;
//             });
//             barsHtml += '</div>';
// 
//             container.innerHTML = warningHtml + barsHtml;
// 
//         } catch (error) {
//             console.error("Error checking case type:", error);
//             container.innerHTML = "";
//             container.classList.add("hidden-section");
//         }
//     }
// 
//     // --- DOM REFERENCES ---
//     const navItems = document.querySelectorAll(".nav-item");
//     const viewports = document.querySelectorAll(".tab-viewport");
//     const tabTitleText = document.getElementById("tab-title-text");
//     const dbStatusText = document.getElementById("db-status-text");
//     const statusDot = document.querySelector(".status-dot");
//     const serverStatus = document.getElementById("server-status");
//     const pulseIndicator = document.querySelector(".pulse-indicator");
// 
//     // TAB 1: CALCULATOR WORKSPACE
//     const caseTypeSelect = document.getElementById("case-type");
//     const sharedFields = document.getElementById("shared-fields");
//     const deathFields = document.getElementById("death-fields");
//     const injuryFields = document.getElementById("injury-fields");
//     const formActionsBar = document.getElementById("form-actions-bar");
//     const compensationForm = document.getElementById("compensation-form");
// 
//     // Single Case PDF Upload & Preview
//     const singleUploadSection = document.getElementById("single-upload-section");
//     const singleDropZone = document.getElementById("single-drop-zone");
//     const singleFileInput = document.getElementById("single-file-input");
//     const singlePreviewCard = document.getElementById("single-preview-card");
//     const singlePreviewContainer = document.getElementById("single-preview-container");
//     const singlePreviewFilename = document.getElementById("single-preview-filename");
//     const aiExtractBtn = document.getElementById("ai-extract-btn");
// 
//     // Age & Dates
//     const dobInput = document.getElementById("date-of-birth");
//     const doaInput = document.getElementById("date-of-accident");
//     const ageInput = document.getElementById("age");
// 
//     // Live previews
//     const liveMetricsCard = document.getElementById("live-metrics-card");
//     const liveAge = document.getElementById("live-age");
//     const liveMultiplier = document.getElementById("live-multiplier");
//     const liveProspects = document.getElementById("live-prospects");
//     const liveProspectsBar = document.getElementById("live-prospects-bar");
//     const liveProspectsItem = document.getElementById("live-prospects-item");
//     const liveDeductions = document.getElementById("live-deductions");
//     const liveDeductionsBar = document.getElementById("live-deductions-bar");
//     const liveDeductionsItem = document.getElementById("live-deductions-item");
// 
//     // Extra elements
//     const dependentsInput = document.getElementById("dependents");
//     const maritalStatusSelect = document.getElementById("marital-status");
//     const futureTypeSelect = document.getElementById("future-type");
//     const monthlyIncomeInput = document.getElementById("monthly-income");
// 
//     // Precedents benchmarking
//     const evaluatorCard = document.getElementById("evaluator-card");
//     const triggerEvalBtn = document.getElementById("trigger-eval-btn");
//     const evaluatorCardBody = document.getElementById("evaluator-card-body");
// 
//     // TAB 2: PDF LIBRARY
//     const dropZone = document.getElementById("drop-zone");
//     const fileInput = document.getElementById("file-input");
//     const batchFileList = document.getElementById("batch-file-list");
//     const queueBadge = document.getElementById("queue-badge");
//     const queueCountLabel = document.getElementById("queue-count-label");
//     const previewContainer = document.getElementById("preview-container");
//     const previewFilenameBadge = document.getElementById("preview-filename-badge");
// 
//     // TAB 3: AI LEGAL CHAT
//     const chatInput = document.getElementById("chat-input");
//     const chatSendBtn = document.getElementById("chat-send-btn");
//     const chatMessages = document.getElementById("chat-messages");
//     const chatCaseFilter = document.getElementById("chat-case-filter");
// 
//     // MODAL DASHBOARD
//     const resultsModal = document.getElementById("results-modal");
//     const modalBodyContent = document.getElementById("modal-body-content");
//     const closeModalBtn = document.getElementById("close-modal-btn");
//     const dismissModalBtn = document.getElementById("dismiss-modal-btn");
//     const printBtn = document.getElementById("print-btn");
// 
//     // Glassmorphic Premium Toast Notification System
//     function showToast(message, type = "info") {
//         let container = document.getElementById("toast-container");
//         if (!container) {
//             container = document.createElement("div");
//             container.id = "toast-container";
//             container.style.cssText = `
//                 position: fixed;
//                 bottom: 24px;
//                 right: 24px;
//                 display: flex;
//                 flex-direction: column;
//                 gap: 12px;
//                 z-index: 9999;
//                 max-width: 360px;
//                 pointer-events: none;
//             `;
//             document.body.appendChild(container);
//         }
// 
//         const toast = document.createElement("div");
//         toast.className = `toast toast-${type}`;
// 
//         let icon = "fa-info-circle";
//         let color = "var(--color-primary, #3b82f6)";
//         if (type === "success") {
//             icon = "fa-circle-check";
//             color = "#10b981";
//         } else if (type === "error") {
//             icon = "fa-triangle-exclamation";
//             color = "#ef4444";
//         } else if (type === "warning") {
//             icon = "fa-circle-exclamation";
//             color = "#f59e0b";
//         }
// 
//         toast.style.cssText = `
//             background: rgba(30, 41, 59, 0.85);
//             backdrop-filter: blur(12px);
//             -webkit-backdrop-filter: blur(12px);
//             border: 1px solid rgba(255, 255, 255, 0.08);
//             border-left: 4px solid ${color};
//             color: #f1f5f9;
//             padding: 14px 18px;
//             border-radius: 8px;
//             font-family: 'Inter', sans-serif;
//             font-size: 0.875rem;
//             box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.3);
//             display: flex;
//             align-items: center;
//             gap: 12px;
//             transform: translateY(20px);
//             opacity: 0;
//             transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
//             pointer-events: auto;
//         `;
// 
//         toast.innerHTML = `
//             <i class="fa-solid ${icon}" style="color: ${color}; font-size: 1.125rem;"></i>
//             <span style="flex-grow: 1; line-height: 1.4;">${message}</span>
//         `;
// 
//         container.appendChild(toast);
// 
//         setTimeout(() => {
//             toast.style.transform = "translateY(0)";
//             toast.style.opacity = "1";
//         }, 50);
// 
//         setTimeout(() => {
//             toast.style.transform = "translateY(-20px)";
//             toast.style.opacity = "0";
//             setTimeout(() => {
//                 toast.remove();
//             }, 300);
//         }, 4000);
//     }
// 
//     // ==========================================================================
//     // SIDEBAR TAB CONTROLLERS
//     // ==========================================================================
//     navItems.forEach(item => {
//         item.addEventListener("click", () => {
//             const target = item.getAttribute("data-tab");
//             switchTab(target);
//         });
//     });
// 
//     function switchTab(tabName) {
//         activeTab = tabName;
// 
//         // Active indicator on navigation
//         navItems.forEach(item => {
//             if (item.getAttribute("data-tab") === tabName) {
//                 item.classList.add("active");
//             } else {
//                 item.classList.remove("active");
//             }
//         });
// 
//         // Toggle viewport display
//         viewports.forEach(vp => {
//             if (vp.id === `tab-${tabName}`) {
//                 vp.classList.add("active-viewport");
//             } else {
//                 vp.classList.remove("active-viewport");
//             }
//         });
// 
//         // Update Title text
//         const titleMap = {
//             calculator: "Motor Claims Compensation Workstation",
//             library: "Centralized PDF Library & Qdrant Queue",
//             chat: "AI Precedent Assistant & Semantic Search",
//             qdrant: "Qdrant Vector Database Explorer Dashboard"
//         };
//         tabTitleText.textContent = titleMap[tabName] || "Compensation Calculator Workstation";
// 
//         // Trigger dashboard reload when viewing Qdrant DB Explorer
//         if (tabName === "qdrant") {
//             loadQdrantDashboard();
//         }
//     }
// 
//     // ==========================================================================
//     // EMBEDDED QDRANT OFFICIAL UI DASHBOARD EXPLORER
//     // ==========================================================================
//     const qdrantPointsTableBody = document.getElementById("qdrant-points-table-body");
//     const qdrantCollectionName = document.getElementById("qdrant-collection-name");
//     const qdrantPointsCount = document.getElementById("qdrant-points-count");
//     const qdrantDistance = document.getElementById("qdrant-distance");
//     const qdrantVectorSize = document.getElementById("qdrant-vector-size");
//     const refreshQdrantBtn = document.getElementById("refresh-qdrant-btn");
// 
//     const payloadModal = document.getElementById("qdrant-payload-modal");
//     const closePayloadModalBtn = document.getElementById("close-payload-modal-btn");
//     const dismissPayloadModalBtn = document.getElementById("dismiss-payload-modal-btn");
//     const payloadCodeblock = document.getElementById("qdrant-payload-codeblock");
// 
//     if (refreshQdrantBtn) {
//         refreshQdrantBtn.addEventListener("click", loadQdrantDashboard);
//     }
// 
//     async function loadQdrantDashboard() {
//         if (!qdrantPointsTableBody) return;
// 
//         qdrantPointsTableBody.innerHTML = `
//             <tr>
//                 <td colspan="5" style="padding: 24px; text-align: center; color: var(--text-secondary);">
//                     <i class="fa-solid fa-spinner fa-spin fa-2x" style="color: var(--color-primary); margin-bottom: 8px;"></i>
//                     Scrolling points and loading vectors from local Qdrant collection...
//                 </td>
//             </tr>
//         `;
// 
//         try {
//             const response = await fetch("/api/qdrant/points");
//             if (!response.ok) throw new Error("Failed to load Qdrant points");
//             const data = await response.json();
// 
//             // Populate cards
//             if (qdrantCollectionName) qdrantCollectionName.textContent = data.collection_name || "legal_documents";
//             if (qdrantPointsCount) qdrantPointsCount.textContent = data.points_count !== undefined ? data.points_count : 0;
//             if (qdrantDistance) qdrantDistance.textContent = data.distance || "Cosine";
//             if (qdrantVectorSize) qdrantVectorSize.textContent = data.vector_size ? `${data.vector_size} dims` : "384 dims";
// 
//             if (!data.points || data.points.length === 0) {
//                 qdrantPointsTableBody.innerHTML = `
//                     <tr>
//                         <td colspan="5" style="padding: 24px; text-align: center; color: var(--text-muted);">
//                             <i class="fa-solid fa-box-open" style="font-size: 1.8rem; display: block; margin-bottom: 8px;"></i>
//                             No vectors currently indexed in the Qdrant database collection.<br>
//                             <span style="font-size: 0.75rem; color: var(--text-muted); opacity: 0.7;">Drop a legal case PDF in the workstation to auto-OCR & populate vectors!</span>
//                         </td>
//                     </tr>
//                 `;
//                 return;
//             }
// 
//             qdrantPointsTableBody.innerHTML = "";
//             data.points.forEach(point => {
//                 const tr = document.createElement("tr");
//                 tr.style.cssText = "border-bottom: 1px solid var(--border-glass); transition: background 0.2s ease;";
// 
//                 // Highlight row on hover
//                 tr.addEventListener("mouseenter", () => tr.style.background = "rgba(255, 255, 255, 0.01)");
//                 tr.addEventListener("mouseleave", () => tr.style.background = "transparent");
// 
//                 const payload = point.payload || {};
//                 const filename = payload.filename || "unknown";
//                 const chunkId = payload.chunk_id !== undefined ? payload.chunk_id : 0;
//                 let text = payload.text || "";
//                 if (text.length > 75) {
//                     text = text.slice(0, 72) + "...";
//                 }
// 
//                 tr.innerHTML = `
//                     <td style="padding: 12px 16px; font-family: monospace; color: var(--color-primary); font-size: 0.8rem;">${point.id}</td>
//                     <td style="padding: 12px 16px; font-weight: 500;">${filename}</td>
//                     <td style="padding: 12px 16px; text-align: center;"><span class="badge tech-badge" style="padding: 2px 6px;"># ${chunkId}</span></td>
//                     <td style="padding: 12px 16px; color: var(--text-secondary); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">"${text}"</td>
//                     <td style="padding: 12px 16px; text-align: right;">
//                         <button type="button" class="btn btn-secondary btn-small view-payload-btn" data-point-id="${point.id}">
//                             <i class="fa-solid fa-code"></i> Payload
//                         </button>
//                     </td>
//                 `;
// 
//                 // Bind payload detail viewer
//                 tr.querySelector(".view-payload-btn").addEventListener("click", () => {
//                     if (payloadCodeblock && payloadModal) {
//                         payloadCodeblock.textContent = JSON.stringify(payload, null, 4);
//                         payloadModal.classList.add("open");
//                     }
//                 });
// 
//                 qdrantPointsTableBody.appendChild(tr);
//             });
// 
//         } catch (error) {
//             console.error("Qdrant Explorer error:", error);
//             qdrantPointsTableBody.innerHTML = `
//                 <tr>
//                     <td colspan="5" style="padding: 24px; text-align: center; color: var(--color-danger);">
//                         <i class="fa-solid fa-triangle-exclamation" style="font-size: 1.8rem; display: block; margin-bottom: 8px;"></i>
//                         Failed to read points from Qdrant: ${error.message}
//                     </td>
//                 </tr>
//             `;
//         }
//     }
// 
//     // Modal controls for payload explorer
//     if (closePayloadModalBtn) {
//         closePayloadModalBtn.addEventListener("click", () => payloadModal.classList.remove("open"));
//     }
//     if (dismissPayloadModalBtn) {
//         dismissPayloadModalBtn.addEventListener("click", () => payloadModal.classList.remove("open"));
//     }
//     window.addEventListener("click", (e) => {
//         if (e.target === payloadModal) {
//             payloadModal.classList.remove("open");
//         }
//     });
// 
//     // ==========================================================================
//     // BACKEND HEALTH & QDRANT CONNECTOR
//     // ==========================================================================
//     async function checkBackendHealth() {
//         try {
//             const response = await fetch("/api/health");
//             if (response.ok) {
//                 const data = await response.json();
//                 serverStatus.textContent = "Server Online";
//                 pulseIndicator.className = "pulse-indicator active";
// 
//                 if (data.vector_db === "online") {
//                     dbStatusText.textContent = "Qdrant Vector DB: Online";
//                     statusDot.className = "status-dot online";
//                 } else {
//                     dbStatusText.textContent = "Qdrant: Fallback Simulation";
//                     statusDot.className = "status-dot";
//                 }
//             } else {
//                 throw new Error("HTTP health check error");
//             }
//         } catch (error) {
//             console.error("Health probe failed:", error);
//             serverStatus.textContent = "Offline Sandbox Mode";
//             pulseIndicator.className = "pulse-indicator active error";
//             dbStatusText.textContent = "Qdrant: Sandbox Mode";
//             statusDot.className = "status-dot";
//         }
//     }
// 
//     checkBackendHealth();
// 
//     // ==========================================================================
//     // FORM TOGGLER & LIVE MATH ENGINE
//     // ==========================================================================
//     caseTypeSelect.addEventListener("change", (e) => {
//         const caseType = e.target.value;
// 
//         const existingBadge = document.querySelector(`.suggested-badge[data-field="case_type"]`);
//         if (existingBadge) {
//             existingBadge.remove();
//         }
// 
//         sharedFields.classList.remove("show");
//         sharedFields.classList.add("hidden-section");
// 
//         deathFields.classList.remove("show");
//         deathFields.classList.add("hidden-section");
// 
//         injuryFields.classList.remove("show");
//         injuryFields.classList.add("hidden-section");
// 
//         formActionsBar.classList.remove("show-flex");
//         formActionsBar.classList.add("hidden-section");
// 
//         if (liveMetricsCard) {
//             liveMetricsCard.classList.remove("show");
//             liveMetricsCard.classList.add("hidden-section");
//         }
//         if (evaluatorCard) {
//             evaluatorCard.classList.remove("show");
//             evaluatorCard.classList.add("hidden-section");
//         }
// 
//         singleUploadSection.classList.remove("show");
//         singleUploadSection.classList.remove("show-flex");
//         singleUploadSection.classList.add("hidden-section");
// 
//         sharedFields.classList.remove("hidden-section");
//         sharedFields.classList.add("show");
// 
//         singleUploadSection.classList.remove("hidden-section");
//         singleUploadSection.classList.add("show-flex");
// 
//         if (caseType === "injury") {
//             injuryFields.classList.remove("hidden-section");
//             injuryFields.classList.add("show");
// 
//             if (liveDeductionsItem) liveDeductionsItem.classList.add("hidden");
//             if (liveProspectsItem) liveProspectsItem.classList.add("hidden");
// 
//             const labelDeps = document.getElementById("label-dependents");
//             if (labelDeps) {
//                 labelDeps.innerHTML = "Number of Dependents";
//             }
//             if (dependentsInput) dependentsInput.removeAttribute("required");
// 
//             const futureProspectInput = document.getElementById("future-prospect");
//             if (futureProspectInput) futureProspectInput.removeAttribute("required");
//         } else if (caseType === "death") {
//             deathFields.classList.remove("hidden-section");
//             deathFields.classList.add("show");
// 
//             if (liveDeductionsItem) liveDeductionsItem.classList.remove("hidden");
//             if (liveProspectsItem) liveProspectsItem.classList.remove("hidden");
// 
//             const labelDeps = document.getElementById("label-dependents");
//             if (labelDeps) {
//                 labelDeps.innerHTML = "Number of Dependents <span class=\"req\">*</span>";
//             }
//             if (dependentsInput) dependentsInput.setAttribute("required", "required");
// 
//             const futureProspectInput = document.getElementById("future-prospect");
//             if (futureProspectInput) futureProspectInput.setAttribute("required", "required");
//         }
// 
//         formActionsBar.classList.remove("hidden-section");
//         formActionsBar.classList.add("show-flex");
// 
//         if (liveMetricsCard) {
//             liveMetricsCard.classList.remove("hidden-section");
//             liveMetricsCard.classList.add("show");
//         }
//         if (evaluatorCard) {
//             evaluatorCard.classList.remove("hidden-section");
//             evaluatorCard.classList.add("show");
//         }
//         // Populate fields from local cache if we already ran extraction!
//         populateFieldsForActiveCaseType();
// 
//         updateLiveCalculations();
// 
//         if (window.lastRawText) {
//             checkCaseType(caseType, window.lastRawText);
//         } else {
//             const container = document.getElementById("case-type-suggestion");
//             if (container) {
//                 container.innerHTML = "";
//                 container.classList.add("hidden-section");
//             }
//         }
//     });
// 
//     // Trigger change event dynamically to handle browser auto-restored values on page refresh
//     if (caseTypeSelect && caseTypeSelect.value) {
//         caseTypeSelect.dispatchEvent(new Event("change"));
//     }
// 
//     // DOB & Date of Accident -> Calculated Age
//     function calculateAge(dobStr, doaStr) {
//         if (!dobStr || !doaStr) return null;
//         const dob = new Date(dobStr);
//         const doa = new Date(doaStr);
//         if (isNaN(dob.getTime()) || isNaN(doa.getTime())) return null;
// 
//         let age = doa.getFullYear() - dob.getFullYear();
//         const monthDiff = doa.getMonth() - dob.getMonth();
//         if (monthDiff < 0 || (monthDiff === 0 && doa.getDate() < dob.getDate())) {
//             age--;
//         }
//         return age >= 0 ? age : 0;
//     }
// 
//     function getMultiplier(age) {
//         if (age === null || age === undefined || age === "") return 0;
//         const a = parseInt(age);
//         if (a <= 15) return 15;
//         if (a <= 20) return 18;
//         if (a <= 25) return 18;
//         if (a <= 30) return 17;
//         if (a <= 35) return 16;
//         if (a <= 40) return 15;
//         if (a <= 45) return 14;
//         if (a <= 50) return 13;
//         if (a <= 55) return 11;
//         if (a <= 60) return 9;
//         if (a <= 65) return 7;
//         return 5;
//     }
// 
//     function getFutureProspectPercentage(age, futureType) {
//         if (age === null || age === undefined || age === "") return 0;
//         const a = parseInt(age);
//         const fType = parseInt(futureType);
//         if (a > 60) return 0;
//         if (fType === 1) {
//             if (a < 40) return 50;
//             if (a <= 50) return 30;
//             if (a <= 60) return 15;
//             return 0;
//         } else {
//             if (a < 40) return 40;
//             if (a <= 50) return 25;
//             if (a <= 60) return 10;
//             return 0;
//         }
//     }
// 
//     function getDeductionRatio(dependents, status) {
//         if (dependents === null || dependents === undefined || dependents === "") return 0.50;
//         const deps = parseInt(dependents);
//         const stat = String(status || "married").trim().toLowerCase();
//         if (stat === "single") return 0.50;
//         if (deps <= 1) return 0.50;
//         if (deps <= 3) return 1 / 3;
//         if (deps <= 6) return 0.25;
//         return 0.20;
//     }
// 
//     function updateLiveCalculations() {
//         const age = parseInt(ageInput.value);
//         const caseType = caseTypeSelect.value;
//         
//         if (!isNaN(age) && age >= 0) {
//             if (liveAge) liveAge.textContent = `${age} years`;
//             
//             const mult = getMultiplier(age);
//             if (liveMultiplier) liveMultiplier.textContent = mult;
//             
//             if (caseType === "death") {
//                 const futureType = futureTypeSelect ? futureTypeSelect.value : 2;
//                 const futureProspectInput = document.getElementById("future-prospect");
//                 let prospects;
//                 if (futureProspectInput && futureProspectInput.value !== "" && !isNaN(parseFloat(futureProspectInput.value))) {
//                     prospects = parseFloat(futureProspectInput.value);
//                 } else {
//                     prospects = getFutureProspectPercentage(age, futureType);
//                     if (futureProspectInput) futureProspectInput.value = prospects;
//                 }
//                 if (liveProspects) liveProspects.textContent = `${prospects}%`;
//                 if (liveProspectsBar) liveProspectsBar.style.width = `${prospects}%`;
//                 
//                 // Populate only helper parameters
//                 const deathMultInput = document.getElementById("death-multiplier");
//                 if (deathMultInput) deathMultInput.value = mult;
//                 
//                 const deps = parseInt(dependentsInput.value) || 0;
//                 const status = maritalStatusSelect.value || "married";
//                 const deductionRatio = getDeductionRatio(deps, status);
//                 const deductionsPercent = Math.round(deductionRatio * 100);
//                 if (liveDeductions) liveDeductions.textContent = `${deductionsPercent}%`;
//                 if (liveDeductionsBar) liveDeductionsBar.style.width = `${deductionsPercent}%`;
//                 
//                 const deathDeductInput = document.getElementById("death-deduction");
//                 if (deathDeductInput) deathDeductInput.value = deductionsPercent;
// 
//                 // Populate dynamic dashboard helper elements only (no monetary figures)
//                 if (document.getElementById("live-calc-multiplier")) {
//                     document.getElementById("live-calc-multiplier").textContent = mult;
//                 }
//                 if (document.getElementById("live-calc-deduct-pct")) {
//                     document.getElementById("live-calc-deduct-pct").textContent = `${deductionsPercent}%`;
//                 }
// 
//             } else {
//                 if (liveProspects) liveProspects.textContent = "—%";
//                 if (liveProspectsBar) liveProspectsBar.style.width = "0%";
//                 if (liveDeductions) liveDeductions.textContent = "—%";
//                 if (liveDeductionsBar) liveDeductionsBar.style.width = "0%";
//             }
//         } else {
//             // Truly nothing — blank everything
//             if (liveAge) liveAge.textContent = "—";
//             if (liveMultiplier) liveMultiplier.textContent = "—";
//             if (liveProspects) liveProspects.textContent = "—%";
//             if (liveProspectsBar) liveProspectsBar.style.width = "0%";
//             if (liveDeductions) liveDeductions.textContent = "—%";
//             if (liveDeductionsBar) liveDeductionsBar.style.width = "0%";
//             if (caseType === "death") {
//                 if (document.getElementById("live-calc-multiplier")) document.getElementById("live-calc-multiplier").textContent = "—";
//                 if (document.getElementById("live-calc-deduct-pct")) document.getElementById("live-calc-deduct-pct").textContent = "—";
//             }
//         }
//     }
// 
//     const handleRecalculateDefaultProspects = () => {
//         const age = parseInt(ageInput.value);
//         if (!isNaN(age) && age >= 0) {
//             const futureType = futureTypeSelect ? futureTypeSelect.value : 2;
//             const prospects = getFutureProspectPercentage(age, futureType);
//             const futureProspectInput = document.getElementById("future-prospect");
//             if (futureProspectInput) futureProspectInput.value = prospects;
//         }
//         updateLiveCalculations();
//     };
// 
//     if (futureTypeSelect) {
//         futureTypeSelect.addEventListener("change", handleRecalculateDefaultProspects);
//     }
// 
//     dobInput.addEventListener("change", updateLiveCalculations);
//     doaInput.addEventListener("change", updateLiveCalculations);
//     maritalStatusSelect.addEventListener("change", updateLiveCalculations);
//     dependentsInput.addEventListener("input", updateLiveCalculations);
//     monthlyIncomeInput.addEventListener("input", updateLiveCalculations);
//     ageInput.addEventListener("input", handleRecalculateDefaultProspects);
// 
//     // Set dynamic update bindings for new Death Claim inputs and prospects field manual override
//     setTimeout(() => {
//         const consInput = document.getElementById("consortium");
//         const funInput = document.getElementById("funeral-expenses");
//         const estInput = document.getElementById("loss-estate");
//         const futureProspectInput = document.getElementById("future-prospect");
// 
//         if (consInput) consInput.addEventListener("input", updateLiveCalculations);
//         if (funInput) funInput.addEventListener("input", updateLiveCalculations);
//         if (estInput) estInput.addEventListener("input", updateLiveCalculations);
//         if (futureProspectInput) futureProspectInput.addEventListener("input", updateLiveCalculations);
//     }, 50);
// 
//     // ==========================================================================
//     // SINGLE PDF WORKSPACE DRAG & DROP + UPLOAD
//     // ==========================================================================
//     ["dragenter", "dragover"].forEach(eventName => {
//         singleDropZone.addEventListener(eventName, (e) => {
//             e.preventDefault();
//             e.stopPropagation();
//             singleDropZone.classList.add("dragover");
//         }, false);
//     });
// 
//     singleDropZone.addEventListener("dragleave", (e) => {
//         e.preventDefault();
//         e.stopPropagation();
//         singleDropZone.classList.remove("dragover");
//     }, false);
// 
//     singleDropZone.addEventListener("drop", (e) => {
//         e.preventDefault();
//         e.stopPropagation();
//         singleDropZone.classList.remove("dragover");
// 
//         const dt = e.dataTransfer;
//         const files = dt.files;
//         if (files.length > 0) {
//             handleSinglePdfUpload(files[0]);
//         }
//     });
// 
//     singleDropZone.addEventListener("click", (e) => {
//         if (e.target === singleFileInput) return;
//         singleFileInput.click();
//     });
// 
//     singleFileInput.addEventListener("click", (e) => {
//         e.stopPropagation();
//     });
// 
//     singleFileInput.addEventListener("change", (e) => {
//         if (e.target.files.length > 0) {
//             handleSinglePdfUpload(e.target.files[0]);
//         }
//     });
// 
//     async function handleSinglePdfUpload(file) {
//         const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
//         if (!isPdf) {
//             alert("Please upload a valid legal PDF case document.");
//             return;
//         }
// 
//         // Start the Live OCR timer
//         startOcrTimer();
// 
//         // Show a premium glassmorphic loading spinner inside the form panel
//         const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
//         const loader = document.createElement("div");
//         loader.className = "form-ocr-loader";
//         loader.innerHTML = `
//             <div class="spinner-glow"></div>
//             <p>Analyzing document with legal OCR...</p>
//             <span style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Extracting Judgment, Petition, &amp; Prayer sections</span>
//             <div style="margin-top: 12px; font-family: monospace; font-size: 1.15rem; font-weight: 700; color: var(--color-primary); display: flex; align-items: center; gap: 8px; justify-content: center;">
//                 <span>⏱</span>
//                 <span id="ocr-loader-timer">00:00</span>
//             </div>
//         `;
//         formPanel.style.position = "relative";
//         formPanel.appendChild(loader);
// 
//         const formData = new FormData();
//         formData.append("file", file);
// 
//         try {
//             const response = await fetch("/api/ocr/process-ocr", {
//                 method: "POST",
//                 body: formData
//             });
// 
//             if (!response.ok) {
//                 throw new Error("OCR Processing failed");
//             }
// 
//             const reader = response.body.getReader();
//             const decoder = new TextDecoder();
//             let partialBuffer = "";
// 
//             while (true) {
//                 const { done, value } = await reader.read();
//                 if (done) break;
// 
//                 partialBuffer += decoder.decode(value, { stream: true });
//                 const lines = partialBuffer.split("\n");
// 
//                 // Keep the last item in the buffer as it might be incomplete
//                 partialBuffer = lines.pop();
// 
//                 for (const line of lines) {
//                     const cleanLine = line.trim();
//                     if (!cleanLine.startsWith("data: ")) continue;
// 
//                     const payload = cleanLine.slice(6);
//                     const data = JSON.parse(payload);
// 
//                     // Update loader visual progress message and submessage
//                     if (loader) {
//                         const messageEl = loader.querySelector("p");
//                         const submessageEl = loader.querySelector("span");
// 
//                         if (messageEl && data.message) {
//                             messageEl.textContent = data.message;
//                         }
//                         if (submessageEl && data.status) {
//                             submessageEl.textContent = `Phase: ${data.status} (${data.progress}%)`;
//                         }
//                     }
// 
//                     // Update local form panel timer status text
//                     const statusText = document.getElementById("ocr-timer-status-text");
//                     if (statusText && data.message) {
//                         statusText.textContent = data.message;
//                     }
// 
//                     if (data.status === "done") {
//                         // Remove spinner after processing is fully complete
//                         loader.remove();
// 
//                         if (data.success) {
//                             // Stop timer on success
//                             stopOcrTimerSuccess();
// 
//                             // TEMPORARY: Log OCR suggestions structure
//                             console.log("OCR suggestions structure:", JSON.stringify(data.suggestions, null, 2));
// 
//                             // Apply OCR suggestions automatically
//                             applyAllOcrSuggestions(data.suggestions);
// 
//                             // Update OCR Inspector with authentic telemetry data
//                             updateOcrInspector(data);
// 
//                             // Store raw text for AI data recovery
//                             currentOcrRawText = data.raw_text || [];
//                             window.lastRawText = currentOcrRawText.join("\n");
//                             checkCaseType(caseTypeSelect.value, window.lastRawText);
//                             if (aiExtractBtn) {
//                                 if (currentOcrRawText.length > 0) {
//                                     aiExtractBtn.style.display = "inline-flex";
//                                 } else {
//                                     aiExtractBtn.style.display = "none";
//                                 }
//                             }
// 
//                             // Load high-fidelity PDF preview in the right pane!
//                             const blobUrl = URL.createObjectURL(file);
//                             singlePreviewFilename.innerHTML = `${file.name} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: ${data.fallback_source}</span>`;
//                             singlePreviewContainer.innerHTML = `
//                                 <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
//                             `;
//                             singlePreviewCard.classList.remove("hidden-section");
//                             singlePreviewCard.classList.add("show");
// 
//                             // Programmatically switch active right pane tab to PDF Preview upon successful upload
//                             const pdfTabBtn = document.querySelector('.pane-tab-btn[data-pane-tab="pdf"]');
//                             if (pdfTabBtn) {
//                                 pdfTabBtn.click();
//                             }
// 
//                             // Programmatically open the AI Assistant slide-over chatbot drawer upon successful upload
//                             if (aiAssistantTrigger && slideover && !slideover.classList.contains("open")) {
//                                 aiAssistantTrigger.click();
//                             }
// 
//                             // Highlight and show the live metrics and precedents cards
//                             if (liveMetricsCard) liveMetricsCard.classList.add("show");
//                             if (evaluatorCard) evaluatorCard.classList.add("show");
// 
//                             if (typeof triggerTabNotification === "function") {
//                                 triggerTabNotification("analysis");
//                                 triggerTabNotification("ocr-quality");
//                             }
// 
//                             showToast("Case PDF analyzed! Form auto-filled focusing on Previous Judgment, Petition, and Prayer details. Please manually review fields.", "success");
//                         } else {
//                             stopOcrTimerFailure();
//                             showToast("Failed to extract data from the PDF: " + (data.message || "Unknown OCR error."), "error");
//                         }
//                     } else if (data.status === "failed") {
//                         loader.remove();
//                         stopOcrTimerFailure();
//                         showToast("Failed to extract data from the PDF: " + (data.message || "Unknown OCR error."), "error");
//                     }
//                 }
//             }
//         } catch (error) {
//             loader.remove();
//             stopOcrTimerFailure();
//             console.error("Single PDF OCR error:", error);
//             showToast(`OCR processing failed: ${error.message}. Please verify the central FastAPI server is fully initialized.`, "error");
//         }
//     }
// 
//     // ==========================================================================
//     // BATCH PDF MANAGER (DRAG & DROP + POLLING QUEUE)
//     // ==========================================================================
// 
//     // Drag events
//     ["dragenter", "dragover"].forEach(eventName => {
//         dropZone.addEventListener(eventName, (e) => {
//             e.preventDefault();
//             e.stopPropagation();
//             dropZone.classList.add("dragover");
//         }, false);
//     });
// 
//     dropZone.addEventListener("dragleave", (e) => {
//         e.preventDefault();
//         e.stopPropagation();
//         dropZone.classList.remove("dragover");
//     }, false);
// 
//     dropZone.addEventListener("drop", (e) => {
//         e.preventDefault();
//         e.stopPropagation();
//         dropZone.classList.remove("dragover");
// 
//         const dt = e.dataTransfer;
//         const files = dt.files;
//         if (files.length > 0) {
//             handleBatchUpload(files);
//         }
//     });
// 
//     dropZone.addEventListener("click", (e) => {
//         if (e.target === fileInput) return;
//         fileInput.click();
//     });
// 
//     fileInput.addEventListener("click", (e) => {
//         e.stopPropagation();
//     });
// 
//     fileInput.addEventListener("change", (e) => {
//         if (e.target.files.length > 0) {
//             handleBatchUpload(e.target.files);
//         }
//     });
// 
//     // Upload batch files
//     async function handleBatchUpload(files) {
//         // Start the Live OCR timer for batch processing
//         startOcrTimer();
//         const formData = new FormData();
//         let validPdfCount = 0;
// 
//         for (let i = 0; i < files.length; i++) {
//             const file = files[i];
//             const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
//             if (isPdf) {
//                 formData.append("files", file);
//                 validPdfCount++;
// 
//                 // Map local filename to the file object to facilitate local iframe previewing!
//                 uploadedFileObjects[file.name] = file;
//             }
//         }
// 
//         if (validPdfCount === 0) {
//             alert("No valid PDF files selected. Please upload legal document PDFs.");
//             return;
//         }
// 
//         try {
//             const response = await fetch("/api/ocr/upload-batch", {
//                 method: "POST",
//                 body: formData
//             });
// 
//             if (!response.ok) {
//                 throw new Error("Batch upload failed");
//             }
// 
//             const data = await response.json();
// 
//             // Append files to our local tracker
//             data.queue.forEach(item => {
//                 fileQueue.push({
//                     file_id: item.file_id,
//                     filename: item.filename,
//                     status: "queued",
//                     progress: 0,
//                     suggestions: null,
//                     raw_text: []
//                 });
//             });
// 
//             renderQueueList();
//             startQueuePolling();
// 
//         } catch (error) {
//             console.error("Error uploading batch PDFs:", error);
//             alert("Failed to upload batch files to the server.");
//         }
//     }
// 
//     // Render queue card lists
//     function renderQueueList() {
//         if (fileQueue.length === 0) {
//             batchFileList.innerHTML = `
//                 <div class="empty-state">
//                     <i class="fa-solid fa-box-open"></i>
//                     <p>No legal PDFs uploaded yet. Drag and drop PDF claim judgments above to begin centralized vector storage.</p>
//                 </div>
//             `;
//             if (queueBadge) queueBadge.classList.add("hidden");
//             queueCountLabel.textContent = "0 Files";
//             return;
//         }
// 
//         batchFileList.innerHTML = "";
//         if (queueBadge) {
//             queueBadge.classList.remove("hidden");
//             queueBadge.textContent = fileQueue.length;
//         }
//         queueCountLabel.textContent = `${fileQueue.length} Files`;
// 
//         fileQueue.forEach(file => {
//             const item = document.createElement("div");
//             item.className = "batch-file-item";
//             item.setAttribute("data-id", file.file_id);
//             item.setAttribute("data-filename", file.filename);
// 
//             const displayTag = {
//                 queued: `<span class="bf-tag queued">Queued</span>`,
//                 scanning: `<span class="bf-tag scanning">Scanning</span>`,
//                 indexing: `<span class="bf-tag indexing">Indexing</span>`,
//                 indexed: `<span class="bf-tag indexed"><i class="fa-solid fa-circle-check"></i> Indexed</span>`,
//                 failed: `<span class="bf-tag failed">Failed</span>`
//             }[file.status] || `<span class="bf-tag queued">${file.status}</span>`;
// 
//             item.innerHTML = `
//                 <div class="bf-meta">
//                     <span class="bf-name" title="${file.filename}">${file.filename}</span>
//                     ${displayTag}
//                 </div>
//                 <div class="bf-progress-row">
//                     <div class="bf-bar-wrapper">
//                         <div class="bf-bar-fill" style="width: ${file.progress}%"></div>
//                     </div>
//                     <span class="bf-pct">${file.progress}%</span>
//                 </div>
//                 ${file.status === "indexed" ? `
//                     <div class="bf-actions">
//                         <button type="button" class="btn btn-small btn-success autofill-queue-btn" data-id="${file.file_id}">
//                             <i class="fa-solid fa-arrow-left"></i> Auto-fill form
//                         </button>
//                     </div>
//                 ` : ""}
//             `;
// 
//             // Bind click to previews
//             item.addEventListener("click", (e) => {
//                 // Prevent trigger if they click the autofill button specifically
//                 if (e.target.closest(".autofill-queue-btn")) return;
// 
//                 document.querySelectorAll(".batch-file-item").forEach(c => c.classList.remove("active-preview"));
//                 item.classList.add("active-preview");
//                 loadPdfPreview(file.filename);
//             });
// 
//             batchFileList.appendChild(item);
//         });
// 
//         // Bind clicks on autofill buttons
//         document.querySelectorAll(".autofill-queue-btn").forEach(btn => {
//             btn.addEventListener("click", (e) => {
//                 e.preventDefault();
//                 e.stopPropagation();
//                 const id = btn.getAttribute("data-id");
//                 const matchedFile = fileQueue.find(f => f.file_id === id);
//                 if (matchedFile) {
//                     showAutofillChoiceModal(matchedFile);
//                 }
//             });
//         });
// 
//         // Sync chatbot document filter select options
//         syncChatDocumentFilter();
//     }
// 
//     // Open Autofill Selection Modal to choose between OCR and AI Deep Extraction
//     function showAutofillChoiceModal(matchedFile) {
//         const choiceModal = document.getElementById("autofill-choice-modal");
//         if (!choiceModal) return;
// 
//         const quickBtn = document.getElementById("btn-quick-autofill");
//         const aiBtn = document.getElementById("btn-ai-autofill");
//         const cancelBtn = document.getElementById("dismiss-autofill-choice-btn");
//         const closeBtn = document.getElementById("close-autofill-choice-btn");
// 
//         // Clone buttons to clear previous event listeners cleanly
//         const newQuickBtn = quickBtn.cloneNode(true);
//         const newAiBtn = aiBtn.cloneNode(true);
//         quickBtn.parentNode.replaceChild(newQuickBtn, quickBtn);
//         aiBtn.parentNode.replaceChild(newAiBtn, aiBtn);
// 
//         // Bind quick OCR path
//         newQuickBtn.addEventListener("click", (e) => {
//             e.stopPropagation();
//             choiceModal.classList.remove("open");
//             if (matchedFile.suggestions) {
//                 stopOcrTimerSuccess();
// 
//                 // Store raw text for AI data recovery if they want to click it manually later
//                 currentOcrRawText = matchedFile.raw_text || [];
//                 if (aiExtractBtn) {
//                     if (currentOcrRawText.length > 0) {
//                         aiExtractBtn.style.display = "inline-flex";
//                     } else {
//                         aiExtractBtn.style.display = "none";
//                     }
//                 }
// 
//                 // Update workstation preview card with the batch-loaded PDF if possible
//                 const fileObj = uploadedFileObjects[matchedFile.filename];
//                 if (fileObj && singlePreviewContainer && singlePreviewFilename) {
//                     const blobUrl = URL.createObjectURL(fileObj);
//                     singlePreviewFilename.innerHTML = `${matchedFile.filename} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: Batch Library</span>`;
//                     singlePreviewContainer.innerHTML = `
//                         <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
//                     `;
//                     if (singlePreviewCard) {
//                         singlePreviewCard.classList.remove("hidden-section");
//                         singlePreviewCard.classList.add("show");
//                     }
//                 }
// 
//                 applyAllOcrSuggestions(matchedFile.suggestions);
// 
//                 if (matchedFile.ocr_debug) {
//                     updateOcrInspector(matchedFile);
//                     triggerTabNotification("ocr-quality");
//                 }
// 
//                 window.lastRawText = (matchedFile.raw_text || []).join("\n");
//                 checkCaseType(caseTypeSelect.value, window.lastRawText);
// 
//                 switchTab("calculator");
//             } else {
//                 showToast("No pre-parsed heuristic data available for this file.", "warning");
//             }
//         });
// 
//         // Bind AI LLM Deep Extraction path
//         newAiBtn.addEventListener("click", async (e) => {
//             e.stopPropagation();
// 
//             // Validate that we have raw text before attempting LLM recovery
//             const rawTextLines = matchedFile.raw_text || [];
//             if (rawTextLines.length === 0) {
//                 showToast("No raw OCR text is available for this file to perform AI recovery.", "warning");
//                 choiceModal.classList.remove("open");
//                 return;
//             }
// 
//             choiceModal.classList.remove("open");
// 
//             // Set currentOcrRawText from batch file
//             currentOcrRawText = rawTextLines;
//             window.lastRawText = currentOcrRawText.join("\n");
//             checkCaseType(caseTypeSelect.value, window.lastRawText);
// 
//             if (aiExtractBtn) {
//                 aiExtractBtn.style.display = "inline-flex";
//             }
// 
//             // Update workstation preview card with the batch-loaded PDF if possible
//             const fileObj = uploadedFileObjects[matchedFile.filename];
//             if (fileObj && singlePreviewContainer && singlePreviewFilename) {
//                 const blobUrl = URL.createObjectURL(fileObj);
//                 singlePreviewFilename.innerHTML = `${matchedFile.filename} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: Batch Library</span>`;
//                 singlePreviewContainer.innerHTML = `
//                     <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
//                 `;
//                 if (singlePreviewCard) {
//                     singlePreviewCard.classList.remove("hidden-section");
//                     singlePreviewCard.classList.add("show");
//                 }
//             }
// 
//             // Switch to workstation tab
//             switchTab("calculator");
// 
//             // Show spinning loader overlay in workstation panel
//             const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
//             if (!formPanel) return;
// 
//             const loader = document.createElement("div");
//             loader.className = "form-ocr-loader";
//             loader.innerHTML = `
//                 <div class="spinner-glow"></div>
//                 <p>AI Legal LLM is parsing text...</p>
//                 <span style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Recovering missing legal compensation entities</span>
//             `;
//             formPanel.style.position = "relative";
//             formPanel.appendChild(loader);
// 
//             try {
//                 // Call backend
//                 const response = await fetch("/api/ocr/ai-recover", {
//                     method: "POST",
//                     headers: { "Content-Type": "application/json" },
//                     body: JSON.stringify({ raw_text: currentOcrRawText })
//                 });
// 
//                 loader.remove();
// 
//                 if (!response.ok) {
//                     const errData = await response.json().catch(() => ({}));
//                     throw new Error(errData.detail || "AI recovery API returned error status");
//                 }
//                 const data = await response.json();
// 
//                 if (data.success) {
//                     const confidenceScores = data.raw_recovered ? data.raw_recovered.confidence_scores : null;
//                     const ocrEvidence = data.raw_recovered ? data.raw_recovered.ocr_evidence_case : null;
// 
//                     // Apply suggestions exactly the same way as clicking "Ask LLM to Extract" manually
//                     applyAllOcrSuggestions(data.suggestions, confidenceScores, ocrEvidence, data.raw_recovered);
//                     showToast("AI data extraction complete! All recovered parameters cached internally.", "success");
//                 } else {
//                     showToast("AI extraction failed to extract fields.", "error");
//                 }
//             } catch (error) {
//                 if (loader) loader.remove();
//                 console.error("AI recovery failed:", error);
//                 showToast(`AI extraction failed: ${error.message}`, "error");
//             }
//         });
// 
//         // Close on cancel/close
//         const closeHandler = (e) => {
//             if (e) e.stopPropagation();
//             choiceModal.classList.remove("open");
//         };
//         cancelBtn.onclick = closeHandler;
//         closeBtn.onclick = closeHandler;
// 
//         // Open modal
//         choiceModal.classList.add("open");
//     }
// 
//     // Close choice modal when clicking outside content area
//     window.addEventListener("click", (e) => {
//         const choiceModal = document.getElementById("autofill-choice-modal");
//         if (e.target === choiceModal) {
//             choiceModal.classList.remove("open");
//         }
//     });
// 
//     // High-Fidelity local Blob URL previewing
//     function loadPdfPreview(filename) {
//         const fileObj = uploadedFileObjects[filename];
//         if (!fileObj) {
//             previewContainer.innerHTML = `
//                 <div class="preview-empty-state">
//                     <i class="fa-solid fa-triangle-exclamation" style="font-size: 3rem; color: var(--color-warning);"></i>
//                     <p>PDF file context lost. Please select a freshly uploaded PDF or re-upload to preview.</p>
//                 </div>
//             `;
//             previewFilenameBadge.classList.add("hidden");
//             return;
//         }
// 
//         // Generate instant in-memory Blob URL for local PDF rendering
//         const blobUrl = URL.createObjectURL(fileObj);
// 
//         previewFilenameBadge.classList.remove("hidden");
//         previewFilenameBadge.textContent = filename;
// 
//         previewContainer.innerHTML = `
//             <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
//         `;
//     }
// 
//     // Batch Status Polling Loop
//     function startQueuePolling() {
//         if (isPolling) return;
//         isPolling = true;
// 
//         const pollInterval = setInterval(async () => {
//             // Only poll if we have queued/active files
//             const activeFiles = fileQueue.filter(f => f.status === "queued" || f.status === "scanning" || f.status === "indexing");
//             if (activeFiles.length === 0) {
//                 stopOcrTimerSuccess();
//                 clearInterval(pollInterval);
//                 isPolling = false;
//                 return;
//             }
// 
//             try {
//                 const response = await fetch("/api/ocr/batch-status");
//                 if (response.ok) {
//                     const data = await response.json();
// 
//                     // Sync backend statuses with local queue
//                     data.queue.forEach(srvItem => {
//                         const localIndex = fileQueue.findIndex(f => f.file_id === srvItem.file_id);
//                         if (localIndex !== -1) {
//                             fileQueue[localIndex].status = srvItem.status;
//                             fileQueue[localIndex].progress = srvItem.progress;
//                             fileQueue[localIndex].suggestions = srvItem.suggestions;
//                             fileQueue[localIndex].raw_text = srvItem.raw_text;
//                             fileQueue[localIndex].ocr_debug = srvItem.ocr_debug;
//                         }
//                     });
// 
//                     renderQueueList();
//                 }
//             } catch (error) {
//                 console.error("Queue status polling failed:", error);
//             }
//         }, 1500);
//     }
// 
//     // Helper to populate fields based on active case type (Part 5 & Part 6)
//     function populateFieldsForActiveCaseType() {
//         const activeCaseType = caseTypeSelect.value;
//         if (!activeCaseType) return;
// 
//         // Clear all previous low-confidence warning labels, styles, and AI metadata badges again to refresh
//         document.querySelectorAll(".verification-warning").forEach(el => el.remove());
//         document.querySelectorAll(".low-confidence-input").forEach(el => el.classList.remove("low-confidence-input"));
//         document.querySelectorAll(".ai-metadata-badge:not([data-field='case_type'])").forEach(el => el.remove());
// 
//         // Field definitions and mapping to DOM input IDs
//         // Always Populate (Part 6)
//         const commonMapping = {
//             "name": "name",
//             "father_name": "father-name",
//             "date_of_birth": "date-of-birth",
//             "age": "age",
//             "monthly_income": "monthly-income",
//             "date_of_accident": "date-of-accident",
//             "place_of_accident": "place-of-accident"
//         };
// 
//         // Injury Specific (Part 6)
//         const injuryMapping = {
//             "medical_expenses": "medical-expenses",
//             "future_medical_expenses": "future-medical-expenses",
//             "pain_and_suffering": "pain-and-suffering",
//             "transportation": "transportation",
//             "special_diet": "special-diet",
//             "attender_charges": "attender-charges",
//             "loss_of_income": "loss-of-income",
//             "disability": "disability"
//         };
// 
//         // Death Specific (Part 6)
//         const deathMapping = {
//             "consortium": "consortium",
//             "funeral_expenses": "funeral-expenses",
//             "loss_estate": "loss-estate",
//             "dependents": "dependents",
//             "marital_status": "marital-status"
//         };        // Helper to populate a single DOM element based on key, inputId, and active status
//         function populateField(cacheKey, inputId, isAllowed) {
//             const el = document.getElementById(inputId);
//             if (!el) return;
// 
//             if (!isAllowed) {
//                 // If not allowed for this mode, do NOT populate.
//                 return;
//             }
// 
//             const val = lastExtractedFields[cacheKey];
// 
//             if (val === undefined || val === null || val === "") {
//                 return;
//             }
// 
//             // Direct Auto-fill (no confidence gate / suggestion badge for other fields)
//             if (inputId === "date-of-birth" || inputId === "date-of-accident") {
//                 let htmlDate = val;
//                 if (val.includes("-")) {
//                     const parts = val.split("-");
//                     if (parts.length === 3 && parts[2].length === 4) {
//                         htmlDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
//                     }
//                 }
//                 el.value = htmlDate;
//             } else {
//                 el.value = val;
//             }
//             el.dispatchEvent(new Event("input"));
//             el.dispatchEvent(new Event("change"));
//         }
//         // Run population for all common fields
//         Object.keys(commonMapping).forEach(cacheKey => {
//             populateField(cacheKey, commonMapping[cacheKey], true);
//         });
// 
//         // Run population for Injury specific fields
//         const isInjury = (activeCaseType === "injury");
//         Object.keys(injuryMapping).forEach(cacheKey => {
//             populateField(cacheKey, injuryMapping[cacheKey], isInjury);
//         });
// 
//         // Run population for Death specific fields
//         const isDeath = (activeCaseType === "death");
//         Object.keys(deathMapping).forEach(cacheKey => {
//             populateField(cacheKey, deathMapping[cacheKey], isDeath);
//         });
// 
//         updateLiveCalculations();
//     }
// 
//     // Helper to update the visual Audit Log (Part 7)
//     function updateAuditLog(userCase, llmCase, ocrEvidence, avgConfidence, overwriteBlocked) {
//         const userCaseVal = document.getElementById("audit-val-user-case");
//         const llmCaseVal = document.getElementById("audit-val-llm-case");
//         const ocrEvidenceVal = document.getElementById("audit-val-ocr-evidence");
//         const confidenceVal = document.getElementById("audit-val-confidence");
//         const overwriteBlockedVal = document.getElementById("audit-val-overwrite-blocked");
//         const terminal = document.getElementById("audit-log-terminal");
// 
//         const displayMap = {
//             "injury": "Injury Case",
//             "death": "Death Case",
//             "None Selected": "None Selected",
//             "Unspecified": "Unspecified"
//         };
// 
//         if (userCaseVal) userCaseVal.textContent = displayMap[userCase] || userCase;
//         if (llmCaseVal) llmCaseVal.textContent = displayMap[llmCase] || llmCase;
//         if (ocrEvidenceVal) {
//             ocrEvidenceVal.textContent = ocrEvidence;
//             if (ocrEvidence === "INJURY") {
//                 ocrEvidenceVal.style.color = "#34d399";
//             } else if (ocrEvidence === "DEATH") {
//                 ocrEvidenceVal.style.color = "#f43f5e";
//             } else {
//                 ocrEvidenceVal.style.color = "#f59e0b";
//             }
//         }
//         if (confidenceVal) confidenceVal.textContent = (avgConfidence * 100).toFixed(1) + "%";
// 
//         if (overwriteBlockedVal) {
//             overwriteBlockedVal.textContent = overwriteBlocked ? "TRUE" : "FALSE";
//             if (overwriteBlocked) {
//                 overwriteBlockedVal.style.color = "#ef4444";
//                 overwriteBlockedVal.className = "value text-glow";
//             } else {
//                 overwriteBlockedVal.style.color = "#10b981";
//                 overwriteBlockedVal.className = "value";
//             }
//         }
// 
//         if (terminal) {
//             const timestamp = new Date().toLocaleTimeString();
//             const logMsg = document.createElement("div");
//             logMsg.style.marginBottom = "4px";
// 
//             if (overwriteBlocked) {
//                 logMsg.innerHTML = `<span style="color: #ef4444;">[${timestamp}] [WARN] Overwrite Blocked!</span> Manual Case Type '${displayMap[userCase]}' preserved over predicted '${displayMap[llmCase]}'.`;
//             } else {
//                 logMsg.innerHTML = `<span style="color: #34d399;">[${timestamp}] [AUDIT]</span> Applied suggestions. User: ${displayMap[userCase]} | LLM: ${displayMap[llmCase]} | OCR: ${ocrEvidence}.`;
//             }
// 
//             if (terminal.children.length > 20) {
//                 terminal.removeChild(terminal.children[0]);
//             }
// 
//             terminal.appendChild(logMsg);
//             terminal.scrollTop = terminal.scrollHeight;
//         }
//     }
// 
//     // Apply parsed suggestions
//     function applyAllOcrSuggestions(suggestions, confidenceScores = null, ocrEvidence = null, rawRecovered = null) {
//         if (!suggestions) return;
// 
//         // Normalize flat suggestions into expected nested structure
//         if (suggestions && !suggestions.fields) {
//             const { case_type, low_confidence_fields, ocr_quality_insufficient, 
//                     ocr_warning, partial_extraction_recovery_mode, 
//                     fallback_source_used, award_amount, total_compensation,
//                     ai_recovery_triggered, ...fieldValues } = suggestions;
//             suggestions = {
//                 case_type: case_type,
//                 fields: fieldValues,
//                 low_confidence_fields: low_confidence_fields || [],
//                 ocr_quality_insufficient: ocr_quality_insufficient,
//                 ocr_warning: ocr_warning,
//                 fallback_source_used: fallback_source_used
//             };
//         }
// 
//         // Clear all previous low-confidence warning labels, styles, and AI metadata badges
//         document.querySelectorAll(".verification-warning").forEach(el => el.remove());
//         document.querySelectorAll(".low-confidence-input").forEach(el => el.classList.remove("low-confidence-input"));
//         document.querySelectorAll(".ai-metadata-badge").forEach(el => el.remove());
// 
//         // Extract case type (Part 1 Manual case lock)
//         let suggestionsCaseType = suggestions.case_type;
//         const currentCaseType = caseTypeSelect.value;
//         let overwriteBlocked = false;
//         let loggedUserCaseType = currentCaseType || "None Selected";
//         let loggedLlmCaseType = suggestionsCaseType || "Unspecified";
// 
//         if (currentCaseType && currentCaseType !== "") {
//             if (suggestionsCaseType && suggestionsCaseType !== currentCaseType) {
//                 overwriteBlocked = true;
// 
//                 // Show interactive suggestion badge under case type dropdown
//                 const parent = caseTypeSelect.closest(".form-group");
//                 if (parent) {
//                     const badge = document.createElement("div");
//                     badge.className = "suggested-badge ai-metadata-badge";
//                     badge.setAttribute("data-field", "case_type");
// 
//                     const displayVal = suggestionsCaseType === "injury" ? "Injury Case" : "Death Case";
//                     // Find confidence score for case_type if available, default to 95%
//                     let conf = 0.95;
//                     if (confidenceScores && confidenceScores.case_type) {
//                         conf = confidenceScores.case_type.confidence !== undefined 
//                             ? confidenceScores.case_type.confidence 
//                             : confidenceScores.case_type;
//                     } else if (suggestions.confidence_scores && suggestions.confidence_scores.case_type) {
//                         conf = suggestions.confidence_scores.case_type.confidence !== undefined 
//                             ? suggestions.confidence_scores.case_type.confidence 
//                             : suggestions.confidence_scores.case_type;
//                     }
//                     conf = typeof conf === "number" ? conf : parseFloat(conf) || 0.95;
//                     if (conf > 1.0) conf = conf / 100.0;
// 
//                     badge.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Suggest: ${displayVal} (${Math.round(conf * 100)}%)`;
// 
//                     badge.addEventListener("click", () => {
//                         caseTypeSelect.value = suggestionsCaseType;
//                         caseTypeSelect.dispatchEvent(new Event("change"));
//                         badge.remove();
//                         showToast(`Switched to suggested Case Type: ${displayVal}!`, "success");
//                     });
// 
//                     parent.appendChild(badge);
//                 }
//             }
//             suggestionsCaseType = currentCaseType;
//         } else {
//             if (suggestionsCaseType) {
//                 caseTypeSelect.value = suggestionsCaseType;
//                 caseTypeSelect.dispatchEvent(new Event("change"));
//             }
//         }
// 
//         // Cache all fields (Part 5 & Part 6)
//         const fields = suggestions.fields || {};
// 
//         Object.keys(fields).forEach(key => {
//             lastExtractedFields[key] = fields[key];
//         });
// 
//         ["date_of_birth", "date_of_accident"].forEach(key => {
//             if (fields[key]) {
//                 lastExtractedFields[key] = fields[key];
//             }
//         });
// 
//         // Ensure canonical "name" key is populated from specific name keys
//         if (fields.injured_name) lastExtractedFields["name"] = fields.injured_name;
//         if (fields.deceased_name) lastExtractedFields["name"] = fields.deceased_name;
//         if (fields.claimant_name) lastExtractedFields["name"] = fields.claimant_name;
// 
//         // Merge raw recovered details if LLM is executed (Part 5 offline store)
//         if (rawRecovered) {
//             const keyMappings = {
//                 "claimant_name": "name",
//                 "deceased_name": "name",
//                 "injured_name": "name",
//                 "father_name": "father_name",
//                 "place_of_accident": "place_of_accident",
//                 "accident_place": "place_of_accident",
//                 "age": "age",
//                 "monthly_income": "monthly_income",
//                 "dependents": "dependents",
//                 "marital_status": "marital_status",
//                 "future_prospect": "future_prospect",
//                 "disability": "disability",
//                 "disability_percentage": "disability",
//                 "medical_expenses": "medical_expenses",
//                 "future_medical_expenses": "future_medical_expenses",
//                 "pain_and_suffering": "pain_and_suffering",
//                 "transportation": "transportation",
//                 "special_diet": "special_diet",
//                 "attender_charges": "attender_charges",
//                 "loss_of_income": "loss_of_income",
//                 "loss_of_consortium": "consortium",
//                 "consortium": "consortium",
//                 "funeral_expenses": "funeral_expenses",
//                 "loss_of_estate": "loss_estate",
//                 "loss_estate": "loss_estate",
//                 "dob": "date_of_birth",
//                 "date_of_birth": "date_of_birth",
//                 "accident_date": "date_of_accident",
//                 "date_of_accident": "date_of_accident"
//             };
// 
//             Object.keys(keyMappings).forEach(rawKey => {
//                 const cacheKey = keyMappings[rawKey];
//                 const rawObj = rawRecovered[rawKey];
//                 let val = null;
//                 let conf = null;
// 
//                 if (rawObj && typeof rawObj === "object" && "value" in rawObj) {
//                     val = rawObj.value;
//                     conf = rawObj.confidence;
//                 } else if (rawObj !== undefined) {
//                     val = rawObj;
//                 }
// 
//                 if (val !== null && val !== undefined && val !== "") {
//                     lastExtractedFields[cacheKey] = val;
//                     if (conf !== null && conf !== undefined) {
//                         lastExtractedConfidences[cacheKey] = conf;
//                     }
//                 }
//             });
//         }
// 
//         // Cache confidences
//         const lowConfFields = suggestions.low_confidence_fields || [];
//         const combinedKeys = new Set([...Object.keys(lastExtractedFields), "date_of_birth", "date_of_accident"]);
// 
//         combinedKeys.forEach(key => {
//             if (confidenceScores && confidenceScores[key]) {
//                 const confVal = confidenceScores[key].confidence !== undefined 
//                     ? confidenceScores[key].confidence 
//                     : confidenceScores[key];
//                 lastExtractedConfidences[key] = typeof confVal === "number" ? confVal : parseFloat(confVal) || 1.0;
//             } else if (lastExtractedConfidences[key] === undefined) {
//                 lastExtractedConfidences[key] = lowConfFields.includes(key) ? 0.65 : 1.0;
//             }
//         });
// 
//         // Run case-specific field population (Part 5 & Part 6)
//         populateFieldsForActiveCaseType();
// 
//         // Telemetry Audit log update (Part 7)
//         let evidenceStr = ocrEvidence || "UNCLEAR";
//         if (rawRecovered && rawRecovered.ocr_evidence_case) {
//             evidenceStr = rawRecovered.ocr_evidence_case;
//         }
// 
//         let totalConf = 0;
//         let confCount = 0;
//         Object.keys(lastExtractedConfidences).forEach(k => {
//             if (lastExtractedFields[k] !== undefined && lastExtractedFields[k] !== "") {
//                 totalConf += lastExtractedConfidences[k];
//                 confCount++;
//             }
//         });
//         const avgConf = confCount > 0 ? (totalConf / confCount) : 0.85;
// 
//         updateAuditLog(loggedUserCaseType, loggedLlmCaseType, evidenceStr, avgConf, overwriteBlocked);
// 
//         if (overwriteBlocked) {
//             showToast(`Preserved manually selected Case Type (${loggedUserCaseType})! Overwrite blocked.`, "warning");
//         } else {
//             showToast(`Workstation variables successfully auto-filled!`, "success");
//         }
// 
//         // Auto trigger automatic recalculation after autofill is completed (Task 18)
//         setTimeout(() => {
//             console.log("AUTO RECALCULATING after OCR autofill...");
//             if (compensationForm) {
//                 compensationForm.dispatchEvent(new Event("submit"));
//             }
//         }, 500);
//     }
// 
//     // ==========================================================================
//     // AI DATA RECOVERY (LLM OPTIMIZED PARSING EXTRACTION)
//     // ==========================================================================
//     // AI DATA RECOVERY (LLM OPTIMIZED PARSING EXTRACTION) (Part 3, Part 4 & Part 5 integration)
//     if (aiExtractBtn) {
//         aiExtractBtn.addEventListener("click", async () => {
//             if (!currentOcrRawText || currentOcrRawText.length === 0) {
//                 showToast("No raw OCR text available. Please upload a PDF first.", "warning");
//                 return;
//             }
// 
//             const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
//             const loader = document.createElement("div");
//             loader.className = "form-ocr-loader";
//             loader.innerHTML = `
//                 <div class="spinner-glow"></div>
//                 <p>AI Legal LLM is parsing text...</p>
//                 <span style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Recovering missing legal compensation entities</span>
//             `;
//             formPanel.style.position = "relative";
//             formPanel.appendChild(loader);
// 
//             try {
//                 const response = await fetch("/api/ocr/ai-recover", {
//                     method: "POST",
//                     headers: { "Content-Type": "application/json" },
//                     body: JSON.stringify({ raw_text: currentOcrRawText })
//                 });
// 
//                 loader.remove();
// 
//                 if (!response.ok) {
//                     const errData = await response.json().catch(() => ({}));
//                     throw new Error(errData.detail || "AI recovery API returned error status");
//                 }
//                 const data = await response.json();
// 
//                 if (data.success) {
//                     const confidenceScores = data.raw_recovered ? data.raw_recovered.confidence_scores : null;
//                     const ocrEvidence = data.raw_recovered ? data.raw_recovered.ocr_evidence_case : null;
//                     applyAllOcrSuggestions(data.suggestions, confidenceScores, ocrEvidence, data.raw_recovered);
//                     showToast("AI data extraction complete! All recovered parameters cached internally.", "success");
//                 } else {
//                     showToast("AI extraction failed to extract fields.", "error");
//                 }
//             } catch (error) {
//                 loader.remove();
//                 console.error("AI recovery failed:", error);
//                 showToast(`AI extraction failed: ${error.message}`, "error");
//             }
//         });
//     }
// 
//     function syncChatDocumentFilter() {
//         const chatDocumentFilter = document.getElementById("chat-document-filter");
//         if (!chatDocumentFilter) return;
// 
//         const currentSelection = chatDocumentFilter.value;
// 
//         chatDocumentFilter.innerHTML = '<option value="all">All Documents</option>';
// 
//         const indexedFiles = fileQueue.filter(f => f.status === "indexed").map(f => f.filename);
// 
//         const uniqueFiles = [...new Set(indexedFiles)];
//         uniqueFiles.forEach(filename => {
//             const opt = document.createElement("option");
//             opt.value = filename;
//             opt.textContent = filename;
//             chatDocumentFilter.appendChild(opt);
//         });
// 
//         if (uniqueFiles.includes(currentSelection)) {
//             chatDocumentFilter.value = currentSelection;
//         }
//     }
// 
//     // ==========================================================================
//     // AI PRECEDENTS SEARCH & CHAT (TAB 3)
//     // ==========================================================================
//     chatSendBtn.addEventListener("click", handleChatSend);
//     chatInput.addEventListener("keypress", (e) => {
//         if (e.key === "Enter") handleChatSend();
//     });
// 
//     async function handleChatSend() {
//         const query = chatInput.value.trim();
//         if (!query) return;
// 
//         // Render user message bubble
//         appendChatBubble(query, "user");
//         chatInput.value = "";
// 
//         // Render thinking loader bubble
//         const loadingId = appendChatBubble(`<i class="fa-solid fa-spinner fa-spin"></i> Semantic AI searching Qdrant database...`, "bot", true);
// 
//         try {
//             const payload = {
//                 message: query,
//                 case_type: chatCaseFilter.value
//             };
// 
//             const chatDocumentFilter = document.getElementById("chat-document-filter");
//             const docFilterVal = chatDocumentFilter ? chatDocumentFilter.value : "all";
//             if (docFilterVal !== "all") {
//                 payload.filename = docFilterVal;
//             }
// 
//             const response = await fetch("/api/chat/pdf", {
//                 method: "POST",
//                 headers: { "Content-Type": "application/json" },
//                 body: JSON.stringify(payload)
//             });
// 
//             if (!response.ok) throw new Error("Search API failure");
//             const data = await response.json();
// 
//             // Remove loading bubble
//             document.getElementById(loadingId).remove();
// 
//             // Render structured markdown legal response
//             appendChatBubble(data.response, "bot");
// 
//         } catch (error) {
//             console.error("AI Legal chat error:", error);
//             document.getElementById(loadingId).remove();
//             appendChatBubble("I apologize, but I encountered an error searching the centralized database. Please verify the backend uvicorn service is fully initialized.", "bot");
//         }
//     }
// 
//     function appendChatBubble(text, sender, isLoader = false) {
//         const bubble = document.createElement("div");
//         const id = `msg_${Date.now()}`;
//         bubble.id = id;
//         bubble.className = `chat-bubble ${sender}`;
// 
//         const avatarHtml = sender === "bot" ? `<i class="fa-solid fa-robot"></i>` : `<i class="fa-solid fa-user-tie"></i>`;
// 
//         // Render markdown formatting inside bubble text (simple converter)
//         let formattedText = text;
//         if (!isLoader) {
//             formattedText = text
//                 .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
//                 .replace(/\*(.*?)\*/g, '<em>$1</em>')
//                 .replace(/\n/g, '<br>');
//         }
// 
//         bubble.innerHTML = `
//             <div class="chat-avatar">${avatarHtml}</div>
//             <div class="chat-text">${formattedText}</div>
//         `;
// 
//         chatMessages.appendChild(bubble);
//         chatMessages.scrollTop = chatMessages.scrollHeight;
// 
//         if (!isLoader && typeof bindChatBubbleClick === "function") {
//             bindChatBubbleClick(bubble);
//         }
// 
//         return id;
//     }
// 
//     // ==========================================================================
//     // COMPARATIVE LEGAL EVALUATOR (TAB 1)
//     // ==========================================================================
//     if (triggerEvalBtn) {
//         triggerEvalBtn.addEventListener("click", async () => {
//             if (!currentCalculationAmount || currentCalculationAmount <= 0) {
//                 alert("Please calculate the compensation first by filling in mandatory workstation variables and clicking 'Calculate'.");
//                 return;
//             }
// 
//             // Display loading loader inside evaluator card body
//             if (evaluatorCardBody) {
//                 evaluatorCardBody.innerHTML = `
//                     <div class="empty-state" style="padding: 10px 0;">
//                         <i class="fa-solid fa-spinner fa-spin fa-2x" style="color: var(--color-primary);"></i>
//                         <p>Generating query embeddings & fetching precedents from Qdrant vector database...</p>
//                     </div>
//                 `;
//             }
// 
//             const payload = {
//                 params: {
//                     case_type: caseTypeSelect.value,
//                     age: parseInt(ageInput.value) || 0,
//                     monthly_income: parseFloat(monthlyIncomeInput.value) || 0,
//                     dependents: parseInt(dependentsInput.value) || 0,
//                     marital_status: maritalStatusSelect.value || "married",
//                     future_type: parseInt(futureTypeSelect?.value || 2),
//                     future_prospect: parseFloat(document.getElementById("future-prospect")?.value || 0),
//                     consortium: parseFloat(document.getElementById("consortium")?.value || 40000),
//                     funeral_expenses: parseFloat(document.getElementById("funeral-expenses")?.value || 15000),
//                     loss_estate: parseFloat(document.getElementById("loss-estate")?.value || 15000),
//                     disability: parseFloat(document.getElementById("disability")?.value || 0)
//                 },
//                 calculated_amount: currentCalculationAmount
//             };
// 
//             try {
//                 const response = await fetch("/api/search/evaluate", {
//                     method: "POST",
//                     headers: { "Content-Type": "application/json" },
//                     body: JSON.stringify(payload)
//                 });
// 
//                 if (!response.ok) throw new Error("Comparative evaluation API error");
//                 const data = await response.json();
// 
//                 if (!data.success || !data.evaluation) {
//                     throw new Error(data.message || "Failed to generate evaluation");
//                 }
// 
//                 renderPrecedentEvaluation(data.evaluation);
// 
//             } catch (error) {
//                 console.error("Benchmarking evaluation failed:", error);
//                 alert("Failed to benchmark precedents on server. Running simulated evaluation analysis.");
//                 // Offline fallback evaluator
//                 const fallbackEvaluation = simulateEvaluationMath(payload);
//                 renderPrecedentEvaluation(fallbackEvaluation);
//             }
//         });
//     }
// 
//     function simulateEvaluationMath(req) {
//         const cal = req.calculated_amount;
//         const avg = cal * (0.93 + Math.random() * 0.12);
//         const margin = ((cal - avg) / avg) * 100;
// 
//         return {
//             calculated_amount: cal,
//             average_precedent_award: Math.round(avg),
//             margin_percent: Math.round(margin * 100) / 100,
//             alignment: Math.abs(margin) <= 5.0 ? "aligned" : (margin > 5.0 ? "high" : "low"),
//             recommendation: Math.abs(margin) <= 5.0 
//                 ? `Calculated award is extremely well-aligned with precedents (${margin > 0 ? '+':''}${margin.toFixed(1)}% margin).`
//                 : `Calculated award is ${Math.abs(margin).toFixed(1)}% ${margin > 0 ? 'higher':'lower'} than precedent averages.`,
//             insurance_defense: `Historically claims of similar profiles average around Rs. ${Math.round(avg).toLocaleString('en-IN')}.`,
//             claimant_argument: `Judicial precedents reach up to Rs. ${Math.round(avg * 1.1).toLocaleString('en-IN')}.`,
//             precedents: [
//                 { filename: "judgment_mact_2023.pdf", score: 0.89, name: "Late Ram Sharan", details: "Age: 32 | Income: Rs. 22,000", award_amount: Math.round(avg * 0.95) },
//                 { filename: "hc_fatal_indore_2022.pdf", score: 0.84, name: "Late Suresh Verma", details: "Age: 35 | Income: Rs. 27,000", award_amount: Math.round(avg * 1.05) }
//             ]
//         };
//     }
// 
//     function renderPrecedentEvaluation(evalData) {
//         const alignLabels = {
//             aligned: `<span class="eval-badge aligned"><i class="fa-solid fa-circle-check"></i> Aligned</span>`,
//             high: `<span class="eval-badge high"><i class="fa-solid fa-triangle-exclamation"></i> High Valuation</span>`,
//             low: `<span class="eval-badge low"><i class="fa-solid fa-arrow-down-long"></i> Under-valued</span>`
//         };
// 
//         let precedentsHtml = "";
//         evalData.precedents.forEach(p => {
//             precedentsHtml += `
//                 <div class="precedent-mini-card">
//                     <div class="pm-info">
//                         <span class="pm-name">${p.name}</span>
//                         <span class="pm-details" title="${p.filename}">${p.filename} | ${p.details}</span>
//                     </div>
//                     <div>
//                         <span class="pm-award">Rs. ${p.award_amount.toLocaleString('en-IN')}</span>
//                         <span class="pm-score">${(p.score * 100).toFixed(1)}% Match</span>
//                     </div>
//                 </div>
//             `;
//         });
// 
//         evaluatorCardBody.innerHTML = `
//             <!-- Hero comparative stats -->
//             <div class="eval-hero">
//                 <div class="eval-stats">
//                     <span class="label">Calculated Award</span>
//                     <span class="value">Rs. ${evalData.calculated_amount.toLocaleString('en-IN')}</span>
//                 </div>
//                 <div class="eval-stats" style="text-align: right;">
//                     <span class="label">Precedent Avg</span>
//                     <span class="value" style="color: var(--text-secondary)">Rs. ${evalData.average_precedent_award.toLocaleString('en-IN')}</span>
//                 </div>
//             </div>
// 
//             <!-- Alignment and margin -->
//             <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
//                 <span class="card-text">Award Margin: <strong>${evalData.margin_percent > 0 ? '+':''}${evalData.margin_percent}%</strong></span>
//                 ${alignLabels[evalData.alignment] || ""}
//             </div>
// 
//             <!-- Legal recommendation -->
//             <div class="eval-desc">
//                 <strong><i class="fa-solid fa-gavel"></i> Legal Opinion:</strong><br>
//                 ${evalData.recommendation}
//             </div>
// 
//             <!-- Legal Argument briefs -->
//             <div class="eval-desc" style="background: rgba(186, 104, 200, 0.02); border-color: rgba(186, 104, 200, 0.12); margin-top: 8px;">
//                 <strong><i class="fa-solid fa-scroll"></i> Court Brief Argument:</strong><br>
//                 <em>"${evalData.claimant_argument}"</em>
//             </div>
// 
//             <!-- Retrieved precedent list -->
//             <div style="margin-top: 14px;">
//                 <span class="metric-label">Matching Cases Indexed (Qdrant)</span>
//                 ${precedentsHtml}
//             </div>
//         `;
// 
//         if (typeof triggerTabNotification === "function") {
//             triggerTabNotification("benchmarking");
//         }
//     }
// 
//     // ==========================================================================
//     // FORM CALCULATOR API SUBMISSION
//     // ==========================================================================
//     compensationForm.addEventListener("submit", async (e) => {
//         e.preventDefault();
//         console.log("CALCULATE CLICKED");
// 
//         const caseType = caseTypeSelect.value;
//         if (!caseType) {
//             showToast("Please select a case type first!", "warning");
//             return;
//         }
// 
//         // Validate all required inputs are filled prior to calculations
//         if (!compensationForm.reportValidity()) {
//             showToast("Please fill all mandatory case fields before calculating.", "warning");
//             return;
//         }
// 
//         // Before submitting, check if age is missing
//         const ageVal = parseInt(ageInput.value);
//         if (!ageVal || ageVal <= 0) {
//             showToast("⚠️ Age not set — calculation will use default age 30. Upload a PDF or enter DOB + accident date.", "warning");
//         }
// 
//         const payload = {
//             case_type: caseType,
//             age: Number(ageInput.value || 0),
//             monthly_income: Number(monthlyIncomeInput.value || 0),
// 
//             dependents: Number(dependentsInput.value || 0),
//             marital_status: maritalStatusSelect.value || "married",
//             future_type: Number(futureTypeSelect?.value || 2),
//             future_prospect: Number(document.getElementById("future-prospect")?.value || 0),
//             consortium: Number(document.getElementById("consortium")?.value || 40000),
//             funeral_expenses: Number(document.getElementById("funeral-expenses")?.value || 15000),
//             loss_estate: Number(document.getElementById("loss-estate")?.value || 15000),
// 
//             // Consortium breakdown (hardcoded to 0 under the hood)
//             conlum: 0,
//             conspo: 0,
//             conpar: 0,
//             conchil: 0,
//             conwif: 0,
//             conmo: 0,
//             confath: 0,
//             conhus: 0,
//             conbro: 0,
//             consis: 0,
// 
//             disability: Number(document.getElementById("disability")?.value || 0),
//             medical_expenses: Number(document.getElementById("medical-expenses")?.value || 0),
//             future_medical_expenses: Number(document.getElementById("future-medical-expenses")?.value || 0),
//             pain_and_suffering: Number(document.getElementById("pain-and-suffering")?.value || 0),
//             transportation: Number(document.getElementById("transportation")?.value || 0),
//             special_diet: Number(document.getElementById("special-diet")?.value || 0),
//             attender_charges: Number(document.getElementById("attender-charges")?.value || 0),
//             loss_of_income: Number(document.getElementById("loss-of-income")?.value || 0),
// 
//             // Extra Injury heads
//             coliti: 0,
//             misex: 0,
//             loamiti: 0,
//             lopmarri: 0,
//             loexlife: 0,
//             loveaff: 0,
//             lossofenjoy: 0
//         };
// 
//         try {
//             const response = await fetch("/api/calculate/", {
//                 method: "POST",
//                 headers: { "Content-Type": "application/json" },
//                 body: JSON.stringify(payload)
//             });
// 
//             if (!response.ok) throw new Error("Server calculator returned error status");
//             const results = await response.json();
// 
//             if (results.success === false) {
//                 throw new Error(results.error || "Server calculation process failed");
//             }
// 
//             // Align with nested schema: use results.breakdown if available, otherwise flat results
//             const breakdown = results.breakdown || results;
//             currentCalculationAmount = results.total_compensation || breakdown.final_amount || 0;
// 
//             // Update inputs and previews with real calculated money values
//             updateMonetaryOutputs(breakdown);
// 
//             renderResultsDashboard(breakdown, payload);
//             openModal();
//             showToast("Compensation calculated successfully via FastAPI server!", "success");
// 
//             // Enable Evaluator button
//             if (triggerEvalBtn) triggerEvalBtn.disabled = false;
// 
//         } catch (error) {
//             console.error("Server-side calculation failed:", error);
//             showToast(`Backend computation failed: ${error.message}. Running local mathematical fallback engine.`, "warning");
// 
//             const localResults = calculateCompensationLocally(payload);
// 
//             currentCalculationAmount = localResults.final_amount;
// 
//             // Update inputs and previews with real calculated money values locally
//             updateMonetaryOutputs(localResults);
// 
//             renderResultsDashboard(localResults, payload);
//             openModal();
//             if (triggerEvalBtn) triggerEvalBtn.disabled = false;
//         }
//     });
// 
//     // Local Math Evaluator fallback
//     function calculateCompensationLocally(data) {
//         const age = data.age;
//         const multiplier = getMultiplier(age);
//         const monthly = data.monthly_income;
//         const annual = monthly * 12;
// 
//         if (data.case_type === "death") {
//             const futureProspect = getFutureProspectPercentage(age, data.future_type);
//             const futureProspectAmount = monthly * futureProspect / 100;
//             const enhancedMonthlyIncome = monthly + futureProspectAmount;
//             const annualIncome = enhancedMonthlyIncome * 12;
//             const deductionRatio = getDeductionRatio(data.dependents, data.marital_status);
//             const deductionPercent = Math.round(deductionRatio * 100);
//             const deductionAmount = annualIncome * deductionRatio;
//             const dependencyIncome = annualIncome - deductionAmount;
//             const lossOfDependency = dependencyIncome * multiplier;
//             const finalCompensation = lossOfDependency + data.consortium + data.funeral_expenses + data.loss_estate;
// 
//             return {
//                 case_type: "death",
//                 multiplier: multiplier,
//                 future_prospect_percentage: Math.round(futureProspect),
//                 future_prospect_amount: Math.round(futureProspectAmount),
//                 enhanced_monthly_income: Math.round(enhancedMonthlyIncome),
//                 monthly_income: Math.round(monthly),
//                 annual_income: Math.round(annualIncome),
//                 future_income: Math.round(annualIncome), // for backwards compatibility
//                 deduction_percentage: Math.round(deductionPercent),
//                 deduction_amount: Math.round(deductionAmount),
//                 dependency_income: Math.round(dependencyIncome),
//                 loss_of_dependency: Math.round(lossOfDependency),
//                 consortium: data.consortium,
//                 funeral_expenses: data.funeral_expenses,
//                 loss_estate: data.loss_estate,
//                 final_compensation: Math.round(finalCompensation),
//                 final_amount: Math.round(finalCompensation)
//             };
//         } else {
//             const disabilityCompensation = annual * (data.disability / 100) * multiplier;
//             const finalCompensation = disabilityCompensation + data.medical_expenses + data.future_medical_expenses + 
//                 data.pain_and_suffering + data.transportation + data.special_diet + data.attender_charges + data.loss_of_income;
// 
//             return {
//                 case_type: "injury",
//                 multiplier: multiplier,
//                 annual_income: Math.round(annual),
//                 future_income_loss: Math.round(disabilityCompensation),
//                 medical_expenses: data.medical_expenses,
//                 future_medical_expenses: data.future_medical_expenses,
//                 pain_and_suffering: data.pain_and_suffering,
//                 transportation: data.transportation,
//                 special_diet: data.special_diet,
//                 attender_charges: data.attender_charges,
//                 loss_of_income: data.loss_of_income,
//                 coliti: 0,
//                 misex: 0,
//                 loamiti: 0,
//                 lopmarri: 0,
//                 loexlife: 0,
//                 loveaff: 0,
//                 lossofenjoy: 0,
//                 final_amount: Math.round(finalCompensation)
//             };
//         }
//     }
// 
//     function formatCurrency(amount) {
//         return new Intl.NumberFormat('en-IN', {
//             style: 'currency',
//             currency: 'INR',
//             maximumFractionDigits: 0
//         }).format(amount);
//     }
// 
//     function updateMonetaryOutputs(res) {
//         if (res.case_type === "death") {
//             const annualIncome = res.annual_income || 0;
//             const enhancedMonthlyIncome = res.enhanced_monthly_income || 0;
//             const deductionPercent = res.deduction_percentage || 0;
//             const deductionAmount = res.deduction_amount || 0;
//             const mult = res.multiplier || 0;
//             const lossOfDependency = res.loss_of_dependency || 0;
//             const finalComp = res.final_compensation || res.final_amount || 0;
// 
//             // Populate read-only inputs
//             const lossDepInput = document.getElementById("loss-of-dependency");
//             if (lossDepInput) lossDepInput.value = Math.round(lossOfDependency);
// 
//             const finalDeathCompInput = document.getElementById("death-final-compensation");
//             if (finalDeathCompInput) finalDeathCompInput.value = Math.round(finalComp);
// 
//             // Populate dynamic dashboard elements
//             if (document.getElementById("live-calc-annual")) {
//                 document.getElementById("live-calc-annual").textContent = formatCurrency(annualIncome);
//                 document.getElementById("live-calc-future").textContent = formatCurrency(enhancedMonthlyIncome);
//                 document.getElementById("live-calc-deduct-pct").textContent = `${deductionPercent}%`;
//                 document.getElementById("live-calc-deduct-amt").textContent = formatCurrency(deductionAmount);
//                 document.getElementById("live-calc-multiplier").textContent = mult;
//                 document.getElementById("live-calc-dependency").textContent = formatCurrency(lossOfDependency);
//                 document.getElementById("live-calc-total").textContent = formatCurrency(finalComp);
//             }
//         }
//     }
// 
//     function updateOcrInspector(data) {
//         if (!data || !data.ocr_debug) return;
//         const debug = data.ocr_debug;
// 
//         // 1. Overall stats
//         const qScore = debug.ocr_quality_score !== undefined ? debug.ocr_quality_score : 0.0;
//         const avgConf = debug.average_page_confidence !== undefined ? debug.average_page_confidence : 0.0;
//         const textDensity = debug.text_density_score !== undefined ? debug.text_density_score : 0.0;
// 
//         const qEl = document.getElementById("ocr-val-quality");
//         if (qEl) qEl.textContent = qScore.toFixed(3);
// 
//         const cEl = document.getElementById("ocr-val-confidence");
//         if (cEl) cEl.textContent = (avgConf * 100).toFixed(1) + "%";
// 
//         const eEl = document.getElementById("ocr-val-engine");
//         if (eEl) eEl.textContent = debug.ocr_engine_used || "Unknown";
// 
//         const fEl = document.getElementById("ocr-val-fallback");
//         if (fEl) fEl.textContent = debug.fallback_ocr_engine || "None";
// 
//         const rEl = document.getElementById("ocr-val-retries");
//         if (rEl) rEl.textContent = debug.ocr_retry_count !== undefined ? debug.ocr_retry_count : 0;
// 
//         const dEl = document.getElementById("ocr-val-density");
//         if (dEl) dEl.textContent = textDensity.toFixed(3);
// 
//         const durationEl = document.getElementById("ocr-val-duration");
//         if (durationEl) {
//             const durationSec = debug.total_ocr_time !== undefined ? debug.total_ocr_time : ocrSecondsElapsed;
//             durationEl.textContent = typeof durationSec === "number" ? formatTimeMMSS(Math.round(durationSec)) : durationSec || "—";
//         }
// 
//         // Update badge
//         const badge = document.getElementById("ocr-inspector-badge");
//         if (badge) {
//             badge.textContent = data.fallback_source || "Loaded";
//             badge.className = "badge tech-badge " + (qScore >= 0.5 ? "bg-success" : "bg-danger");
//         }
// 
//         // 2. Raw Text Dump
//         const textDump = document.getElementById("ocr-raw-text-dump");
//         if (textDump && data.raw_text) {
//             textDump.value = data.raw_text.join("\n");
//         }
// 
//         // 3. Page Breakdown Table
//         const tableBody = document.getElementById("ocr-pages-table-body");
//         if (tableBody) {
//             if (debug.pages && debug.pages.length > 0) {
//                 tableBody.innerHTML = "";
//                 debug.pages.forEach(p => {
//                     const tr = document.createElement("tr");
//                     tr.style.borderBottom = "1px solid var(--border-glass)";
// 
//                     const pageNum = p.page || 1;
//                     const engine = p.engine || "PaddleOCR";
//                     const dpi = p.dpi || 180;
//                     const pageTime = p.total_page_time !== undefined ? p.total_page_time.toFixed(2) + "s" : "—";
//                     const conf = p.confidence !== undefined ? (p.confidence * 100).toFixed(1) + "%" : "—";
//                     const quality = p.quality_score !== undefined ? p.quality_score.toFixed(3) : "—";
// 
//                     tr.innerHTML = `
//                         <td style="padding: 8px 12px; font-weight: 600; color: var(--text-primary);">Page ${pageNum}</td>
//                         <td style="padding: 8px 12px; color: var(--text-secondary);">${engine}</td>
//                         <td style="padding: 8px 12px; color: var(--text-secondary);">${dpi} DPI</td>
//                         <td style="padding: 8px 12px; text-align: right; font-family: monospace; color: var(--text-secondary);">${pageTime}</td>
//                         <td style="padding: 8px 12px; text-align: right; font-family: monospace; color: var(--color-success);">${conf}</td>
//                         <td style="padding: 8px 12px; text-align: right; font-family: monospace; color: var(--color-primary);">${quality}</td>
//                     `;
//                     tableBody.appendChild(tr);
//                 });
//             } else {
//                 tableBody.innerHTML = `
//                     <tr>
//                         <td colspan="6" style="padding: 16px; text-align: center; color: var(--text-muted);">
//                             No page details returned.
//                         </td>
//                     </tr>
//                 `;
//             }
//         }
//     }
// 
//     function renderResultsDashboard(res, req) {
//         const claimantName = document.getElementById("name")?.value || "N/A";
//         const fatherNameVal = document.getElementById("father-name")?.value || "N/A";
//         const dateAccidentVal = doaInput.value ? new Date(doaInput.value).toLocaleDateString('en-IN') : "N/A";
//         const dateBirthVal = dobInput.value ? new Date(dobInput.value).toLocaleDateString('en-IN') : "N/A";
//         const placeAccidentVal = document.getElementById("place-of-accident")?.value || "N/A";
//         const caseTypeLabel = res.case_type === "death" ? "Death Claim" : "Injury Claim";
// 
//         let parametersHtml = "";
//         if (res.case_type === "death") {
//             const futureProspectPercent = res.future_prospect_percentage !== undefined ? res.future_prospect_percentage : 0;
//             const monthlyIncomeVal = res.monthly_income !== undefined ? res.monthly_income : req.monthly_income;
//             const enhancedMonthlyIncomeVal = res.enhanced_monthly_income !== undefined ? res.enhanced_monthly_income : (monthlyIncomeVal * (1 + futureProspectPercent / 100));
//             const annualIncomeVal = res.annual_income !== undefined ? res.annual_income : (enhancedMonthlyIncomeVal * 12);
// 
//             parametersHtml = `
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Monthly Income</span>
//                     <strong>${formatCurrency(monthlyIncomeVal)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Future Prospects Added</span>
//                     <strong>+${futureProspectPercent}%</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Enhanced Monthly Income</span>
//                     <strong>${formatCurrency(enhancedMonthlyIncomeVal)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Annual Income (Enhanced)</span>
//                     <strong>${formatCurrency(annualIncomeVal)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Deduction Applied</span>
//                     <strong>${res.deduction_percentage}% (-${formatCurrency(res.deduction_amount)})</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Dependency Income</span>
//                     <strong>${formatCurrency(res.dependency_income)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Multiplier Used</span>
//                     <strong>${res.multiplier}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Loss of Dependency</span>
//                     <strong>${formatCurrency(res.loss_of_dependency)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Consortium</span>
//                     <strong>${formatCurrency(res.consortium)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Funeral Expenses</span>
//                     <strong>${formatCurrency(res.funeral_expenses)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0;">
//                     <span>Loss of Estate</span>
//                     <strong>${formatCurrency(res.loss_estate)}</strong>
//                 </div>
//             `;
//         } else {
//             parametersHtml = `
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Monthly Income</span>
//                     <strong>${formatCurrency(req.monthly_income)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Sarla Verma Multiplier</span>
//                     <strong>${res.multiplier}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Permanent Impairment</span>
//                     <strong>${req.disability}%</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Medical Expenses</span>
//                     <strong>${formatCurrency(res.medical_expenses + res.future_medical_expenses)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
//                     <span>Pain & Suffering</span>
//                     <strong>${formatCurrency(res.pain_and_suffering)}</strong>
//                 </div>
//                 <div style="display: flex; justify-content: space-between; padding: 6px 0;">
//                     <span>Other Allowances (Diet, Attender, Transport, Income Loss)</span>
//                     <strong>${formatCurrency(res.transportation + res.special_diet + res.attender_charges + res.loss_of_income)}</strong>
//                 </div>
//             `;
//         }
// 
//         modalBodyContent.innerHTML = `
//             <div class="results-dashboard simplified-dashboard">
//                 <div class="award-hero" style="text-align: center; margin-bottom: 20px;">
//                     <span class="hero-label" style="display: block; font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px;">FINAL COMPENSATION</span>
//                     <span class="hero-amount" style="display: block; font-size: 2.5rem; font-weight: 800; font-family: 'Outfit', sans-serif; color: var(--color-success); margin: 6px 0; text-shadow: 0 0 20px rgba(52, 211, 153, 0.2);">${formatCurrency(res.final_compensation || res.final_amount)}</span>
//                     <span class="hero-tag" style="background: rgba(186, 104, 200, 0.2); color: #e9d5ff; border: 1px solid rgba(186, 104, 200, 0.3); font-size: 0.75rem; padding: 3px 10px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 6px;"><i class="fa-solid fa-gavel"></i> ${caseTypeLabel}</span>
//                 </div>
// 
//                 <div class="briefing-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.85rem; border: 1px solid var(--border-glass); padding: 16px; border-radius: var(--radius-sm); background: rgba(255,255,255,0.01); margin-bottom: 20px; color: var(--text-primary);">
//                     <div><strong>Claimant / Deceased Name:</strong> ${claimantName}</div>
//                     <div><strong>Father / Husband Name:</strong> ${fatherNameVal}</div>
//                     <div><strong>Date of Birth (Age):</strong> ${dateBirthVal} (${req.age} years)</div>
//                     <div><strong>Date of Accident:</strong> ${dateAccidentVal}</div>
//                     <div style="grid-column: span 2;"><strong>Place of Accident:</strong> ${placeAccidentVal}</div>
//                 </div>
// 
//                 <div class="parameters-summary-box" style="border: 1px solid var(--border-glass); border-radius: var(--radius-sm); background: rgba(255,255,255,0.02); padding: 16px; color: var(--text-primary);">
//                     <h4 style="margin-top: 0; margin-bottom: 12px; font-family: 'Outfit', sans-serif; font-size: 0.95rem; border-bottom: 1px solid var(--border-glass); padding-bottom: 6px; color: var(--color-primary); display: flex; align-items: center; gap: 8px;"><i class="fa-solid fa-list-check"></i> Calculation Parameters</h4>
//                     <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.85rem;">
//                         ${parametersHtml}
//                     </div>
//                 </div>
//             </div>
//         `;
// 
//         const finalCompEl = document.getElementById("final-compensation");
//         if (finalCompEl) {
//             finalCompEl.innerText = `₹ ${(res.final_compensation || res.final_amount).toLocaleString("en-IN")}`;
//         }
//     }
// 
//     // Modal controls
//     function openModal() { resultsModal.classList.add("open"); }
//     function closeModal() { resultsModal.classList.remove("open"); }
// 
//     closeModalBtn.addEventListener("click", closeModal);
//     dismissModalBtn.addEventListener("click", closeModal);
//     window.addEventListener("click", (e) => {
//         if (e.target === resultsModal) closeModal();
//     });
// 
//     document.getElementById("reset-btn").addEventListener("click", () => {
//         compensationForm.reset();
// 
//         window.lastRawText = "";
//         const suggestionDiv = document.getElementById("case-type-suggestion");
//         if (suggestionDiv) {
//             suggestionDiv.innerHTML = "";
//             suggestionDiv.classList.add("hidden-section");
//         }
// 
//         // Clear all live calculated dashboard elements back to hyphens
//         ["live-calc-annual", "live-calc-future", "live-calc-deduct-pct", "live-calc-deduct-amt", "live-calc-multiplier", "live-calc-dependency", "live-calc-total"].forEach(id => {
//             const el = document.getElementById(id);
//             if (el) el.textContent = "—";
//         });
// 
//         // Clear AI metadata badges
//         document.querySelectorAll(".ai-metadata-badge").forEach(el => el.remove());
// 
//         // Reset live OCR timers
//         if (ocrTimerInterval) {
//             clearInterval(ocrTimerInterval);
//             ocrTimerInterval = null;
//         }
//         ocrSecondsElapsed = 0;
// 
//         const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
//         const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");
//         const statusIcon = document.getElementById("ocr-timer-status-icon");
//         const statusText = document.getElementById("ocr-timer-status-text");
//         const elapsedText = document.getElementById("ocr-timer-elapsed");
// 
//         if (headerElapsedText) {
//             headerElapsedText.textContent = "Ready";
//         }
//         if (headerTimerContainer) {
//             headerTimerContainer.style.color = "var(--text-secondary)";
//             headerTimerContainer.style.borderColor = "var(--border-glass)";
//             headerTimerContainer.style.background = "rgba(15, 23, 42, 0.04)";
//         }
//         if (statusIcon) {
//             statusIcon.innerHTML = `<i class="fa-solid fa-clock" style="color: var(--color-primary);"></i>`;
//         }
//         if (statusText) {
//             statusText.textContent = "Ready for upload";
//             statusText.style.color = "var(--text-secondary)";
//         }
//         if (elapsedText) {
//             elapsedText.textContent = "Ready";
//             elapsedText.style.color = "var(--text-secondary)";
//         }
// 
//         sharedFields.classList.remove("show");
//         sharedFields.classList.add("hidden-section");
// 
//         deathFields.classList.remove("show");
//         deathFields.classList.add("hidden-section");
// 
//         injuryFields.classList.remove("show");
//         injuryFields.classList.add("hidden-section");
// 
//         formActionsBar.classList.remove("show-flex");
//         formActionsBar.classList.add("hidden-section");
// 
//         if (liveMetricsCard) {
//             liveMetricsCard.classList.remove("show");
//             liveMetricsCard.classList.add("hidden-section");
//         }
//         if (evaluatorCard) {
//             evaluatorCard.classList.remove("show");
//             evaluatorCard.classList.add("hidden-section");
//         }
// 
//         singleUploadSection.classList.remove("show");
//         singleUploadSection.classList.remove("show-flex");
//         singleUploadSection.classList.add("hidden-section");
//         singlePreviewCard.classList.add("hidden-section");
//         singlePreviewCard.classList.remove("show");
//         singlePreviewContainer.innerHTML = `
//             <div class="preview-empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 10px; opacity: 0.5;">
//                 <i class="fa-solid fa-file-pdf" style="font-size: 3rem; color: var(--color-primary)"></i>
//                 <p style="font-size: 0.8rem; color: var(--text-secondary)">Upload a PDF on the left to see the live document preview here.</p>
//             </div>
//         `;
//         singlePreviewFilename.textContent = "No File Loaded";
// 
//         const summaryCard = document.getElementById("legal-ai-summary-card");
//         if (summaryCard) {
//             summaryCard.classList.add("hidden-section");
//             summaryCard.classList.remove("show");
//             const summaryBody = document.getElementById("legal-ai-summary-body");
//             if (summaryBody) {
//                 summaryBody.innerHTML = `
//                     <div class="empty-summary-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; opacity: 0.5; padding: 20px 0;">
//                         <i class="fa-solid fa-gavel" style="font-size: 2.5rem; color: #c084fc;"></i>
//                         <p style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; margin: 0;">Upload a PDF to see the structured legal analysis summary and judicial anomaly checklist.</p>
//                     </div>
//                 `;
//             }
//         }
// 
//         const tableCard = document.getElementById("compensation-table-card");
//         if (tableCard) {
//             tableCard.classList.add("hidden-section");
//             tableCard.classList.remove("show");
//             const tableBody = document.getElementById("compensation-table-body");
//             if (tableBody) {
//                 tableBody.innerHTML = `
//                     <div class="empty-table-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; opacity: 0.5; padding: 20px 0;">
//                         <i class="fa-solid fa-table-list" style="font-size: 2.5rem; color: #34d399;"></i>
//                         <p style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; margin: 0;">Upload a PDF to view the detailed breakdown of the judicial award heads.</p>
//                     </div>
//                 `;
//             }
//         }
// 
//         triggerEvalBtn.disabled = true;
//         currentCalculationAmount = 0;
//     });
// 
//     // ==========================================================================
//     const slideover = document.getElementById("right-slideover");
//     const closeSlideover = document.getElementById("close-slideover");
//     const aiAssistantTrigger = document.getElementById("ai-assistant-trigger");
// 
//     const assistantChatMessages = document.getElementById("assistant-chat-messages");
//     const assistantChatInput = document.getElementById("assistant-chat-input");
//     const assistantChatSendBtn = document.getElementById("assistant-chat-send-btn");
// 
//     // --- WORKSTATION RIGHT PANE TABS CONTROLLER ---
//     const paneTabButtons = document.querySelectorAll(".pane-tab-btn");
//     const paneTabContents = document.querySelectorAll(".pane-tab-content");
//     const benchmarkingTabDot = document.getElementById("benchmarking-tab-dot");
//     const analysisTabDot = document.getElementById("analysis-tab-dot");
//     const ocrQualityTabDot = document.getElementById("ocr-quality-tab-dot");
// 
//     paneTabButtons.forEach(btn => {
//         btn.addEventListener("click", () => {
//             const targetTab = btn.getAttribute("data-pane-tab");
// 
//             // Switch tabs active styles
//             paneTabButtons.forEach(b => {
//                 if (b === btn) {
//                     b.classList.add("active");
//                     b.style.background = "rgba(11, 58, 114, 0.06)";
//                     b.style.borderColor = "rgba(11, 58, 114, 0.25)";
//                     b.style.color = "var(--color-primary)";
//                 } else {
//                     b.classList.remove("active");
//                     b.style.background = "transparent";
//                     b.style.borderColor = "transparent";
//                     b.style.color = "var(--text-secondary)";
//                 }
//             });
// 
//             // Toggle tab content display
//             paneTabContents.forEach(content => {
//                 if (content.id === `pane-tab-${targetTab}-content`) {
//                     content.classList.add("active");
//                     content.classList.remove("hidden");
//                 } else {
//                     content.classList.remove("active");
//                     content.classList.add("hidden");
//                 }
//             });
// 
//             // Clear dot when tab is clicked
//             if (targetTab === "benchmarking" && benchmarkingTabDot) {
//                 benchmarkingTabDot.classList.add("hidden");
//             } else if (targetTab === "analysis" && analysisTabDot) {
//                 analysisTabDot.classList.add("hidden");
//             } else if (targetTab === "ocr-quality" && ocrQualityTabDot) {
//                 ocrQualityTabDot.classList.add("hidden");
//             }
//         });
//     });
// 
//     // Helper to get active tab
//     function getActiveRightPaneTab() {
//         const activeBtn = document.querySelector(".pane-tab-btn.active");
//         return activeBtn ? activeBtn.getAttribute("data-pane-tab") : "pdf";
//     }
// 
//     // Helper to trigger tab notification dot rather than forcing switch
//     window.triggerTabNotification = function(tabName) {
//         if (getActiveRightPaneTab() !== tabName) {
//             if (tabName === "benchmarking" && benchmarkingTabDot) {
//                 benchmarkingTabDot.classList.remove("hidden");
//             } else if (tabName === "analysis" && analysisTabDot) {
//                 analysisTabDot.classList.remove("hidden");
//             } else if (tabName === "ocr-quality" && ocrQualityTabDot) {
//                 ocrQualityTabDot.classList.remove("hidden");
//             }
//         }
//     };
// 
//     // --- CHAT READ MODAL ENGINE (BIG BOX VIEWER) ---
//     const chatReadModal = document.getElementById("chat-read-modal");
//     const chatModalBodyContent = document.getElementById("chat-modal-body-content");
//     const closeChatModalBtn = document.getElementById("close-chat-modal-btn");
//     const dismissChatModalBtn = document.getElementById("dismiss-chat-modal-btn");
// 
//     window.openChatReader = function(htmlContent) {
//         if (chatReadModal && chatModalBodyContent) {
//             chatModalBodyContent.innerHTML = htmlContent;
//             chatReadModal.classList.add("open");
//         }
//     };
// 
//     window.closeChatReader = function() {
//         if (chatReadModal) {
//             chatReadModal.classList.remove("open");
//         }
//     };
// 
//     if (closeChatModalBtn) closeChatModalBtn.addEventListener("click", closeChatReader);
//     if (dismissChatModalBtn) dismissChatModalBtn.addEventListener("click", closeChatReader);
// 
//     // Close modal when clicking outside content area
//     window.addEventListener("click", (e) => {
//         if (e.target === chatReadModal) {
//             closeChatReader();
//         }
//     });
// 
//     // Function to attach click listeners to chat texts
//     window.bindChatBubbleClick = function(bubbleElement) {
//         const textElement = bubbleElement.querySelector(".chat-text");
//         if (textElement) {
//             textElement.addEventListener("click", () => {
//                 openChatReader(textElement.innerHTML);
//             });
//         }
//     };
// 
//     // Bind existing bubbles on startup
//     document.querySelectorAll(".chat-bubble").forEach(bubble => {
//         bindChatBubbleClick(bubble);
//     });
// 
//     // Wide view toggle inside slideover header
//     const expandSlideoverBtn = document.getElementById("expand-slideover-btn");
//     if (expandSlideoverBtn) {
//         expandSlideoverBtn.addEventListener("click", () => {
//             if (slideover) {
//                 slideover.classList.toggle("expanded");
//                 const icon = expandSlideoverBtn.querySelector("i");
//                 if (icon) {
//                     if (slideover.classList.contains("expanded")) {
//                         icon.className = "fa-solid fa-compress";
//                         expandSlideoverBtn.title = "Toggle Normal View";
//                     } else {
//                         icon.className = "fa-solid fa-expand";
//                         expandSlideoverBtn.title = "Toggle Wide View";
//                     }
//                 }
//             }
//         });
//     }
// 
//     if (aiAssistantTrigger) {
//         aiAssistantTrigger.addEventListener("click", () => {
//             if (aiAssistantTrigger.classList.contains("active") && slideover.classList.contains("open")) {
//                 closeDrawer();
//                 return;
//             }
// 
//             aiAssistantTrigger.classList.add("active");
//             slideover.classList.add("open");
// 
//             // Auto generate CASE BRIEF on open
//             generateCaseBrief();
//         });
//     }
// 
//     function closeDrawer() {
//         if (slideover) {
//             slideover.classList.remove("open");
//             slideover.classList.remove("expanded");
//             if (expandSlideoverBtn) {
//                 const icon = expandSlideoverBtn.querySelector("i");
//                 if (icon) {
//                     icon.className = "fa-solid fa-expand";
//                     expandSlideoverBtn.title = "Toggle Wide View";
//                 }
//             }
//         }
//         if (aiAssistantTrigger) aiAssistantTrigger.classList.remove("active");
//     }
// 
//     if (closeSlideover) {
//         closeSlideover.addEventListener("click", closeDrawer);
//     }
// 
//     // Generate formatted Case Brief automatically based on workstation inputs
//     function generateCaseBrief() {
//         const caseType = caseTypeSelect.value || "N/A";
//         const caseTypeLabel = caseType === "death" ? "Death Claim" : (caseType === "injury" ? "Injury Claim" : "N/A");
// 
//         const claimantName = document.getElementById("name")?.value || "N/A";
//         const respondentName = "Insurance Company / Respondent"; 
//         const ageVal = ageInput.value ? `${ageInput.value} years` : "N/A";
//         const monthlyIncome = parseFloat(monthlyIncomeInput.value) || 0;
//         const incomeVal = monthlyIncome > 0 ? formatCurrency(monthlyIncome) : "N/A";
// 
//         const disabilityInput = document.getElementById("disability");
//         const disabilityVal = (caseType === "injury" && disabilityInput && disabilityInput.value) ? `${disabilityInput.value}%` : "N/A";
// 
//         const awardAmountVal = currentCalculationAmount > 0 ? formatCurrency(currentCalculationAmount) : "N/A";
//         const statusVal = currentCalculationAmount > 0 ? "Calculated (Deterministic Math)" : "Awaiting Mathematical Input";
// 
//         const occupationVal = "Salaried / Self-Employed"; 
// 
//         const contentEl = document.getElementById("assistant-case-brief-content");
//         if (contentEl) {
//             contentEl.innerHTML = `
//                 <table style="width:100%; border-collapse:collapse; font-size:0.8rem; line-height:1.6;">
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Case Type:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${caseTypeLabel}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Claimant:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${claimantName}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Respondent:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${respondentName}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Age:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${ageVal}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Occupation:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${occupationVal}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Income:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${incomeVal}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Disability:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${disabilityVal}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Award Amount:</td><td style="padding:4px 0; text-align:right; font-weight:700; color:var(--color-success);">${awardAmountVal}</td></tr>
//                     <tr><td style="padding:4px 0; color:var(--text-muted);">Status:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:${currentCalculationAmount > 0 ? '#34d399' : '#f59e0b'};">${statusVal}</td></tr>
//                 </table>
//             `;
//         }
//     }
// 
//     // Bind Suggested Question Pills immediately
//     document.querySelectorAll(".suggested-question-pill").forEach(pill => {
//         pill.addEventListener("click", () => {
//             const questionText = pill.getAttribute("data-question");
//             if (assistantChatInput) {
//                 assistantChatInput.value = questionText;
//                 handleAssistantChatSend();
//             }
//         });
//     });
// 
//     // Side panel chat submission
//     if (assistantChatSendBtn) {
//         assistantChatSendBtn.addEventListener("click", handleAssistantChatSend);
//     }
//     if (assistantChatInput) {
//         assistantChatInput.addEventListener("keypress", (e) => {
//             if (e.key === "Enter") handleAssistantChatSend();
//         });
//     }
// 
//     async function handleAssistantChatSend() {
//         const query = assistantChatInput.value.trim();
//         if (!query) return;
// 
//         appendAssistantChatBubble(query, "user");
//         assistantChatInput.value = "";
// 
//         const loadingId = appendAssistantChatBubble(`<i class="fa-solid fa-spinner fa-spin"></i> Auditing workstation state & searching precedents...`, "bot", true);
// 
//         try {
//             // Retrieve current workstation inputs for full LLM validation context (Phase 8 integration)
//             const caseType = caseTypeSelect.value;
//             const parsedFields = {
//                 case_type: caseType,
//                 name: document.getElementById("name")?.value || "",
//                 father_name: document.getElementById("father-name")?.value || "",
//                 age: parseInt(ageInput.value) || 0,
//                 monthly_income: parseFloat(monthlyIncomeInput.value) || 0,
//                 disability: parseFloat(document.getElementById("disability")?.value) || 0,
//                 dependents: parseInt(dependentsInput.value) || 0,
//                 marital_status: maritalStatusSelect.value || "married"
//             };
// 
//             const calculatorResult = {
//                 case_type: caseType,
//                 final_amount: currentCalculationAmount,
//                 total_compensation: currentCalculationAmount
//             };
// 
//             // Identify current active PDF filename
//             let filename = null;
//             if (singlePreviewFilename && singlePreviewFilename.innerHTML) {
//                 const parts = singlePreviewFilename.innerHTML.split("<span");
//                 if (parts.length > 0) {
//                     filename = parts[0].trim();
//                 }
//             }
// 
//             const payload = {
//                 question: query,
//                 filename: (filename && filename !== "No File Loaded") ? filename : null,
//                 ocr_text: currentOcrRawText ? currentOcrRawText.join("\n") : "",
//                 parsed_fields: parsedFields,
//                 calculator_result: calculatorResult
//             };
// 
//             const response = await fetch("/api/chat/pdf", {
//                 method: "POST",
//                 headers: { "Content-Type": "application/json" },
//                 body: JSON.stringify(payload)
//             });
// 
//             if (!response.ok) throw new Error("Assistant API returned error");
//             const data = await response.json();
// 
//             document.getElementById(loadingId).remove();
//             appendAssistantChatBubble(data.response, "bot");
// 
//         } catch (error) {
//             console.error("AI Legal Assistant error:", error);
//             document.getElementById(loadingId).remove();
//             appendAssistantChatBubble("I apologize, but I encountered an error auditing the workstation state. Please ensure the local Ollama service is running.", "bot");
//         }
//     }
// 
//     function appendAssistantChatBubble(text, sender, isLoader = false) {
//         const bubble = document.createElement("div");
//         const id = `ast_msg_${Date.now()}`;
//         bubble.id = id;
//         bubble.className = `chat-bubble ${sender}`;
// 
//         const avatarHtml = sender === "bot" ? `<i class="fa-solid fa-robot"></i>` : `<i class="fa-solid fa-user-tie"></i>`;
// 
//         let formattedText = text;
//         if (!isLoader && sender === "bot" && !text.includes("<ul") && !text.includes("<table")) {
//             formattedText = text
//                 .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
//                 .replace(/\*(.*?)\*/g, '<em>$1</em>')
//                 .replace(/\n/g, '<br>');
//         }
// 
//         bubble.innerHTML = `
//             <div class="chat-avatar">${avatarHtml}</div>
//             <div class="chat-text" style="flex: 1; min-width: 0; overflow-wrap: break-word; font-size: 0.85rem; line-height: 1.5;">${formattedText}</div>
//         `;
// 
//         assistantChatMessages.appendChild(bubble);
//         assistantChatMessages.scrollTop = assistantChatMessages.scrollHeight;
// 
//         if (!isLoader && typeof bindChatBubbleClick === "function") {
//             bindChatBubbleClick(bubble);
//         }
// 
//         return id;
//     }
// 
//     // Escape key listener to close drawer
//     document.addEventListener("keydown", (e) => {
//         if (e.key === "Escape") {
//             closeDrawer();
//         }
//     });
// 
//     // Explicit Calculate Button Click Handler & Logger
//     const calculateBtn = document.getElementById("calculate-btn");
//     if (calculateBtn) {
//         calculateBtn.addEventListener("click", (e) => {
//             compensationForm.dispatchEvent(new Event("submit"));
//         });
//     }
// 
//     if (printBtn) {
//         printBtn.addEventListener("click", () => { window.print(); });
//     }
// });



/* ==========================================================================
   COMPENSATION CALCULATOR WORKSTATION - FRONTEND DASHBOARD ENGINE
   ========================================================================== */

// Global Error Handler to shield against silent crashes (Task 19)
window.onerror = function (msg, src, line, col, err) {
    console.error("GLOBAL ERROR DETECTED:", msg, "at", src, "line:", line, err);
};

document.addEventListener("DOMContentLoaded", () => {

    // --- STATE VARIABLES ---
    let activeTab = "calculator";
    let fileQueue = []; // Local file tracker
    let uploadedFileObjects = {}; // Maps filename -> File object for local blob previews
    let isPolling = false;
    let currentCalculationAmount = 0;
    let currentOcrRawText = []; // Recover raw text from the last successful single OCR

    // Global Cache for Extracted Field Population (Part 5)
    let lastExtractedFields = {};
    let lastExtractedConfidences = {};

    // --- OCR LIVE TIMER STATE & HELPERS ---
    let ocrTimerInterval = null;
    let ocrSecondsElapsed = 0;

    function formatTimeMMSS(totalSeconds) {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    function startOcrTimer() {
        if (ocrTimerInterval) {
            clearInterval(ocrTimerInterval);
        }
        ocrSecondsElapsed = 0;

        const timerContainer = document.getElementById("ocr-timer-container");
        const statusIcon = document.getElementById("ocr-timer-status-icon");
        const statusText = document.getElementById("ocr-timer-status-text");
        const elapsedText = document.getElementById("ocr-timer-elapsed");

        const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
        const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");

        if (timerContainer) {
            timerContainer.classList.remove("hidden-section");
            timerContainer.style.display = "flex";
        }
        if (statusIcon) {
            statusIcon.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-glow" style="color: var(--color-primary);"></i>`;
        }
        if (statusText) {
            statusText.textContent = "Processing PDF...";
            statusText.style.color = "var(--text-primary)";
        }
        if (elapsedText) {
            elapsedText.textContent = "00:00";
            elapsedText.style.color = "var(--color-primary)";
        }

        if (headerTimerContainer) {
            headerTimerContainer.classList.remove("hidden-section");
            headerTimerContainer.style.display = "inline-flex";
            headerTimerContainer.style.color = "var(--color-primary)";
            headerTimerContainer.style.borderColor = "rgba(11, 58, 114, 0.25)";
            headerTimerContainer.style.background = "rgba(11, 58, 114, 0.06)";
        }
        if (headerElapsedText) {
            headerElapsedText.textContent = "00:00";
        }

        ocrTimerInterval = setInterval(() => {
            ocrSecondsElapsed++;
            const formattedTime = formatTimeMMSS(ocrSecondsElapsed);
            if (elapsedText) {
                elapsedText.textContent = formattedTime;
            }
            if (headerElapsedText) {
                headerElapsedText.textContent = formattedTime;
            }
            const loaderTimer = document.getElementById("ocr-loader-timer");
            if (loaderTimer) {
                loaderTimer.textContent = formattedTime;
            }
        }, 1000);
    }

    function stopOcrTimerSuccess() {
        if (ocrTimerInterval) {
            clearInterval(ocrTimerInterval);
            ocrTimerInterval = null;
        }
        const statusIcon = document.getElementById("ocr-timer-status-icon");
        const statusText = document.getElementById("ocr-timer-status-text");
        const elapsedText = document.getElementById("ocr-timer-elapsed");

        const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
        const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");

        if (statusIcon) {
            statusIcon.innerHTML = `<i class="fa-solid fa-circle-check" style="color: var(--color-success);"></i>`;
        }
        if (statusText) {
            statusText.textContent = "✅ OCR Complete";
            statusText.style.color = "var(--color-success)";
        }
        if (elapsedText) {
            elapsedText.textContent = `Total Time: ${formatTimeMMSS(ocrSecondsElapsed)}`;
            elapsedText.style.color = "var(--color-success)";
        }

        if (headerElapsedText && headerTimerContainer) {
            headerElapsedText.textContent = `✅ Complete: ${formatTimeMMSS(ocrSecondsElapsed)}`;
            headerTimerContainer.style.color = "var(--color-success)";
            headerTimerContainer.style.borderColor = "rgba(22, 163, 74, 0.3)";
            headerTimerContainer.style.background = "rgba(22, 163, 74, 0.08)";
        }
    }

    function stopOcrTimerFailure() {
        if (ocrTimerInterval) {
            clearInterval(ocrTimerInterval);
            ocrTimerInterval = null;
        }
        const statusIcon = document.getElementById("ocr-timer-status-icon");
        const statusText = document.getElementById("ocr-timer-status-text");
        const elapsedText = document.getElementById("ocr-timer-elapsed");

        const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
        const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");

        if (statusIcon) {
            statusIcon.innerHTML = `<i class="fa-solid fa-circle-xmark" style="color: var(--color-danger);"></i>`;
        }
        if (statusText) {
            statusText.textContent = "❌ OCR Failed";
            statusText.style.color = "var(--color-danger)";
        }
        if (elapsedText) {
            elapsedText.textContent = `OCR Failed after ${formatTimeMMSS(ocrSecondsElapsed)}`;
            elapsedText.style.color = "var(--color-danger)";
        }

        if (headerElapsedText && headerTimerContainer) {
            headerElapsedText.textContent = `❌ Failed: ${formatTimeMMSS(ocrSecondsElapsed)}`;
            headerTimerContainer.style.color = "var(--color-danger)";
            headerTimerContainer.style.borderColor = "rgba(220, 38, 38, 0.3)";
            headerTimerContainer.style.background = "rgba(220, 38, 38, 0.08)";
        }
    }

    // Programmatically Inject Suggestion Badge CSS Styles
    const styleEl = document.createElement("style");
    styleEl.innerHTML = `
        .suggested-badge {
            display: inline-flex !important;
            align-items: center !important;
            gap: 6px !important;
            margin-top: 6px !important;
            background: #fef3c7 !important; /* warm amber background for high contrast */
            color: #b45309 !important; /* dark amber text for readable AAA-level contrast */
            border: 1px solid #fde68a !important;
            padding: 5px 10px !important;
            border-radius: 6px !important;
            font-size: 0.75rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            user-select: none !important;
            width: fit-content !important;
            box-shadow: 0 1px 2px rgba(180, 83, 9, 0.08) !important;
        }
        .suggested-badge:hover {
            background: #fcd34d !important;
            border-color: #fbbf24 !important;
            color: #78350f !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 4px rgba(180, 83, 9, 0.15) !important;
        }
        .low-confidence-input {
            border-color: #fbbf24 !important;
            box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.15) !important;
        }
    `;
    document.head.appendChild(styleEl);

    // Dynamically Inject Audit Log Card (Part 7)
    const ocrQualityTab = document.getElementById("pane-tab-ocr-quality-content");
    if (ocrQualityTab) {
        let auditCard = document.getElementById("extraction-audit-log-card");
        if (!auditCard) {
            auditCard = document.createElement("div");
            auditCard.id = "extraction-audit-log-card";
            auditCard.className = "card";
            auditCard.style.marginTop = "20px";
            auditCard.innerHTML = `
                <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <h3><i class="fa-solid fa-clipboard-list text-glow" style="color: #f59e0b;"></i> Case Type &amp; Extraction Audit Log</h3>
                    <span class="badge tech-badge" id="audit-log-badge" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);">Audit Log</span>
                </div>
                <div class="card-body" style="padding-top: 12px; display: flex; flex-direction: column; gap: 15px;">
                    <div class="metrics-grid" style="grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));">
                        <div class="metric-item">
                            <span class="label">User Case Type</span>
                            <span class="value" id="audit-val-user-case" style="color: #60a5fa; font-weight: 600;">—</span>
                        </div>
                        <div class="metric-item">
                            <span class="label">LLM Case Type</span>
                            <span class="value" id="audit-val-llm-case" style="color: #c084fc; font-weight: 600;">—</span>
                        </div>
                        <div class="metric-item">
                            <span class="label">OCR Evidence</span>
                            <span class="value" id="audit-val-ocr-evidence" style="color: #34d399; font-weight: 600;">—</span>
                        </div>
                        <div class="metric-item">
                            <span class="label">Avg Confidence</span>
                            <span class="value" id="audit-val-confidence" style="color: #f59e0b; font-weight: 600;">—</span>
                        </div>
                        <div class="metric-item">
                            <span class="label">Overwrite Blocked</span>
                            <span class="value" id="audit-val-overwrite-blocked" style="font-weight: 700;">—</span>
                        </div>
                    </div>
                    <div style="background: rgba(10, 15, 30, 0.6); border: 1px solid var(--border-glass); border-radius: var(--radius-sm); padding: 12px; font-family: monospace; font-size: 0.8rem; max-height: 150px; overflow-y: auto; line-height: 1.4; color: #94a3b8;" id="audit-log-terminal">
                        <span style="color: #64748b;">[SYSTEM] Ready. Awaiting document upload or LLM extraction...</span>
                    </div>
                </div>
            `;
            const rawCard = document.getElementById("ocr-raw-text-card");
            if (rawCard) {
                ocrQualityTab.insertBefore(auditCard, rawCard);
            } else {
                ocrQualityTab.appendChild(auditCard);
            }
        }
    }

    // --- LLM CASE TYPE SUGGESTION ENGINE (Issue 2) ---
    async function checkCaseType(selectedType, rawText) {
        const container = document.getElementById("case-type-suggestion");
        if (!container) return;

        if (!rawText || !rawText.trim()) {
            container.innerHTML = "";
            container.classList.add("hidden-section");
            return;
        }

        container.classList.remove("hidden-section");
        container.innerHTML = `<div class="suggestion-loading">Analyzing case type...</div>`;

        try {
            const response = await fetch("/api/ocr/suggest-case-type", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    raw_text: rawText,
                    selected_case_type: selectedType
                })
            });

            if (!response.ok) {
                throw new Error("Failed to fetch case type suggestions");
            }

            const data = await response.json();
            const suggestions = data.suggestions || [];

            if (suggestions.length === 0) {
                container.innerHTML = "";
                container.classList.add("hidden-section");
                return;
            }

            // First item is the top prediction (since it is sorted descending by the backend)
            const topPrediction = suggestions[0];
            const topCategory = topPrediction.case_type;
            const topConfidence = topPrediction.confidence;

            const topIsDeath = (topCategory === "Death");
            const selectedIsDeath = (selectedType === "death");
            const isMismatch = (topConfidence > 0.50) && (topIsDeath !== selectedIsDeath);

            let warningHtml = "";
            if (isMismatch) {
                warningHtml = `
                    <div class="case-warning">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <span>⚠️ Document suggests ${topCategory} — please verify</span>
                    </div>
                `;
            }

            let barsHtml = '<div class="case-type-bars">';
            suggestions.forEach(item => {
                const isDeathItem = (item.case_type === "Death");
                const isSelectedCategory = (isDeathItem && selectedIsDeath) || (!isDeathItem && !selectedIsDeath);
                const confidencePct = Math.round(item.confidence * 100);
                const selectedClass = isSelectedCategory ? "selected" : "";

                barsHtml += `
                    <div class="case-bar-row ${selectedClass}">
                        <span class="case-label" title="${item.case_type}">${item.case_type}</span>
                        <div class="bar-track">
                            <div class="bar-fill" style="width: ${confidencePct}%"></div>
                        </div>
                        <span class="case-pct">${confidencePct}%</span>
                    </div>
                `;
            });
            barsHtml += '</div>';

            container.innerHTML = warningHtml + barsHtml;

        } catch (error) {
            console.error("Error checking case type:", error);
            container.innerHTML = "";
            container.classList.add("hidden-section");
        }
    }

    // --- DOM REFERENCES ---
    const navItems = document.querySelectorAll(".nav-item");
    const viewports = document.querySelectorAll(".tab-viewport");
    const tabTitleText = document.getElementById("tab-title-text");
    const dbStatusText = document.getElementById("db-status-text");
    const statusDot = document.querySelector(".status-dot");
    const serverStatus = document.getElementById("server-status");
    const pulseIndicator = document.querySelector(".pulse-indicator");

    // TAB 1: CALCULATOR WORKSPACE
    const caseTypeSelect = document.getElementById("case-type");
    const sharedFields = document.getElementById("shared-fields");
    const deathFields = document.getElementById("death-fields");
    const injuryFields = document.getElementById("injury-fields");
    const formActionsBar = document.getElementById("form-actions-bar");
    const compensationForm = document.getElementById("compensation-form");

    // Single Case PDF Upload & Preview
    const singleUploadSection = document.getElementById("single-upload-section");
    const singleDropZone = document.getElementById("single-drop-zone");
    const singleFileInput = document.getElementById("single-file-input");
    const singlePreviewCard = document.getElementById("single-preview-card");
    const singlePreviewContainer = document.getElementById("single-preview-container");
    const singlePreviewFilename = document.getElementById("single-preview-filename");
    const aiExtractBtn = document.getElementById("ai-extract-btn");

    // Age & Dates
    const dobInput = document.getElementById("date-of-birth");
    const doaInput = document.getElementById("date-of-accident");
    const ageInput = document.getElementById("age");

    // Live previews
    const liveMetricsCard = document.getElementById("live-metrics-card");
    const liveAge = document.getElementById("live-age");
    const liveMultiplier = document.getElementById("live-multiplier");
    const liveProspects = document.getElementById("live-prospects");
    const liveProspectsBar = document.getElementById("live-prospects-bar");
    const liveProspectsItem = document.getElementById("live-prospects-item");
    const liveDeductions = document.getElementById("live-deductions");
    const liveDeductionsBar = document.getElementById("live-deductions-bar");
    const liveDeductionsItem = document.getElementById("live-deductions-item");

    // Extra elements
    const dependentsInput = document.getElementById("dependents");
    const maritalStatusSelect = document.getElementById("marital-status");
    const futureTypeSelect = document.getElementById("future-type");
    const monthlyIncomeInput = document.getElementById("monthly-income");

    // Precedents benchmarking
    const evaluatorCard = document.getElementById("evaluator-card");
    const triggerEvalBtn = document.getElementById("trigger-eval-btn");
    const evaluatorCardBody = document.getElementById("evaluator-card-body");

    // TAB 2: PDF LIBRARY
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const batchFileList = document.getElementById("batch-file-list");
    const queueBadge = document.getElementById("queue-badge");
    const queueCountLabel = document.getElementById("queue-count-label");
    const previewContainer = document.getElementById("preview-container");
    const previewFilenameBadge = document.getElementById("preview-filename-badge");

    // TAB 3: AI LEGAL CHAT
    const chatInput = document.getElementById("chat-input");
    const chatSendBtn = document.getElementById("chat-send-btn");
    const chatMessages = document.getElementById("chat-messages");
    const chatCaseFilter = document.getElementById("chat-case-filter");

    // MODAL DASHBOARD
    const resultsModal = document.getElementById("results-modal");
    const modalBodyContent = document.getElementById("modal-body-content");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const dismissModalBtn = document.getElementById("dismiss-modal-btn");
    const printBtn = document.getElementById("print-btn");

    // Glassmorphic Premium Toast Notification System
    function showToast(message, type = "info") {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                display: flex;
                flex-direction: column;
                gap: 12px;
                z-index: 9999;
                max-width: 360px;
                pointer-events: none;
            `;
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        let icon = "fa-info-circle";
        let color = "var(--color-primary, #3b82f6)";
        if (type === "success") {
            icon = "fa-circle-check";
            color = "#10b981";
        } else if (type === "error") {
            icon = "fa-triangle-exclamation";
            color = "#ef4444";
        } else if (type === "warning") {
            icon = "fa-circle-exclamation";
            color = "#f59e0b";
        }

        toast.style.cssText = `
            background: rgba(30, 41, 59, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-left: 4px solid ${color};
            color: #f1f5f9;
            padding: 14px 18px;
            border-radius: 8px;
            font-family: 'Inter', sans-serif;
            font-size: 0.875rem;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            gap: 12px;
            transform: translateY(20px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: auto;
        `;

        toast.innerHTML = `
            <i class="fa-solid ${icon}" style="color: ${color}; font-size: 1.125rem;"></i>
            <span style="flex-grow: 1; line-height: 1.4;">${message}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.transform = "translateY(0)";
            toast.style.opacity = "1";
        }, 50);

        setTimeout(() => {
            toast.style.transform = "translateY(-20px)";
            toast.style.opacity = "0";
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 4000);
    }

    // ==========================================================================
    // SIDEBAR TAB CONTROLLERS
    // ==========================================================================
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const target = item.getAttribute("data-tab");
            switchTab(target);
        });
    });

    function switchTab(tabName) {
        activeTab = tabName;

        // Active indicator on navigation
        navItems.forEach(item => {
            if (item.getAttribute("data-tab") === tabName) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // Toggle viewport display
        viewports.forEach(vp => {
            if (vp.id === `tab-${tabName}`) {
                vp.classList.add("active-viewport");
            } else {
                vp.classList.remove("active-viewport");
            }
        });

        // Update Title text
        const titleMap = {
            calculator: "Motor Claims Compensation Workstation",
            library: "Centralized PDF Library & Qdrant Queue",
            chat: "AI Precedent Assistant & Semantic Search",
            qdrant: "Qdrant Vector Database Explorer Dashboard"
        };
        tabTitleText.textContent = titleMap[tabName] || "Compensation Calculator Workstation";

        // Trigger dashboard reload when viewing Qdrant DB Explorer
        if (tabName === "qdrant") {
            loadQdrantDashboard();
        }
    }

    // ==========================================================================
    // EMBEDDED QDRANT OFFICIAL UI DASHBOARD EXPLORER
    // ==========================================================================
    const qdrantPointsTableBody = document.getElementById("qdrant-points-table-body");
    const qdrantCollectionName = document.getElementById("qdrant-collection-name");
    const qdrantPointsCount = document.getElementById("qdrant-points-count");
    const qdrantDistance = document.getElementById("qdrant-distance");
    const qdrantVectorSize = document.getElementById("qdrant-vector-size");
    const refreshQdrantBtn = document.getElementById("refresh-qdrant-btn");

    const payloadModal = document.getElementById("qdrant-payload-modal");
    const closePayloadModalBtn = document.getElementById("close-payload-modal-btn");
    const dismissPayloadModalBtn = document.getElementById("dismiss-payload-modal-btn");
    const payloadCodeblock = document.getElementById("qdrant-payload-codeblock");

    if (refreshQdrantBtn) {
        refreshQdrantBtn.addEventListener("click", loadQdrantDashboard);
    }

    async function loadQdrantDashboard() {
        if (!qdrantPointsTableBody) return;

        qdrantPointsTableBody.innerHTML = `
            <tr>
                <td colspan="5" style="padding: 24px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-spinner fa-spin fa-2x" style="color: var(--color-primary); margin-bottom: 8px;"></i>
                    Scrolling points and loading vectors from local Qdrant collection...
                </td>
            </tr>
        `;

        try {
            const response = await fetch("/api/qdrant/points");
            if (!response.ok) throw new Error("Failed to load Qdrant points");
            const data = await response.json();

            // Populate cards
            if (qdrantCollectionName) qdrantCollectionName.textContent = data.collection_name || "legal_documents";
            if (qdrantPointsCount) qdrantPointsCount.textContent = data.points_count !== undefined ? data.points_count : 0;
            if (qdrantDistance) qdrantDistance.textContent = data.distance || "Cosine";
            if (qdrantVectorSize) qdrantVectorSize.textContent = data.vector_size ? `${data.vector_size} dims` : "384 dims";

            if (!data.points || data.points.length === 0) {
                qdrantPointsTableBody.innerHTML = `
                    <tr>
                        <td colspan="5" style="padding: 24px; text-align: center; color: var(--text-muted);">
                            <i class="fa-solid fa-box-open" style="font-size: 1.8rem; display: block; margin-bottom: 8px;"></i>
                            No vectors currently indexed in the Qdrant database collection.<br>
                            <span style="font-size: 0.75rem; color: var(--text-muted); opacity: 0.7;">Drop a legal case PDF in the workstation to auto-OCR & populate vectors!</span>
                        </td>
                    </tr>
                `;
                return;
            }

            qdrantPointsTableBody.innerHTML = "";
            data.points.forEach(point => {
                const tr = document.createElement("tr");
                tr.style.cssText = "border-bottom: 1px solid var(--border-glass); transition: background 0.2s ease;";

                // Highlight row on hover
                tr.addEventListener("mouseenter", () => tr.style.background = "rgba(255, 255, 255, 0.01)");
                tr.addEventListener("mouseleave", () => tr.style.background = "transparent");

                const payload = point.payload || {};
                const filename = payload.filename || "unknown";
                const chunkId = payload.chunk_id !== undefined ? payload.chunk_id : 0;
                let text = payload.text || "";
                if (text.length > 75) {
                    text = text.slice(0, 72) + "...";
                }

                tr.innerHTML = `
                    <td style="padding: 12px 16px; font-family: monospace; color: var(--color-primary); font-size: 0.8rem;">${point.id}</td>
                    <td style="padding: 12px 16px; font-weight: 500;">${filename}</td>
                    <td style="padding: 12px 16px; text-align: center;"><span class="badge tech-badge" style="padding: 2px 6px;"># ${chunkId}</span></td>
                    <td style="padding: 12px 16px; color: var(--text-secondary); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">"${text}"</td>
                    <td style="padding: 12px 16px; text-align: right;">
                        <button type="button" class="btn btn-secondary btn-small view-payload-btn" data-point-id="${point.id}">
                            <i class="fa-solid fa-code"></i> Payload
                        </button>
                    </td>
                `;

                // Bind payload detail viewer
                tr.querySelector(".view-payload-btn").addEventListener("click", () => {
                    if (payloadCodeblock && payloadModal) {
                        payloadCodeblock.textContent = JSON.stringify(payload, null, 4);
                        payloadModal.classList.add("open");
                    }
                });

                qdrantPointsTableBody.appendChild(tr);
            });

        } catch (error) {
            console.error("Qdrant Explorer error:", error);
            qdrantPointsTableBody.innerHTML = `
                <tr>
                    <td colspan="5" style="padding: 24px; text-align: center; color: var(--color-danger);">
                        <i class="fa-solid fa-triangle-exclamation" style="font-size: 1.8rem; display: block; margin-bottom: 8px;"></i>
                        Failed to read points from Qdrant: ${error.message}
                    </td>
                </tr>
            `;
        }
    }

    // Modal controls for payload explorer
    if (closePayloadModalBtn) {
        closePayloadModalBtn.addEventListener("click", () => payloadModal.classList.remove("open"));
    }
    if (dismissPayloadModalBtn) {
        dismissPayloadModalBtn.addEventListener("click", () => payloadModal.classList.remove("open"));
    }
    window.addEventListener("click", (e) => {
        if (e.target === payloadModal) {
            payloadModal.classList.remove("open");
        }
    });

    // ==========================================================================
    // BACKEND HEALTH & QDRANT CONNECTOR
    // ==========================================================================
    async function checkBackendHealth() {
        try {
            const response = await fetch("/api/health");
            if (response.ok) {
                const data = await response.json();
                serverStatus.textContent = "Server Online";
                pulseIndicator.className = "pulse-indicator active";

                if (data.vector_db === "online") {
                    dbStatusText.textContent = "Qdrant Vector DB: Online";
                    statusDot.className = "status-dot online";
                } else {
                    dbStatusText.textContent = "Qdrant: Fallback Simulation";
                    statusDot.className = "status-dot";
                }
            } else {
                throw new Error("HTTP health check error");
            }
        } catch (error) {
            console.error("Health probe failed:", error);
            serverStatus.textContent = "Offline Sandbox Mode";
            pulseIndicator.className = "pulse-indicator active error";
            dbStatusText.textContent = "Qdrant: Sandbox Mode";
            statusDot.className = "status-dot";
        }
    }

    checkBackendHealth();

    // ==========================================================================
    // FORM TOGGLER & LIVE MATH ENGINE
    // ==========================================================================
    caseTypeSelect.addEventListener("change", (e) => {
        const caseType = e.target.value;

        const existingBadge = document.querySelector(`.suggested-badge[data-field="case_type"]`);
        if (existingBadge) {
            existingBadge.remove();
        }

        sharedFields.classList.remove("show");
        sharedFields.classList.add("hidden-section");

        deathFields.classList.remove("show");
        deathFields.classList.add("hidden-section");

        injuryFields.classList.remove("show");
        injuryFields.classList.add("hidden-section");

        formActionsBar.classList.remove("show-flex");
        formActionsBar.classList.add("hidden-section");

        if (liveMetricsCard) {
            liveMetricsCard.classList.remove("show");
            liveMetricsCard.classList.add("hidden-section");
        }
        if (evaluatorCard) {
            evaluatorCard.classList.remove("show");
            evaluatorCard.classList.add("hidden-section");
        }

        singleUploadSection.classList.remove("show");
        singleUploadSection.classList.remove("show-flex");
        singleUploadSection.classList.add("hidden-section");

        sharedFields.classList.remove("hidden-section");
        sharedFields.classList.add("show");

        singleUploadSection.classList.remove("hidden-section");
        singleUploadSection.classList.add("show-flex");

        if (caseType === "injury") {
            injuryFields.classList.remove("hidden-section");
            injuryFields.classList.add("show");

            if (liveDeductionsItem) liveDeductionsItem.classList.add("hidden");
            if (liveProspectsItem) liveProspectsItem.classList.add("hidden");

            const labelDeps = document.getElementById("label-dependents");
            if (labelDeps) {
                labelDeps.innerHTML = "Number of Dependents";
            }
            if (dependentsInput) dependentsInput.removeAttribute("required");

            const futureProspectInput = document.getElementById("future-prospect");
            if (futureProspectInput) futureProspectInput.removeAttribute("required");
        } else if (caseType === "death") {
            deathFields.classList.remove("hidden-section");
            deathFields.classList.add("show");

            if (liveDeductionsItem) liveDeductionsItem.classList.remove("hidden");
            if (liveProspectsItem) liveProspectsItem.classList.remove("hidden");

            const labelDeps = document.getElementById("label-dependents");
            if (labelDeps) {
                labelDeps.innerHTML = "Number of Dependents <span class=\"req\">*</span>";
            }
            if (dependentsInput) dependentsInput.setAttribute("required", "required");

            const futureProspectInput = document.getElementById("future-prospect");
            if (futureProspectInput) futureProspectInput.setAttribute("required", "required");
        }

        formActionsBar.classList.remove("hidden-section");
        formActionsBar.classList.add("show-flex");

        if (liveMetricsCard) {
            liveMetricsCard.classList.remove("hidden-section");
            liveMetricsCard.classList.add("show");
        }
        if (evaluatorCard) {
            evaluatorCard.classList.remove("hidden-section");
            evaluatorCard.classList.add("show");
        }
        // Populate fields from local cache if we already ran extraction!
        populateFieldsForActiveCaseType();

        updateLiveCalculations();

        if (window.lastRawText) {
            checkCaseType(caseType, window.lastRawText);
        } else {
            const container = document.getElementById("case-type-suggestion");
            if (container) {
                container.innerHTML = "";
                container.classList.add("hidden-section");
            }
        }
    });

    // Trigger change event dynamically to handle browser auto-restored values on page refresh
    if (caseTypeSelect && caseTypeSelect.value) {
        caseTypeSelect.dispatchEvent(new Event("change"));
    }

    // DOB & Date of Accident -> Calculated Age
    function calculateAge(dobStr, doaStr) {
        if (!dobStr || !doaStr) return null;
        const dob = new Date(dobStr);
        const doa = new Date(doaStr);
        if (isNaN(dob.getTime()) || isNaN(doa.getTime())) return null;

        let age = doa.getFullYear() - dob.getFullYear();
        const monthDiff = doa.getMonth() - dob.getMonth();
        if (monthDiff < 0 || (monthDiff === 0 && doa.getDate() < dob.getDate())) {
            age--;
        }
        return age >= 0 ? age : 0;
    }

    function getMultiplier(age) {
        if (age === null || age === undefined || age === "") return 0;
        const a = parseInt(age);
        if (a <= 15) return 15;
        if (a <= 20) return 18;
        if (a <= 25) return 18;
        if (a <= 30) return 17;
        if (a <= 35) return 16;
        if (a <= 40) return 15;
        if (a <= 45) return 14;
        if (a <= 50) return 13;
        if (a <= 55) return 11;
        if (a <= 60) return 9;
        if (a <= 65) return 7;
        return 5;
    }

    function getFutureProspectPercentage(age, futureType) {
        if (age === null || age === undefined || age === "") return 0;
        const a = parseInt(age);
        const fType = parseInt(futureType);
        if (a > 60) return 0;
        if (fType === 1) {
            if (a < 40) return 50;
            if (a <= 50) return 30;
            if (a <= 60) return 15;
            return 0;
        } else {
            if (a < 40) return 40;
            if (a <= 50) return 25;
            if (a <= 60) return 10;
            return 0;
        }
    }

    function getDeductionRatio(dependents, status) {
        if (dependents === null || dependents === undefined || dependents === "") return 0.50;
        const deps = parseInt(dependents);
        const stat = String(status || "married").trim().toLowerCase();
        if (stat === "single") return 0.50;
        if (deps <= 1) return 0.50;
        if (deps <= 3) return 1 / 3;
        if (deps <= 6) return 0.25;
        return 0.20;
    }

    function updateLiveCalculations() {
        const age = parseInt(ageInput.value);
        const caseType = caseTypeSelect.value;

        if (!isNaN(age) && age >= 0) {
            if (liveAge) liveAge.textContent = `${age} years`;

            const mult = getMultiplier(age);
            if (liveMultiplier) liveMultiplier.textContent = mult;

            if (caseType === "death") {
                const futureType = futureTypeSelect ? futureTypeSelect.value : 2;
                const futureProspectInput = document.getElementById("future-prospect");
                let prospects;
                if (futureProspectInput && futureProspectInput.value !== "" && !isNaN(parseFloat(futureProspectInput.value))) {
                    prospects = parseFloat(futureProspectInput.value);
                } else {
                    prospects = getFutureProspectPercentage(age, futureType);
                    if (futureProspectInput) futureProspectInput.value = prospects;
                }
                if (liveProspects) liveProspects.textContent = `${prospects}%`;
                if (liveProspectsBar) liveProspectsBar.style.width = `${prospects}%`;

                // Populate only helper parameters
                const deathMultInput = document.getElementById("death-multiplier");
                if (deathMultInput) deathMultInput.value = mult;

                const deps = parseInt(dependentsInput.value) || 0;
                const status = maritalStatusSelect.value || "married";
                const deductionRatio = getDeductionRatio(deps, status);
                const deductionsPercent = Math.round(deductionRatio * 100);
                if (liveDeductions) liveDeductions.textContent = `${deductionsPercent}%`;
                if (liveDeductionsBar) liveDeductionsBar.style.width = `${deductionsPercent}%`;

                const deathDeductInput = document.getElementById("death-deduction");
                if (deathDeductInput) deathDeductInput.value = deductionsPercent;

                // Populate dynamic dashboard helper elements only (no monetary figures)
                if (document.getElementById("live-calc-multiplier")) {
                    document.getElementById("live-calc-multiplier").textContent = mult;
                }
                if (document.getElementById("live-calc-deduct-pct")) {
                    document.getElementById("live-calc-deduct-pct").textContent = `${deductionsPercent}%`;
                }

            } else {
                if (liveProspects) liveProspects.textContent = "—%";
                if (liveProspectsBar) liveProspectsBar.style.width = "0%";
                if (liveDeductions) liveDeductions.textContent = "—%";
                if (liveDeductionsBar) liveDeductionsBar.style.width = "0%";
            }
        } else {
            // Truly nothing — blank everything
            if (liveAge) liveAge.textContent = "—";
            if (liveMultiplier) liveMultiplier.textContent = "—";
            if (liveProspects) liveProspects.textContent = "—%";
            if (liveProspectsBar) liveProspectsBar.style.width = "0%";
            if (liveDeductions) liveDeductions.textContent = "—%";
            if (liveDeductionsBar) liveDeductionsBar.style.width = "0%";
            if (caseType === "death") {
                if (document.getElementById("live-calc-multiplier")) document.getElementById("live-calc-multiplier").textContent = "—";
                if (document.getElementById("live-calc-deduct-pct")) document.getElementById("live-calc-deduct-pct").textContent = "—";
            }
        }
    }

    const handleRecalculateDefaultProspects = () => {
        const age = parseInt(ageInput.value);
        if (!isNaN(age) && age >= 0) {
            const futureType = futureTypeSelect ? futureTypeSelect.value : 2;
            const prospects = getFutureProspectPercentage(age, futureType);
            const futureProspectInput = document.getElementById("future-prospect");
            if (futureProspectInput) futureProspectInput.value = prospects;
        }
        updateLiveCalculations();
    };

    if (futureTypeSelect) {
        futureTypeSelect.addEventListener("change", handleRecalculateDefaultProspects);
    }

    dobInput.addEventListener("change", updateLiveCalculations);
    doaInput.addEventListener("change", updateLiveCalculations);
    maritalStatusSelect.addEventListener("change", updateLiveCalculations);
    dependentsInput.addEventListener("input", updateLiveCalculations);
    monthlyIncomeInput.addEventListener("input", updateLiveCalculations);
    ageInput.addEventListener("input", handleRecalculateDefaultProspects);

    // Set dynamic update bindings for new Death Claim inputs and prospects field manual override
    setTimeout(() => {
        const consInput = document.getElementById("consortium");
        const funInput = document.getElementById("funeral-expenses");
        const estInput = document.getElementById("loss-estate");
        const futureProspectInput = document.getElementById("future-prospect");

        if (consInput) consInput.addEventListener("input", updateLiveCalculations);
        if (funInput) funInput.addEventListener("input", updateLiveCalculations);
        if (estInput) estInput.addEventListener("input", updateLiveCalculations);
        if (futureProspectInput) futureProspectInput.addEventListener("input", updateLiveCalculations);
    }, 50);

    // ==========================================================================
    // SINGLE PDF WORKSPACE DRAG & DROP + UPLOAD
    // ==========================================================================
    ["dragenter", "dragover"].forEach(eventName => {
        singleDropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            singleDropZone.classList.add("dragover");
        }, false);
    });

    singleDropZone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        e.stopPropagation();
        singleDropZone.classList.remove("dragover");
    }, false);

    singleDropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        e.stopPropagation();
        singleDropZone.classList.remove("dragover");

        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleSinglePdfUpload(files[0]);
        }
    });

    singleDropZone.addEventListener("click", (e) => {
        if (e.target === singleFileInput) return;
        singleFileInput.click();
    });

    singleFileInput.addEventListener("click", (e) => {
        e.stopPropagation();
    });

    singleFileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleSinglePdfUpload(e.target.files[0]);
        }
    });

    async function handleSinglePdfUpload(file) {
        const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
        if (!isPdf) {
            alert("Please upload a valid legal PDF case document.");
            return;
        }

        // Start the Live OCR timer
        startOcrTimer();

        // Show a premium glassmorphic loading spinner inside the form panel
        const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
        const loader = document.createElement("div");
        loader.className = "form-ocr-loader";
        loader.innerHTML = `
            <div class="spinner-glow"></div>
            <p id="ocr-loader-message">Analyzing document with legal OCR...</p>
            <span id="ocr-loader-phase" style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Extracting Judgment, Petition, &amp; Prayer sections</span>
            <div style="margin-top: 12px; font-family: monospace; font-size: 1.15rem; font-weight: 700; color: var(--color-primary); display: flex; align-items: center; gap: 8px; justify-content: center;">
                <span>⏱</span>
                <span id="ocr-loader-timer">00:00</span>
            </div>
            <div id="ocr-page-monitor" style="display:none; margin-top:16px; width:100%; max-width:520px; text-align:left;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:0.75rem; font-weight:600; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.05em;">Page Processing</span>
                    <span id="ocr-page-counter" style="font-size:0.75rem; font-family:monospace; color:var(--color-primary);">0 / ?</span>
                </div>
                <div style="width:100%; background:rgba(255,255,255,0.08); border-radius:4px; height:5px; margin-bottom:10px; overflow:hidden;">
                    <div id="ocr-page-bar" style="height:100%; width:0%; background:var(--color-primary); border-radius:4px; transition:width 0.3s ease;"></div>
                </div>
                <div id="ocr-page-grid" style="display:grid; grid-template-columns:repeat(auto-fill,minmax(62px,1fr)); gap:5px; max-height:160px; overflow-y:auto;"></div>
                <div id="ocr-recent-log" style="margin-top:10px; font-size:0.7rem; font-family:monospace; color:var(--text-secondary); line-height:1.6; max-height:60px; overflow:hidden;"></div>
            </div>
        `;
        formPanel.style.position = "relative";
        formPanel.appendChild(loader);

        // Per-page monitor state
        const _ocrPages = {};
        let _ocrTotalPages = 0;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/ocr/process-ocr", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                throw new Error("OCR Processing failed");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let partialBuffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                partialBuffer += decoder.decode(value, { stream: true });
                const lines = partialBuffer.split("\n");

                // Keep the last item in the buffer as it might be incomplete
                partialBuffer = lines.pop();

                for (const line of lines) {
                    const cleanLine = line.trim();
                    if (!cleanLine.startsWith("data: ")) continue;

                    const payload = cleanLine.slice(6);
                    const data = JSON.parse(payload);

                    // Update loader visual progress message and submessage
                    if (loader) {
                        const messageEl = loader.querySelector("#ocr-loader-message");
                        const phaseEl = loader.querySelector("#ocr-loader-phase");

                        if (data.status === "page_progress" && data.page_info) {
                            const pg = data.page_info;
                            _ocrTotalPages = pg.total_pages;

                            // Show the page monitor panel on first page event
                            const monitor = loader.querySelector("#ocr-page-monitor");
                            if (monitor) monitor.style.display = "block";

                            // Update progress bar and counter
                            const bar = loader.querySelector("#ocr-page-bar");
                            const counter = loader.querySelector("#ocr-page-counter");
                            if (bar) bar.style.width = Math.round((pg.pages_done / pg.total_pages) * 100) + "%";
                            if (counter) counter.textContent = `${pg.pages_done} / ${pg.total_pages}`;

                            // Engine colour coding
                            const engineColor = pg.engine === "PaddleOCR" || pg.engine === "PaddleOCR-Retry"
                                ? "#34d399" : pg.engine === "PyMuPDF"
                                    ? "#60a5fa" : pg.engine === "Tesseract"
                                        ? "#fbbf24" : pg.engine === "Skipped-blank"
                                            ? "#6b7280" : "#a78bfa";

                            // Add or update page chip in the grid
                            const grid = loader.querySelector("#ocr-page-grid");
                            if (grid) {
                                const chipId = "ocr-chip-p" + pg.page;
                                let chip = loader.querySelector("#" + chipId);
                                if (!chip) {
                                    chip = document.createElement("div");
                                    chip.id = chipId;
                                    chip.style.cssText = `border-radius:4px; padding:3px 4px; font-size:0.62rem; font-family:monospace; text-align:center; border:1px solid rgba(255,255,255,0.12); line-height:1.4;`;
                                    grid.appendChild(chip);
                                }
                                const confPct = Math.round((pg.confidence || 0) * 100);
                                chip.style.background = engineColor + "22";
                                chip.style.borderColor = engineColor + "55";
                                chip.style.color = engineColor;
                                chip.title = `Page ${pg.page} | ${pg.engine} | conf:${confPct}% | lines:${pg.lines} | ${pg.total_page_time}s`;
                                chip.innerHTML = `<span style="font-weight:700;">P${pg.page}</span><br>${pg.engine ? pg.engine.replace("PaddleOCR", "Paddle").replace("Tesseract", "Tess").replace("PyMuPDF", "Fitz").replace("Skipped-blank", "Skip").replace("-Retry", "↺") : "?"}<br>${confPct}%`;
                                // Scroll newest chip into view
                                chip.scrollIntoView({ block: "nearest" });
                            }

                            // Append to recent log (keep last 3 lines)
                            const logEl = loader.querySelector("#ocr-recent-log");
                            if (logEl) {
                                const logLine = document.createElement("div");
                                const engShort = (pg.engine || "?").replace("PaddleOCR-Retry", "Paddle↺");
                                logLine.textContent = `[P${String(pg.page).padStart(2, "0")}] ${engShort.padEnd(10)} conf:${String(Math.round((pg.confidence || 0) * 100)).padStart(3)}%  lines:${String(pg.lines).padStart(3)}  ${pg.total_page_time}s`;
                                logEl.prepend(logLine);
                                while (logEl.children.length > 4) logEl.removeChild(logEl.lastChild);
                            }

                            if (messageEl) messageEl.textContent = `OCR: page ${pg.pages_done} of ${pg.total_pages} (${pg.engine || "??"})`;
                            if (phaseEl) phaseEl.textContent = `${pg.total_pages - pg.pages_done} page(s) remaining`;

                        } else {
                            if (messageEl && data.message) messageEl.textContent = data.message;
                            if (phaseEl && data.status) phaseEl.textContent = `Phase: ${data.status} (${data.progress}%)`;
                        }
                    }

                    // Update local form panel timer status text
                    const statusText = document.getElementById("ocr-timer-status-text");
                    if (statusText && data.message) {
                        statusText.textContent = data.message;
                    }

                    if (data.status === "done") {
                        // Remove spinner after processing is fully complete
                        loader.remove();

                        if (data.success) {
                            // Stop timer on success
                            stopOcrTimerSuccess();

                            // TEMPORARY: Log OCR suggestions structure
                            console.log("OCR suggestions structure:", JSON.stringify(data.suggestions, null, 2));

                            // Apply OCR suggestions automatically
                            applyAllOcrSuggestions(data.suggestions);

                            // Update OCR Inspector with authentic telemetry data
                            updateOcrInspector(data);

                            // Store raw text for AI data recovery
                            currentOcrRawText = data.raw_text || [];
                            window.lastRawText = currentOcrRawText.join("\n");
                            checkCaseType(caseTypeSelect.value, window.lastRawText);
                            if (aiExtractBtn) {
                                if (currentOcrRawText.length > 0) {
                                    aiExtractBtn.style.display = "inline-flex";
                                } else {
                                    aiExtractBtn.style.display = "none";
                                }
                            }

                            // Load high-fidelity PDF preview in the right pane!
                            const blobUrl = URL.createObjectURL(file);
                            singlePreviewFilename.innerHTML = `${file.name} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: ${data.fallback_source}</span>`;
                            singlePreviewContainer.innerHTML = `
                                <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
                            `;
                            singlePreviewCard.classList.remove("hidden-section");
                            singlePreviewCard.classList.add("show");

                            // Programmatically switch active right pane tab to PDF Preview upon successful upload
                            const pdfTabBtn = document.querySelector('.pane-tab-btn[data-pane-tab="pdf"]');
                            if (pdfTabBtn) {
                                pdfTabBtn.click();
                            }

                            // Programmatically open the AI Assistant slide-over chatbot drawer upon successful upload
                            if (aiAssistantTrigger && slideover && !slideover.classList.contains("open")) {
                                aiAssistantTrigger.click();
                            }

                            // Highlight and show the live metrics and precedents cards
                            if (liveMetricsCard) liveMetricsCard.classList.add("show");
                            if (evaluatorCard) evaluatorCard.classList.add("show");

                            if (typeof triggerTabNotification === "function") {
                                triggerTabNotification("analysis");
                                triggerTabNotification("ocr-quality");
                            }

                            showToast("Case PDF analyzed! Form auto-filled focusing on Previous Judgment, Petition, and Prayer details. Please manually review fields.", "success");
                        } else {
                            stopOcrTimerFailure();
                            showToast("Failed to extract data from the PDF: " + (data.message || "Unknown OCR error."), "error");
                        }
                    } else if (data.status === "failed") {
                        loader.remove();
                        stopOcrTimerFailure();
                        showToast("Failed to extract data from the PDF: " + (data.message || "Unknown OCR error."), "error");
                    }
                }
            }
        } catch (error) {
            loader.remove();
            stopOcrTimerFailure();
            console.error("Single PDF OCR error:", error);
            showToast(`OCR processing failed: ${error.message}. Please verify the central FastAPI server is fully initialized.`, "error");
        }
    }

    // ==========================================================================
    // BATCH PDF MANAGER (DRAG & DROP + POLLING QUEUE)
    // ==========================================================================

    // Drag events
    ["dragenter", "dragover"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add("dragover");
        }, false);
    });

    dropZone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove("dragover");
    }, false);

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove("dragover");

        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleBatchUpload(files);
        }
    });

    dropZone.addEventListener("click", (e) => {
        if (e.target === fileInput) return;
        fileInput.click();
    });

    fileInput.addEventListener("click", (e) => {
        e.stopPropagation();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleBatchUpload(e.target.files);
        }
    });

    // Upload batch files
    async function handleBatchUpload(files) {
        // Start the Live OCR timer for batch processing
        startOcrTimer();
        const formData = new FormData();
        let validPdfCount = 0;

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
            if (isPdf) {
                formData.append("files", file);
                validPdfCount++;

                // Map local filename to the file object to facilitate local iframe previewing!
                uploadedFileObjects[file.name] = file;
            }
        }

        if (validPdfCount === 0) {
            alert("No valid PDF files selected. Please upload legal document PDFs.");
            return;
        }

        try {
            const response = await fetch("/api/ocr/upload-batch", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                throw new Error("Batch upload failed");
            }

            const data = await response.json();

            // Append files to our local tracker
            data.queue.forEach(item => {
                fileQueue.push({
                    file_id: item.file_id,
                    filename: item.filename,
                    status: "queued",
                    progress: 0,
                    suggestions: null,
                    raw_text: []
                });
            });

            renderQueueList();
            startQueuePolling();

        } catch (error) {
            console.error("Error uploading batch PDFs:", error);
            alert("Failed to upload batch files to the server.");
        }
    }

    // Render queue card lists
    function renderQueueList() {
        if (fileQueue.length === 0) {
            batchFileList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-box-open"></i>
                    <p>No legal PDFs uploaded yet. Drag and drop PDF claim judgments above to begin centralized vector storage.</p>
                </div>
            `;
            if (queueBadge) queueBadge.classList.add("hidden");
            queueCountLabel.textContent = "0 Files";
            return;
        }

        batchFileList.innerHTML = "";
        if (queueBadge) {
            queueBadge.classList.remove("hidden");
            queueBadge.textContent = fileQueue.length;
        }
        queueCountLabel.textContent = `${fileQueue.length} Files`;

        fileQueue.forEach(file => {
            const item = document.createElement("div");
            item.className = "batch-file-item";
            item.setAttribute("data-id", file.file_id);
            item.setAttribute("data-filename", file.filename);

            const displayTag = {
                queued: `<span class="bf-tag queued">Queued</span>`,
                scanning: `<span class="bf-tag scanning">Scanning</span>`,
                indexing: `<span class="bf-tag indexing">Indexing</span>`,
                indexed: `<span class="bf-tag indexed"><i class="fa-solid fa-circle-check"></i> Indexed</span>`,
                failed: `<span class="bf-tag failed">Failed</span>`
            }[file.status] || `<span class="bf-tag queued">${file.status}</span>`;

            item.innerHTML = `
                <div class="bf-meta">
                    <span class="bf-name" title="${file.filename}">${file.filename}</span>
                    ${displayTag}
                </div>
                <div class="bf-progress-row">
                    <div class="bf-bar-wrapper">
                        <div class="bf-bar-fill" style="width: ${file.progress}%"></div>
                    </div>
                    <span class="bf-pct">${file.progress}%</span>
                </div>
                ${file.status === "indexed" ? `
                    <div class="bf-actions">
                        <button type="button" class="btn btn-small btn-success autofill-queue-btn" data-id="${file.file_id}">
                            <i class="fa-solid fa-arrow-left"></i> Auto-fill form
                        </button>
                        <button type="button" class="btn btn-small btn-danger remove-indexed-btn" data-id="${file.file_id}" data-filename="${file.filename}" title="Remove from database and chat">
                            <i class="fa-solid fa-trash"></i> Remove
                        </button>
                    </div>
                ` : ""}
            `;

            // Bind click to previews
            item.addEventListener("click", (e) => {
                // Prevent trigger if they click action buttons
                if (e.target.closest(".autofill-queue-btn")) return;
                if (e.target.closest(".remove-indexed-btn")) return;

                document.querySelectorAll(".batch-file-item").forEach(c => c.classList.remove("active-preview"));
                item.classList.add("active-preview");
                loadPdfPreview(file.filename);
            });

            batchFileList.appendChild(item);
        });

        // Bind clicks on autofill buttons
        document.querySelectorAll(".autofill-queue-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                const id = btn.getAttribute("data-id");
                const matchedFile = fileQueue.find(f => f.file_id === id);
                if (matchedFile) {
                    showAutofillChoiceModal(matchedFile);
                }
            });
        });

        // Bind clicks on remove buttons
        document.querySelectorAll(".remove-indexed-btn").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                e.stopPropagation();
                const id = btn.getAttribute("data-id");
                const filename = btn.getAttribute("data-filename");
                if (!confirm(`Remove "${filename}" from the vector database and AI chat?

This cannot be undone.`)) return;

                // Visual feedback — disable button while deleting
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Removing...`;

                try {
                    const res = await fetch(`/api/qdrant/document/${encodeURIComponent(filename)}`, {
                        method: "DELETE"
                    });
                    const data = await res.json();

                    if (data.success) {
                        // Remove from local fileQueue
                        const idx = fileQueue.findIndex(f => f.file_id === id);
                        if (idx !== -1) fileQueue.splice(idx, 1);

                        showToast(`"${filename}" removed from database.`, "success");
                        renderQueueList();

                        // Re-sync the chat document filter dropdown
                        syncChatDocumentFilter();
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = `<i class="fa-solid fa-trash"></i> Remove`;
                        showToast(`Failed to remove: ${data.detail || "Unknown error"}`, "error");
                    }
                } catch (err) {
                    btn.disabled = false;
                    btn.innerHTML = `<i class="fa-solid fa-trash"></i> Remove`;
                    showToast(`Network error while removing file.`, "error");
                }
            });
        });

        // Sync chatbot document filter select options
        syncChatDocumentFilter();
    }

    // Open Autofill Selection Modal to choose between OCR and AI Deep Extraction
    function showAutofillChoiceModal(matchedFile) {
        const choiceModal = document.getElementById("autofill-choice-modal");
        if (!choiceModal) return;

        const quickBtn = document.getElementById("btn-quick-autofill");
        const aiBtn = document.getElementById("btn-ai-autofill");
        const cancelBtn = document.getElementById("dismiss-autofill-choice-btn");
        const closeBtn = document.getElementById("close-autofill-choice-btn");

        // Clone buttons to clear previous event listeners cleanly
        const newQuickBtn = quickBtn.cloneNode(true);
        const newAiBtn = aiBtn.cloneNode(true);
        quickBtn.parentNode.replaceChild(newQuickBtn, quickBtn);
        aiBtn.parentNode.replaceChild(newAiBtn, aiBtn);

        // Bind quick OCR path
        newQuickBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            choiceModal.classList.remove("open");
            if (matchedFile.suggestions) {
                stopOcrTimerSuccess();

                // Store raw text for AI data recovery if they want to click it manually later
                currentOcrRawText = matchedFile.raw_text || [];
                if (aiExtractBtn) {
                    if (currentOcrRawText.length > 0) {
                        aiExtractBtn.style.display = "inline-flex";
                    } else {
                        aiExtractBtn.style.display = "none";
                    }
                }

                // Update workstation preview card with the batch-loaded PDF if possible
                const fileObj = uploadedFileObjects[matchedFile.filename];
                if (fileObj && singlePreviewContainer && singlePreviewFilename) {
                    const blobUrl = URL.createObjectURL(fileObj);
                    singlePreviewFilename.innerHTML = `${matchedFile.filename} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: Batch Library</span>`;
                    singlePreviewContainer.innerHTML = `
                        <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
                    `;
                    if (singlePreviewCard) {
                        singlePreviewCard.classList.remove("hidden-section");
                        singlePreviewCard.classList.add("show");
                    }
                }

                applyAllOcrSuggestions(matchedFile.suggestions);

                if (matchedFile.ocr_debug) {
                    updateOcrInspector(matchedFile);
                    triggerTabNotification("ocr-quality");
                }

                window.lastRawText = (matchedFile.raw_text || []).join("\n");
                checkCaseType(caseTypeSelect.value, window.lastRawText);

                switchTab("calculator");
            } else {
                showToast("No pre-parsed heuristic data available for this file.", "warning");
            }
        });

        // Bind AI LLM Deep Extraction path
        newAiBtn.addEventListener("click", async (e) => {
            e.stopPropagation();

            // Validate that we have raw text before attempting LLM recovery
            const rawTextLines = matchedFile.raw_text || [];
            if (rawTextLines.length === 0) {
                showToast("No raw OCR text is available for this file to perform AI recovery.", "warning");
                choiceModal.classList.remove("open");
                return;
            }

            choiceModal.classList.remove("open");

            // Set currentOcrRawText from batch file
            currentOcrRawText = rawTextLines;
            window.lastRawText = currentOcrRawText.join("\n");
            checkCaseType(caseTypeSelect.value, window.lastRawText);

            if (aiExtractBtn) {
                aiExtractBtn.style.display = "inline-flex";
            }

            // Update workstation preview card with the batch-loaded PDF if possible
            const fileObj = uploadedFileObjects[matchedFile.filename];
            if (fileObj && singlePreviewContainer && singlePreviewFilename) {
                const blobUrl = URL.createObjectURL(fileObj);
                singlePreviewFilename.innerHTML = `${matchedFile.filename} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: Batch Library</span>`;
                singlePreviewContainer.innerHTML = `
                    <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
                `;
                if (singlePreviewCard) {
                    singlePreviewCard.classList.remove("hidden-section");
                    singlePreviewCard.classList.add("show");
                }
            }

            // Switch to workstation tab
            switchTab("calculator");

            // Show spinning loader overlay in workstation panel
            const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
            if (!formPanel) return;

            const loader = document.createElement("div");
            loader.className = "form-ocr-loader";
            loader.innerHTML = `
                <div class="spinner-glow"></div>
                <p>AI Legal LLM is parsing text...</p>
                <span style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Recovering missing legal compensation entities</span>
            `;
            formPanel.style.position = "relative";
            formPanel.appendChild(loader);

            try {
                // Call backend
                const response = await fetch("/api/ocr/ai-recover", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ raw_text: currentOcrRawText })
                });

                loader.remove();

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.detail || "AI recovery API returned error status");
                }
                const data = await response.json();

                if (data.success) {
                    const confidenceScores = data.raw_recovered ? data.raw_recovered.confidence_scores : null;
                    const ocrEvidence = data.raw_recovered ? data.raw_recovered.ocr_evidence_case : null;

                    // Apply suggestions exactly the same way as clicking "Ask LLM to Extract" manually
                    applyAllOcrSuggestions(data.suggestions, confidenceScores, ocrEvidence, data.raw_recovered);
                    showToast("AI data extraction complete! All recovered parameters cached internally.", "success");
                } else {
                    showToast("AI extraction failed to extract fields.", "error");
                }
            } catch (error) {
                if (loader) loader.remove();
                console.error("AI recovery failed:", error);
                showToast(`AI extraction failed: ${error.message}`, "error");
            }
        });

        // Close on cancel/close
        const closeHandler = (e) => {
            if (e) e.stopPropagation();
            choiceModal.classList.remove("open");
        };
        cancelBtn.onclick = closeHandler;
        closeBtn.onclick = closeHandler;

        // Open modal
        choiceModal.classList.add("open");
    }

    // Close choice modal when clicking outside content area
    window.addEventListener("click", (e) => {
        const choiceModal = document.getElementById("autofill-choice-modal");
        if (e.target === choiceModal) {
            choiceModal.classList.remove("open");
        }
    });

    // High-Fidelity local Blob URL previewing
    function loadPdfPreview(filename) {
        const fileObj = uploadedFileObjects[filename];
        if (!fileObj) {
            previewContainer.innerHTML = `
                <div class="preview-empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 3rem; color: var(--color-warning);"></i>
                    <p>PDF file context lost. Please select a freshly uploaded PDF or re-upload to preview.</p>
                </div>
            `;
            previewFilenameBadge.classList.add("hidden");
            return;
        }

        // Generate instant in-memory Blob URL for local PDF rendering
        const blobUrl = URL.createObjectURL(fileObj);

        previewFilenameBadge.classList.remove("hidden");
        previewFilenameBadge.textContent = filename;

        previewContainer.innerHTML = `
            <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
        `;
    }

    // Batch Status Polling Loop
    function startQueuePolling() {
        if (isPolling) return;
        isPolling = true;

        const pollInterval = setInterval(async () => {
            // Only poll if we have queued/active files
            const activeFiles = fileQueue.filter(f => f.status === "queued" || f.status === "scanning" || f.status === "indexing");
            if (activeFiles.length === 0) {
                stopOcrTimerSuccess();
                clearInterval(pollInterval);
                isPolling = false;
                return;
            }

            try {
                const response = await fetch("/api/ocr/batch-status");
                if (response.ok) {
                    const data = await response.json();

                    // Sync backend statuses with local queue
                    data.queue.forEach(srvItem => {
                        const localIndex = fileQueue.findIndex(f => f.file_id === srvItem.file_id);
                        if (localIndex !== -1) {
                            fileQueue[localIndex].status = srvItem.status;
                            fileQueue[localIndex].progress = srvItem.progress;
                            fileQueue[localIndex].suggestions = srvItem.suggestions;
                            fileQueue[localIndex].raw_text = srvItem.raw_text;
                            fileQueue[localIndex].ocr_debug = srvItem.ocr_debug;
                        }
                    });

                    renderQueueList();
                }
            } catch (error) {
                console.error("Queue status polling failed:", error);
            }
        }, 1500);
    }

    // Helper to populate fields based on active case type (Part 5 & Part 6)
    function populateFieldsForActiveCaseType() {
        const activeCaseType = caseTypeSelect.value;
        if (!activeCaseType) return;

        // Clear all previous low-confidence warning labels, styles, and AI metadata badges again to refresh
        document.querySelectorAll(".verification-warning").forEach(el => el.remove());
        document.querySelectorAll(".low-confidence-input").forEach(el => el.classList.remove("low-confidence-input"));
        document.querySelectorAll(".ai-metadata-badge:not([data-field='case_type'])").forEach(el => el.remove());

        // Field definitions and mapping to DOM input IDs
        // Always Populate (Part 6)
        const commonMapping = {
            "name": "name",
            "father_name": "father-name",
            "date_of_birth": "date-of-birth",
            "age": "age",
            "monthly_income": "monthly-income",
            "date_of_accident": "date-of-accident",
            "place_of_accident": "place-of-accident"
        };

        // Injury Specific (Part 6)
        const injuryMapping = {
            "medical_expenses": "medical-expenses",
            "future_medical_expenses": "future-medical-expenses",
            "pain_and_suffering": "pain-and-suffering",
            "transportation": "transportation",
            "special_diet": "special-diet",
            "attender_charges": "attender-charges",
            "loss_of_income": "loss-of-income",
            "disability": "disability"
        };

        // Death Specific (Part 6)
        const deathMapping = {
            "consortium": "consortium",
            "funeral_expenses": "funeral-expenses",
            "loss_estate": "loss-estate",
            "dependents": "dependents",
            "marital_status": "marital-status"
        };        // Helper to populate a single DOM element based on key, inputId, and active status
        function populateField(cacheKey, inputId, isAllowed) {
            const el = document.getElementById(inputId);
            if (!el) return;

            if (!isAllowed) {
                // If not allowed for this mode, do NOT populate.
                return;
            }

            const val = lastExtractedFields[cacheKey];

            if (val === undefined || val === null || val === "") {
                return;
            }

            // Direct Auto-fill (no confidence gate / suggestion badge for other fields)
            if (inputId === "date-of-birth" || inputId === "date-of-accident") {
                let htmlDate = val;
                if (val.includes("-")) {
                    const parts = val.split("-");
                    if (parts.length === 3 && parts[2].length === 4) {
                        htmlDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
                    }
                }
                el.value = htmlDate;
            } else {
                el.value = val;
            }
            el.dispatchEvent(new Event("input"));
            el.dispatchEvent(new Event("change"));
        }
        // Run population for all common fields
        Object.keys(commonMapping).forEach(cacheKey => {
            populateField(cacheKey, commonMapping[cacheKey], true);
        });

        // Run population for Injury specific fields
        const isInjury = (activeCaseType === "injury");
        Object.keys(injuryMapping).forEach(cacheKey => {
            populateField(cacheKey, injuryMapping[cacheKey], isInjury);
        });

        // Run population for Death specific fields
        const isDeath = (activeCaseType === "death");
        Object.keys(deathMapping).forEach(cacheKey => {
            populateField(cacheKey, deathMapping[cacheKey], isDeath);
        });

        updateLiveCalculations();
    }

    // Helper to update the visual Audit Log (Part 7)
    function updateAuditLog(userCase, llmCase, ocrEvidence, avgConfidence, overwriteBlocked) {
        const userCaseVal = document.getElementById("audit-val-user-case");
        const llmCaseVal = document.getElementById("audit-val-llm-case");
        const ocrEvidenceVal = document.getElementById("audit-val-ocr-evidence");
        const confidenceVal = document.getElementById("audit-val-confidence");
        const overwriteBlockedVal = document.getElementById("audit-val-overwrite-blocked");
        const terminal = document.getElementById("audit-log-terminal");

        const displayMap = {
            "injury": "Injury Case",
            "death": "Death Case",
            "None Selected": "None Selected",
            "Unspecified": "Unspecified"
        };

        if (userCaseVal) userCaseVal.textContent = displayMap[userCase] || userCase;
        if (llmCaseVal) llmCaseVal.textContent = displayMap[llmCase] || llmCase;
        if (ocrEvidenceVal) {
            ocrEvidenceVal.textContent = ocrEvidence;
            if (ocrEvidence === "INJURY") {
                ocrEvidenceVal.style.color = "#34d399";
            } else if (ocrEvidence === "DEATH") {
                ocrEvidenceVal.style.color = "#f43f5e";
            } else {
                ocrEvidenceVal.style.color = "#f59e0b";
            }
        }
        if (confidenceVal) confidenceVal.textContent = (avgConfidence * 100).toFixed(1) + "%";

        if (overwriteBlockedVal) {
            overwriteBlockedVal.textContent = overwriteBlocked ? "TRUE" : "FALSE";
            if (overwriteBlocked) {
                overwriteBlockedVal.style.color = "#ef4444";
                overwriteBlockedVal.className = "value text-glow";
            } else {
                overwriteBlockedVal.style.color = "#10b981";
                overwriteBlockedVal.className = "value";
            }
        }

        if (terminal) {
            const timestamp = new Date().toLocaleTimeString();
            const logMsg = document.createElement("div");
            logMsg.style.marginBottom = "4px";

            if (overwriteBlocked) {
                logMsg.innerHTML = `<span style="color: #ef4444;">[${timestamp}] [WARN] Overwrite Blocked!</span> Manual Case Type '${displayMap[userCase]}' preserved over predicted '${displayMap[llmCase]}'.`;
            } else {
                logMsg.innerHTML = `<span style="color: #34d399;">[${timestamp}] [AUDIT]</span> Applied suggestions. User: ${displayMap[userCase]} | LLM: ${displayMap[llmCase]} | OCR: ${ocrEvidence}.`;
            }

            if (terminal.children.length > 20) {
                terminal.removeChild(terminal.children[0]);
            }

            terminal.appendChild(logMsg);
            terminal.scrollTop = terminal.scrollHeight;
        }
    }

    // Apply parsed suggestions
    function applyAllOcrSuggestions(suggestions, confidenceScores = null, ocrEvidence = null, rawRecovered = null) {
        if (!suggestions) return;

        // Normalize flat suggestions into expected nested structure
        if (suggestions && !suggestions.fields) {
            const { case_type, low_confidence_fields, ocr_quality_insufficient,
                ocr_warning, partial_extraction_recovery_mode,
                fallback_source_used, award_amount, total_compensation,
                ai_recovery_triggered, ...fieldValues } = suggestions;
            suggestions = {
                case_type: case_type,
                fields: fieldValues,
                low_confidence_fields: low_confidence_fields || [],
                ocr_quality_insufficient: ocr_quality_insufficient,
                ocr_warning: ocr_warning,
                fallback_source_used: fallback_source_used
            };
        }

        // Clear all previous low-confidence warning labels, styles, and AI metadata badges
        document.querySelectorAll(".verification-warning").forEach(el => el.remove());
        document.querySelectorAll(".low-confidence-input").forEach(el => el.classList.remove("low-confidence-input"));
        document.querySelectorAll(".ai-metadata-badge").forEach(el => el.remove());

        // Extract case type (Part 1 Manual case lock)
        let suggestionsCaseType = suggestions.case_type;
        const currentCaseType = caseTypeSelect.value;
        let overwriteBlocked = false;
        let loggedUserCaseType = currentCaseType || "None Selected";
        let loggedLlmCaseType = suggestionsCaseType || "Unspecified";

        if (currentCaseType && currentCaseType !== "") {
            if (suggestionsCaseType && suggestionsCaseType !== currentCaseType) {
                overwriteBlocked = true;

                // Show interactive suggestion badge under case type dropdown
                const parent = caseTypeSelect.closest(".form-group");
                if (parent) {
                    const badge = document.createElement("div");
                    badge.className = "suggested-badge ai-metadata-badge";
                    badge.setAttribute("data-field", "case_type");

                    const displayVal = suggestionsCaseType === "injury" ? "Injury Case" : "Death Case";
                    // Find confidence score for case_type if available, default to 95%
                    let conf = 0.95;
                    if (confidenceScores && confidenceScores.case_type) {
                        conf = confidenceScores.case_type.confidence !== undefined
                            ? confidenceScores.case_type.confidence
                            : confidenceScores.case_type;
                    } else if (suggestions.confidence_scores && suggestions.confidence_scores.case_type) {
                        conf = suggestions.confidence_scores.case_type.confidence !== undefined
                            ? suggestions.confidence_scores.case_type.confidence
                            : suggestions.confidence_scores.case_type;
                    }
                    conf = typeof conf === "number" ? conf : parseFloat(conf) || 0.95;
                    if (conf > 1.0) conf = conf / 100.0;

                    badge.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Suggest: ${displayVal} (${Math.round(conf * 100)}%)`;

                    badge.addEventListener("click", () => {
                        caseTypeSelect.value = suggestionsCaseType;
                        caseTypeSelect.dispatchEvent(new Event("change"));
                        badge.remove();
                        showToast(`Switched to suggested Case Type: ${displayVal}!`, "success");
                    });

                    parent.appendChild(badge);
                }
            }
            suggestionsCaseType = currentCaseType;
        } else {
            if (suggestionsCaseType) {
                caseTypeSelect.value = suggestionsCaseType;
                caseTypeSelect.dispatchEvent(new Event("change"));
            }
        }

        // Cache all fields (Part 5 & Part 6)
        const fields = suggestions.fields || {};

        Object.keys(fields).forEach(key => {
            lastExtractedFields[key] = fields[key];
        });

        // ── Alias normalisation: map LLM/heuristic field name variants to
        //    the canonical keys that injuryMapping/deathMapping expect ──────
        const fieldAliases = {
            "disability_percentage": "disability",
            "permanent_disability": "disability",
            "accident_date": "date_of_accident",
            "dob": "date_of_birth",
            "accident_place": "place_of_accident",
            "loss_of_consortium": "consortium",
            "loss_of_estate": "loss_estate",
            "loss_estate": "loss_estate",
            "funeral": "funeral_expenses",
            "claimant_name": "name",
            "injured_name": "name",
            "deceased_name": "name",
        };
        Object.keys(fieldAliases).forEach(src => {
            const dst = fieldAliases[src];
            if ((fields[src] !== undefined && fields[src] !== null && fields[src] !== "") &&
                (lastExtractedFields[dst] === undefined || lastExtractedFields[dst] === null || lastExtractedFields[dst] === "")) {
                lastExtractedFields[dst] = fields[src];
            }
        });

        ["date_of_birth", "date_of_accident"].forEach(key => {
            if (fields[key]) {
                lastExtractedFields[key] = fields[key];
            }
        });

        // Ensure canonical "name" key is populated from specific name keys
        if (fields.injured_name) lastExtractedFields["name"] = fields.injured_name;
        if (fields.deceased_name) lastExtractedFields["name"] = fields.deceased_name;
        if (fields.claimant_name) lastExtractedFields["name"] = fields.claimant_name;

        // Merge raw recovered details if LLM is executed (Part 5 offline store)
        if (rawRecovered) {
            const keyMappings = {
                "claimant_name": "name",
                "deceased_name": "name",
                "injured_name": "name",
                "father_name": "father_name",
                "place_of_accident": "place_of_accident",
                "accident_place": "place_of_accident",
                "age": "age",
                "monthly_income": "monthly_income",
                "dependents": "dependents",
                "marital_status": "marital_status",
                "future_prospect": "future_prospect",
                "disability": "disability",
                "disability_percentage": "disability",
                "medical_expenses": "medical_expenses",
                "future_medical_expenses": "future_medical_expenses",
                "pain_and_suffering": "pain_and_suffering",
                "transportation": "transportation",
                "special_diet": "special_diet",
                "attender_charges": "attender_charges",
                "loss_of_income": "loss_of_income",
                "loss_of_consortium": "consortium",
                "consortium": "consortium",
                "funeral_expenses": "funeral_expenses",
                "loss_of_estate": "loss_estate",
                "loss_estate": "loss_estate",
                "dob": "date_of_birth",
                "date_of_birth": "date_of_birth",
                "accident_date": "date_of_accident",
                "date_of_accident": "date_of_accident"
            };

            Object.keys(keyMappings).forEach(rawKey => {
                const cacheKey = keyMappings[rawKey];
                const rawObj = rawRecovered[rawKey];
                let val = null;
                let conf = null;

                if (rawObj && typeof rawObj === "object" && "value" in rawObj) {
                    val = rawObj.value;
                    conf = rawObj.confidence;
                } else if (rawObj !== undefined) {
                    val = rawObj;
                }

                if (val !== null && val !== undefined && val !== "") {
                    lastExtractedFields[cacheKey] = val;
                    if (conf !== null && conf !== undefined) {
                        lastExtractedConfidences[cacheKey] = conf;
                    }
                }
            });
        }

        // Cache confidences
        const lowConfFields = suggestions.low_confidence_fields || [];
        const combinedKeys = new Set([...Object.keys(lastExtractedFields), "date_of_birth", "date_of_accident"]);

        combinedKeys.forEach(key => {
            if (confidenceScores && confidenceScores[key]) {
                const confVal = confidenceScores[key].confidence !== undefined
                    ? confidenceScores[key].confidence
                    : confidenceScores[key];
                lastExtractedConfidences[key] = typeof confVal === "number" ? confVal : parseFloat(confVal) || 1.0;
            } else if (lastExtractedConfidences[key] === undefined) {
                lastExtractedConfidences[key] = lowConfFields.includes(key) ? 0.65 : 1.0;
            }
        });

        // Run case-specific field population (Part 5 & Part 6)
        populateFieldsForActiveCaseType();

        // Telemetry Audit log update (Part 7)
        let evidenceStr = ocrEvidence || "UNCLEAR";
        if (rawRecovered && rawRecovered.ocr_evidence_case) {
            evidenceStr = rawRecovered.ocr_evidence_case;
        }

        let totalConf = 0;
        let confCount = 0;
        Object.keys(lastExtractedConfidences).forEach(k => {
            if (lastExtractedFields[k] !== undefined && lastExtractedFields[k] !== "") {
                totalConf += lastExtractedConfidences[k];
                confCount++;
            }
        });
        const avgConf = confCount > 0 ? (totalConf / confCount) : 0.85;

        updateAuditLog(loggedUserCaseType, loggedLlmCaseType, evidenceStr, avgConf, overwriteBlocked);

        if (overwriteBlocked) {
            showToast(`Preserved manually selected Case Type (${loggedUserCaseType})! Overwrite blocked.`, "warning");
        } else {
            showToast(`Workstation variables successfully auto-filled!`, "success");
        }

        // Auto trigger automatic recalculation after autofill is completed (Task 18)
        setTimeout(() => {
            console.log("AUTO RECALCULATING after OCR autofill...");
            if (compensationForm) {
                compensationForm.dispatchEvent(new Event("submit"));
            }
        }, 500);
    }

    // ==========================================================================
    // AI DATA RECOVERY (LLM OPTIMIZED PARSING EXTRACTION)
    // ==========================================================================
    // AI DATA RECOVERY (LLM OPTIMIZED PARSING EXTRACTION) (Part 3, Part 4 & Part 5 integration)
    if (aiExtractBtn) {
        aiExtractBtn.addEventListener("click", async () => {
            if (!currentOcrRawText || currentOcrRawText.length === 0) {
                showToast("No raw OCR text available. Please upload a PDF first.", "warning");
                return;
            }

            const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
            const loader = document.createElement("div");
            loader.className = "form-ocr-loader";
            loader.innerHTML = `
                <div class="spinner-glow"></div>
                <p>AI Legal LLM is parsing text...</p>
                <span style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Recovering missing legal compensation entities</span>
            `;
            formPanel.style.position = "relative";
            formPanel.appendChild(loader);

            try {
                const response = await fetch("/api/ocr/ai-recover", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ raw_text: currentOcrRawText })
                });

                loader.remove();

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    const detail = errData.detail || "";
                    if (response.status === 503 || detail.toLowerCase().includes("llm") || detail.toLowerCase().includes("unavailable") || detail.toLowerCase().includes("ollama")) {
                        throw new Error(`LLM server unreachable. Is Ollama running with model ${detail || "qwen2.5:14b"}? Check backend logs.`);
                    }
                    throw new Error(detail || `Server error ${response.status}`);
                }
                const data = await response.json();

                if (data.success) {
                    const confidenceScores = data.raw_recovered ? data.raw_recovered.confidence_scores : null;
                    const ocrEvidence = data.raw_recovered ? data.raw_recovered.ocr_evidence_case : null;
                    applyAllOcrSuggestions(data.suggestions, confidenceScores, ocrEvidence, data.raw_recovered);
                    showToast("AI data extraction complete! All recovered parameters cached internally.", "success");
                } else {
                    showToast("AI extraction failed to extract fields.", "error");
                }
            } catch (error) {
                loader.remove();
                console.error("AI recovery failed:", error);
                showToast(`AI extraction failed: ${error.message}`, "error");
            }
        });
    }

    function syncChatDocumentFilter() {
        const chatDocumentFilter = document.getElementById("chat-document-filter");
        if (!chatDocumentFilter) return;

        const currentSelection = chatDocumentFilter.value;

        chatDocumentFilter.innerHTML = '<option value="all">All Documents</option>';

        const indexedFiles = fileQueue.filter(f => f.status === "indexed").map(f => f.filename);

        const uniqueFiles = [...new Set(indexedFiles)];
        uniqueFiles.forEach(filename => {
            const opt = document.createElement("option");
            opt.value = filename;
            opt.textContent = filename;
            chatDocumentFilter.appendChild(opt);
        });

        if (uniqueFiles.includes(currentSelection)) {
            chatDocumentFilter.value = currentSelection;
        }
    }

    // ==========================================================================
    // AI PRECEDENTS SEARCH & CHAT (TAB 3)
    // ==========================================================================
    chatSendBtn.addEventListener("click", handleChatSend);
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleChatSend();
    });

    async function handleChatSend() {
        const query = chatInput.value.trim();
        if (!query) return;

        // Render user message bubble
        appendChatBubble(query, "user");
        chatInput.value = "";

        // Render thinking loader bubble
        const loadingId = appendChatBubble(`<i class="fa-solid fa-spinner fa-spin"></i> Semantic AI searching Qdrant database...`, "bot", true);

        try {
            const payload = {
                message: query,
                case_type: chatCaseFilter.value
            };

            const chatDocumentFilter = document.getElementById("chat-document-filter");
            const docFilterVal = chatDocumentFilter ? chatDocumentFilter.value : "all";
            if (docFilterVal !== "all") {
                payload.filename = docFilterVal;
            }

            const response = await fetch("/api/chat/pdf", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error("Search API failure");
            const data = await response.json();

            // Remove loading bubble
            document.getElementById(loadingId).remove();

            // Render structured markdown legal response
            appendChatBubble(data.response, "bot");

        } catch (error) {
            console.error("AI Legal chat error:", error);
            document.getElementById(loadingId).remove();
            appendChatBubble("I apologize, but I encountered an error searching the centralized database. Please verify the backend uvicorn service is fully initialized.", "bot");
        }
    }

    function appendChatBubble(text, sender, isLoader = false) {
        const bubble = document.createElement("div");
        const id = `msg_${Date.now()}`;
        bubble.id = id;
        bubble.className = `chat-bubble ${sender}`;

        const avatarHtml = sender === "bot" ? `<i class="fa-solid fa-robot"></i>` : `<i class="fa-solid fa-user-tie"></i>`;

        // Render markdown formatting inside bubble text (simple converter)
        let formattedText = text;
        if (!isLoader) {
            formattedText = text
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/\n/g, '<br>');
        }

        bubble.innerHTML = `
            <div class="chat-avatar">${avatarHtml}</div>
            <div class="chat-text">${formattedText}</div>
        `;

        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        if (!isLoader && typeof bindChatBubbleClick === "function") {
            bindChatBubbleClick(bubble);
        }

        return id;
    }

    // ==========================================================================
    // COMPARATIVE LEGAL EVALUATOR (TAB 1)
    // ==========================================================================
    if (triggerEvalBtn) {
        triggerEvalBtn.addEventListener("click", async () => {
            if (!currentCalculationAmount || currentCalculationAmount <= 0) {
                alert("Please calculate the compensation first by filling in mandatory workstation variables and clicking 'Calculate'.");
                return;
            }

            // Display loading loader inside evaluator card body
            if (evaluatorCardBody) {
                evaluatorCardBody.innerHTML = `
                    <div class="empty-state" style="padding: 10px 0;">
                        <i class="fa-solid fa-spinner fa-spin fa-2x" style="color: var(--color-primary);"></i>
                        <p>Generating query embeddings & fetching precedents from Qdrant vector database...</p>
                    </div>
                `;
            }

            const payload = {
                params: {
                    case_type: caseTypeSelect.value,
                    age: parseInt(ageInput.value) || 0,
                    monthly_income: parseFloat(monthlyIncomeInput.value) || 0,
                    dependents: parseInt(dependentsInput.value) || 0,
                    marital_status: maritalStatusSelect.value || "married",
                    future_type: parseInt(futureTypeSelect?.value || 2),
                    future_prospect: parseFloat(document.getElementById("future-prospect")?.value || 0),
                    consortium: parseFloat(document.getElementById("consortium")?.value || 40000),
                    funeral_expenses: parseFloat(document.getElementById("funeral-expenses")?.value || 15000),
                    loss_estate: parseFloat(document.getElementById("loss-estate")?.value || 15000),
                    disability: parseFloat(document.getElementById("disability")?.value || 0)
                },
                calculated_amount: currentCalculationAmount
            };

            try {
                const response = await fetch("/api/search/evaluate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) throw new Error("Comparative evaluation API error");
                const data = await response.json();

                if (!data.success || !data.evaluation) {
                    throw new Error(data.message || "Failed to generate evaluation");
                }

                renderPrecedentEvaluation(data.evaluation);

            } catch (error) {
                console.error("Benchmarking evaluation failed:", error);
                alert("Failed to benchmark precedents on server. Running simulated evaluation analysis.");
                // Offline fallback evaluator
                const fallbackEvaluation = simulateEvaluationMath(payload);
                renderPrecedentEvaluation(fallbackEvaluation);
            }
        });
    }

    function simulateEvaluationMath(req) {
        const cal = req.calculated_amount;
        const avg = cal * (0.93 + Math.random() * 0.12);
        const margin = ((cal - avg) / avg) * 100;

        return {
            calculated_amount: cal,
            average_precedent_award: Math.round(avg),
            margin_percent: Math.round(margin * 100) / 100,
            alignment: Math.abs(margin) <= 5.0 ? "aligned" : (margin > 5.0 ? "high" : "low"),
            recommendation: Math.abs(margin) <= 5.0
                ? `Calculated award is extremely well-aligned with precedents (${margin > 0 ? '+' : ''}${margin.toFixed(1)}% margin).`
                : `Calculated award is ${Math.abs(margin).toFixed(1)}% ${margin > 0 ? 'higher' : 'lower'} than precedent averages.`,
            insurance_defense: `Historically claims of similar profiles average around Rs. ${Math.round(avg).toLocaleString('en-IN')}.`,
            claimant_argument: `Judicial precedents reach up to Rs. ${Math.round(avg * 1.1).toLocaleString('en-IN')}.`,
            precedents: [
                { filename: "judgment_mact_2023.pdf", score: 0.89, name: "Late Ram Sharan", details: "Age: 32 | Income: Rs. 22,000", award_amount: Math.round(avg * 0.95) },
                { filename: "hc_fatal_indore_2022.pdf", score: 0.84, name: "Late Suresh Verma", details: "Age: 35 | Income: Rs. 27,000", award_amount: Math.round(avg * 1.05) }
            ]
        };
    }

    function renderPrecedentEvaluation(evalData) {
        const alignLabels = {
            aligned: `<span class="eval-badge aligned"><i class="fa-solid fa-circle-check"></i> Aligned</span>`,
            high: `<span class="eval-badge high"><i class="fa-solid fa-triangle-exclamation"></i> High Valuation</span>`,
            low: `<span class="eval-badge low"><i class="fa-solid fa-arrow-down-long"></i> Under-valued</span>`
        };

        let precedentsHtml = "";
        evalData.precedents.forEach(p => {
            precedentsHtml += `
                <div class="precedent-mini-card">
                    <div class="pm-info">
                        <span class="pm-name">${p.name}</span>
                        <span class="pm-details" title="${p.filename}">${p.filename} | ${p.details}</span>
                    </div>
                    <div>
                        <span class="pm-award">Rs. ${p.award_amount.toLocaleString('en-IN')}</span>
                        <span class="pm-score">${(p.score * 100).toFixed(1)}% Match</span>
                    </div>
                </div>
            `;
        });

        evaluatorCardBody.innerHTML = `
            <!-- Hero comparative stats -->
            <div class="eval-hero">
                <div class="eval-stats">
                    <span class="label">Calculated Award</span>
                    <span class="value">Rs. ${evalData.calculated_amount.toLocaleString('en-IN')}</span>
                </div>
                <div class="eval-stats" style="text-align: right;">
                    <span class="label">Precedent Avg</span>
                    <span class="value" style="color: var(--text-secondary)">Rs. ${evalData.average_precedent_award.toLocaleString('en-IN')}</span>
                </div>
            </div>

            <!-- Alignment and margin -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                <span class="card-text">Award Margin: <strong>${evalData.margin_percent > 0 ? '+' : ''}${evalData.margin_percent}%</strong></span>
                ${alignLabels[evalData.alignment] || ""}
            </div>

            <!-- Legal recommendation -->
            <div class="eval-desc">
                <strong><i class="fa-solid fa-gavel"></i> Legal Opinion:</strong><br>
                ${evalData.recommendation}
            </div>

            <!-- Legal Argument briefs -->
            <div class="eval-desc" style="background: rgba(186, 104, 200, 0.02); border-color: rgba(186, 104, 200, 0.12); margin-top: 8px;">
                <strong><i class="fa-solid fa-scroll"></i> Court Brief Argument:</strong><br>
                <em>"${evalData.claimant_argument}"</em>
            </div>

            <!-- Retrieved precedent list -->
            <div style="margin-top: 14px;">
                <span class="metric-label">Matching Cases Indexed (Qdrant)</span>
                ${precedentsHtml}
            </div>
        `;

        if (typeof triggerTabNotification === "function") {
            triggerTabNotification("benchmarking");
        }
    }

    // ==========================================================================
    // FORM CALCULATOR API SUBMISSION
    // ==========================================================================
    compensationForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        console.log("CALCULATE CLICKED");

        const caseType = caseTypeSelect.value;
        if (!caseType) {
            showToast("Please select a case type first!", "warning");
            return;
        }

        // Validate all required inputs are filled prior to calculations
        if (!compensationForm.reportValidity()) {
            showToast("Please fill all mandatory case fields before calculating.", "warning");
            return;
        }

        // Before submitting, check if age is missing
        const ageVal = parseInt(ageInput.value);
        if (!ageVal || ageVal <= 0) {
            showToast("⚠️ Age not set — calculation will use default age 30. Upload a PDF or enter DOB + accident date.", "warning");
        }

        const payload = {
            case_type: caseType,
            age: Number(ageInput.value || 0),
            monthly_income: Number(monthlyIncomeInput.value || 0),

            dependents: Number(dependentsInput.value || 0),
            marital_status: maritalStatusSelect.value || "married",
            future_type: Number(futureTypeSelect?.value || 2),
            future_prospect: Number(document.getElementById("future-prospect")?.value || 0),
            consortium: Number(document.getElementById("consortium")?.value || 40000),
            funeral_expenses: Number(document.getElementById("funeral-expenses")?.value || 15000),
            loss_estate: Number(document.getElementById("loss-estate")?.value || 15000),

            // Consortium breakdown (hardcoded to 0 under the hood)
            conlum: 0,
            conspo: 0,
            conpar: 0,
            conchil: 0,
            conwif: 0,
            conmo: 0,
            confath: 0,
            conhus: 0,
            conbro: 0,
            consis: 0,

            disability: Number(document.getElementById("disability")?.value || 0),
            medical_expenses: Number(document.getElementById("medical-expenses")?.value || 0),
            future_medical_expenses: Number(document.getElementById("future-medical-expenses")?.value || 0),
            pain_and_suffering: Number(document.getElementById("pain-and-suffering")?.value || 0),
            transportation: Number(document.getElementById("transportation")?.value || 0),
            special_diet: Number(document.getElementById("special-diet")?.value || 0),
            attender_charges: Number(document.getElementById("attender-charges")?.value || 0),
            loss_of_income: Number(document.getElementById("loss-of-income")?.value || 0),

            // Extra Injury heads
            coliti: 0,
            misex: 0,
            loamiti: 0,
            lopmarri: 0,
            loexlife: 0,
            loveaff: 0,
            lossofenjoy: 0
        };

        try {
            const response = await fetch("/api/calculate/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error("Server calculator returned error status");
            const results = await response.json();

            if (results.success === false) {
                throw new Error(results.error || "Server calculation process failed");
            }

            // Align with nested schema: use results.breakdown if available, otherwise flat results
            const breakdown = results.breakdown || results;
            currentCalculationAmount = results.total_compensation || breakdown.final_amount || 0;

            // Update inputs and previews with real calculated money values
            updateMonetaryOutputs(breakdown);

            renderResultsDashboard(breakdown, payload);
            openModal();
            showToast("Compensation calculated successfully via FastAPI server!", "success");

            // Enable Evaluator button
            if (triggerEvalBtn) triggerEvalBtn.disabled = false;

        } catch (error) {
            console.error("Server-side calculation failed:", error);
            showToast(`Backend computation failed: ${error.message}. Running local mathematical fallback engine.`, "warning");

            const localResults = calculateCompensationLocally(payload);

            currentCalculationAmount = localResults.final_amount;

            // Update inputs and previews with real calculated money values locally
            updateMonetaryOutputs(localResults);

            renderResultsDashboard(localResults, payload);
            openModal();
            if (triggerEvalBtn) triggerEvalBtn.disabled = false;
        }
    });

    // Local Math Evaluator fallback
    function calculateCompensationLocally(data) {
        const age = data.age;
        const multiplier = getMultiplier(age);
        const monthly = data.monthly_income;
        const annual = monthly * 12;

        if (data.case_type === "death") {
            const futureProspect = getFutureProspectPercentage(age, data.future_type);
            const futureProspectAmount = monthly * futureProspect / 100;
            const enhancedMonthlyIncome = monthly + futureProspectAmount;
            const annualIncome = enhancedMonthlyIncome * 12;
            const deductionRatio = getDeductionRatio(data.dependents, data.marital_status);
            const deductionPercent = Math.round(deductionRatio * 100);
            const deductionAmount = annualIncome * deductionRatio;
            const dependencyIncome = annualIncome - deductionAmount;
            const lossOfDependency = dependencyIncome * multiplier;
            const finalCompensation = lossOfDependency + data.consortium + data.funeral_expenses + data.loss_estate;

            return {
                case_type: "death",
                multiplier: multiplier,
                future_prospect_percentage: Math.round(futureProspect),
                future_prospect_amount: Math.round(futureProspectAmount),
                enhanced_monthly_income: Math.round(enhancedMonthlyIncome),
                monthly_income: Math.round(monthly),
                annual_income: Math.round(annualIncome),
                future_income: Math.round(annualIncome), // for backwards compatibility
                deduction_percentage: Math.round(deductionPercent),
                deduction_amount: Math.round(deductionAmount),
                dependency_income: Math.round(dependencyIncome),
                loss_of_dependency: Math.round(lossOfDependency),
                consortium: data.consortium,
                funeral_expenses: data.funeral_expenses,
                loss_estate: data.loss_estate,
                final_compensation: Math.round(finalCompensation),
                final_amount: Math.round(finalCompensation)
            };
        } else {
            const disabilityCompensation = annual * (data.disability / 100) * multiplier;
            const finalCompensation = disabilityCompensation + data.medical_expenses + data.future_medical_expenses +
                data.pain_and_suffering + data.transportation + data.special_diet + data.attender_charges + data.loss_of_income;

            return {
                case_type: "injury",
                multiplier: multiplier,
                annual_income: Math.round(annual),
                future_income_loss: Math.round(disabilityCompensation),
                medical_expenses: data.medical_expenses,
                future_medical_expenses: data.future_medical_expenses,
                pain_and_suffering: data.pain_and_suffering,
                transportation: data.transportation,
                special_diet: data.special_diet,
                attender_charges: data.attender_charges,
                loss_of_income: data.loss_of_income,
                coliti: 0,
                misex: 0,
                loamiti: 0,
                lopmarri: 0,
                loexlife: 0,
                loveaff: 0,
                lossofenjoy: 0,
                final_amount: Math.round(finalCompensation)
            };
        }
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }).format(amount);
    }

    function updateMonetaryOutputs(res) {
        if (res.case_type === "death") {
            const annualIncome = res.annual_income || 0;
            const enhancedMonthlyIncome = res.enhanced_monthly_income || 0;
            const deductionPercent = res.deduction_percentage || 0;
            const deductionAmount = res.deduction_amount || 0;
            const mult = res.multiplier || 0;
            const lossOfDependency = res.loss_of_dependency || 0;
            const finalComp = res.final_compensation || res.final_amount || 0;

            // Populate read-only inputs
            const lossDepInput = document.getElementById("loss-of-dependency");
            if (lossDepInput) lossDepInput.value = Math.round(lossOfDependency);

            const finalDeathCompInput = document.getElementById("death-final-compensation");
            if (finalDeathCompInput) finalDeathCompInput.value = Math.round(finalComp);

            // Populate dynamic dashboard elements
            if (document.getElementById("live-calc-annual")) {
                document.getElementById("live-calc-annual").textContent = formatCurrency(annualIncome);
                document.getElementById("live-calc-future").textContent = formatCurrency(enhancedMonthlyIncome);
                document.getElementById("live-calc-deduct-pct").textContent = `${deductionPercent}%`;
                document.getElementById("live-calc-deduct-amt").textContent = formatCurrency(deductionAmount);
                document.getElementById("live-calc-multiplier").textContent = mult;
                document.getElementById("live-calc-dependency").textContent = formatCurrency(lossOfDependency);
                document.getElementById("live-calc-total").textContent = formatCurrency(finalComp);
            }
        }
    }

    function updateOcrInspector(data) {
        if (!data || !data.ocr_debug) return;
        const debug = data.ocr_debug;

        // 1. Overall stats
        const qScore = debug.ocr_quality_score !== undefined ? debug.ocr_quality_score : 0.0;
        const avgConf = debug.average_page_confidence !== undefined ? debug.average_page_confidence : 0.0;
        const textDensity = debug.text_density_score !== undefined ? debug.text_density_score : 0.0;

        const qEl = document.getElementById("ocr-val-quality");
        if (qEl) qEl.textContent = qScore.toFixed(3);

        const cEl = document.getElementById("ocr-val-confidence");
        if (cEl) cEl.textContent = (avgConf * 100).toFixed(1) + "%";

        const eEl = document.getElementById("ocr-val-engine");
        if (eEl) eEl.textContent = debug.ocr_engine_used || "Unknown";

        const fEl = document.getElementById("ocr-val-fallback");
        if (fEl) fEl.textContent = debug.fallback_ocr_engine || "None";

        const rEl = document.getElementById("ocr-val-retries");
        if (rEl) rEl.textContent = debug.ocr_retry_count !== undefined ? debug.ocr_retry_count : 0;

        const dEl = document.getElementById("ocr-val-density");
        if (dEl) dEl.textContent = textDensity.toFixed(3);

        const durationEl = document.getElementById("ocr-val-duration");
        if (durationEl) {
            const durationSec = debug.total_ocr_time !== undefined ? debug.total_ocr_time : ocrSecondsElapsed;
            durationEl.textContent = typeof durationSec === "number" ? formatTimeMMSS(Math.round(durationSec)) : durationSec || "—";
        }

        // Update badge
        const badge = document.getElementById("ocr-inspector-badge");
        if (badge) {
            badge.textContent = data.fallback_source || "Loaded";
            badge.className = "badge tech-badge " + (qScore >= 0.5 ? "bg-success" : "bg-danger");
        }

        // 2. Raw Text Dump
        const textDump = document.getElementById("ocr-raw-text-dump");
        if (textDump && data.raw_text) {
            textDump.value = data.raw_text.join("\n");
        }

        // 3. Page Breakdown Table
        const tableBody = document.getElementById("ocr-pages-table-body");
        if (tableBody) {
            if (debug.pages && debug.pages.length > 0) {
                tableBody.innerHTML = "";
                debug.pages.forEach(p => {
                    const tr = document.createElement("tr");
                    tr.style.borderBottom = "1px solid var(--border-glass)";

                    const pageNum = p.page || 1;
                    const engine = p.engine || "PaddleOCR";
                    const dpi = p.dpi || 180;
                    const pageTime = p.total_page_time !== undefined ? p.total_page_time.toFixed(2) + "s" : "—";
                    const conf = p.confidence !== undefined ? (p.confidence * 100).toFixed(1) + "%" : "—";
                    const quality = p.quality_score !== undefined ? p.quality_score.toFixed(3) : "—";

                    tr.innerHTML = `
                        <td style="padding: 8px 12px; font-weight: 600; color: var(--text-primary);">Page ${pageNum}</td>
                        <td style="padding: 8px 12px; color: var(--text-secondary);">${engine}</td>
                        <td style="padding: 8px 12px; color: var(--text-secondary);">${dpi} DPI</td>
                        <td style="padding: 8px 12px; text-align: right; font-family: monospace; color: var(--text-secondary);">${pageTime}</td>
                        <td style="padding: 8px 12px; text-align: right; font-family: monospace; color: var(--color-success);">${conf}</td>
                        <td style="padding: 8px 12px; text-align: right; font-family: monospace; color: var(--color-primary);">${quality}</td>
                    `;
                    tableBody.appendChild(tr);
                });
            } else {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="6" style="padding: 16px; text-align: center; color: var(--text-muted);">
                            No page details returned.
                        </td>
                    </tr>
                `;
            }
        }
    }

    function renderResultsDashboard(res, req) {
        const claimantName = document.getElementById("name")?.value || "N/A";
        const fatherNameVal = document.getElementById("father-name")?.value || "N/A";
        const dateAccidentVal = doaInput.value ? new Date(doaInput.value).toLocaleDateString('en-IN') : "N/A";
        const dateBirthVal = dobInput.value ? new Date(dobInput.value).toLocaleDateString('en-IN') : "N/A";
        const placeAccidentVal = document.getElementById("place-of-accident")?.value || "N/A";
        const caseTypeLabel = res.case_type === "death" ? "Death Claim" : "Injury Claim";

        let parametersHtml = "";
        if (res.case_type === "death") {
            const futureProspectPercent = res.future_prospect_percentage !== undefined ? res.future_prospect_percentage : 0;
            const monthlyIncomeVal = res.monthly_income !== undefined ? res.monthly_income : req.monthly_income;
            const enhancedMonthlyIncomeVal = res.enhanced_monthly_income !== undefined ? res.enhanced_monthly_income : (monthlyIncomeVal * (1 + futureProspectPercent / 100));
            const annualIncomeVal = res.annual_income !== undefined ? res.annual_income : (enhancedMonthlyIncomeVal * 12);

            parametersHtml = `
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Monthly Income</span>
                    <strong>${formatCurrency(monthlyIncomeVal)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Future Prospects Added</span>
                    <strong>+${futureProspectPercent}%</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Enhanced Monthly Income</span>
                    <strong>${formatCurrency(enhancedMonthlyIncomeVal)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Annual Income (Enhanced)</span>
                    <strong>${formatCurrency(annualIncomeVal)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Deduction Applied</span>
                    <strong>${res.deduction_percentage}% (-${formatCurrency(res.deduction_amount)})</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Dependency Income</span>
                    <strong>${formatCurrency(res.dependency_income)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Multiplier Used</span>
                    <strong>${res.multiplier}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Loss of Dependency</span>
                    <strong>${formatCurrency(res.loss_of_dependency)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Consortium</span>
                    <strong>${formatCurrency(res.consortium)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Funeral Expenses</span>
                    <strong>${formatCurrency(res.funeral_expenses)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0;">
                    <span>Loss of Estate</span>
                    <strong>${formatCurrency(res.loss_estate)}</strong>
                </div>
            `;
        } else {
            parametersHtml = `
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Monthly Income</span>
                    <strong>${formatCurrency(req.monthly_income)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Sarla Verma Multiplier</span>
                    <strong>${res.multiplier}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Permanent Impairment</span>
                    <strong>${req.disability}%</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Medical Expenses</span>
                    <strong>${formatCurrency(res.medical_expenses + res.future_medical_expenses)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Pain & Suffering</span>
                    <strong>${formatCurrency(res.pain_and_suffering)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0;">
                    <span>Other Allowances (Diet, Attender, Transport, Income Loss)</span>
                    <strong>${formatCurrency(res.transportation + res.special_diet + res.attender_charges + res.loss_of_income)}</strong>
                </div>
            `;
        }

        modalBodyContent.innerHTML = `
            <div class="results-dashboard simplified-dashboard">
                <div class="award-hero" style="text-align: center; margin-bottom: 20px;">
                    <span class="hero-label" style="display: block; font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px;">FINAL COMPENSATION</span>
                    <span class="hero-amount" style="display: block; font-size: 2.5rem; font-weight: 800; font-family: 'Outfit', sans-serif; color: var(--color-success); margin: 6px 0; text-shadow: 0 0 20px rgba(52, 211, 153, 0.2);">${formatCurrency(res.final_compensation || res.final_amount)}</span>
                    <span class="hero-tag" style="background: rgba(186, 104, 200, 0.2); color: #e9d5ff; border: 1px solid rgba(186, 104, 200, 0.3); font-size: 0.75rem; padding: 3px 10px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 6px;"><i class="fa-solid fa-gavel"></i> ${caseTypeLabel}</span>
                </div>

                <div class="briefing-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.85rem; border: 1px solid var(--border-glass); padding: 16px; border-radius: var(--radius-sm); background: rgba(255,255,255,0.01); margin-bottom: 20px; color: var(--text-primary);">
                    <div><strong>Claimant / Deceased Name:</strong> ${claimantName}</div>
                    <div><strong>Father / Husband Name:</strong> ${fatherNameVal}</div>
                    <div><strong>Date of Birth (Age):</strong> ${dateBirthVal} (${req.age} years)</div>
                    <div><strong>Date of Accident:</strong> ${dateAccidentVal}</div>
                    <div style="grid-column: span 2;"><strong>Place of Accident:</strong> ${placeAccidentVal}</div>
                </div>

                <div class="parameters-summary-box" style="border: 1px solid var(--border-glass); border-radius: var(--radius-sm); background: rgba(255,255,255,0.02); padding: 16px; color: var(--text-primary);">
                    <h4 style="margin-top: 0; margin-bottom: 12px; font-family: 'Outfit', sans-serif; font-size: 0.95rem; border-bottom: 1px solid var(--border-glass); padding-bottom: 6px; color: var(--color-primary); display: flex; align-items: center; gap: 8px;"><i class="fa-solid fa-list-check"></i> Calculation Parameters</h4>
                    <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.85rem;">
                        ${parametersHtml}
                    </div>
                </div>
            </div>
        `;

        const finalCompEl = document.getElementById("final-compensation");
        if (finalCompEl) {
            finalCompEl.innerText = `₹ ${(res.final_compensation || res.final_amount).toLocaleString("en-IN")}`;
        }
    }

    // Modal controls
    function openModal() { resultsModal.classList.add("open"); }
    function closeModal() { resultsModal.classList.remove("open"); }

    closeModalBtn.addEventListener("click", closeModal);
    dismissModalBtn.addEventListener("click", closeModal);
    window.addEventListener("click", (e) => {
        if (e.target === resultsModal) closeModal();
    });

    document.getElementById("reset-btn").addEventListener("click", () => {
        compensationForm.reset();

        window.lastRawText = "";
        const suggestionDiv = document.getElementById("case-type-suggestion");
        if (suggestionDiv) {
            suggestionDiv.innerHTML = "";
            suggestionDiv.classList.add("hidden-section");
        }

        // Clear all live calculated dashboard elements back to hyphens
        ["live-calc-annual", "live-calc-future", "live-calc-deduct-pct", "live-calc-deduct-amt", "live-calc-multiplier", "live-calc-dependency", "live-calc-total"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = "—";
        });

        // Clear AI metadata badges
        document.querySelectorAll(".ai-metadata-badge").forEach(el => el.remove());

        // Reset live OCR timers
        if (ocrTimerInterval) {
            clearInterval(ocrTimerInterval);
            ocrTimerInterval = null;
        }
        ocrSecondsElapsed = 0;

        const headerTimerContainer = document.getElementById("header-ocr-timer-badge");
        const headerElapsedText = document.getElementById("header-ocr-timer-elapsed");
        const statusIcon = document.getElementById("ocr-timer-status-icon");
        const statusText = document.getElementById("ocr-timer-status-text");
        const elapsedText = document.getElementById("ocr-timer-elapsed");

        if (headerElapsedText) {
            headerElapsedText.textContent = "Ready";
        }
        if (headerTimerContainer) {
            headerTimerContainer.style.color = "var(--text-secondary)";
            headerTimerContainer.style.borderColor = "var(--border-glass)";
            headerTimerContainer.style.background = "rgba(15, 23, 42, 0.04)";
        }
        if (statusIcon) {
            statusIcon.innerHTML = `<i class="fa-solid fa-clock" style="color: var(--color-primary);"></i>`;
        }
        if (statusText) {
            statusText.textContent = "Ready for upload";
            statusText.style.color = "var(--text-secondary)";
        }
        if (elapsedText) {
            elapsedText.textContent = "Ready";
            elapsedText.style.color = "var(--text-secondary)";
        }

        sharedFields.classList.remove("show");
        sharedFields.classList.add("hidden-section");

        deathFields.classList.remove("show");
        deathFields.classList.add("hidden-section");

        injuryFields.classList.remove("show");
        injuryFields.classList.add("hidden-section");

        formActionsBar.classList.remove("show-flex");
        formActionsBar.classList.add("hidden-section");

        if (liveMetricsCard) {
            liveMetricsCard.classList.remove("show");
            liveMetricsCard.classList.add("hidden-section");
        }
        if (evaluatorCard) {
            evaluatorCard.classList.remove("show");
            evaluatorCard.classList.add("hidden-section");
        }

        singleUploadSection.classList.remove("show");
        singleUploadSection.classList.remove("show-flex");
        singleUploadSection.classList.add("hidden-section");
        singlePreviewCard.classList.add("hidden-section");
        singlePreviewCard.classList.remove("show");
        singlePreviewContainer.innerHTML = `
            <div class="preview-empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 10px; opacity: 0.5;">
                <i class="fa-solid fa-file-pdf" style="font-size: 3rem; color: var(--color-primary)"></i>
                <p style="font-size: 0.8rem; color: var(--text-secondary)">Upload a PDF on the left to see the live document preview here.</p>
            </div>
        `;
        singlePreviewFilename.textContent = "No File Loaded";

        const summaryCard = document.getElementById("legal-ai-summary-card");
        if (summaryCard) {
            summaryCard.classList.add("hidden-section");
            summaryCard.classList.remove("show");
            const summaryBody = document.getElementById("legal-ai-summary-body");
            if (summaryBody) {
                summaryBody.innerHTML = `
                    <div class="empty-summary-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; opacity: 0.5; padding: 20px 0;">
                        <i class="fa-solid fa-gavel" style="font-size: 2.5rem; color: #c084fc;"></i>
                        <p style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; margin: 0;">Upload a PDF to see the structured legal analysis summary and judicial anomaly checklist.</p>
                    </div>
                `;
            }
        }

        const tableCard = document.getElementById("compensation-table-card");
        if (tableCard) {
            tableCard.classList.add("hidden-section");
            tableCard.classList.remove("show");
            const tableBody = document.getElementById("compensation-table-body");
            if (tableBody) {
                tableBody.innerHTML = `
                    <div class="empty-table-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; opacity: 0.5; padding: 20px 0;">
                        <i class="fa-solid fa-table-list" style="font-size: 2.5rem; color: #34d399;"></i>
                        <p style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; margin: 0;">Upload a PDF to view the detailed breakdown of the judicial award heads.</p>
                    </div>
                `;
            }
        }

        triggerEvalBtn.disabled = true;
        currentCalculationAmount = 0;
    });

    // ==========================================================================
    const slideover = document.getElementById("right-slideover");
    const closeSlideover = document.getElementById("close-slideover");
    const aiAssistantTrigger = document.getElementById("ai-assistant-trigger");

    const assistantChatMessages = document.getElementById("assistant-chat-messages");
    const assistantChatInput = document.getElementById("assistant-chat-input");
    const assistantChatSendBtn = document.getElementById("assistant-chat-send-btn");

    // --- WORKSTATION RIGHT PANE TABS CONTROLLER ---
    const paneTabButtons = document.querySelectorAll(".pane-tab-btn");
    const paneTabContents = document.querySelectorAll(".pane-tab-content");
    const benchmarkingTabDot = document.getElementById("benchmarking-tab-dot");
    const analysisTabDot = document.getElementById("analysis-tab-dot");
    const ocrQualityTabDot = document.getElementById("ocr-quality-tab-dot");

    paneTabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-pane-tab");

            // Switch tabs active styles
            paneTabButtons.forEach(b => {
                if (b === btn) {
                    b.classList.add("active");
                    b.style.background = "rgba(11, 58, 114, 0.06)";
                    b.style.borderColor = "rgba(11, 58, 114, 0.25)";
                    b.style.color = "var(--color-primary)";
                } else {
                    b.classList.remove("active");
                    b.style.background = "transparent";
                    b.style.borderColor = "transparent";
                    b.style.color = "var(--text-secondary)";
                }
            });

            // Toggle tab content display
            paneTabContents.forEach(content => {
                if (content.id === `pane-tab-${targetTab}-content`) {
                    content.classList.add("active");
                    content.classList.remove("hidden");
                } else {
                    content.classList.remove("active");
                    content.classList.add("hidden");
                }
            });

            // Clear dot when tab is clicked
            if (targetTab === "benchmarking" && benchmarkingTabDot) {
                benchmarkingTabDot.classList.add("hidden");
            } else if (targetTab === "analysis" && analysisTabDot) {
                analysisTabDot.classList.add("hidden");
            } else if (targetTab === "ocr-quality" && ocrQualityTabDot) {
                ocrQualityTabDot.classList.add("hidden");
            }
        });
    });

    // Helper to get active tab
    function getActiveRightPaneTab() {
        const activeBtn = document.querySelector(".pane-tab-btn.active");
        return activeBtn ? activeBtn.getAttribute("data-pane-tab") : "pdf";
    }

    // Helper to trigger tab notification dot rather than forcing switch
    window.triggerTabNotification = function (tabName) {
        if (getActiveRightPaneTab() !== tabName) {
            if (tabName === "benchmarking" && benchmarkingTabDot) {
                benchmarkingTabDot.classList.remove("hidden");
            } else if (tabName === "analysis" && analysisTabDot) {
                analysisTabDot.classList.remove("hidden");
            } else if (tabName === "ocr-quality" && ocrQualityTabDot) {
                ocrQualityTabDot.classList.remove("hidden");
            }
        }
    };

    // --- CHAT READ MODAL ENGINE (BIG BOX VIEWER) ---
    const chatReadModal = document.getElementById("chat-read-modal");
    const chatModalBodyContent = document.getElementById("chat-modal-body-content");
    const closeChatModalBtn = document.getElementById("close-chat-modal-btn");
    const dismissChatModalBtn = document.getElementById("dismiss-chat-modal-btn");

    window.openChatReader = function (htmlContent) {
        if (chatReadModal && chatModalBodyContent) {
            chatModalBodyContent.innerHTML = htmlContent;
            chatReadModal.classList.add("open");
        }
    };

    window.closeChatReader = function () {
        if (chatReadModal) {
            chatReadModal.classList.remove("open");
        }
    };

    if (closeChatModalBtn) closeChatModalBtn.addEventListener("click", closeChatReader);
    if (dismissChatModalBtn) dismissChatModalBtn.addEventListener("click", closeChatReader);

    // Close modal when clicking outside content area
    window.addEventListener("click", (e) => {
        if (e.target === chatReadModal) {
            closeChatReader();
        }
    });

    // Function to attach click listeners to chat texts
    window.bindChatBubbleClick = function (bubbleElement) {
        const textElement = bubbleElement.querySelector(".chat-text");
        if (textElement) {
            textElement.addEventListener("click", () => {
                openChatReader(textElement.innerHTML);
            });
        }
    };

    // Bind existing bubbles on startup
    document.querySelectorAll(".chat-bubble").forEach(bubble => {
        bindChatBubbleClick(bubble);
    });

    // Wide view toggle inside slideover header
    const expandSlideoverBtn = document.getElementById("expand-slideover-btn");
    if (expandSlideoverBtn) {
        expandSlideoverBtn.addEventListener("click", () => {
            if (slideover) {
                slideover.classList.toggle("expanded");
                const icon = expandSlideoverBtn.querySelector("i");
                if (icon) {
                    if (slideover.classList.contains("expanded")) {
                        icon.className = "fa-solid fa-compress";
                        expandSlideoverBtn.title = "Toggle Normal View";
                    } else {
                        icon.className = "fa-solid fa-expand";
                        expandSlideoverBtn.title = "Toggle Wide View";
                    }
                }
            }
        });
    }

    if (aiAssistantTrigger) {
        aiAssistantTrigger.addEventListener("click", () => {
            if (aiAssistantTrigger.classList.contains("active") && slideover.classList.contains("open")) {
                closeDrawer();
                return;
            }

            aiAssistantTrigger.classList.add("active");
            slideover.classList.add("open");

            // Auto generate CASE BRIEF on open
            generateCaseBrief();
        });
    }

    function closeDrawer() {
        if (slideover) {
            slideover.classList.remove("open");
            slideover.classList.remove("expanded");
            if (expandSlideoverBtn) {
                const icon = expandSlideoverBtn.querySelector("i");
                if (icon) {
                    icon.className = "fa-solid fa-expand";
                    expandSlideoverBtn.title = "Toggle Wide View";
                }
            }
        }
        if (aiAssistantTrigger) aiAssistantTrigger.classList.remove("active");
    }

    if (closeSlideover) {
        closeSlideover.addEventListener("click", closeDrawer);
    }

    // Generate formatted Case Brief automatically based on workstation inputs
    function generateCaseBrief() {
        const caseType = caseTypeSelect.value || "N/A";
        const caseTypeLabel = caseType === "death" ? "Death Claim" : (caseType === "injury" ? "Injury Claim" : "N/A");

        const claimantName = document.getElementById("name")?.value || "N/A";
        const respondentName = "Insurance Company / Respondent";
        const ageVal = ageInput.value ? `${ageInput.value} years` : "N/A";
        const monthlyIncome = parseFloat(monthlyIncomeInput.value) || 0;
        const incomeVal = monthlyIncome > 0 ? formatCurrency(monthlyIncome) : "N/A";

        const disabilityInput = document.getElementById("disability");
        const disabilityVal = (caseType === "injury" && disabilityInput && disabilityInput.value) ? `${disabilityInput.value}%` : "N/A";

        const awardAmountVal = currentCalculationAmount > 0 ? formatCurrency(currentCalculationAmount) : "N/A";
        const statusVal = currentCalculationAmount > 0 ? "Calculated (Deterministic Math)" : "Awaiting Mathematical Input";

        const occupationVal = "Salaried / Self-Employed";

        const contentEl = document.getElementById("assistant-case-brief-content");
        if (contentEl) {
            contentEl.innerHTML = `
                <table style="width:100%; border-collapse:collapse; font-size:0.8rem; line-height:1.6;">
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Case Type:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${caseTypeLabel}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Claimant:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${claimantName}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Respondent:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${respondentName}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Age:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${ageVal}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Occupation:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${occupationVal}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Income:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${incomeVal}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Disability:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:var(--text-primary);">${disabilityVal}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Award Amount:</td><td style="padding:4px 0; text-align:right; font-weight:700; color:var(--color-success);">${awardAmountVal}</td></tr>
                    <tr><td style="padding:4px 0; color:var(--text-muted);">Status:</td><td style="padding:4px 0; text-align:right; font-weight:600; color:${currentCalculationAmount > 0 ? '#34d399' : '#f59e0b'};">${statusVal}</td></tr>
                </table>
            `;
        }
    }

    // Bind Suggested Question Pills immediately
    document.querySelectorAll(".suggested-question-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            const questionText = pill.getAttribute("data-question");
            if (assistantChatInput) {
                assistantChatInput.value = questionText;
                handleAssistantChatSend();
            }
        });
    });

    // Side panel chat submission
    if (assistantChatSendBtn) {
        assistantChatSendBtn.addEventListener("click", handleAssistantChatSend);
    }
    if (assistantChatInput) {
        assistantChatInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") handleAssistantChatSend();
        });
    }

    async function handleAssistantChatSend() {
        const query = assistantChatInput.value.trim();
        if (!query) return;

        appendAssistantChatBubble(query, "user");
        assistantChatInput.value = "";

        const loadingId = appendAssistantChatBubble(`<i class="fa-solid fa-spinner fa-spin"></i> Auditing workstation state & searching precedents...`, "bot", true);

        try {
            // Retrieve current workstation inputs for full LLM validation context (Phase 8 integration)
            const caseType = caseTypeSelect.value;
            const parsedFields = {
                case_type: caseType,
                name: document.getElementById("name")?.value || "",
                father_name: document.getElementById("father-name")?.value || "",
                age: parseInt(ageInput.value) || 0,
                monthly_income: parseFloat(monthlyIncomeInput.value) || 0,
                disability: parseFloat(document.getElementById("disability")?.value) || 0,
                dependents: parseInt(dependentsInput.value) || 0,
                marital_status: maritalStatusSelect.value || "married"
            };

            const calculatorResult = {
                case_type: caseType,
                final_amount: currentCalculationAmount,
                total_compensation: currentCalculationAmount
            };

            // Identify current active PDF filename
            let filename = null;
            if (singlePreviewFilename && singlePreviewFilename.innerHTML) {
                const parts = singlePreviewFilename.innerHTML.split("<span");
                if (parts.length > 0) {
                    filename = parts[0].trim();
                }
            }

            const payload = {
                question: query,
                filename: (filename && filename !== "No File Loaded") ? filename : null,
                ocr_text: currentOcrRawText ? currentOcrRawText.join("\n") : "",
                parsed_fields: parsedFields,
                calculator_result: calculatorResult
            };

            const response = await fetch("/api/chat/pdf", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error("Assistant API returned error");
            const data = await response.json();

            document.getElementById(loadingId).remove();
            appendAssistantChatBubble(data.response, "bot");

        } catch (error) {
            console.error("AI Legal Assistant error:", error);
            document.getElementById(loadingId).remove();
            appendAssistantChatBubble("I apologize, but I encountered an error auditing the workstation state. Please ensure the local Ollama service is running.", "bot");
        }
    }

    function appendAssistantChatBubble(text, sender, isLoader = false) {
        const bubble = document.createElement("div");
        const id = `ast_msg_${Date.now()}`;
        bubble.id = id;
        bubble.className = `chat-bubble ${sender}`;

        const avatarHtml = sender === "bot" ? `<i class="fa-solid fa-robot"></i>` : `<i class="fa-solid fa-user-tie"></i>`;

        let formattedText = text;
        if (!isLoader && sender === "bot" && !text.includes("<ul") && !text.includes("<table")) {
            formattedText = text
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/\n/g, '<br>');
        }

        bubble.innerHTML = `
            <div class="chat-avatar">${avatarHtml}</div>
            <div class="chat-text" style="flex: 1; min-width: 0; overflow-wrap: break-word; font-size: 0.85rem; line-height: 1.5;">${formattedText}</div>
        `;

        assistantChatMessages.appendChild(bubble);
        assistantChatMessages.scrollTop = assistantChatMessages.scrollHeight;

        if (!isLoader && typeof bindChatBubbleClick === "function") {
            bindChatBubbleClick(bubble);
        }

        return id;
    }

    // Escape key listener to close drawer
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeDrawer();
        }
    });

    // Explicit Calculate Button Click Handler & Logger
    const calculateBtn = document.getElementById("calculate-btn");
    if (calculateBtn) {
        calculateBtn.addEventListener("click", (e) => {
            compensationForm.dispatchEvent(new Event("submit"));
        });
    }

    if (printBtn) {
        printBtn.addEventListener("click", () => { window.print(); });
    }
});
