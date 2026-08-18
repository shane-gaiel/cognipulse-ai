import os
import json
import time
import tempfile
import streamlit as st
from google import genai
from google.genai import types
from streamlit_local_storage import LocalStorage

# -------------------------------------------------------------
# 1. Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="CogniPulse AI Socratic Tutor",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Browser LocalStorage
localStorage = LocalStorage()
SESSION_TIMEOUT_SECONDS = 3600  # 1 Hour session window

# -------------------------------------------------------------
# 2. Local Storage & Persistence Helpers
# -------------------------------------------------------------
def load_save_data():
    try:
        data_str = localStorage.getItem("cognipulse_user_session")
        if data_str:
            return json.loads(data_str)
    except Exception:
        pass
    return {}

def save_data():
    try:
        data = {
            "api_key": st.session_state.get("api_key", ""),
            "selected_model": st.session_state.get("selected_model", "Auto-Select (Flash & Pro Engine)"),
            "custom_model": st.session_state.get("custom_model", ""),
            "messages": st.session_state.get("messages", []),
            "last_active": time.time(),
            "recent_questions": st.session_state.get("recent_questions", []),
            "subject": st.session_state.get("subject", "Physics & Mechanics"),
            "analogy_theme": st.session_state.get("analogy_theme", "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)"),
            "strictness": st.session_state.get("strictness", "High (Strict Socratic)"),
            "detail_level": st.session_state.get("detail_level", "Detailed & Step-by-Step")
        }
        unique_key = f"save_{int(time.time() * 1000)}"
        localStorage.setItem("cognipulse_user_session", json.dumps(data), key=unique_key)
    except Exception as e:
        st.warning(f"Unable to auto-save session: {e}")

# -------------------------------------------------------------
# 3. Session State Initialization
# -------------------------------------------------------------
if "initialized" not in st.session_state:
    saved = load_save_data()
    st.session_state.api_key = saved.get("api_key", "")
    st.session_state.selected_model = saved.get("selected_model", "Auto-Select (Flash & Pro Engine)")
    st.session_state.custom_model = saved.get("custom_model", "")
    st.session_state.recent_questions = saved.get("recent_questions", [])
    st.session_state.subject = saved.get("subject", "Physics & Mechanics")
    st.session_state.analogy_theme = saved.get("analogy_theme", "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)")
    st.session_state.strictness = saved.get("strictness", "High (Strict Socratic)")
    st.session_state.detail_level = saved.get("detail_level", "Detailed & Step-by-Step")
    st.session_state.last_working_model = "Auto-Engine"
    st.session_state.is_generating = False
    
    last_active = saved.get("last_active", 0)
    current_time = time.time()
    saved_messages = saved.get("messages", [])
    
    if (current_time - last_active < SESSION_TIMEOUT_SECONDS) and saved_messages:
        st.session_state.messages = saved_messages
    else:
        st.session_state.messages = [{
            "role": "assistant", 
            "content": f"Welcome back to **CogniPulse AI**! Calibrated for **{st.session_state.subject}**. What problem or concept are we breaking down today?"
        }]
        save_data()
        
    st.session_state.initialized = True

# -------------------------------------------------------------
# 4. Custom Responsive UI Styling & Smart Floating Scroll Button
# -------------------------------------------------------------
is_gen = st.session_state.get("is_generating", False)

if is_gen:
    st.markdown("""
    <style>
        button[data-testid='stChatInputSubmitButton'] { position: relative !important; }
        button[data-testid='stChatInputSubmitButton'] svg { display: none !important; }
        button[data-testid='stChatInputSubmitButton']::after { 
            content: '■' !important; 
            color: #ff4b4b !important; 
            font-size: 1.2rem !important; 
            position: absolute !important; 
            top: 0 !important; 
            left: 0 !important; 
            width: 100% !important; 
            height: 100% !important; 
            display: flex !important; 
            align-items: center !important; 
            justify-content: center !important; 
        }
    </style>
    """, unsafe_allow_html=True)

