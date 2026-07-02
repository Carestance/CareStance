
    
    const interestOptions = Object.keys(phase1Inputs.interest_selection_mapping || {}).sort();
    const incomeOptions = Object.keys(phase1Inputs.family_income_mapping || {});
    const occupationOptions = Object.keys(phase1Inputs.occupation_category_mapping || {}).sort();

    let assessmentState = {};
    let activePhaseData = null;
    let swipeLogs = [];
    let swipeCards = [];
    let activeSwipeIndex = 0;
    
    // Voice synthesizers
    let speechSynth = window.speechSynthesis;
    let activeUtterance = null;

    document.addEventListener("DOMContentLoaded", async () => {
        await refreshState();
    });

    async function refreshState() {
        showLoader("Retrieving pipeline states...");
        try {
            const res = await fetch("/assessment/api/state");
            const data = await res.json();
            if (data.status === "success") {
                assessmentState = data;
                updateHeader();
                await loadPhase();
            } else {
                window.location.href = "/dashboard";
            }
        } catch (e) {
            console.error("Critical: Failed to resolve phase nodes", e);
            hideLoader();
        }
    }

    function showLoader(text = "Processing...") {
        document.getElementById("loader-text").innerText = text;
        const loader = document.getElementById("loader");
        loader.style.opacity = "1";
        loader.style.pointerEvents = "auto";
        loader.classList.remove("hidden");
    }

    function hideLoader() {
        const loader = document.getElementById("loader");
        loader.style.opacity = "0";
        loader.style.pointerEvents = "none";
        setTimeout(() => loader.classList.add("hidden"), 300);
    }

    function updateHeader() {
        const isG12 = assessmentState.student_type === "12th";
        
        const gradeTitle = document.getElementById("grade-title");
        if (gradeTitle) {
            gradeTitle.innerText = isG12 ? "Grade 12 Career Track" : "Grade 10 Stream Planner";
        }
        
        let phaseName = "Student Information Intake";
        if (assessmentState.current_phase === 1) phaseName = "Behavioral Assessment";
        if (assessmentState.current_phase === 2) phaseName = "Career Matching";
        
        document.getElementById("phase-step-label").innerText = phaseName;
        
        // Progress percentage calculation
        let percent = 33;
        if (assessmentState.current_phase === 1) percent = 66;
        if (assessmentState.current_phase === 2) percent = 100;
        
        document.getElementById("global-progress-fill").style.width = `${percent}%`;
        
        const subtitleTracker = document.getElementById("subtitle-tracker");
        if (subtitleTracker) {
            subtitleTracker.innerText = phaseName;
        }
    }

    async function loadPhase() {
        const phase = assessmentState.current_phase;
        
        if (speechSynth.speaking) speechSynth.cancel();

        try {
            const body = document.getElementById("phase-body");
            body.innerHTML = "";

            if (phase === 0) {
                renderIntakePhase();
                hideLoader();
            } else if (phase === 1) {
                renderPhase2MCQs();
            } else if (phase === 2 || phase === 5) {
                // If it hits 2 or 5, just compile. 
                renderCompilePhase();
                hideLoader();
            }
        } catch (e) {
            console.error("Critical failure during question load state", e);
            hideLoader();
        }
    }

    function speakActivePrompt() {}


    // --- PHASE 0: CLINICAL CONVERSATIONAL INTAKE ---

    function toggleInterest(val, btn) {
        const select = document.getElementById('hidden-interests');
        let option = Array.from(select.options).find(opt => opt.value === val);
        if (!option) return;
        
        if (option.selected) {
            option.selected = false;
            btn.classList.remove('bg-teal-600', 'text-white', 'border-teal-600', 'shadow-md');
            btn.classList.add('text-slate-600', 'border-slate-200', 'hover:bg-slate-50', 'hover:border-teal-300');
        } else {
            if (select.selectedOptions.length >= 4) {
                btn.classList.add('animate-pulse', 'bg-red-50', 'border-red-300');
                setTimeout(() => btn.classList.remove('animate-pulse', 'bg-red-50', 'border-red-300'), 400);
                return;
            }
            option.selected = true;
            btn.classList.add('bg-teal-600', 'text-white', 'border-teal-600', 'shadow-md');
            btn.classList.remove('text-slate-600', 'border-slate-200', 'hover:bg-slate-50', 'hover:border-teal-300');
        }
        
        if (select.selectedOptions.length > 0) {
            const container = document.getElementById('interests-container');
            if(container) container.classList.remove('border-red-400');
            const err = container?.parentElement?.querySelector('.error-msg');
            if(err) err.classList.add('hidden');
        }
    }
    function renderIntakePhase() {
        const body = document.getElementById("phase-body");
        body.innerHTML = `
            <div class="stagger-in max-w-3xl mx-auto">
                <!-- Header Title block -->
                <div class="mb-8 text-center md:text-left">
                    <span class="cyber-badge mb-2">Phase 1: Student Intake</span>
                    <h2 class="text-3xl font-extrabold text-slate-900 mt-1">Let's get to know you better</h2>
                    <p class="text-slate-500 text-sm mt-1">We'll ask you a few questions to understand you better and provide personalized insights.</p>
                </div>

                <!-- Alert Box -->
                <div class="bg-teal-50 border border-teal-100/80 text-teal-800 rounded-2xl p-4 mb-8 flex items-center gap-3 text-sm">
                    <i class="fas fa-info-circle text-teal-600 text-lg"></i>
                    <span>Your information is safe with us and will only be used to guide your career journey.</span>
                </div>

                <!-- Form Rows -->
                <form id="intake-form" onsubmit="submitIntakeForm(event)" class="space-y-6">
                    <!-- Row 1: Full Name -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-user"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">What is your full name?</h4>
                                <p class="text-slate-400 text-xs">Please enter your full name.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <input type="text" name="name" required placeholder="Enter your full name" 
                                class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:bg-white focus:outline-none text-sm transition-all">
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please enter a valid name (at least 2 characters).</div>
                        </div>
                    </div>

                    <!-- Row 2: Currently Pursuing -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-graduation-cap"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">What are you currently pursuing?</h4>
                                <p class="text-slate-400 text-xs">Select your current class/education level.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <input type="text" name="pursuing" required placeholder="Enter current education (e.g. Grade 12)" 
                                class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:bg-white focus:outline-none text-sm transition-all">
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please enter your current studies (at least 2 characters).</div>
                        </div>
                    </div>

                    <!-- Row 3: Areas of Interest -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-star"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">Which areas interest you the most?</h4>
                                <p class="text-slate-400 text-xs">Choose up to four areas you would enjoy exploring.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <select name="interests" multiple required class="hidden" id="hidden-interests">
                                ${interestOptions.map(opt => `<option value="${opt}">${opt}</option>`).join("")}
                            </select>
                            <div class="flex flex-wrap gap-2 max-h-52 overflow-y-auto p-1 border-2 border-transparent rounded-xl" id="interests-container">
                                ${interestOptions.map(opt => `
                                    <button type="button" 
                                        onclick="toggleInterest('${opt}', this)"
                                        class="px-3 py-1.5 rounded-full border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-50 hover:border-teal-300 transition-all text-left select-none">
                                        ${opt}
                                    </button>
                                `).join("")}
                            </div>
                            <div class="text-xs text-slate-400 mt-2">Select up to 4 areas</div>
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please select 1 to 4 interests.</div>
                        </div>
                    </div>

                    <!-- Row 4: Family Income -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-money-bill-wave"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">Family Income Range</h4>
                                <p class="text-slate-400 text-xs">Select your family's annual income bracket.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <select name="family_income" required class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:border-teal-500 focus:outline-none text-sm transition-all">
                                <option value="" disabled selected>Select an option...</option>
                                ${incomeOptions.map(opt => `<option value="${opt}">${opt}</option>`).join("")}
                            </select>
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please select an income range.</div>
                        </div>
                    </div>

                    <!-- Row 5: Father's Occupation -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-user-tie"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">Father's Occupation</h4>
                                <p class="text-slate-400 text-xs">Select primary occupation.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <select name="father_occupation" required class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:border-teal-500 focus:outline-none text-sm transition-all">
                                <option value="" disabled selected>Select an option...</option>
                                ${occupationOptions.map(opt => `<option value="${opt}">${opt}</option>`).join("")}
                            </select>
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please select an occupation.</div>
                        </div>
                    </div>

                    <!-- Row 6: Mother's Occupation -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-user-nurse"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">Mother's Occupation</h4>
                                <p class="text-slate-400 text-xs">Select primary occupation.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <select name="mother_occupation" required class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:border-teal-500 focus:outline-none text-sm transition-all">
                                <option value="" disabled selected>Select an option...</option>
                                ${occupationOptions.map(opt => `<option value="${opt}">${opt}</option>`).join("")}
                            </select>
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please select an occupation.</div>
                        </div>
                    </div>

                    <!-- Row 7: Salary Priority (Career Choice) -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between p-5 bg-slate-50/40 border border-slate-100 rounded-2xl gap-4 hover:border-teal-500/10 transition-all duration-300">
                        <div class="flex items-center gap-4">
                            <div class="h-12 w-12 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-wallet"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-slate-900">What matters most to you?</h4>
                                <p class="text-slate-400 text-xs">When choosing a future career.</p>
                            </div>
                        </div>
                        <div class="w-full md:w-80">
                            <select name="salary_priority" required class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:border-teal-500 focus:outline-none text-sm transition-all">
                                <option value="" disabled selected>Select an option...</option>
                                <option value="high_salary">High salary and financial growth</option>
                                <option value="balanced">A balance of salary, interest, and stability</option>
                                <option value="meaningful_work">Interest, purpose, and meaningful work</option>
                                <option value="unsure">I am still exploring</option>
                            </select>
                            <div class="error-msg text-red-500 text-xs mt-1 hidden">Please select a priority.</div>
                        </div>
                    </div>

                    <!-- Footer Control Bar -->
                    <div class="flex justify-between items-center pt-6 border-t border-slate-100 mt-8">
                        <div class="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                            <i class="fas fa-shield-alt text-teal-600"></i> Secure & Confidential
                        </div>
                        <button type="submit" id="intake-submit-btn" class="px-8 py-3.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold transition-all text-sm flex items-center gap-2 shadow-md shadow-teal-600/10">
                            Save & Continue <i class="fas fa-arrow-right"></i>
                        </button>
                    </div>
                </form>
            </div>
        `;
    }

    async function submitIntakeForm(event) {
        event.preventDefault();
        const form = event.target;
        const submitBtn = document.getElementById("intake-submit-btn");
        
        const nameVal = form.name.value.trim();
        const pursuingVal = form.pursuing.value.trim();
        const interestsSelect = Array.from(form.interests.selectedOptions).map(opt => opt.value);
        const familyIncomeVal = form.family_income.value;
        const fatherOccupationVal = form.father_occupation.value;
        const motherOccupationVal = form.mother_occupation.value;
        const salaryPriorityVal = form.salary_priority.value;
        
        let isValid = true;
        
        function toggleError(inputName, show) {
            const input = form[inputName];
            const error = (input.parentElement || document.getElementById('interests-container').parentElement).querySelector('.error-msg');
            
            let targetEl = input;
            if (inputName === 'interests') {
                targetEl = document.getElementById('interests-container');
            }

            if (show) {
                if (targetEl && targetEl.classList) targetEl.classList.add("border-red-400");
                if (error) error.classList.remove("hidden");
                isValid = false;
            } else {
                if (targetEl && targetEl.classList) targetEl.classList.remove("border-red-400");
                if (error) error.classList.add("hidden");
            }
        }
        
        if (nameVal.length < 2) toggleError("name", true);
        else toggleError("name", false);
        
        if (pursuingVal.length < 2) toggleError("pursuing", true);
        else toggleError("pursuing", false);
        
        if (interestsSelect.length === 0) toggleError("interests", true);
        else toggleError("interests", false);
        
        if (!familyIncomeVal) toggleError("family_income", true);
        else toggleError("family_income", false);
        
        if (!fatherOccupationVal) toggleError("father_occupation", true);
        else toggleError("father_occupation", false);
        
        if (!motherOccupationVal) toggleError("mother_occupation", true);
        else toggleError("mother_occupation", false);
        
        if (!salaryPriorityVal) toggleError("salary_priority", true);
        else toggleError("salary_priority", false);
        
        if (!isValid) return;
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fas fa-spinner animate-spin"></i> Processing...`;
        
        document.getElementById("bottom-status").innerHTML = `<span class="h-2 w-2 rounded-full bg-cyan-400 animate-ping"></span> Querying extraction pipeline...`;
        
        try {
            const res = await fetch("/assessment/api/intake", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: nameVal,
                    pursuing: pursuingVal,
                    interests: interestsSelect,
                    family_income: familyIncomeVal,
                    father_occupation: fatherOccupationVal,
                    mother_occupation: motherOccupationVal,
                    salary_priority: salaryPriorityVal
                })
            });
            const data = await res.json();
            
            document.getElementById("bottom-status").innerHTML = `<span class="h-2 w-2 rounded-full bg-cyan-400 animate-ping"></span> Sync Ready`;
            
            if (data.status === "success") {
                setTimeout(async () => {
                    await refreshState();
                }, 800);
            } else {
                alert("Failed to submit intake. Please verify your data and try again.");
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Save & Continue <i class="fas fa-arrow-right"></i>`;
            }
        } catch (e) {
            console.error(e);
            document.getElementById("bottom-status").innerHTML = `Extraction Error`;
            submitBtn.disabled = false;
            submitBtn.innerHTML = `Save & Continue <i class="fas fa-arrow-right"></i>`;
        }
    }

    // --- PHASE 1: REFLEX PREFERENCE CARD SWIPES (BOTH) ---
    

    // --- PHASE 1: BEHAVIORAL MCQs ---
    let phase2Questions = [];
    let currentQuestionIdx = 0;
    let phase2Answers = [];
    let currentLang = 'en';

    window.togglePhase2Lang = function(lang) {
        currentLang = lang;
        document.querySelectorAll('.lang-en').forEach(el => el.classList.toggle('hidden', lang !== 'en'));
        document.querySelectorAll('.lang-hi').forEach(el => el.classList.toggle('hidden', lang !== 'hi'));
        
        const btnEn = document.getElementById('btn-lang-en');
        const btnHi = document.getElementById('btn-lang-hi');
        const activeClass = "px-4 py-1.5 text-sm font-bold rounded-full bg-teal-600 text-white shadow-sm transition-all";
        const inactiveClass = "px-4 py-1.5 text-sm font-medium rounded-full bg-white text-slate-500 border border-slate-200 hover:bg-slate-50 transition-all";
        
        if (btnEn && btnHi) {
            if (lang === 'en') {
                btnEn.className = activeClass;
                btnHi.className = inactiveClass;
            } else {
                btnEn.className = inactiveClass;
                btnHi.className = activeClass;
            }
        }
    };

    async function renderPhase2MCQs() {
        showLoader("Loading behavioral assessment...");
        try {
            const res = await fetch("/assessment/api/phase2_mcqs");
            const data = await res.json();
            if (data.status === "success") {
                phase2Questions = data.mcqs;
                currentQuestionIdx = 0;
                phase2Answers = [];
                hideLoader();
                renderCurrentMCQ();
            } else {
                hideLoader();
                alert("Failed to load questions.");
            }
        } catch (e) {
            console.error(e);
            hideLoader();
        }
    }

    function renderCurrentMCQ() {
        const body = document.getElementById("phase-body");
        if (currentQuestionIdx >= phase2Questions.length) {
            submitPhase2Answers();
            return;
        }

        const q = phase2Questions[currentQuestionIdx];
        
        const enClass = currentLang === 'en' ? "px-4 py-1.5 text-sm font-bold rounded-full bg-teal-600 text-white shadow-sm transition-all" : "px-4 py-1.5 text-sm font-medium rounded-full bg-white text-slate-500 border border-slate-200 hover:bg-slate-50 transition-all";
        const hiClass = currentLang === 'hi' ? "px-4 py-1.5 text-sm font-bold rounded-full bg-teal-600 text-white shadow-sm transition-all" : "px-4 py-1.5 text-sm font-medium rounded-full bg-white text-slate-500 border border-slate-200 hover:bg-slate-50 transition-all";
        
        let optionsHtml = q.options.map((opt) => `
            <button onclick="selectPhase2Option('${opt.archetype_id}', this)" class="w-full text-left p-4 rounded-xl border border-slate-200 bg-white hover:border-teal-500 hover:bg-teal-50 hover:shadow-md transition-all duration-300 group">
                <div class="flex items-start gap-4">
                    <div class="h-8 w-8 shrink-0 rounded-full border-2 border-slate-200 group-hover:border-teal-500 flex items-center justify-center text-teal-600 transition-colors mt-0.5">
                        <span class="opacity-0 group-hover:opacity-100 text-sm"><i class="fas fa-check"></i></span>
                    </div>
                    <div class="flex flex-col justify-center min-h-[32px]">
                        <p class="lang-en text-slate-800 font-bold text-base ${currentLang !== 'en' ? 'hidden' : ''}">${opt.option_en}</p>
                        <p class="lang-hi text-slate-800 font-bold text-base ${currentLang !== 'hi' ? 'hidden' : ''}">${opt.option_hi_en}</p>
                    </div>
                </div>
            </button>
        `).join("");

        body.innerHTML = `
            <div class="max-w-3xl mx-auto stagger-in">
                <!-- Header with Toggle -->
                <div class="flex flex-col sm:flex-row justify-between items-center mb-4 gap-4">
                    <span class="cyber-badge">Question ${currentQuestionIdx + 1} of ${phase2Questions.length}</span>
                    <div class="flex bg-slate-100 p-1 rounded-full border border-slate-200 shadow-inner">
                        <button id="btn-lang-en" onclick="togglePhase2Lang('en')" class="${enClass}">English</button>
                        <button id="btn-lang-hi" onclick="togglePhase2Lang('hi')" class="${hiClass}">Hinglish</button>
                    </div>
                </div>
                
                <div class="mb-8 text-center md:text-left bg-slate-50 p-6 rounded-2xl border border-slate-100 shadow-sm">
                    <h2 class="lang-en text-2xl md:text-3xl font-extrabold text-slate-900 leading-tight ${currentLang !== 'en' ? 'hidden' : ''}">${q.question_en}</h2>
                    <h2 class="lang-hi text-2xl md:text-3xl font-extrabold text-slate-900 leading-tight ${currentLang !== 'hi' ? 'hidden' : ''}">${q.question_hi_en}</h2>
                </div>
                <div class="space-y-4">
                    ${optionsHtml}
                </div>
            </div>
        `;
    }

    window.selectPhase2Option = function(archetypeId, btn) {
        if (btn.disabled) return;
        
        btn.classList.add("border-teal-500", "bg-teal-50");
        btn.querySelector(".h-8").classList.add("border-teal-500");
        btn.querySelector(".h-8 span").classList.add("opacity-100");
        
        const q = phase2Questions[currentQuestionIdx];
        phase2Answers.push({
            question_id: q.id,
            archetype_id: archetypeId
        });
        
        setTimeout(() => {
            currentQuestionIdx++;
            renderCurrentMCQ();
        }, 400);
    };

    async function submitPhase2Answers() {
        showLoader("Analyzing behavioral patterns...");
        try {
            const res = await fetch("/assessment/api/phase2/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ answers: phase2Answers })
            });
            const data = await res.json();
            if (data.status === "success") {
                await refreshState();
            } else {
                hideLoader();
                alert("Failed to submit Phase 2 assessment.");
            }
        } catch(e) {
            console.error(e);
            hideLoader();
            alert("Network error.");
        }
    }


    // --- PHASE 2: COMPILING RESULTS ---
function renderCompilePhase() {
        const body = document.getElementById("phase-body");
        body.innerHTML = `
            <div class="text-center py-10 flex flex-col items-center justify-center stagger-in">
                <div class="relative flex items-center justify-center mb-8">
                    <div class="animate-ping absolute inline-flex h-20 w-20 rounded-full bg-teal-500 opacity-20"></div>
                    <div class="w-20 h-20 rounded-full bg-gradient-to-tr from-teal-500 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-teal-600/10">
                        <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>
                    </div>
                </div>
                <h2 class="text-2xl font-extrabold text-slate-900">Shadow Compilation Ready</h2>
                <p class="text-slate-500 max-w-md mt-3 text-sm leading-relaxed">Your reflex latency indices, RIASEC profiles, geographical variables, and ego coefficients are consolidated.</p>
                
                <button onclick="compileFinalResults()" id="compile-btn" class="mt-8 px-12 py-4 bg-teal-600 hover:bg-teal-700 text-white rounded-xl font-extrabold transition-all shadow-md shadow-teal-600/10 hover:scale-105 active:scale-95 tracking-widest uppercase text-xs">Execute Matrix Compilation</button>
                <p id="compiling-indicator" class="hidden text-teal-600 font-bold mt-5 animate-pulse text-xs tracking-widest uppercase">Formulating career fit projections...</p>
            </div>
        `;
    }

    async function compileFinalResults() {
        const btn = document.getElementById("compile-btn");
        const ind = document.getElementById("compiling-indicator");
        if (btn) btn.disabled = true;
        if (btn) btn.classList.add("opacity-40", "cursor-not-allowed");
        if (ind) ind.classList.remove("hidden");
        
        try {
            const res = await fetch("/assessment/api/compile", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await res.json();
            if (data.status === "success") {
                window.location.href = data.redirect;
            } else {
                alert("Compilation failed. Please try resetting assessment progress.");
                if (btn) btn.disabled = false;
                if (btn) btn.classList.remove("opacity-40", "cursor-not-allowed");
                if (ind) ind.classList.add("hidden");
            }
        } catch (e) {
            console.error(e);
            alert("Matrix Compilation Error. Check local gateway connections.");
            if (btn) btn.disabled = false;
            if (btn) btn.classList.remove("opacity-40", "cursor-not-allowed");
            if (ind) ind.classList.add("hidden");
        }
    }

