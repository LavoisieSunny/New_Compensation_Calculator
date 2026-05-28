/* ==========================================================================
   COMPENSATION CALCULATOR WORKSTATION - FRONTEND DASHBOARD ENGINE
   ========================================================================== */

// Global Error Handler to shield against silent crashes (Task 19)
window.onerror = function(msg, src, line, col, err) {
    console.error("GLOBAL ERROR DETECTED:", msg, "at", src, "line:", line, err);
};

document.addEventListener("DOMContentLoaded", () => {
    
    // --- STATE VARIABLES ---
    let activeTab = "calculator";
    let fileQueue = []; // Local file tracker
    let uploadedFileObjects = {}; // Maps filename -> File object for local blob previews
    let isPolling = false;
    let currentCalculationAmount = 0;
    
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
            chat: "AI Precedent Assistant & Semantic Search"
        };
        tabTitleText.textContent = titleMap[tabName] || "Compensation Calculator Workstation";
    }

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

        setTimeout(() => {
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
            
            updateLiveCalculations();
        }, 150);
    });

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
        const dobVal = dobInput.value;
        const doaVal = doaInput.value;
        
        const age = calculateAge(dobVal, doaVal);
        const caseType = caseTypeSelect.value;
        
        if (age !== null) {
            ageInput.value = age;
            if (liveAge) liveAge.textContent = `${age} years`;
            
            const mult = getMultiplier(age);
            if (liveMultiplier) liveMultiplier.textContent = mult;
            
            if (caseType === "death") {
                const futureType = futureTypeSelect ? futureTypeSelect.value : 2;
                const prospects = getFutureProspectPercentage(age, futureType);
                if (liveProspects) liveProspects.textContent = `${prospects}%`;
                if (liveProspectsBar) liveProspectsBar.style.width = `${prospects}%`;
                
                const futureProspectInput = document.getElementById("future-prospect");
                if (futureProspectInput) futureProspectInput.value = prospects;
                
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

                // Dynamic live calculations
                const monthlyIncome = parseFloat(monthlyIncomeInput.value) || 0;
                const annualIncome = monthlyIncome * 12;
                const futureIncome = annualIncome + (annualIncome * prospects / 100);
                const deductionAmount = futureIncome * deductionRatio;
                const dependencyIncome = futureIncome - deductionAmount;
                const lossOfDependency = dependencyIncome * mult;

                const consortium = parseFloat(document.getElementById("consortium")?.value) || 40000;
                const funeral = parseFloat(document.getElementById("funeral-expenses")?.value) || 15000;
                const lossEstate = parseFloat(document.getElementById("loss-estate")?.value) || 15000;
                const finalComp = lossOfDependency + consortium + funeral + lossEstate;

                // Populate read-only inputs
                const lossDepInput = document.getElementById("loss-of-dependency");
                if (lossDepInput) lossDepInput.value = Math.round(lossOfDependency);

                const finalDeathCompInput = document.getElementById("death-final-compensation");
                if (finalDeathCompInput) finalDeathCompInput.value = Math.round(finalComp);

                // Populate dynamic dashboard elements
                if (document.getElementById("live-calc-annual")) {
                    document.getElementById("live-calc-annual").textContent = formatCurrency(annualIncome);
                    document.getElementById("live-calc-future").textContent = formatCurrency(futureIncome);
                    document.getElementById("live-calc-deduct-pct").textContent = `${deductionsPercent}%`;
                    document.getElementById("live-calc-deduct-amt").textContent = formatCurrency(deductionAmount);
                    document.getElementById("live-calc-multiplier").textContent = mult;
                    document.getElementById("live-calc-dependency").textContent = formatCurrency(lossOfDependency);
                    document.getElementById("live-calc-total").textContent = formatCurrency(finalComp);
                }

            } else {
                if (liveProspects) liveProspects.textContent = "—%";
                if (liveProspectsBar) liveProspectsBar.style.width = "0%";
                if (liveDeductions) liveDeductions.textContent = "—%";
                if (liveDeductionsBar) liveDeductionsBar.style.width = "0%";
            }
        } else {
            ageInput.value = "";
            if (liveAge) liveAge.textContent = "—";
            if (liveMultiplier) liveMultiplier.textContent = "—";
            if (liveProspects) liveProspects.textContent = "—%";
            if (liveProspectsBar) liveProspectsBar.style.width = "0%";
            if (liveDeductions) liveDeductions.textContent = "—%";
            if (liveDeductionsBar) liveDeductionsBar.style.width = "0%";

            // Clear dynamic dashboard elements
            if (caseType === "death" && document.getElementById("live-calc-annual")) {
                document.getElementById("live-calc-annual").textContent = "—";
                document.getElementById("live-calc-future").textContent = "—";
                document.getElementById("live-calc-deduct-pct").textContent = "—";
                document.getElementById("live-calc-deduct-amt").textContent = "—";
                document.getElementById("live-calc-multiplier").textContent = "—";
                document.getElementById("live-calc-dependency").textContent = "—";
                document.getElementById("live-calc-total").textContent = "—";
            }
        }
    }

    if (futureTypeSelect) {
        futureTypeSelect.addEventListener("change", updateLiveCalculations);
    }

    dobInput.addEventListener("change", updateLiveCalculations);
    doaInput.addEventListener("change", updateLiveCalculations);
    maritalStatusSelect.addEventListener("change", updateLiveCalculations);
    dependentsInput.addEventListener("input", updateLiveCalculations);
    monthlyIncomeInput.addEventListener("input", updateLiveCalculations);
    
    // Set dynamic update bindings for new Death Claim inputs
    setTimeout(() => {
        const consInput = document.getElementById("consortium");
        const funInput = document.getElementById("funeral-expenses");
        const estInput = document.getElementById("loss-estate");
        
        if (consInput) consInput.addEventListener("input", updateLiveCalculations);
        if (funInput) funInput.addEventListener("input", updateLiveCalculations);
        if (estInput) estInput.addEventListener("input", updateLiveCalculations);
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

    ["dragleave", "drop"].forEach(eventName => {
        singleDropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            singleDropZone.classList.remove("dragover");
        }, false);
    });

    singleDropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleSinglePdfUpload(files[0]);
        }
    });

    singleDropZone.addEventListener("click", () => {
        singleFileInput.click();
    });

    singleFileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleSinglePdfUpload(e.target.files[0]);
        }
    });

    async function handleSinglePdfUpload(file) {
        if (file.type !== "application/pdf") {
            alert("Please upload a valid legal PDF case document.");
            return;
        }

        // Show a premium glassmorphic loading spinner inside the form panel
        const formPanel = document.querySelector("#tab-calculator .panel.scroll-y");
        const loader = document.createElement("div");
        loader.className = "form-ocr-loader";
        loader.innerHTML = `
            <div class="spinner-glow"></div>
            <p>Analyzing document with legal OCR...</p>
            <span style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">Extracting Judgment, Petition, &amp; Prayer sections</span>
        `;
        formPanel.style.position = "relative";
        formPanel.appendChild(loader);

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

            const data = await response.json();
            
            // Remove spinner
            loader.remove();

            if (data.success) {
                // Apply OCR suggestions automatically
                applyAllOcrSuggestions(data.suggestions);

                // Load high-fidelity PDF preview in the right pane!
                const blobUrl = URL.createObjectURL(file);
                singlePreviewFilename.innerHTML = `${file.name} <span class="badge source-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: ${data.fallback_source}</span>`;
                singlePreviewContainer.innerHTML = `
                    <iframe class="pdf-iframe" src="${blobUrl}#toolbar=0" width="100%" height="100%"></iframe>
                `;
                singlePreviewCard.classList.remove("hidden-section");
                singlePreviewCard.classList.add("show");

                // Highlight and show the live metrics and precedents cards
                if (liveMetricsCard) liveMetricsCard.classList.add("show");
                if (evaluatorCard) evaluatorCard.classList.add("show");

                showToast("Case PDF analyzed! Form auto-filled focusing on Previous Judgment, Petition, and Prayer details. Please manually review fields.", "success");
            } else {
                showToast("Failed to extract data from the PDF: " + (data.message || "Unknown OCR error."), "error");
            }
        } catch (error) {
            loader.remove();
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

    ["dragleave", "drop"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("dragover");
        }, false);
    });

    dropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleBatchUpload(files);
        }
    });

    dropZone.addEventListener("click", () => {
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleBatchUpload(e.target.files);
        }
    });

    // Upload batch files
    async function handleBatchUpload(files) {
        const formData = new FormData();
        let validPdfCount = 0;

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (file.type === "application/pdf") {
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
            queueBadge.classList.add("hidden");
            queueCountLabel.textContent = "0 Files";
            return;
        }

        batchFileList.innerHTML = "";
        queueBadge.classList.remove("hidden");
        queueBadge.textContent = fileQueue.length;
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
                    </div>
                ` : ""}
            `;

            // Bind click to previews
            item.addEventListener("click", (e) => {
                // Prevent trigger if they click the autofill button specifically
                if (e.target.closest(".autofill-queue-btn")) return;
                
                document.querySelectorAll(".batch-file-item").forEach(c => c.classList.remove("active-preview"));
                item.classList.add("active-preview");
                loadPdfPreview(file.filename);
            });

            batchFileList.appendChild(item);
        });

        // Bind clicks on autofill buttons
        document.querySelectorAll(".autofill-queue-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const id = btn.getAttribute("data-id");
                const matchedFile = fileQueue.find(f => f.file_id === id);
                if (matchedFile && matchedFile.suggestions) {
                    applyAllOcrSuggestions(matchedFile.suggestions);
                    switchTab("calculator");
                }
            });
        });
    }

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
                        }
                    });

                    renderQueueList();
                }
            } catch (error) {
                console.error("Queue status polling failed:", error);
            }
        }, 1500);
    }

    // Apply parsed suggestions
    function applyAllOcrSuggestions(suggestions) {
        // Clear all previous low-confidence warning labels, styles, and AI metadata badges
        document.querySelectorAll(".verification-warning").forEach(el => el.remove());
        document.querySelectorAll(".low-confidence-input").forEach(el => el.classList.remove("low-confidence-input"));
        document.querySelectorAll(".ai-metadata-badge").forEach(el => el.remove());

        // Extract case type
        const caseType = suggestions.case_type;
        if (caseType) {
            caseTypeSelect.value = caseType;
            caseTypeSelect.dispatchEvent(new Event("change"));
        }

        const fields = suggestions.fields || {};

        // Helper to map incoming clean fields to the corresponding DOM element IDs
        const fieldMapping = {
            "deceased_name": "name",
            "injured_name": "name",
            "father_name": "father-name",
            "place_of_accident": "place-of-accident",
            "age": "age",
            "monthly_income": "monthly-income",
            "dependents": "dependents",
            "marital_status": "marital-status",
            "future_prospect": "future-prospect",
            "disability": "disability",
            "medical_expenses": "medical-expenses",
            "future_medical_expenses": "future-medical-expenses",
            "pain_and_suffering": "pain-and-suffering",
            "transportation": "transportation",
            "special_diet": "special-diet",
            "attender_charges": "attender-charges",
            "loss_of_income": "loss-of-income"
        };

        // Populate form inputs
        Object.keys(fieldMapping).forEach(apiKey => {
            const domId = fieldMapping[apiKey];
            const val = fields[apiKey];
            if (val !== undefined && val !== null && val !== "") {
                const el = document.getElementById(domId);
                if (el) {
                    el.value = val;
                    el.dispatchEvent(new Event("input"));
                    el.dispatchEvent(new Event("change"));
                }
            }
        });

        // Convert and apply dates
        ["date_of_birth", "date_of_accident"].forEach(key => {
            const val = fields[key];
            if (val && val.includes("-")) {
                const parts = val.split("-");
                if (parts.length === 3 && parts[2].length === 4) {
                    const htmlDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
                    const targetEl = key === "date_of_birth" ? dobInput : doaInput;
                    if (targetEl) {
                        targetEl.value = htmlDate;
                        targetEl.dispatchEvent(new Event("change"));
                    }
                }
            }
        });
        
        alert(`Auto-filled workstation variables successfully! DOB and accident dates converted.`);
        
        // Auto trigger automatic recalculation after autofill is completed (Task 18)
        setTimeout(() => {
            console.log("AUTO RECALCULATING after OCR autofill...");
            if (compensationForm) {
                compensationForm.dispatchEvent(new Event("submit"));
            }
        }, 500);
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
            const response = await fetch("/api/search/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: query,
                    case_type: chatCaseFilter.value
                })
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
            evaluatorCardBody.innerHTML = `
                <div class="empty-state" style="padding: 10px 0;">
                    <i class="fa-solid fa-spinner fa-spin fa-2x" style="color: var(--color-primary);"></i>
                    <p>Generating query embeddings & fetching precedents from Qdrant vector database...</p>
                </div>
            `;

            const caseType = caseTypeSelect.value;
            const payload = {
                params: {
                    case_type: caseType,
                    age: parseInt(ageInput.value) || 0,
                    monthly_income: parseFloat(monthlyIncomeInput.value) || 0,
                    dependents: parseInt(dependentsInput.value) || 0,
                    marital_status: maritalStatusSelect.value || "married",
                    disability: parseFloat(document.getElementById("disability").value) || 0,
                    name: document.getElementById("name").value || "Claimant"
                },
                calculated_amount: currentCalculationAmount
            };

            try {
                const response = await fetch("/api/search/evaluate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) throw new Error("Evaluation failed");
                const data = await response.json();
                
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
                ? `Calculated award is extremely well-aligned with precedents (${margin > 0 ? '+':''}${margin.toFixed(1)}% margin).`
                : `Calculated award is ${Math.abs(margin).toFixed(1)}% ${margin > 0 ? 'higher':'lower'} than precedent averages.`,
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
                <span class="card-text">Award Margin: <strong>${evalData.margin_percent > 0 ? '+':''}${evalData.margin_percent}%</strong></span>
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

        const payload = {
            case_type: caseType,
            age: Number(ageInput.value || 0),
            monthly_income: Number(monthlyIncomeInput.value || 0),
            
            dependents: Number(dependentsInput.value || 0),
            marital_status: maritalStatusSelect.value || "married",
            future_type: Number(futureTypeSelect?.value || 2),
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
            const annualIncome = monthly * 12;
            const futureIncome = annualIncome + (annualIncome * futureProspect / 100);
            const deductionRatio = getDeductionRatio(data.dependents, data.marital_status);
            const deductionPercent = Math.round(deductionRatio * 100);
            const deductionAmount = futureIncome * deductionRatio;
            const dependencyIncome = futureIncome - deductionAmount;
            const lossOfDependency = dependencyIncome * multiplier;
            const finalCompensation = lossOfDependency + data.consortium + data.funeral_expenses + data.loss_estate;

            return {
                case_type: "death",
                multiplier: multiplier,
                future_prospect_percentage: Math.round(futureProspect),
                future_percentage: Math.round(futureProspect),
                monthly_income: Math.round(monthly),
                annual_income: Math.round(annualIncome),
                future_income: Math.round(futureIncome),
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

    function renderResultsDashboard(res, req) {
        const claimantName = document.getElementById("name")?.value || "N/A";
        const fatherNameVal = document.getElementById("father-name")?.value || "N/A";
        const dateAccidentVal = doaInput.value ? new Date(doaInput.value).toLocaleDateString('en-IN') : "N/A";
        const dateBirthVal = dobInput.value ? new Date(dobInput.value).toLocaleDateString('en-IN') : "N/A";
        const placeAccidentVal = document.getElementById("place-of-accident")?.value || "N/A";
        const caseTypeLabel = res.case_type === "death" ? "Death Claim" : "Injury Claim";

        let parametersHtml = "";
        if (res.case_type === "death") {
            const futureProspectPercent = res.future_prospect_percentage !== undefined ? res.future_prospect_percentage : (res.future_percentage || 0);
            const futureIncomeVal = res.future_income !== undefined ? res.future_income : (req.monthly_income * 12 * (1 + futureProspectPercent / 100));
            const annualIncomeVal = res.annual_income !== undefined ? res.annual_income : (req.monthly_income * 12);
            
            parametersHtml = `
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Annual Income</span>
                    <strong>${formatCurrency(annualIncomeVal)}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Future Prospect Added</span>
                    <strong>+${futureProspectPercent}% (${formatCurrency(futureIncomeVal - annualIncomeVal)})</strong>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-glass);">
                    <span>Deduction Applied</span>
                    <strong>${res.deduction_percentage}% (-${formatCurrency(res.deduction_amount)})</strong>
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
        
        // Clear AI metadata badges
        document.querySelectorAll(".ai-metadata-badge").forEach(el => el.remove());
        
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
        
        caseTypeSelect.value = "";
    });

    // ==========================================================================
    // FLOATING TOOLBAR & SLIDE-OVER OVERLAY CONTROLLER
    // ==========================================================================
    const slideover = document.getElementById("right-slideover");
    const slideoverTitle = document.getElementById("slideover-title");
    const closeSlideover = document.getElementById("close-slideover");
    const toolbarButtons = document.querySelectorAll(".floating-tool-btn");
    const tabContents = document.querySelectorAll(".slideover-tab-content");

    const tabTitleMapping = {
        "summary": "AI Legal Summary Briefing",
        "table": "Extracted Compensation Table",
        "heuristics": "Dynamic Legal Heuristics",
        "benchmarks": "Qdrant Precedents Benchmark"
    };

    const tabIdMapping = {
        "summary": "legal-ai-summary-card",
        "table": "compensation-table-card",
        "heuristics": "live-metrics-card",
        "benchmarks": "evaluator-card"
    };

    toolbarButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetPanel = btn.getAttribute("data-panel");
            const targetCardId = tabIdMapping[targetPanel];

            // If the panel is already open and we clicked the same button, close it
            if (btn.classList.contains("active") && slideover.classList.contains("open")) {
                closeDrawer();
                return;
            }

            // Set active states on buttons
            toolbarButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            // Update slide-over title
            slideoverTitle.textContent = tabTitleMapping[targetPanel] || "Information Desk";

            // Switch tab content visibility inside slideover
            tabContents.forEach(content => {
                if (content.getAttribute("id") === targetCardId) {
                    content.classList.remove("tab-hidden");
                } else {
                    content.classList.add("tab-hidden");
                }
            });

            // Open drawer
            slideover.classList.add("open");
        });
    });

    function closeDrawer() {
        if (slideover) slideover.classList.remove("open");
        toolbarButtons.forEach(b => b.classList.remove("active"));
    }

    if (closeSlideover) {
        closeSlideover.addEventListener("click", closeDrawer);
    }

    // Escape key listener to close drawer
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeDrawer();
        }
    });

    // Explicit Calculate Button Click Handler & Logger (Task 1 & Task 2)
    const calculateBtn = document.getElementById("calculate-btn");
    if (calculateBtn) {
        console.log("CALCULATE BUTTON FOUND");
        calculateBtn.addEventListener("click", (e) => {
            console.log("CALCULATE CLICKED");
            compensationForm.dispatchEvent(new Event("submit"));
        });
    }

    printBtn.addEventListener("click", () => { window.print(); });
});
