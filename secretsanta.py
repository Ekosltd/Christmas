"""
Secret Santa - Streamlit app

"""

import json
import random
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------
# Settings
# ---------------------------------------------------------------
PARTICIPANTS = [
    "Alessia", "Michael", "Mick", "Brian", "Nicola", "Alison",
    "Joe", "Gemma", "Dianne", "Connor", "Chris",
]
DATA_FILE = Path(__file__).parent / "secret_santa_data.json"

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:  # no secrets file / key missing
    ADMIN_PASSWORD = None


# ---------------------------------------------------------------
# One shared lock for every user session, so simultaneous draws
# are handled one at a time and never overwrite each other.
# ---------------------------------------------------------------
@st.cache_resource
def get_lock():
    return threading.Lock()


LOCK = get_lock()


def make_assignments(names):
    """Shuffle everyone into one loop: each person gives to the next.
    Nobody gets themselves; everyone gives and receives exactly once."""
    shuffled = names[:]
    random.shuffle(shuffled)
    return {shuffled[i]: shuffled[(i + 1) % len(shuffled)] for i in range(len(shuffled))}


def _read():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return None


def _write(data):
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(DATA_FILE)  # atomic swap, never a half-written file


def load_data():
    with LOCK:
        data = _read()
        if data is None:
            data = {"assignments": make_assignments(PARTICIPANTS), "revealed": {}}
            _write(data)
        return data


def claim_draw(name):
    """Returns the match if this is the person's first draw, else None."""
    with LOCK:
        data = _read()
        if name in data["revealed"]:
            return None
        data["revealed"][name] = datetime.now().strftime("%d %b %Y, %H:%M:%S")
        _write(data)
        return data["assignments"][name]


def reset_data():
    with LOCK:
        _write({"assignments": make_assignments(PARTICIPANTS), "revealed": {}})


# ---------------------------------------------------------------
# App
# ---------------------------------------------------------------
st.set_page_config(page_title="Secret Santa", page_icon="🎅", layout="centered")
st.title("🎅 Office Secret Santa")

tab_draw, tab_admin = st.tabs(["Draw", "Admin"])

# ---------------- Draw tab ----------------
with tab_draw:
    # Result lives only in this browser session -> gone on refresh
    if "my_result" in st.session_state:
        who, match = st.session_state["my_result"]
        st.success(f"### {who}, you're buying a gift for **{match}**! 🎁")
    else:
        data = load_data()
        remaining = [p for p in PARTICIPANTS if p not in data["revealed"]]

        if not remaining:
            st.info("Everyone has drawn!")
        else:
            st.write("Pick your name. You get **one** look ")
            name = st.selectbox("Your name", ["-- select --"] + remaining)

            if st.button("Reveal🎄", type="primary", disabled=name == "-- select --"):
                match = claim_draw(name)
                if match is None:
                    st.error(f"{name} has already drawn. If that wasn't you, tell the organiser.")
                else:
                    st.session_state["my_result"] = (name, match)
                    st.balloons()
                    st.rerun()

        st.caption(f"{len(data['revealed'])} of {len(PARTICIPANTS)} people have drawn so far.")

# ---------------- Admin tab ----------------
with tab_admin:
    if not ADMIN_PASSWORD:
        st.error("No ADMIN_PASSWORD set in Streamlit secrets.")
        st.stop()

    pw = st.text_input("Admin password", type="password")
    if pw != ADMIN_PASSWORD:
        if pw:
            st.error("Wrong password.")
        st.stop()

    data = load_data()
    st.subheader("Results")
    rows = [
        {
            "Giver": giver,
            "Buying for": receiver,
            "Drawn?": "✅" if giver in data["revealed"] else "⏳",
            "When": data["revealed"].get(giver, ""),
        }
        for giver, receiver in sorted(data["assignments"].items())
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    not_drawn = [p for p in PARTICIPANTS if p not in data["revealed"]]
    st.write("**Still to draw:** " + (", ".join(not_drawn) if not_drawn else "nobody 🎉"))

    st.divider()
    st.subheader("Reset")
    st.write("Clears all draws and reshuffles the matches. Use for testing.")
    confirm = st.checkbox("Yes, I want to reset everything")
    if st.button("Reset 🔄", disabled=not confirm):
        reset_data()
        st.session_state.pop("my_result", None)
        st.success("Reset done. New matches generated.")
        st.rerun()
