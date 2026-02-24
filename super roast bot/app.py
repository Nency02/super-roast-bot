"""
RoastBot 🔥 — A RAG-based AI chatbot that roasts you into oblivion.
Built with Streamlit + Groq + FAISS.
"""

import os
from pathlib import Path
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from rag import retrieve_context
from prompt import SYSTEM_PROMPT
from memory import add_to_memory, format_memory, clear_memory
from rate_limiter import is_rate_limited, record_request

# ── Load environment variables from the .env file next to this script ──
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

# ── Validate the API key is present and not a placeholder ──
_api_key = os.getenv("GROQ_KEY")
if not _api_key or _api_key.strip() in ("", "YOUR API KEY", "your_groq_api_key_here"):
    raise EnvironmentError(
        "GROQ_KEY is not set or is still the placeholder value. "
        "Please add your Groq API key to the .env file:\n"
        "  GROQ_KEY=your_actual_key_here"
    )

# ── Configuration ──
GROQ_API_KEY = os.getenv("GROQ_KEY")
if not GROQ_API_KEY:
    st.error("❌ GROQ_KEY not found in .env file. Please configure your API key.")
    st.stop()

# ── Configure Groq client (OpenAI-compatible) ──
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

TEMPERATURE = float(os.getenv("TEMPERATURE", 0.8))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 512))
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")


def chat(user_input: str) -> str:
    """Generate a roast response for the user's input using structured messages."""

    # used .strip to remove whitespaces 
    if not user_input or user_input.isspace():
        return "You sent me nothing? Even your messages are empty, just like your GitHub contribution graph. 🔥"

    try:
        # Retrieve relevant roast context via RAG
        context = retrieve_context(user_input)

        # Get conversation history
        history = format_memory()

        # Build structured messages to avoid prompt injection and instruction mixing
        messages = [
            {
                "role": "user",
                "content": (
                    f"Roast context (from knowledge base):\n{context}\n\n"
                    f"Recent conversation:\n{history}\n\n"
                    f"Current message: {user_input}"
                ),
            },
        ]

        # Generate response from Groq using structured system prompt
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages,
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        reply = response.choices[0].message.content

        # Store in memory
        add_to_memory(user_input, reply)

        return reply

    except Exception as e:
        st.error(f"Error generating roast: {e}")
        return f"Even I broke trying to roast you. Error: {str(e)[:100]}"

st.set_page_config(page_title="Super RoastBot", page_icon="🔥", layout="centered")

st.title("🔥Super RoastBot")
st.caption("I roast harder than your code roasts your CPU")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        clear_memory()
        st.success("Chat cleared!")
        st.rerun()
    st.divider()
    st.markdown(
        "**How it works:**\n"
        "1. Your message is sent to RAG retrieval\n"
        "2. Relevant roast knowledge is fetched\n"
        "3. Groq crafts a personalized roast\n"
        "4. You cry. Repeat."
    )
    st.divider()
    st.markdown(
        "**⚙️ Config (env-based):**\n"
        f"- Model: `{MODEL_NAME}`\n"
        f"- Temp: `{TEMPERATURE}`\n"
        f"- Max tokens: `{MAX_TOKENS}`"
    )

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="😈" if msg["role"] == "assistant" else "🤡"):
        st.markdown(msg["content"])

# Chat input
if user_input := st.chat_input("Say something... if you dare 🔥"):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🤡"):
        st.markdown(user_input)


    # Check rate limit before processing
    session_id = st.session_state.session_id
    limited, info = is_rate_limited(session_id)

    if limited:
        with st.chat_message("assistant", avatar="😈"):
            reply = (
                f"🚫 **Rate limit exceeded.** "
                f"You've hit the max of {info['limit']} requests per {info['window']}s. "
                f"Try again in **{info['retry_after']}s**. "
                f"Even roast masters need a cooldown. 🔥"
            )
            st.warning(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
    else:
        # Record the request and generate roast
        record_request(session_id)
        with st.chat_message("assistant", avatar="😈"):
            with st.spinner("Cooking up a roast... 🍳"):
                try:
                    reply = chat(user_input)
                    st.markdown(reply)
                except Exception as e:
                    reply = f"Even I broke trying to roast you. Error: {e}"
                    st.error(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})

