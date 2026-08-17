import json
import time
import streamlit as st
from google import genai
from google.genai import types
from streamlit_local_storage import LocalStorage

# -------------------------------------------------------------
# 1. Page Configuration (Must be first Streamlit command)
# -------------------------------------------------------------
st.set_page_config(
    page_title="CogniPulse AI Socratic Tutor",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Browser LocalStorage
localStorage = LocalStorage()
SESSION_TIMEOUT_SECONDS = 3600  # 1 Hour timeout

# -------------------------------------------------------------
# 2. Local Storage Helpers (Device-Isolated Persistence)
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
# 3. State Initialization
# -------------------------------------------------------------
if "initialized" not in st.session_state:
    saved = load_save_data()
    st.session_state.api_key = saved.get("api_key", "")
    st.session_state.recent_questions = saved.get("recent_questions", [])
    st.session_state.subject = saved.get("subject", "Physics & Mechanics")
    st.session_state.analogy_theme = saved.get("analogy_theme", "Battle Shonen Anime (Jujutsu Kaisen, Dragon Ball, Solo Leveling)")
    st.session_state.strictness = saved.get("strictness", "High (Strict Socratic)")
    st.session_state.detail_level = saved.get("detail_level", "Detailed & Step-by-Step")
    
    # Session Timeout Check
    last_active = saved.get("last_active", 0)
    current_time = time.time()
    saved_messages = saved.get("messages", [])
    
    if (current_time - last_active < SESSION_TIMEOUT_SECONDS) and saved_messages:
        st.session_state.messages = saved_messages
    else:
        st.session_state.messages = [{
            "role": "assistant", 
            "content": f"Welcome back to **CogniPulse AI**! I'm calibrated for **{st.session_state.subject}**. What are we studying today?"
        }]
        save_data()
        
    st.session_state.initialized = True

# -------------------------------------------------------------
# 4. Fluid UI Styling & CSS
# -------------------------------------------------------------
st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    .dashboard-card {
        background-color: var(--secondary-background-color);
        color: var(--text-color);
        border-radius: 12px;
        padding: 18px 24px;
        border-left: 6px solid var(--primary-color);
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .dashboard-card:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0,0,0,0.1); }
    .highlight { color: var(--primary-color); font-weight: 600; }

    .credits-footer {
        margin-top: 30px;
        padding: 20px 15px;
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        text-align: center;
        border-bottom: 4px solid var(--primary-color);
    }
    .contact-btn {
        display: inline-block;
        margin-top: 12px;
        padding: 8px 16px;
        background-color: var(--primary-color);
        color: #ffffff !important;
        text-decoration: none;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .contact-btn:hover { filter: brightness(1.1); transform: translateY(-2px); }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. Sidebar Control Panel
# -------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Control Panel")
    
    # API Key Handling
    if not st.session_state.api_key:
        st.info("Enter Your API Key.")
        st.markdown("<div style='font-size: 0.85rem; margin-bottom: 10px;'>Don't have an API Key? Get one from an AI API Source <a href='https://aistudio.google.com/app/apikey' target='_blank'>here</a>.</div>", unsafe_allow_html=True)
        input_key = st.text_input("Gemini API Key:", type="password")
        if st.button("🔒 Lock In Key", use_container_width=True, type="primary"):
            if input_key.strip():
                st.session_state.api_key = input_key.strip()
                save_data()
                st.rerun()
    else:
        st.success("✅ API Key Locked & Saved")
        if st.button("🔑 Clear Saved Key", use_container_width=True):
            st.session_state.api_key = ""
            save_data()
            st.rerun()
            
    st.divider()

    # Core AI Configurations
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

    if st.button("🗑️ Clear Current Session Chat", use_container_width=True):
        st.session_state.messages = [{
            "role": "assistant", 
            "content": f"Chat cleared. What are we studying in **{st.session_state.subject}** today?"
        }]
        save_data()
        st.rerun()

    st.divider()
    
    # -------------------------------------------------------------
    # 6. Interactive Recent Questions Center (Q&A Recall)
    # -------------------------------------------------------------
    st.subheader("🕒 Recent Questions Center")
    if st.session_state.recent_questions:
        st.caption("Click any past topic to restore the question and AI answer:")
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

    # -------------------------------------------------------------
    # Creator Credits Footer
    # -------------------------------------------------------------
    st.markdown("""
    <div class="credits-footer">
        <span style="font-size: 0.8rem; opacity: 0.7;">Project created by</span><br>
        <span style="font-weight: 700; font-size: 1.15rem; letter-spacing: 0.5px;">Shane Gaiel</span><br>
        <a href="https://linktr.ee/shane.gaiel" target="_blank" class="contact-btn">Contact me on Linktree</a>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 7. Main UI Layout & Dashboard
# -------------------------------------------------------------
st.title("🧠 CogniPulse AI")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="dashboard-card">
        <div><small>ACTIVE SUBJECT</small></div>
        <div class="highlight" style="font-size: 1.2rem;">{st.session_state.subject}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    theme_display = st.session_state.analogy_theme.split(' (')[0]
    st.markdown(f"""
    <div class="dashboard-card">
        <div><small>ANALOGY ENGINE</small></div>
        <div class="highlight" style="font-size: 1.2rem;">{theme_display}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    turn_count = len(st.session_state.get('messages', [])) // 2
    st.markdown(f"""
    <div class="dashboard-card">
        <div><small>SESSION TURNS</small></div>
        <div class="highlight" style="font-size: 1.2rem;">{turn_count} Interactions</div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 8. Dynamic Prompt Engineering & Math Accuracy Engine
# -------------------------------------------------------------
if "None" in st.session_state.strictness:
    guardrail_instructions = "CORE RULE: PROVIDE DIRECT ANSWERS AND FULL SOLUTIONS IMMEDIATELY. Do not hold back."
elif "Low" in st.session_state.strictness:
    guardrail_instructions = "CORE RULE: Give the direct answer first, then provide a brief step-by-step breakdown."
elif "Medium" in st.session_state.strictness:
    guardrail_instructions = "CORE RULE: Start with a clear hint. If the user asks again, give the answer directly."
else:  
    guardrail_instructions = "CORE RULE: NEVER provide direct answers to homework. Guide the student step-by-step using targeted questions."

SYSTEM_INSTRUCTION = f"""
You are CogniPulse, an advanced AI Study Assistant.
Subject context: {st.session_state.subject}.
Analogy thematic style: {st.session_state.analogy_theme}.
Depth requirement: {st.session_state.detail_level}.

{guardrail_instructions}

MATHEMATICAL EQUATIONS & CALCULATION ACCURACY RULE:
- For any mathematical equation, arithmetic subtraction, addition, multiplication, or division, perform the math step-by-step independently BEFORE presenting the final answer.
- Double-check every single column, digit carry/borrow, and calculation operation for 100% precision.
- Keep standard Markdown text and headers strictly OUTSIDE of LaTeX math blocks ($$ or $).
"""

# Render Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# -------------------------------------------------------------
# 9. Trigger Handling & Response Generation
# -------------------------------------------------------------
active_prompt = None

chat_input_val = st.chat_input("Ask a question, request a concept explanation, or share a problem...")
if chat_input_val:
    active_prompt = chat_input_val
elif "selected_recent" in st.session_state and st.session_state.selected_recent:
    active_prompt = st.session_state.selected_recent
    del st.session_state.selected_recent

if active_prompt:
    if not st.session_state.api_key:
        st.warning("⚠️ Please enter and lock in your Gemini API key in the sidebar first!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": active_prompt})
    save_data()

    with st.chat_message("user"):
        st.markdown(active_prompt)

    try:
        client = genai.Client(api_key=st.session_state.api_key)
        
        history = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])]
            )
            for m in st.session_state.messages[:-1]
        ]

        chat = client.chats.create(
            model="gemini-3.6-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
            ),
            history=history
        )

        with st.chat_message("assistant"):
            response = chat.send_message(active_prompt)
            assistant_reply = response.text
            st.markdown(assistant_reply)
            
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
        st.error(f"Error communicating with AI: {e}")
