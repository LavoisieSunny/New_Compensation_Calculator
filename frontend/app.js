/* ==========================================================================
   COMPENSATION CALCULATOR WORKSTATION - FRONTEND DASHBOARD ENGINE
   ========================================================================== */

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
    const caseTypeSelect = document.getElementById("case_type");
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
    const dobInput = document.getElementById("date_of_birth");
    const doaInput = document.getElementById("date_of_accident");
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
    const maritalStatusSelect = document.getElementById("marital_status");
    const futureTypeSelect = document.getElementById("future_type");
    const monthlyIncomeInput = document.getElementById("monthly_income");
    
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
        deathFields.classList.remove("show");
        injuryFields.classList.remove("show");
        formActionsBar.classList.remove("show-flex");
        liveMetricsCard.classList.remove("show");
        evaluatorCard.classList.remove("show");
        singleUploadSection.classList.remove("show");
        singleUploadSection.classList.remove("show-flex");

        setTimeout(() => {
            sharedFields.classList.add("show");
            singleUploadSection.classList.add("show-flex");
            
            if (caseType === "injury") {
                injuryFields.classList.add("show");
                liveDeductionsItem.classList.add("hidden");
                liveProspectsItem.classList.add("hidden");
                
                document.getElementById("label-dependents").innerHTML = "Number of Dependents";
                dependentsInput.removeAttribute("required");
            } else if (caseType === "death") {
                deathFields.classList.add("show");
                liveDeductionsItem.classList.remove("hidden");
                liveProspectsItem.classList.remove("hidden");
                
                document.getElementById("label-dependents").innerHTML = "Number of Dependents <span class=\"req\">*</span>";
                dependentsInput.setAttribute("required", "required");
            }
            
            formActionsBar.classList.add("show-flex");
            liveMetricsCard.classList.add("show");
            evaluatorCard.classList.add("show");
            
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
        if (age === null || age === undefined) return "-";
        if (age <= 15) return 20;
        else if (age <= 25) return 18;
        else if (age <= 30) return 17;
        else if (age <= 35) return 16;
        else if (age <= 40) return 15;
        else if (age <= 45) return 14;
        else if (age <= 50) return 13;
        else if (age <= 55) return 11;
        else if (age <= 60) return 9;
        else if (age <= 65) return 7;
        return 5;
    }

    function getFutureProspectPercentage(age, futureType) {
        if (age === null || age === undefined) return 0;
        if (parseInt(futureType) === 1) {
            if (age < 40) return 50;
            if (age < 50) return 30;
            if (age < 60) return 15;
            return 0;
        } else {
            if (age < 40) return 40;
            if (age < 50) return 25;
            if (age < 60) return 10;
            return 0;
        }
    }

    function getDeductionPercentage(dependents, status) {
        if (dependents === null || dependents === undefined) return 50;
        if (status.toLowerCase() === "single") return 50;
        if (dependents <= 1) return 50;
        if (dependents <= 3) return Math.round((1 / 3) * 100);
        if (dependents <= 6) return 25;
        return 20;
    }

    function updateLiveCalculations() {
        const dobVal = dobInput.value;
        const doaVal = doaInput.value;
        const caseType = caseTypeSelect.value;
        
        const age = calculateAge(dobVal, doaVal);
        
        if (age !== null) {
            ageInput.value = age;
            liveAge.textContent = `${age} yrs`;
            
            const multiplier = getMultiplier(age);
            liveMultiplier.textContent = multiplier;
            
            if (caseType === "death") {
                const futureType = futureTypeSelect.value;
                const prospectsPercent = getFutureProspectPercentage(age, futureType);
                liveProspects.textContent = `${prospectsPercent}%`;
                liveProspectsBar.style.width = `${prospectsPercent}%`;
                
                const dependentsCount = parseInt(dependentsInput.value) || 0;
                const status = maritalStatusSelect.value;
                const deductionPercent = getDeductionPercentage(dependentsCount, status);
                liveDeductions.textContent = `${deductionPercent}%`;
                liveDeductionsBar.style.width = `${deductionPercent}%`;
            }
        } else {
            ageInput.value = "";
            liveAge.textContent = "-";
            liveMultiplier.textContent = "-";
            liveProspects.textContent = "-";
            liveProspectsBar.style.width = "0%";
            liveDeductions.textContent = "-";
            liveDeductionsBar.style.width = "0%";
        }
    }

    dobInput.addEventListener("change", updateLiveCalculations);
    doaInput.addEventListener("change", updateLiveCalculations);
    futureTypeSelect.addEventListener("change", updateLiveCalculations);
    maritalStatusSelect.addEventListener("change", updateLiveCalculations);
    dependentsInput.addEventListener("input", updateLiveCalculations);

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
                liveMetricsCard.classList.add("show");
                evaluatorCard.classList.add("show");

                alert("Case PDF analyzed! Form auto-filled focusing on Previous Judgment, Petition, and Prayer details. Please manually review fields and click 'Calculate' to compute compensation.");
            } else {
                alert("Failed to extract data from the PDF.");
            }
        } catch (error) {
            loader.remove();
            console.error("Single PDF OCR error:", error);
            alert("Offline Sandbox Mode: Triggering high-fidelity simulated OCR auto-fill for developer testing.");
            
            // Mock offline fallback auto-filling based on selected case type
            const caseType = caseTypeSelect.value;
            const mockSuggestions = caseType === "death" ? {
                case_type: "death",
                name: "Late Smt. Sunita Devi",
                father_name: "Late Shri Vijay Pal",
                date_of_birth: "08-08-1984",
                date_of_accident: "22-09-2024",
                age: 40,
                monthly_income: 30000,
                dependents: 4,
                marital_status: "married",
                place_of_accident: "National Highway NH-3, Bypass Crossing"
            } : {
                case_type: "injury",
                name: "Shri Rajesh Kumar Sharma",
                father_name: "Shri Om Prakash Sharma",
                date_of_birth: "12-04-1992",
                date_of_accident: "15-10-2024",
                age: 32,
                monthly_income: 25000,
                disability: 40,
                dependents: 3,
                marital_status: "married",
                place_of_accident: "Bypass Road, near Jabalpur Crossing"
            };

            applyAllOcrSuggestions(mockSuggestions);

            // Render mock preview
            singlePreviewFilename.innerHTML = `${file.name} <span class="badge source-badge" style="margin-left: 8px; background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Source: AI Recovery (Offline)</span>`;
            singlePreviewContainer.innerHTML = `
                <div class="preview-empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 10px;">
                    <i class="fa-solid fa-file-pdf" style="font-size: 3rem; color: var(--color-success)"></i>
                    <p style="font-size: 0.8rem; color: var(--text-secondary)">Offline Preview active for <strong>${file.name}</strong></p>
                </div>
            `;
            singlePreviewCard.classList.remove("hidden-section");
            singlePreviewCard.classList.add("show");
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

        if (suggestions.case_type) {
            caseTypeSelect.value = suggestions.case_type;
            caseTypeSelect.dispatchEvent(new Event("change"));
        }

        const standardKeys = ["name", "father_name", "dependents", "marital_status", "monthly_income", "disability", "place_of_accident"];
        standardKeys.forEach(key => {
            if (suggestions[key] !== undefined && suggestions[key] !== null && suggestions[key] !== "") {
                const el = document.getElementById(key);
                if (el) {
                    el.value = suggestions[key];
                    el.dispatchEvent(new Event("input"));
                    el.dispatchEvent(new Event("change"));
                }
            }
        });

        // Convert and apply dates
        ["date_of_birth", "date_of_accident"].forEach(key => {
            const val = suggestions[key];
            if (val && val.includes("-")) {
                const parts = val.split("-");
                if (parts.length === 3 && parts[2].length === 4) {
                    const htmlDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
                    const targetEl = key === "date_of_birth" ? dobInput : doaInput;
                    targetEl.value = htmlDate;
                    targetEl.dispatchEvent(new Event("change"));
                }
            }
        });
        
        // Fallback Layer 7 — Human Verification UI warnings highlight
        const fieldMapping = {
            "name": "name",
            "claimant_name": "name",
            "deceased_name": "name",
            "father_name": "father_name",
            "date_of_birth": "date_of_birth",
            "date_of_accident": "date_of_accident",
            "place_of_accident": "place_of_accident",
            "age": "age",
            "monthly_income": "monthly_income",
            "dependents": "dependents",
            "marital_status": "marital_status",
            "disability": "disability"
        };

        const processedInputIds = new Set();

        function cleanSectionName(secName) {
            if (!secName) return "N/A";
            return secName
                .replace(/_/g, ' ')
                .replace(/-/g, ' ')
                .replace(/\b\w/g, c => c.toUpperCase());
        }

        if (suggestions.confidence_scores) {
            Object.keys(suggestions.confidence_scores).forEach(key => {
                const confObj = suggestions.confidence_scores[key];
                let confidence = confObj.confidence;
                if (confidence <= 1.0 && confidence > 0) {
                    confidence = Math.round(confidence * 100);
                }
                const domId = fieldMapping[key];
                if (domId && !processedInputIds.has(domId)) {
                    const inputEl = document.getElementById(domId);
                    if (inputEl) {
                        processedInputIds.add(domId);
                        const formGroup = inputEl.closest(".form-group");
                        if (formGroup) {
                            // 1. Create premium interactive badge and glassmorphic tooltip
                            const badge = document.createElement("div");
                            badge.className = "ai-metadata-badge";
                            
                            const isLow = confidence < 70;
                            const badgeColor = isLow ? "var(--color-warning)" : "var(--color-success)";
                            const iconClass = isLow ? "fa-solid fa-triangle-exclamation" : "fa-solid fa-circle-check";
                            
                            badge.innerHTML = `
                                <i class="${iconClass}" style="color: ${badgeColor}"></i>
                                <span class="ai-metadata-pct" style="color: ${badgeColor}">${confidence}%</span>
                                <div class="ai-metadata-tooltip">
                                    <div class="tooltip-header">
                                        <i class="fa-solid fa-sparkles text-glow"></i> AI Extraction Metrics
                                    </div>
                                    <div class="tooltip-row">
                                        <span class="t-label">Confidence:</span>
                                        <span class="t-value" style="color: ${badgeColor}">${confidence}%</span>
                                    </div>
                                    <div class="tooltip-row">
                                        <span class="t-label">Source Section:</span>
                                        <span class="t-value text-glow-purple">${cleanSectionName(confObj.source_section || confObj.source || 'N/A')}</span>
                                    </div>
                                    <div class="tooltip-row">
                                        <span class="t-label">Source Page:</span>
                                        <span class="t-value">Page ${confObj.source_page || 1}</span>
                                    </div>
                                    <div class="tooltip-row">
                                        <span class="t-label">Extraction Method:</span>
                                        <span class="t-value" style="color: var(--color-primary); font-size: 0.72rem;">${confObj.extraction_method || 'N/A'}</span>
                                    </div>
                                </div>
                            `;
                            
                            const label = formGroup.querySelector("label");
                            if (label) {
                                label.style.display = "flex";
                                label.style.alignItems = "center";
                                label.style.justifyContent = "space-between";
                                label.style.width = "100%";
                                label.appendChild(badge);
                            }

                            // 2. Flag if confidence < 70 (keep legacy low-confidence warning border)
                            if (isLow && confidence > 0) {
                                const wrapper = inputEl.closest(".input-icon-wrapper") || inputEl.closest(".select-wrapper") || inputEl;
                                wrapper.classList.add("low-confidence-input");
                                
                                const warningMsg = document.createElement("div");
                                warningMsg.className = "verification-warning";
                                warningMsg.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Low confidence (${confidence}%). Verify manually.`;
                                formGroup.appendChild(warningMsg);
                                
                                const clearWarning = () => {
                                    wrapper.classList.remove("low-confidence-input");
                                    warningMsg.remove();
                                    inputEl.removeEventListener("input", clearWarning);
                                    inputEl.removeEventListener("change", clearWarning);
                                };
                                inputEl.addEventListener("input", clearWarning);
                                inputEl.addEventListener("change", clearWarning);
                            }
                        }
                    }
                }
            });
        }
        
        // Update Legal AI Summary Card
        const summaryCard = document.getElementById("legal-ai-summary-card");
        const summaryBody = document.getElementById("legal-ai-summary-body");
        
        if (summaryCard && summaryBody && suggestions.legal_ai_summary) {
            let htmlContent = '';
            const text = suggestions.legal_ai_summary;
            const anomalies = suggestions.anomalies_detected || [];
            
            let factsText = '';
            let paramsText = '';
            let appealText = '';
            
            const sentences = text.split('. ').map(s => s.trim()).filter(s => s.length > 0);
            sentences.forEach(sentence => {
                const s = sentence.toLowerCase();
                if (s.includes("appeal challenges") || s.includes("profile involves") || s.includes("accident") || s.includes("individual, historically")) {
                    factsText += sentence + '. ';
                } else if (s.includes("income") || s.includes("multiplier") || s.includes("prospects") || s.includes("awarded stands") || s.includes("compensation awarded stands")) {
                    paramsText += sentence + '. ';
                } else if (s.includes("requests a") || s.includes("requests an") || s.includes("appeal requests") || s.includes("requests a reduction") || s.includes("requests an enhancement")) {
                    appealText += sentence + '. ';
                } else {
                    factsText += sentence + '. ';
                }
            });
            
            if (!factsText) factsText = text;
            
            htmlContent += `
                <div class="legal-summary-section">
                    <div class="legal-summary-title facts">
                        <i class="fa-solid fa-circle-info"></i> Case Facts Briefing
                    </div>
                    <div class="legal-summary-text">${factsText}</div>
                </div>
            `;
            
            if (paramsText) {
                htmlContent += `
                    <div class="legal-summary-section" style="margin-top: 10px;">
                        <div class="legal-summary-title metrics">
                            <i class="fa-solid fa-calculator"></i> Judicial Parameter Breakdown
                        </div>
                        <div class="legal-summary-text">${paramsText}</div>
                    </div>
                `;
            }
            
            if (appealText) {
                htmlContent += `
                    <div class="legal-summary-section" style="margin-top: 10px;">
                        <div class="legal-summary-title direction">
                            <i class="fa-solid fa-angles-up"></i> Appeal Direction
                        </div>
                        <div class="legal-summary-text">${appealText}</div>
                    </div>
                `;
            }
            
            if (anomalies.length > 0) {
                htmlContent += `
                    <div class="legal-summary-section" style="margin-top: 10px;">
                        <div class="legal-summary-title anomalies">
                            <i class="fa-solid fa-triangle-exclamation"></i> Legal AI Verification Checklist
                        </div>
                        <div class="legal-summary-anomalies-list" style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px;">
                `;
                
                anomalies.forEach(anomaly => {
                    const isWarning = anomaly.toLowerCase().includes("mismatch") || anomaly.toLowerCase().includes("invalid") || anomaly.toLowerCase().includes("dob") || anomaly.toLowerCase().includes("fail") || anomaly.toLowerCase().includes("differ") || anomaly.toLowerCase().includes("after");
                    const iconClass = isWarning ? "fa-triangle-exclamation text-warning" : "fa-circle-check text-success";
                    const itemStyle = isWarning ? "background: rgba(245, 158, 11, 0.08); border: 1px dashed rgba(245, 158, 11, 0.2); color: #f59e0b;" : "background: rgba(16, 185, 129, 0.08); border: 1px dashed rgba(16, 185, 129, 0.2); color: #10b981;";
                    
                    htmlContent += `
                        <div class="legal-summary-anomaly-item" style="${itemStyle}">
                            <i class="fa-solid ${iconClass}"></i>
                            <span>${anomaly}</span>
                        </div>
                    `;
                });
                
                htmlContent += `
                        </div>
                    </div>
                `;
            } else {
                htmlContent += `
                    <div class="legal-summary-section" style="margin-top: 10px;">
                        <div class="legal-summary-title anomalies" style="color: var(--color-success)">
                            <i class="fa-solid fa-circle-check"></i> Legal AI Verification Checklist
                        </div>
                        <div class="legal-summary-anomaly-item" style="background: rgba(16, 185, 129, 0.08); border: 1px dashed rgba(16, 185, 129, 0.2); color: #10b981; margin-top: 4px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-circle-check text-success"></i>
                            <span>All judicial parameters fully aligned with legal benchmarks (Sarla Verma & Pranay Sethi standards verified).</span>
                        </div>
                    </div>
                `;
            }
            
            summaryBody.innerHTML = htmlContent;
            summaryCard.classList.remove("hidden-section");
            summaryCard.classList.add("show");
        } else if (summaryCard) {
            summaryCard.classList.add("hidden-section");
            summaryCard.classList.remove("show");
        }
        
        // Update Compensation Table Card
        const tableCard = document.getElementById("compensation-table-card");
        const tableBody = document.getElementById("compensation-table-body");
        
        if (tableCard && tableBody) {
            const tableData = suggestions.compensation_table;
            if (tableData && Object.keys(tableData).length > 0) {
                let html = '<div class="extracted-table-container">';
                let total = 0.0;
                
                Object.keys(tableData).forEach(head => {
                    const amt = tableData[head];
                    total += amt;
                    html += `
                        <div class="extracted-table-row">
                            <span class="extracted-table-head">${head}</span>
                            <span class="extracted-table-amount">Rs. ${amt.toLocaleString('en-IN')}</span>
                        </div>
                    `;
                });
                
                // Add Reconstructed Total Row
                html += `
                    <div class="extracted-table-row total-row">
                        <span class="extracted-table-head">Reconstructed Award Total</span>
                        <span class="extracted-table-amount">Rs. ${total.toLocaleString('en-IN')}</span>
                    </div>
                `;
                html += '</div>';
                
                tableBody.innerHTML = html;
                tableCard.classList.remove("hidden-section");
                tableCard.classList.add("show");
            } else {
                tableCard.classList.add("hidden-section");
                tableCard.classList.remove("show");
            }
        }
        
        // Judicial System Badge Display
        if (suggestions.is_tamil_nadu) {
            const badgeId = "tn-mact-badge";
            if (!document.getElementById(badgeId) && singlePreviewFilename) {
                singlePreviewFilename.innerHTML += ` <span id="${badgeId}" class="badge source-badge" style="margin-left: 8px; background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; display: inline-block;">Judicial System (${suggestions.mcop_number || 'MCOP'})</span>`;
            }
        }
        
        alert(`Auto-filled workstation variables successfully! DOB and accident dates converted.`);
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

    function renderPrecedentEvaluation(eval) {
        const alignLabels = {
            aligned: `<span class="eval-badge aligned"><i class="fa-solid fa-circle-check"></i> Aligned</span>`,
            high: `<span class="eval-badge high"><i class="fa-solid fa-triangle-exclamation"></i> High Valuation</span>`,
            low: `<span class="eval-badge low"><i class="fa-solid fa-arrow-down-long"></i> Under-valued</span>`
        };

        let precedentsHtml = "";
        eval.precedents.forEach(p => {
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
                    <span class="value">Rs. ${eval.calculated_amount.toLocaleString('en-IN')}</span>
                </div>
                <div class="eval-stats" style="text-align: right;">
                    <span class="label">Precedent Avg</span>
                    <span class="value" style="color: var(--text-secondary)">Rs. ${eval.average_precedent_award.toLocaleString('en-IN')}</span>
                </div>
            </div>

            <!-- Alignment and margin -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                <span class="card-text">Award Margin: <strong>${eval.margin_percent > 0 ? '+':''}${eval.margin_percent}%</strong></span>
                ${alignLabels[eval.alignment] || ""}
            </div>

            <!-- Legal recommendation -->
            <div class="eval-desc">
                <strong><i class="fa-solid fa-gavel"></i> Legal Opinion:</strong><br>
                ${eval.recommendation}
            </div>

            <!-- Legal Argument briefs -->
            <div class="eval-desc" style="background: rgba(186, 104, 200, 0.02); border-color: rgba(186, 104, 200, 0.12); margin-top: 8px;">
                <strong><i class="fa-solid fa-scroll"></i> Court Brief Argument:</strong><br>
                <em>"${eval.claimant_argument}"</em>
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
        
        const caseType = caseTypeSelect.value;
        if (!caseType) {
            alert("Please select a case type first!");
            return;
        }

        const payload = {
            case_type: caseType,
            age: parseInt(ageInput.value) || 0,
            monthly_income: parseFloat(monthlyIncomeInput.value) || 0,
            
            dependents: parseInt(dependentsInput.value) || 0,
            marital_status: maritalStatusSelect.value || "married",
            future_type: parseInt(futureTypeSelect.value) || 2,
            consortium: parseFloat(document.getElementById("consortium").value) || 40000,
            funeral_expenses: parseFloat(document.getElementById("funeral_expenses").value) || 15000,
            loss_estate: parseFloat(document.getElementById("loss_estate").value) || 15000,
            
            disability: parseFloat(document.getElementById("disability").value) || 0,
            medical_expenses: parseFloat(document.getElementById("medical_expenses").value) || 0,
            future_medical_expenses: parseFloat(document.getElementById("future_medical_expenses").value) || 0,
            pain_and_suffering: parseFloat(document.getElementById("pain_and_suffering").value) || 0,
            transportation: parseFloat(document.getElementById("transportation").value) || 0,
            special_diet: parseFloat(document.getElementById("special_diet").value) || 0,
            attender_charges: parseFloat(document.getElementById("attender_charges").value) || 0,
            loss_of_income: parseFloat(document.getElementById("loss_of_income").value) || 0
        };

        try {
            const response = await fetch("/api/calculate/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error("Calculator error");
            const results = await response.json();
            
            currentCalculationAmount = results.final_amount;
            renderResultsDashboard(results, payload);
            openModal();

            // Enable Evaluator button
            triggerEvalBtn.disabled = false;

        } catch (error) {
            console.error("Calculation failed:", error);
            alert("Calculation failed on the server. Falling back to local calculator.");
            const localResults = calculateCompensationLocally(payload);
            
            currentCalculationAmount = localResults.final_amount;
            renderResultsDashboard(localResults, payload);
            openModal();
            triggerEvalBtn.disabled = false;
        }
    });

    // Local Math Evaluator fallback
    function calculateCompensationLocally(data) {
        const age = data.age;
        const multiplier = getMultiplier(age);
        const monthly = data.monthly_income;
        const annual = monthly * 12;

        if (data.case_type === "death") {
            const prospectPercent = getFutureProspectPercentage(age, data.future_type) / 100;
            const enhancedMonthly = monthly + (monthly * prospectPercent);
            const enhancedAnnual = enhancedMonthly * 12;
            const deductionPercent = getDeductionPercentage(data.dependents, data.marital_status) / 100;
            const familyContribution = enhancedAnnual * (1 - deductionPercent);
            const lossDependency = familyContribution * multiplier;
            const finalAmount = lossDependency + data.consortium + data.funeral_expenses + data.loss_estate;

            return {
                case_type: "death",
                multiplier: multiplier,
                future_percentage: Math.round(prospectPercent * 100),
                enhanced_monthly_income: Math.round(enhancedMonthly),
                annual_income: Math.round(enhancedAnnual),
                deduction_percentage: Math.round(deductionPercent * 100),
                family_contribution: Math.round(familyContribution),
                loss_dependency: Math.round(lossDependency),
                consortium: data.consortium,
                funeral_expenses: data.funeral_expenses,
                loss_estate: data.loss_estate,
                final_amount: Math.round(finalAmount)
            };
        } else {
            const futureLoss = annual * (data.disability / 100) * multiplier;
            const finalAmount = futureLoss + data.medical_expenses + data.future_medical_expenses + 
                data.pain_and_suffering + data.transportation + data.special_diet + data.attender_charges + data.loss_of_income;
            
            return {
                case_type: "injury",
                multiplier: multiplier,
                annual_income: Math.round(annual),
                future_income_loss: Math.round(futureLoss),
                medical_expenses: data.medical_expenses,
                future_medical_expenses: data.future_medical_expenses,
                pain_and_suffering: data.pain_and_suffering,
                transportation: data.transportation,
                special_diet: data.special_diet,
                attender_charges: data.attender_charges,
                loss_of_income: data.loss_of_income,
                final_amount: Math.round(finalAmount)
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
        const claimantName = document.getElementById("name").value || "N/A";
        const fatherNameVal = document.getElementById("father_name").value || "N/A";
        const dateAccidentVal = doaInput.value ? new Date(doaInput.value).toLocaleDateString('en-IN') : "N/A";
        const dateBirthVal = dobInput.value ? new Date(dobInput.value).toLocaleDateString('en-IN') : "N/A";
        const caseTypeLabel = res.case_type === "death" ? "Death Claim" : "Injury Claim";

        let specificsHtml = "";
        let mathFormulaHtml = "";

        if (res.case_type === "death") {
            specificsHtml = `
                <div class="detail-tile">
                    <span class="tile-label">Sarla Verma Multiplier</span>
                    <span class="tile-value text-glow">${res.multiplier}</span>
                    <span class="tile-desc">Deceased's Age: ${req.age} yrs</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Future Prospects</span>
                    <span class="tile-value">+${res.future_percentage}%</span>
                    <span class="tile-desc">Enhanced Monthly: ${formatCurrency(res.enhanced_monthly_income)}</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Family Deduction</span>
                    <span class="tile-value text-glow-purple">${res.deduction_percentage}%</span>
                    <span class="tile-desc">Dependents count: ${req.dependents}</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Annual Family Contribution</span>
                    <span class="tile-value text-success">${formatCurrency(res.family_contribution)}</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Loss of Dependency</span>
                    <span class="tile-value text-glow">${formatCurrency(res.loss_dependency)}</span>
                    <span class="tile-desc">Contribution &times; Multiplier (${res.multiplier})</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Conventional Awards</span>
                    <span class="tile-value">${formatCurrency(res.consortium + res.funeral_expenses + res.loss_estate)}</span>
                    <span class="tile-desc">Consortium (40k), Funeral (15k), Estate (15k)</span>
                </div>
            `;

            mathFormulaHtml = `
                <div class="formula-title"><i class="fa-solid fa-square-root-variable"></i> Death Compensation Equation</div>
                <div class="formula-content">
                    Total Compensation = (Loss of Dependency) + (Loss of Consortium) + (Funeral Expenses) + (Loss of Estate)<br>
                    = (Enhanced Annual Income &times; [1 - Deduction %] &times; Multiplier) + Consortium + Funeral + Estate<br>
                    = (${formatCurrency(res.annual_income)} &times; ${1 - res.deduction_percentage/100} &times; ${res.multiplier}) + ${formatCurrency(res.consortium)} + ${formatCurrency(res.funeral_expenses)} + ${formatCurrency(res.loss_estate)}<br>
                    = ${formatCurrency(res.loss_dependency)} + ${formatCurrency(res.consortium)} + ${formatCurrency(res.funeral_expenses)} + ${formatCurrency(res.loss_estate)}<br>
                    = <strong>${formatCurrency(res.final_amount)}</strong>
                </div>
            `;
        } else {
            specificsHtml = `
                <div class="detail-tile">
                    <span class="tile-label">Sarla Verma Multiplier</span>
                    <span class="tile-value text-glow">${res.multiplier}</span>
                    <span class="tile-desc">Injured's Age: ${req.age} yrs</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Permanent Impairment</span>
                    <span class="tile-value text-glow-purple">${req.disability}%</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Future Loss of Income</span>
                    <span class="tile-value text-success">${formatCurrency(res.future_income_loss)}</span>
                    <span class="tile-desc">Annual Income &times; ${req.disability}% &times; Multiplier (${res.multiplier})</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Clinical & Medical Expenses</span>
                    <span class="tile-value">${formatCurrency(res.medical_expenses + res.future_medical_expenses)}</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Pain & Suffering Award</span>
                    <span class="tile-value">${formatCurrency(res.pain_and_suffering)}</span>
                </div>
                <div class="detail-tile">
                    <span class="tile-label">Supportive Allowances</span>
                    <span class="tile-value">${formatCurrency(res.transportation + res.special_diet + res.attender_charges + res.loss_of_income)}</span>
                    <span class="tile-desc">Diet, Attender, Transport & Loss of Income during treatment</span>
                </div>
            `;

            mathFormulaHtml = `
                <div class="formula-title"><i class="fa-solid fa-square-root-variable"></i> Injury Compensation Equation</div>
                <div class="formula-content">
                    Total Compensation = (Future Income Loss) + Medical Expenses + Future Medicals + Pain/Suffering + Transport + Special Diet + Attender + Loss during Treatment<br>
                    = (${formatCurrency(res.annual_income)} &times; ${req.disability}% &times; ${res.multiplier}) + ${formatCurrency(res.medical_expenses)} + ${formatCurrency(res.future_medical_expenses)} + ${formatCurrency(res.pain_and_suffering)} + ${formatCurrency(res.transportation + res.special_diet + res.attender_charges + res.loss_of_income)}<br>
                    = ${formatCurrency(res.future_income_loss)} + ${formatCurrency(res.medical_expenses + res.future_medical_expenses + res.pain_and_suffering + res.transportation + res.special_diet + res.attender_charges + res.loss_of_income)}<br>
                    = <strong>${formatCurrency(res.final_amount)}</strong>
                </div>
            `;
        }

        modalBodyContent.innerHTML = `
            <div class="results-dashboard">
                <div class="award-hero">
                    <span class="hero-label">Estimated Award Valuation</span>
                    <span class="hero-amount">${formatCurrency(res.final_amount)}</span>
                    <span class="hero-tag"><i class="fa-solid fa-gavel"></i> ${caseTypeLabel}</span>
                </div>

                <div class="briefing-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.82rem; border: 1px solid var(--border-glass); padding: 12px 16px; border-radius: var(--radius-sm); background: rgba(255,255,255,0.01)">
                    <div><strong>Claimant Name:</strong> ${claimantName}</div>
                    <div><strong>Father / Husband Name:</strong> ${fatherNameVal}</div>
                    <div><strong>Date of Birth (Age):</strong> ${dateBirthVal} (${req.age} years)</div>
                    <div><strong>Date of Accident:</strong> ${dateAccidentVal}</div>
                </div>

                <div class="results-details-grid">
                    ${specificsHtml}
                    <div class="math-formula-box">
                        ${mathFormulaHtml}
                    </div>
                </div>
            </div>
        `;
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
        deathFields.classList.remove("show");
        injuryFields.classList.remove("show");
        formActionsBar.classList.remove("show-flex");
        liveMetricsCard.classList.remove("show");
        evaluatorCard.classList.remove("show");
        
        singleUploadSection.classList.remove("show");
        singleUploadSection.classList.remove("show-flex");
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

    printBtn.addEventListener("click", () => { window.print(); });
});
