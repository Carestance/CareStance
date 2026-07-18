import re

with open("frontend/templates/assessment.html", "r") as f:
    content = f.read()

with open("good_assessment.html", "r") as f:
    good_content = f.read()

# Extract the script tag content from good_assessment.html
good_script_match = re.search(r"<script>(.*?)</script>", good_content, re.DOTALL)
good_script = good_script_match.group(1) if good_script_match else ""

# Extract the script tag from current assessment.html
script_match = re.search(r"<script>(.*?)</script>", content, re.DOTALL)
current_script = script_match.group(1) if script_match else ""

# We will build a clean script that has:
# 1. State vars
# 2. refreshState, showLoader, hideLoader, updateHeader, loadPhase, speakActivePrompt
# 3. Phase 0: Intake Form (from current)
# 4. Phase 1: Phase 2 MCQs (from current)
# 5. Phase 2: Compile Phase (from good)

clean_script = """
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
"""

# Extract Phase 0 from current_script
intake_phase = re.search(r"(function renderIntakePhase\(\) \{.*?)function renderSwipePhase", current_script, re.DOTALL)
if intake_phase:
    clean_script += "\n\n    // --- PHASE 0: CLINICAL CONVERSATIONAL INTAKE ---\n"
    # Wait, the toggleInterest is inside buildSwipeCards right now. We need it outside.
    clean_script += """
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
    """
    clean_script += intake_phase.group(1)

# Add Phase 2 MCQs (correctly formatted)
clean_script += """

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
"""

# Extract Phase 5 Compile from good_script
compile_phase = re.search(r"(function renderCompilePhase\(\) \{.*)", good_script, re.DOTALL)
if compile_phase:
    clean_script += "\n\n    // --- PHASE 2: COMPILING RESULTS ---\n"
    clean_script += compile_phase.group(1)

new_html = re.sub(r"<script>.*?</script>", "<script>\n" + clean_script + "\n</script>", content, flags=re.DOTALL)

# Also ensure phase1_inputs is defined before the script tag (the user had a small snippet there)
# In good_assessment it wasn't there but the current has it.
# In current_script:
# const phase1Inputs = {{ phase1_inputs | default({}) | tojson | safe }};
# Let's insert that at the top of our script.
header_vars = """
    const phase1Inputs = {{ phase1_inputs | default({}) | tojson | safe }};
    const interestOptions = Object.keys(phase1Inputs.interest_selection_mapping || {}).sort();
    const incomeOptions = Object.keys(phase1Inputs.family_income_mapping || {});
    const occupationOptions = Object.keys(phase1Inputs.occupation_category_mapping || {}).sort();
"""
new_html = new_html.replace("let assessmentState = {};", header_vars + "\n    let assessmentState = {};")

with open("frontend/templates/assessment.html", "w") as f:
    f.write(new_html)

