# app.py
import streamlit as st
from transformers import pipeline
import random
import sqlite3
from datetime import datetime
import time

# --------------------------
# Database (local SQLite)
# --------------------------
DB_PATH = "youth_wellness.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS moods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mood TEXT,
                    note TEXT,
                    ts TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS journals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    entry TEXT,
                    ts TEXT
                )""")
    conn.commit()
    conn.close()

def save_mood(mood, note=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO moods (mood, note, ts) VALUES (?, ?, ?)",
              (mood, note, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_mood_stats(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT mood, ts FROM moods ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def save_journal(title, entry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO journals (title, entry, ts) VALUES (?, ?, ?)",
              (title, entry, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_journals(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, ts FROM journals ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# --------------------------
# Model (Hugging Face DialoGPT-small)
# --------------------------
@st.cache_resource(show_spinner=False)
def load_chat_model():
    # This uses the small DialoGPT model which is free and open-source.
    # It will download the model to disk (may take a minute the first time).
    pipe = pipeline("text-generation", model="microsoft/DialoGPT-small")
    return pipe

# --------------------------
# Psychoeducation content (simple)
# --------------------------
PSYCHO_TOPICS = {
    "Stress": "Stress is your body's response to challenges. Short breathing breaks, journaling, and talking to someone can help.",
    "Anxiety": "Anxiety is worry or nervousness that can feel overwhelming. Grounding exercises (5-4-3-2-1) and small routines help.",
    "Burnout": "Burnout is prolonged exhaustion from overwork. Rest, boundaries, and small enjoyable activities are important recoveries.",
    "Self-care": "Self-care are simple actions to maintain your well-being: sleep, hydration, breaks, friends, hobbies. Small steps matter."
}

# --------------------------
# Crisis keywords & helplines
# --------------------------
CRISIS_KEYWORDS = ["suicide", "kill myself", "want to die", "die", "hopeless", "worthless", "end my life"]
HELPLINES = {
    "India (NIMHANS)": "080-4611-0007",
    "iCall India": "+91 9152987821",
    "US (988)": "988",
    "International (if available)": "Contact local emergency services / national lifeline"
}

# --------------------------
# App layout & logic
# --------------------------
def main():
    init_db()
    st.set_page_config(page_title="Youth Wellness AI Prototype", page_icon="🌱", layout="wide")
    st.title("🌱 Youth Wellness AI — Free Prototype")
    st.markdown("A privacy-first, youth-friendly AI companion (prototype). *This is not a therapist.* For emergencies, contact local services.")

    # Sidebar Navigation
    st.sidebar.header("Navigation")
    page = st.sidebar.radio("", ["Home", "Mood Check-In", "AI Chatbot", "Well-being Toolkit", "Psychoeducation", "Journals", "About / Export"])

    # ---- Home ----
    if page == "Home":
        st.header("Welcome")
        st.write("""
            This prototype implements:
            - Mood check-ins (anonymous, local storage)
            - Empathetic chat using a free Hugging Face model
            - Wellbeing toolkit (tips, breathing exercise)
            - Psychoeducation modules (student-friendly)
            - Journaling & local saving
            - Crisis detection and helplines
        """)
        st.info("Privacy: All data is stored locally in this app (SQLite). No external APIs are used by default (free model).")

        st.markdown("### Quick actions")
        if st.button("Mood Check-In"):
            st.experimental_set_query_params(_page="Mood Check-In")
            st.experimental_rerun()
        if st.button("Open AI Chatbot"):
            st.experimental_set_query_params(_page="AI Chatbot")
            st.experimental_rerun()

    # ---- Mood Check-In ----
    elif page == "Mood Check-In":
        st.header("🧠 Mood Check-In")
        col1, col2 = st.columns([2, 3])
        with col1:
            mood = st.radio("How are you feeling today?",
                            ["😊 Happy", "😔 Sad", "😰 Stressed", "😡 Angry", "😐 Neutral"])
            note = st.text_area("Optional: add a quick note (what's on your mind?)", height=80)
            if st.button("Log Mood"):
                save_mood(mood, note)
                st.success("Thanks — your mood was logged locally. It's okay to feel this way.")
        with col2:
            st.subheader("Recent check-ins")
            rows = get_mood_stats(8)
            if rows:
                for r in rows:
                    st.write(f"- *{r[0]}*  — {r[1][:19]} UTC")
            else:
                st.write("No mood entries yet. Try logging one!")

    # ---- AI Chatbot ----
    elif page == "AI Chatbot":
        st.header("💬 Chat with AI Companion")
        st.write("This uses a free-weights model (DialoGPT-small). Responses are supportive but may be less fluent than paid models.")
        chat_model = load_chat_model()

        # small session state for chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_input = st.text_area("What's on your mind?", height=120, key="chat_input")
        send = st.button("Send")

        if send:
            if not user_input.strip():
                st.warning("Please type something before sending.")
            else:
                # Crisis detection
                low = user_input.lower()
                if any(k in low for k in CRISIS_KEYWORDS):
                    st.error("⚠ It looks like you may be in crisis or feeling unsafe. Please reach out to a helpline or trusted person immediately.")
                    for name, num in HELPLINES.items():
                        st.write(f"{name}** — {num}")
                    st.write("If you are in immediate danger, contact emergency services in your country.")
                # generate reply
                with st.spinner("AI is thinking..."):
                    # Use the text-generation pipeline with a small max length.
                    # We pass the user input as prompt; model will generate a continuation.
                    result = chat_model(user_input, max_length=80, do_sample=True, top_k=50)
                    gen = result[0]["generated_text"]
                    # model's generated_text often contains the prompt + reply
                    # attempt to extract reply portion:
                    reply = gen[len(user_input):].strip()
                    if not reply:
                        # fallback if extraction failed
                        reply = gen
                    # save to session history
                    st.session_state.chat_history.append(("You", user_input))
                    st.session_state.chat_history.append(("AI", reply))

        # show chat history
        if st.session_state.chat_history:
            st.subheader("Conversation")
            for speaker, text in st.session_state.chat_history[-10:]:
                if speaker == "You":
                    st.markdown(f"*You:* {text}")
                else:
                    st.markdown(f"*AI:* {text}")

        st.caption("Disclaimer: the AI is a supportive companion, not a therapist. For serious mental health issues, seek professional help.")

    # ---- Well-being Toolkit ----
    elif page == "Well-being Toolkit":
        st.header("🌸 Well-being Toolkit")
        st.write("Quick tools to help calm and reset.")

        # Daily tip card
        st.subheader("Daily Tip")
        tips = [
            "Take 5 deep breaths slowly.",
            "List 3 small things you are grateful for right now.",
            "Step outside for 2 minutes and notice 3 things.",
            "Drink a full glass of water and stretch.",
            "Send a quick message to a friend or family member."
        ]
        if st.button("Show me a tip"):
            st.info(random.choice(tips))

        # Breathing exercise with simple progress bar
        st.subheader("Breathing Exercise (box breathing — 1 cycle: 4s inhale, 4s hold, 4s exhale, 4s hold)")
        if st.button("Start 1-minute breathing"):
            total_seconds = 60
            t0 = time.time()
            prog = st.progress(0)
            status = st.empty()
            i = 0
            while time.time() - t0 < total_seconds:
                i += 1
                elapsed = time.time() - t0
                prog.progress(int((elapsed / total_seconds) * 100))
                phase = int((elapsed % 16) // 4)
                if phase == 0:
                    status.info("Inhale — 4 seconds")
                elif phase == 1:
                    status.info("Hold — 4 seconds")
                elif phase == 2:
                    status.info("Exhale — 4 seconds")
                else:
                    status.info("Hold — 4 seconds")
                time.sleep(1)
            prog.progress(100)
            status.success("Great — one minute done. How do you feel now?")

        # Gratitude journal quick save
        st.subheader("Gratitude / Quick Journal")
        g = st.text_area("Write one thing you're grateful for (or any quick note)", height=100)
        if st.button("Save Note"):
            if g.strip():
                save_journal("Gratitude Note", g.strip())
                st.success("Saved locally. Thank you for reflecting.")
            else:
                st.warning("Write something first :)")

    # ---- Psychoeducation ----
    elif page == "Psychoeducation":
        st.header("📘 Learn (Psychoeducation)")
        st.write("Short, friendly explanations about common topics.")
        topic = st.selectbox("Choose a topic", list(PSYCHO_TOPICS.keys()))
        st.info(PSYCHO_TOPICS[topic])
        st.markdown("---")
        st.write("Want more? Try journaling, talking to a friend, or doing a small breathing exercise above.")

    # ---- Journals ----
    elif page == "Journals":
        st.header("📓 Journals")
        st.subheader("Create a journal entry")
        title = st.text_input("Title")
        entry = st.text_area("Entry", height=200)
        if st.button("Save Journal Entry"):
            if entry.strip():
                save_journal(title if title.strip() else "Untitled", entry.strip())
                st.success("Journal saved locally.")
            else:
                st.warning("Write something before saving.")
        st.subheader("Recent entries")
        rows = get_journals(8)
        if rows:
            for r in rows:
                st.write(f"- *{r[1]}*  — {r[2][:19]} UTC  (id: {r[0]})")
        else:
            st.write("No journal entries yet.")

    # ---- About / Export ----
    elif page == "About / Export":
        st.header("About this prototype")
        st.write("This is a student-focused, privacy-first prototype implementing features from your project brief.")
        st.markdown("*Export / Data*")
        if st.button("Show database file path"):
            st.write(f"Database path: {DB_PATH} — you can open it with any SQLite viewer.")
        st.write("If you want to export data to CSV, run the following in the terminal or write a small script; data is stored in youth_wellness.db.")

if __name__ == "__main__":
    main()
