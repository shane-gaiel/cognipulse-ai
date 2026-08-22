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

# Initialize Browser LocalStorage Safely
try:
    localStorage = LocalStorage()
except Exception:
    localStorage = None

SESSION_TIMEOUT_SECONDS = 3600  # 1 Hour session window

# -------------------------------------------------------------
# 2. Local Storage Saving Helpers (Optimized for Fast Load)
# -------------------------------------------------------------
def mark_for_save():
    """Sets a flag to safely trigger a save during the main script run."""
    st.session_state.needs_save = True

def execute_save():
    """Writes only lightweight preferences to browser local storage to eliminate lag."""
    if localStorage is None:
        return
    try:
        data = {
            "api_key": st.session_state.get("api_key", ""),
            "selected_model": st.session_state.get("selected_model", "Auto-Select (Dynamic API Detection)"),
            "custom_model": st.session_state.get("custom_model", ""),
            "subject": st.session_state.get("subject", "Physics & Mechanics"),
            "analogy_theme": st.session_state.get("analogy_theme", "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)"),
            "strictness": st.session_state.get("strictness", "High (Strict Socratic)"),
            "detail_level": st.session_state.get("detail_level", "Detailed & Step-by-Step"),
            "last_active": time.time()
        }
        
        data_str = json.dumps(data)
        try:
            localStorage.setItem("cognipulse_user_session", data_str, key="ls_write_key")
        except TypeError:
            localStorage.setItem("cognipulse_user_session", data_str)
    except Exception:
        pass

# -------------------------------------------------------------
# 3. Session State Initialization & Data Restoration
# -------------------------------------------------------------
saved_data = None
if localStorage is not None:
    try:
        try:
            saved_data = localStorage.getItem("cognipulse_user_session", key="ls_read_key")
        except TypeError:
            saved_data = localStorage.getItem("cognipulse_user_session")
    except Exception:
        pass

if "initialized" not in st.session_state:
    st.session_state.api_key = ""
    st.session_state.selected_model = "Auto-Select (Dynamic API Detection)"
    st.session_state.custom_model = ""
    st.session_state.recent_questions = []
    st.session_state.subject = "Physics & Mechanics"
    st.session_state.analogy_theme = "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)"
    st.session_state.strictness = "High (Strict Socratic)"
    st.session_state.detail_level = "Detailed & Step-by-Step"
    st.session_state.last_working_model = "Auto-Engine"
    st.session_state.is_generating = False
    st.session_state.needs_save = False
    st.session_state.pending_files = []
    
    st.session_state.messages = [{
        "role": "assistant", 
        "content": f"Welcome back to **CogniPulse AI**! Calibrated for **{st.session_state.subject}**. What problem or concept are we breaking down today?"
    }]
    
    st.session_state.initialized = True
    st.session_state.ls_loaded = False 

if saved_data and not st.session_state.ls_loaded:
    try:
        if isinstance(saved_data, dict):
            saved = saved_data
        else:
            saved = json.loads(saved_data)
            
        st.session_state.api_key = saved.get("api_key", st.session_state.api_key)
        st.session_state.selected_model = saved.get("selected_model", st.session_state.selected_model)
        st.session_state.custom_model = saved.get("custom_model", saved.get("custom_model", ""))
        st.session_state.subject = saved.get("subject", st.session_state.subject)
        st.session_state.analogy_theme = saved.get("analogy_theme", st.session_state.analogy_theme)
        st.session_state.strictness = saved.get("strictness", st.session_state.strictness)
        st.session_state.detail_level = saved.get("detail_level", st.session_state.detail_level)
            
        st.session_state.ls_loaded = True
    except Exception:
        pass

# -------------------------------------------------------------
# 4. Custom Styling & Header Positioning for Stop Button
# -------------------------------------------------------------
is_gen = st.session_state.get("is_generating", False)
stop_btn_display = "inline-block" if is_gen else "none"