st.markdown("""
<style>
    /* Embed CogniPulse AI directly into Streamlit's sticky top navbar */
    header[data-testid="stHeader"]::before {
        content: "🧠 CogniPulse AI";
        font-size: 1.25rem;
        font-weight: 800;
        color: var(--text-color, #ffffff);
        position: absolute;
        left: 4.2rem;
        top: 50%;
        transform: translateY(-50%);
        white-space: nowrap;
        z-index: 999999;
        pointer-events: none;
    }

    /* Padding adjustment so body elements clear the fixed app bar */
    .main .block-container { 
        padding-top: 4.5rem !important; 
        padding-bottom: 5rem; 
        max-width: 1200px;
    }

    /* Completely hide Streamlit's default header stop button and status widget */
    header [data-testid="stStatusWidget"],
    [data-testid="stStatusWidget"],
    .stStatusWidget,
    header button:not([aria-label]):not([class]),
    header button[title*="Stop"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
    }

    /* Optimize chat input positioning and prevent layout overlap */
    [data-testid="stChatInput"] {
        bottom: 1rem !important;
    }

    /* ===================================================================== */
    /* FLOATING SCROLL-TO-BOTTOM ARROW BUTTON (Hidden by default)           */
    /* ===================================================================== */
    .scroll-down-btn {
        position: fixed;
        bottom: 5.5rem;
        right: 2rem;
        background-color: rgba(40, 40, 40, 0.85);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 50%;
        width: 42px;
        height: 42px;
        display: none; /* Hidden until scrolled up */
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        cursor: pointer;
        box-shadow: 0 4px 14px rgba(0,0,0,0.35);
        z-index: 999999;
        transition: all 0.2s ease;
    }
    .scroll-down-btn:hover {
        background-color: var(--primary-color, #ff4b4b);
        transform: scale(1.1);
    }

    /* Custom Styling for Dashboard Elements */
    .dashboard-card {
        background: var(--secondary-background-color);
        color: var(--text-color);
        border-radius: 14px;
        padding: 16px 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 5px solid var(--primary-color);
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        transition: all 0.25s ease-in-out;
    }
    .dashboard-card:hover { 
        transform: translateY(-2px); 
        box-shadow: 0 8px 20px rgba(0,0,0,0.12); 
    }
    .card-title {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        opacity: 0.7;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .card-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--primary-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .credits-footer {
        margin-top: 25px;
        padding: 18px 14px;
        background: var(--secondary-background-color);
        border-radius: 12px;
        text-align: center;
        border-bottom: 3px solid var(--primary-color);
    }
    .contact-btn {
        display: inline-block;
        margin-top: 10px;
        padding: 8px 18px;
        background-color: var(--primary-color);
        color: #ffffff !important;
        text-decoration: none;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        transition: all 0.25s ease;
    }
    .contact-btn:hover { 
        filter: brightness(1.15); 
        transform: translateY(-1px); 
    }

    .stChatMessage {
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 8px;
    }
</style>

<!-- Floating Scroll-to-Bottom Button Widget -->
<div class="scroll-down-btn" id="scrollDownBtn" title="Jump to bottom" onclick="
    const doc = window.parent.document;
    const mainContainer = doc.querySelector('section.main');
    if (mainContainer) {
        mainContainer.scrollTo({ top: mainContainer.scrollHeight, behavior: 'smooth' });
    }
    window.parent.scrollTo({ top: doc.body.scrollHeight, behavior: 'smooth' });
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
">
    ↓
</div>

<script>
    (function() {
        const doc = window.parent.document;
        function initScrollWatcher() {
            const scrollBtn = doc.getElementById('scrollDownBtn');
            const mainContainer = doc.querySelector('section.main') || doc.documentElement;
            
            if (scrollBtn && mainContainer) {
                const checkPosition = () => {
                    const st = mainContainer.scrollTop || doc.documentElement.scrollTop || doc.body.scrollTop;
                    const sh = mainContainer.scrollHeight || doc.documentElement.scrollHeight || doc.body.scrollHeight;
                    const ch = mainContainer.clientHeight || window.innerHeight;
                    
                    const distanceFromBottom = sh - (st + ch);
                    
                    // Show arrow when scrolled up more than 200px into previous chats
                    if (distanceFromBottom > 200) {
                        scrollBtn.style.display = 'flex';
                    } else {
                        scrollBtn.style.display = 'none';
                    }
                };

                mainContainer.removeEventListener('scroll', checkPosition);
                mainContainer.addEventListener('scroll', checkPosition);
                doc.removeEventListener('scroll', checkPosition);
                doc.addEventListener('scroll', checkPosition, true);
                
                checkPosition();
            }
        }

        setTimeout(initScrollWatcher, 400);
        setTimeout(initScrollWatcher, 1200);
    })();
</script>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. Sidebar Control Panel
# -------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Control Panel")
    
    # --- API Key Management ---
    if not st.session_state.api_key:
        st.info("🔑 Enter Your API Key")
        st.markdown("<div style='font-size: 0.82rem; margin-bottom: 10px;'>Get your free Gemini API key from <a href='https://aistudio.google.com/app/apikey' target='_blank'>Google AI Studio</a>.</div>", unsafe_allow_html=True)
        input_key = st.text_input("Gemini API Key:", type="password")
        if st.button("🔒 Lock In Key", use_container_width=True, type="primary"):
            if input_key.strip():
                st.session_state.api_key = input_key.strip()
                save_data()
                st.rerun()
    else:
        st.success("✅ API Key Active")
        if st.button("🔑 Change API Key", use_container_width=True):
            st.session_state.api_key = ""
            save_data()
            st.rerun()
            
    st.divider()

    # --- Multi-Model Engine ---
    st.subheader("🤖 AI Model Engine")
    model_options = [
        "Auto-Select (Flash & Pro Engine)",
        "gemini-3.6-flash",
        "gemini-3.1-pro",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "Custom Model ID"
    ]
    
    selected_m = st.selectbox(
        "Select Model Mode",
        model_options,
        index=0,
        key="selected_model",
        on_change=save_data
    )
    
    st.caption("💡 *Note: Selected model must match your API key permissions. If unsure, set to **Auto-Select**.*")
    
    if selected_m == "Custom Model ID":
        st.text_input(
            "Enter Custom Model String:",
            key="custom_model",
            on_change=save_data
        )

    st.divider()

    # --- Subject & Analogy Theme Engine ---
    st.subheader("📚 Subject & Context")
    st.selectbox(
        "Current Subject",
        [
            "Physics & Mechanics", "Mathematics & Calculus", "Computer Science & Python", 
            "Video Editing & VFX", "History & World Civilizations", "Biology & Anatomy",
            "Literature & Rhetoric", "Economics & Marketing"
        ],
        key="subject",
        on_change=save_data
    )

    st.selectbox(
        "Analogy Style Engine",
        [
            "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)",
            "Tactical FPS & Gaming (Valorant, CS2)",
            "Racing Sims & Automotive Mechanics (Forza, NFS)",
            "PC Hardware & Custom Builds (GPUs, Liquid Cooling)",
            "Sci-Fi & Cinema (Star Wars, MCU)",
            "Music Performance (Drums, Tempo, Orchestration)",
            "Sports & Athletic Strategy", "Everyday Life & Food"
        ],
        key="analogy_theme",
        on_change=save_data
    )
    
    st.divider()
    
    # --- Guardrail Controls ---
    st.subheader("🛡️ AI Guardrails")
    st.select_slider(
        "Anti-Cheat Strictness",
        options=["None (Direct Answers)", "Low (Answer + Guidance)", "Medium (Hints First)", "High (Strict Socratic)"],
        key="strictness",
        on_change=save_data
    )
    
    st.radio(
        "Explanation Depth",
        ["Concise & Quick", "Detailed & Step-by-Step"],
        horizontal=True,
        key="detail_level",
        on_change=save_data
    )

    st.divider()

    # --- Session & Export Tools ---
    st.subheader("💾 Session Tools")
    
    chat_export = "\n\n".join([f"### {m['role'].capitalize()}\n{m['content']}" for m in st.session_state.get('messages', [])])
    st.download_button(
        label="📥 Export Session Notes (.md)",
        data=chat_export,
        file_name=f"CogniPulse_{st.session_state.get('subject', 'Session').replace(' ', '_')}_Notes.md",
        mime="text/markdown",
        use_container_width=True
    )

    if st.button("🗑️ Clear Chat Session", use_container_width=True):
        st.session_state.messages = [{
            "role": "assistant", 
            "content": f"Chat cleared. What are we studying in **{st.session_state.subject}** today?"
        }]
        save_data()
        st.rerun()

    st.divider()
    
    # --- Interactive Recent Questions Recall ---
    st.subheader("🕒 Recent Questions Center")
    if st.session_state.recent_questions:
        st.caption("Click any topic to recall the prompt:")
        recent_list = list(reversed(st.session_state.recent_questions))[:5]
        
        for idx, item in enumerate(recent_list):
            q_text = item["q"] if isinstance(item, dict) else item
            a_text = item.get("a", "") if isinstance(item, dict) else ""
            
            button_label = f"💬 {q_text[:28]}..." if len(q_text) > 28 else f"💬 {q_text}"
            if st.button(button_label, key=f"recent_q_{idx}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": q_text})
                if a_text:
                    st.session_state.messages.append({"role": "assistant", "content": a_text})
                else:
                    st.session_state.selected_recent = q_text
                save_data()
                st.rerun()
    else:
        st.caption("No recent questions logged yet.")

    # --- Author Attribution ---
    st.markdown("""
    <div class="credits-footer">
        <span style="font-size: 0.8rem; opacity: 0.7;">Project created by</span><br>
        <span style="font-weight: 700; font-size: 1.1rem; letter-spacing: 0.5px;">Shane Gaiel</span><br>
        <a href="https://linktr.ee/shane.gaiel" target="_blank" class="contact-btn">Contact me on Linktree</a>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 6. Dynamic Dashboard
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="dashboard-card">
        <div class="card-title">Active Subject</div>
        <div class="card-value">{st.session_state.subject}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    theme_display = st.session_state.analogy_theme.split(' (')[0]
    st.markdown(f"""
    <div class="dashboard-card">
        <div class="card-title">Analogy Engine</div>
        <div class="card-value">{theme_display}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    display_model = st.session_state.get('last_working_model', st.session_state.selected_model.split(' ')[0])
    st.markdown(f"""
    <div class="dashboard-card">
        <div class="card-title">Engine Target</div>
        <div class="card-value">{display_model}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    turn_count = len(st.session_state.get('messages', [])) // 2
    st.markdown(f"""
    <div class="dashboard-card">
        <div class="card-title">Session Turns</div>
        <div class="card-value">{turn_count} Turns</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# -------------------------------------------------------------
# 7. System Instructions & Formatting Guardrails
# -------------------------------------------------------------
if "None" in st.session_state.strictness:
    guardrail_instructions = "CORE RULE: Provide immediate direct answers and complete mathematical step-by-step solutions."
elif "Low" in st.session_state.strictness:
    guardrail_instructions = "CORE RULE: Give the core direct answer first, followed by a concise breakdown."
elif "Medium" in st.session_state.strictness:
    guardrail_instructions = "CORE RULE: Offer targeted hints first. If asked again, provide full direct resolution."
else:  
    guardrail_instructions = "CORE RULE: Strict Socratic Method. Do not give away final numeric answers immediately. Ask guiding questions to lead the user to self-discovery."

SYSTEM_INSTRUCTION = f"""
You are CogniPulse, an elite AI Study Assistant and Socratic Tutor.
Subject Domain: {st.session_state.subject}.
Analogy Theme Engine: {st.session_state.analogy_theme}.
Explanation Depth Preference: {st.session_state.detail_level}.

{guardrail_instructions}

STRICT FORMATTING RULES:
1. Step-by-step mathematical calculations must be independently computed prior to stating final answers.
2. NEVER output raw complex LaTeX environments like \\phantom or unclosed \\begin{{array}} outside standard LaTeX blocks.
3. Use simple inline $...$ or display $$...$$ for math. For alignment/place values, use standard bullet points or simple text lines.
4. Keep all normal explanations in clean Markdown without unescaped LaTeX tags.
"""

# Render Active Chat Feed
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# -------------------------------------------------------------
# 8. Inline Attachment & Gemini-Style Native Chat Field
# -------------------------------------------------------------
active_prompt = None
attached_files = []

chat_response = st.chat_input(
    "Ask a question, request a concept breakdown, or share a problem...",
    accept_file=True,
    file_type=["png", "jpg", "jpeg", "webp", "pdf", "txt", "py", "js"]
)

if chat_response:
    if isinstance(chat_response, dict):
        active_prompt = chat_response.get("text", "")
        raw_files = chat_response.get("files", [])
    elif hasattr(chat_response, "text"):
        active_prompt = chat_response.text
        raw_files = getattr(chat_response, "files", [])
    else:
        active_prompt = str(chat_response)
        raw_files = []
        
    attached_files = raw_files if isinstance(raw_files, list) else ([raw_files] if raw_files else [])

elif "selected_recent" in st.session_state and st.session_state.selected_recent:
    active_prompt = st.session_state.selected_recent
    del st.session_state.selected_recent

if active_prompt:
    if not st.session_state.api_key:
        st.warning("⚠️ Please enter and lock in your Gemini API key in the sidebar control panel first.")
        st.stop()

    file_names = [f.name for f in attached_files] if attached_files else []
    if file_names:
        display_user_content = f"📎 *Attached file(s): {', '.join(file_names)}*\n\n{active_prompt}"
    else:
        display_user_content = active_prompt

    st.session_state.messages.append({"role": "user", "content": display_user_content})
    save_data()

    with st.chat_message("user"):
        st.markdown(display_user_content)

    # =====================================================================
    # ACTIVATE GENERATION STATE (Triggers red ■ directly on the send button)
    # =====================================================================
    st.session_state.is_generating = True
    st.rerun()

# Execute generation if flagged with Robust Multi-Model Fallback
if st.session_state.get("is_generating", False):
    active_prompt = st.session_state.messages[-1]["content"] if st.session_state.messages else ""
    
    try:
        client = genai.Client(api_key=st.session_state.api_key)
        
        prompt_parts = []
        for uploaded_file in attached_files:
            file_bytes = uploaded_file.getvalue()
            mime_type = uploaded_file.type or "application/octet-stream"
            
            if mime_type.startswith("image/"):
                prompt_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                
                uploaded_remote = client.files.upload(file=tmp_path)
                prompt_parts.append(uploaded_remote)
                os.remove(tmp_path)

        history = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])]
            )
            for m in st.session_state.messages[:-2]
        ]

        if st.session_state.selected_model.startswith("Auto-Select"):
            candidates = [
                "gemini-3.6-flash", "gemini-3.1-pro", "gemini-2.5-pro",
                "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"
            ]
        elif st.session_state.selected_model == "Custom Model ID":
            custom_val = st.session_state.custom_model.strip()
            candidates = [custom_val] if custom_val else ["gemini-3.6-flash", "gemini-3.1-pro", "gemini-2.5-pro"]
        else:
            candidates = [st.session_state.selected_model]

        with st.chat_message("assistant"):
            assistant_reply = None
            last_exception = None

            if prompt_parts:
                prompt_parts.append(active_prompt)
                prompt_payload = prompt_parts
            else:
                prompt_payload = active_prompt

            # Loop through candidate models with silent fallback for 503 / High Demand errors
            for model_id in candidates:
                try:
                    chat = client.chats.create(
                        model=model_id,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.2,
                        ),
                        history=history
                    )
                    response_stream = chat.send_message_stream(prompt_payload)

                    def stream_generator():
                        for chunk in response_stream:
                            if chunk.text:
                                yield chunk.text

                    assistant_reply = st.write_stream(stream_generator())
                    st.session_state.last_working_model = model_id
                    break
                except Exception as model_err:
                    last_exception = model_err
                    err_str = str(model_err).lower()
                    if any(code in err_str for code in ["503", "unavailable", "resource_exhausted", "high demand", "quota"]):
                        continue  # Silently try next fallback model
                    else:
                        raise model_err

            if assistant_reply is None:
                raise last_exception or Exception("All model tiers are currently experiencing heavy traffic. Please try again in a moment.")
            
            st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
            
            st.session_state.recent_questions = [
                item for item in st.session_state.recent_questions 
                if (item.get("q") if isinstance(item, dict) else item) != active_prompt
            ]
            st.session_state.recent_questions.append({
                "q": active_prompt,
                "a": assistant_reply
            })
            
            save_data()

    except Exception as e:
        error_str = str(e).lower()
        if "503" in error_str or "unavailable" in error_str or "high demand" in error_str:
            st.info("🚦 **Heavy Traffic Detected:** The AI models are experiencing high demand. Please try clicking your question from the 'Recent Questions' menu in the sidebar to try again.")
        else:
            st.error(f"Oops! Something went wrong: {str(e)}")

    # =====================================================================
    # DEACTIVATE GENERATION STATE
    # =====================================================================
    st.session_state.is_generating = False
    st.rerun()