st.markdown(f"""
<style>
    /* Theme Adaptive Header Title */
    header[data-testid="stHeader"]::before {{
        content: "🧠 CogniPulse AI";
        font-size: 1.15rem;
        font-weight: 800;
        color: var(--text-color) !important;
        position: absolute;
        left: 3.8rem;
        top: 50%;
        transform: translateY(-50%);
        white-space: nowrap;
        z-index: 999999;
        pointer-events: none;
    }}

    .main .block-container {{ 
        padding-top: 4.5rem !important; 
        padding-bottom: 4rem; 
        max-width: 1200px;
    }}

    /* Completely hide native overlapping status text/spinner animation */
    [data-testid="stStatusWidget"] {{
        display: none !important;
    }}

    [data-testid="stChatInput"] {{
        bottom: 1rem !important;
    }}

    /* Position the Stop button right next to the title in the header toolbar */
    .header-stop-wrapper {{
        display: {stop_btn_display};
        position: fixed;
        top: 50%;
        transform: translateY(-50%);
        left: 15rem;
        z-index: 99999999;
    }}

    .header-stop-wrapper button {{
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        padding: 0.15rem 0.55rem !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
        min-height: 26px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }}

    /* Fix Button Sizing & Smallage in Sidebar */
    .stButton button {{
        min-height: 42px !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        transition: all 0.2s ease;
    }}
    
    .stButton button:hover {{
        transform: translateY(-1px);
        filter: brightness(1.05);
    }}

    .dashboard-card {{
        background: var(--secondary-background-color);
        color: var(--text-color);
        border-radius: 14px;
        padding: 16px 20px;
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-left: 5px solid var(--primary-color);
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        transition: all 0.25s ease-in-out;
    }}
    .dashboard-card:hover {{ 
        transform: translateY(-2px); 
        box-shadow: 0 8px 20px rgba(0,0,0,0.12); 
    }}
    .card-title {{
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        opacity: 0.75;
        margin-bottom: 4px;
        font-weight: 600;
        color: var(--text-color);
    }}
    .card-value {{
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--primary-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .credits-footer {{
        margin-top: 25px;
        padding: 18px 14px;
        background: var(--secondary-background-color);
        color: var(--text-color) !important;
        border-radius: 12px;
        text-align: center;
        border-bottom: 3px solid var(--primary-color);
    }}
    .credits-footer span {{
        color: var(--text-color) !important;
    }}
    .contact-btn {{
        display: inline-block;
        margin-top: 10px;
        padding: 8px 18px;
        background-color: var(--primary-color, #ff4b4b);
        color: #ffffff !important;
        text-decoration: none;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        transition: all 0.25s ease;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }}
    .contact-btn:hover {{ 
        filter: brightness(1.15); 
        transform: translateY(-1px); 
        color: #ffffff !important;
    }}

    .stChatMessage {{
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 8px;
    }}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. Native Header Stop Trigger Container
# -------------------------------------------------------------
if is_gen:
    st.markdown('<div class="header-stop-wrapper">', unsafe_allow_html=True)
    if st.button("⏹️ Stop", key="native_top_stop_btn"):
        st.session_state.is_generating = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# 6. Sidebar Control Panel
# -------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Control Panel")
    
    if not st.session_state.get("api_key", ""):
        st.info("🔑 Enter Your API Key")
        st.markdown("<div style='font-size: 0.82rem; margin-bottom: 10px;'>Get your free Gemini API key from <a href='https://aistudio.google.com/app/apikey' target='_blank'>Google AI Studio</a>.</div>", unsafe_allow_html=True)
        input_key = st.text_input("Gemini API Key:", type="password")
        if st.button("🔒 Lock In Key", use_container_width=True, type="primary"):
            if input_key.strip():
                st.session_state.api_key = input_key.strip()
                mark_for_save()
                st.rerun()
    else:
        st.success("✅ API Key Active")
        if st.button("🔑 Change API Key", use_container_width=True):
            st.session_state.api_key = ""
            mark_for_save()
            st.rerun()
            
    st.divider()

    st.subheader("🤖 AI Model Engine")
    
    model_options = [
        "Auto-Select (Dynamic API Detection)",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-pro",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "Custom Model ID"
    ]
    
    current_model = st.session_state.get("selected_model", "Auto-Select (Dynamic API Detection)")
    
    selected_m = st.selectbox(
        "Select Model Mode",
        model_options,
        index=model_options.index(current_model) if current_model in model_options else 0,
        key="selected_model",
        on_change=mark_for_save
    )
    
    st.caption("💡 *Note: When set to **Auto-Select**, the app queries your API key directly to discover supported models.*")
    
    if selected_m == "Custom Model ID":
        st.text_input(
            "Enter Custom Model String:",
            key="custom_model",
            on_change=mark_for_save
        )

    st.divider()

    st.subheader("📚 Subject & Context")
    subject_opts = [
        "Physics & Mechanics", "Mathematics & Calculus", "Computer Science & Python", 
        "Video Editing & VFX", "History & World Civilizations", "Biology & Anatomy",
        "Literature & Rhetoric", "Economics & Marketing"
    ]
    
    current_subject = st.session_state.get("subject", subject_opts[0])
    st.selectbox(
        "Current Subject",
        subject_opts,
        index=subject_opts.index(current_subject) if current_subject in subject_opts else 0,
        key="subject",
        on_change=mark_for_save
    )

    theme_opts = [
        "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)",
        "Tactical FPS & Gaming (Valorant, CS2)",
        "Racing Sims & Automotive Mechanics (Forza, NFS)",
        "PC Hardware & Custom Builds (GPUs, Liquid Cooling)",
        "Sci-Fi & Cinema (Star Wars, MCU)",
        "Music Performance (Drums, Tempo, Orchestration)",
        "Sports & Athletic Strategy", "Everyday Life & Food"
    ]
    
    current_theme = st.session_state.get("analogy_theme", theme_opts[0])
    st.selectbox(
        "Analogy Style Engine",
        theme_opts,
        index=theme_opts.index(current_theme) if current_theme in theme_opts else 0,
        key="analogy_theme",
        on_change=mark_for_save
    )
    
    st.divider()
    
    st.subheader("🛡️ AI Guardrails")
    strict_opts = ["None (Direct Answers)", "Low (Answer + Guidance)", "Medium (Hints First)", "High (Strict Socratic)"]
    
    st.select_slider(
        "Anti-Cheat Strictness",
        options=strict_opts,
        value=st.session_state.get("strictness", "High (Strict Socratic)"),
        key="strictness",
        on_change=mark_for_save
    )
    
    current_detail = st.session_state.get("detail_level", "Detailed & Step-by-Step")
    st.radio(
        "Explanation Depth",
        ["Concise & Quick", "Detailed & Step-by-Step"],
        index=0 if current_detail == "Concise & Quick" else 1,
        horizontal=True,
        key="detail_level",
        on_change=mark_for_save
    )

    st.divider()

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
            "content": f"Chat cleared. What are we studying in **{st.session_state.get('subject', 'Physics & Mechanics')}** today?"
        }]
        st.session_state.is_generating = False
        st.session_state.pending_files = []
        mark_for_save()
        st.rerun()

    st.divider()
    
    st.subheader("🕒 Recent Questions Center")
    recent_qs = st.session_state.get("recent_questions", [])
    if recent_qs:
        st.caption("Click any topic to recall the prompt:")
        recent_list = list(reversed(recent_qs))[:5]
        
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
                st.rerun()
    else:
        st.caption("No recent questions logged yet.")

    st.markdown("""
    <div class="credits-footer">
        <span style="font-size: 0.8rem; opacity: 0.85;">Project created by</span><br>
        <span style="font-weight: 700; font-size: 1.1rem; letter-spacing: 0.5px;">Shane Gaiel</span><br>
        <a href="https://linktr.ee/shane.gaiel" target="_blank" class="contact-btn">Contact me on Linktree</a>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 7. Dynamic Dashboard
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="dashboard-card">
        <div class="card-title">Active Subject</div>
        <div class="card-value">{st.session_state.get('subject', 'Physics & Mechanics')}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    theme_display = st.session_state.get('analogy_theme', 'Battle Shonen Anime').split(' (')[0]
    st.markdown(f"""
    <div class="dashboard-card">
        <div class="card-title">Analogy Engine</div>
        <div class="card-value">{theme_display}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    display_model = st.session_state.get('last_working_model', st.session_state.get('selected_model', 'Auto').split(' ')[0])
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
# 8. System Instructions & Formatting Guardrails
# -------------------------------------------------------------
current_strictness = st.session_state.get("strictness", "High (Strict Socratic)")

if "None" in current_strictness:
    guardrail_instructions = "CORE RULE: Provide immediate direct answers and complete mathematical step-by-step solutions."
elif "Low" in current_strictness:
    guardrail_instructions = "CORE RULE: Give the core direct answer first, followed by a concise breakdown."
elif "Medium" in current_strictness:
    guardrail_instructions = "CORE RULE: Offer targeted hints first. If asked again, provide full direct resolution."
else:  
    guardrail_instructions = "CORE RULE: Strict Socratic Method. Do not give away final numeric answers immediately. Ask guiding questions to lead the user to self-discovery."

SYSTEM_INSTRUCTION = f"""
You are CogniPulse, an elite AI Study Assistant and Socratic Tutor.
Subject Domain: {st.session_state.get('subject', 'Physics & Mechanics')}.
Analogy Theme Engine: {st.session_state.get('analogy_theme', 'Battle Shonen Anime')}.
Explanation Depth Preference: {st.session_state.get('detail_level', 'Detailed & Step-by-Step')}.

{guardrail_instructions}

STRICT FORMATTING RULES:
1. Step-by-step mathematical calculations must be independently computed prior to stating final answers.
2. NEVER output raw complex LaTeX environments like \\phantom or unclosed \\begin{{array}} outside standard LaTeX blocks.
3. Use simple inline $...$ or display $$...$$ for math. For alignment/place values, use standard bullet points or simple text lines.
4. Keep all normal explanations in clean Markdown without unescaped LaTeX tags.
"""

# Render Active Chat Feed
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# -------------------------------------------------------------
# 9. Chat Field Logic
# -------------------------------------------------------------
active_prompt = None
raw_files = []

chat_response = st.chat_input(
    "Ask a question, request a concept breakdown, or share a problem...",
    accept_file="multiple",
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

elif "selected_recent" in st.session_state and st.session_state.selected_recent:
    active_prompt = st.session_state.selected_recent
    del st.session_state.selected_recent

if active_prompt:
    if not st.session_state.get("api_key", ""):
        st.warning("⚠️ Please enter and lock in your Gemini API key in the sidebar control panel first.")
        st.stop()

    st.session_state.pending_files = []
    file_names = []
    if raw_files:
        files_list = raw_files if isinstance(raw_files, list) else [raw_files]
        for f in files_list:
            file_names.append(f.name)
            st.session_state.pending_files.append({
                "name": f.name,
                "type": f.type or "application/octet-stream",
                "bytes": f.getvalue()
            })

    if file_names:
        display_user_content = f"📎 *Attached file(s): {', '.join(file_names)}*\n\n{active_prompt}"
    else:
        display_user_content = active_prompt

    st.session_state.messages.append({"role": "user", "content": display_user_content})
    st.session_state.is_generating = True
    st.rerun()

# -------------------------------------------------------------
# 10. Execution Block (Streaming & Dynamic Model Discovery)
# -------------------------------------------------------------
if st.session_state.get("is_generating", False):
    active_prompt = st.session_state.messages[-1]["content"] if st.session_state.messages else ""
    
    try:
        client = genai.Client(api_key=st.session_state.get("api_key", ""))
        prompt_parts = []
        
        pending_files = st.session_state.get("pending_files", [])
        for file_info in pending_files:
            f_bytes = file_info["bytes"]
            m_type = file_info["type"]
            f_name = file_info["name"]
            
            if m_type.startswith("image/"):
                prompt_parts.append(types.Part.from_bytes(data=f_bytes, mime_type=m_type))
            else:
                ext = os.path.splitext(f_name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(f_bytes)
                    tmp_path = tmp.name
                
                uploaded_remote = client.files.upload(file=tmp_path)
                prompt_parts.append(uploaded_remote)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        # History sanitization: guarantees strict alternating user/model roles for Gemini API
        history = []
        expected_role = "user"
        for m in st.session_state.messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            if role == expected_role:
                history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=m["content"])]
                    )
                )
                expected_role = "model" if expected_role == "user" else "user"

        selected_model_val = st.session_state.get("selected_model", "Auto-Select (Dynamic API Detection)")
        
        if selected_model_val.startswith("Auto-Select"):
            try:
                discovered_models = []
                for model_obj in client.models.list():
                    methods = getattr(model_obj, "supported_generation_methods", [])
                    if not methods or "generateContent" in methods:
                        m_name = model_obj.name
                        if m_name.startswith("models/"):
                            m_name = m_name[7:]
                        if any(kw in m_name.lower() for kw in ["tts", "embedding", "imagen", "vision-only"]):
                            continue
                        discovered_models.append(m_name)
                
                if discovered_models:
                    discovered_models.sort(key=lambda x: (0 if "flash" in x else (1 if "pro" in x else 2)))
                    candidates = discovered_models
                else:
                    candidates = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
            except Exception:
                candidates = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
        elif selected_model_val == "Custom Model ID":
            custom_val = st.session_state.get("custom_model", "").strip()
            candidates = [custom_val] if custom_val else ["gemini-2.0-flash", "gemini-1.5-flash"]
        else:
            candidates = [selected_model_val, "gemini-2.0-flash", "gemini-1.5-flash"]

        with st.chat_message("assistant"):
            assistant_reply = None
            last_exception = None

            if prompt_parts:
                prompt_parts.append(active_prompt)
                prompt_payload = prompt_parts
            else:
                prompt_payload = active_prompt

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
                    if any(code in err_str for code in ["404", "not_found", "503", "unavailable", "resource_exhausted", "high demand", "quota", "400", "invalid_argument", "multiturn"]):
                        continue
                    else:
                        raise model_err

            if assistant_reply is None:
                raise last_exception or Exception("All discovered model tiers are currently unavailable or not found. Please check your API key permissions.")
            
            st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
            
            current_recent = st.session_state.get("recent_questions", [])
            st.session_state.recent_questions = [
                item for item in current_recent 
                if (item.get("q") if isinstance(item, dict) else item) != active_prompt
            ]
            st.session_state.recent_questions.append({
                "q": active_prompt,
                "a": assistant_reply
            })
            
            st.session_state.pending_files = []

    except Exception as e:
        error_str = str(e).lower()
        if "404" in error_str or "not_found" in error_str:
            st.error("⚠️ **Model Discovery Error:** No supported text models were found for your API key. Please check your API key permissions or enter a custom model ID in the sidebar.")
        elif "503" in error_str or "unavailable" in error_str:
            st.info("🚦 **Heavy Traffic Detected:** The AI models are experiencing high demand. Please try again.")
        else:
            st.error(f"Oops! Something went wrong: {str(e)}")

    st.session_state.is_generating = False
    st.rerun()

# -------------------------------------------------------------
# 11. Execute Safely Staged Saves
# -------------------------------------------------------------
if st.session_state.get("needs_save", False):
    execute_save()
    st.session_state.needs_save = False
