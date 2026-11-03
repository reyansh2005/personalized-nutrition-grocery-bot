"""Streamlit chat client for the personalized nutrition bot."""

import os

import requests
import streamlit as st

API_URL = os.getenv("NUTRITION_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="Nourish | Nutrition Assistant",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #f7fbf6 0%, #eef7f1 100%); }
    [data-testid="stSidebar"] { background: #153b2e; }
    [data-testid="stSidebar"] * { color: #f4fbf5 !important; }

    /* Keep typed ingredient text visible on the dark sidebar. */
    [data-testid="stSidebar"] div[data-testid="stTextInput"] input,
    [data-testid="stSidebar"] div[data-testid="stTextInput"] input:focus {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        -webkit-text-fill-color: #1F2937 !important;
        caret-color: #145A43 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 10px !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stTextInput"] input::placeholder {
        color: #6B7280 !important;
        -webkit-text-fill-color: #6B7280 !important;
        opacity: 1 !important;
    }

    /* Keep number controls readable against both the light page and dark sidebar. */
    div[data-testid="stNumberInput"] input,
    div[data-testid="stNumberInput"] input:focus,
    div[data-testid="stNumberInput"] input:disabled {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        -webkit-text-fill-color: #1F2937 !important;
        caret-color: #145A43 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 10px !important;
        opacity: 1 !important;
    }
    div[data-testid="stNumberInput"] input::placeholder {
        color: #6B7280 !important;
        opacity: 1 !important;
    }
    div[data-testid="stNumberInput"] button,
    div[data-testid="stNumberInput"] button:hover,
    div[data-testid="stNumberInput"] button:focus,
    div[data-testid="stNumberInput"] button:active,
    div[data-testid="stNumberInput"] button:disabled {
        background-color: #E8F5EE !important;
        color: #145A43 !important;
        border-color: #D1D5DB !important;
        opacity: 1 !important;
    }
    div[data-testid="stNumberInput"] button:hover {
        background-color: #CDEBDD !important;
    }
    div[data-testid="stNumberInput"] button svg,
    div[data-testid="stNumberInput"] button svg *,
    div[data-testid="stNumberInput"] button svg path,
    div[data-testid="stNumberInput"] button svg line {
        color: #145A43 !important;
        fill: currentColor !important;
        stroke: currentColor !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] [role="combobox"] {
        color: #1F2937 !important;
        -webkit-text-fill-color: #1F2937 !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"] svg {
        color: #145A43 !important;
        fill: currentColor !important;
        stroke: currentColor !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div {
        border-color: #145A43 !important;
        box-shadow: 0 0 0 1px #145A43 !important;
    }

    /* Keep pantry remove actions distinct from the add action. */
    div.stButton > button {
        background-color: #B42318 !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 1px solid #B42318 !important;
        border-radius: 10px !important;
        opacity: 1 !important;
        font-weight: 700 !important;
        min-width: 2.25rem !important;
    }
    div.stButton > button *,
    div.stButton > button p,
    div.stButton > button span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 1 !important;
    }
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #145A43 !important;
        color: #FFFFFF !important;
        border: 1px solid #145A43 !important;
        border-radius: 10px !important;
        opacity: 1 !important;
    }
    div.stButton > button:hover {
        background-color: #8F1D14 !important;
        border-color: #8F1D14 !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #0F4633 !important;
        border-color: #0F4633 !important;
        color: #FFFFFF !important;
    }
    div.stButton > button:focus-visible,
    div[data-testid="stFormSubmitButton"] > button:focus-visible {
        outline: 3px solid #9AD5B4 !important;
        outline-offset: 2px !important;
    }
    div.stButton > button svg,
    div[data-testid="stFormSubmitButton"] > button svg {
        color: currentColor !important;
        fill: currentColor !important;
        stroke: currentColor !important;
        opacity: 1 !important;
    }

    .hero { padding: 1.4rem 1.6rem; border-radius: 20px; background: linear-gradient(120deg, #1d5c46, #3c9870); color: white; margin-bottom: 1.2rem; }
    .hero h1 { margin: 0; font-size: 2.2rem; }
    .hero p { margin: .4rem 0 0; opacity: .9; }
    .metric-card { background: white; border: 1px solid #dcebe1; border-radius: 14px; padding: 1rem; text-align: center; }
    .source-note { color: #557064; font-size: .85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def fetch_pantry() -> list[dict]:
    try:
        response = requests.get(f"{API_URL}/pantry", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.sidebar.error(f"Backend unavailable: {exc}")
        return []


def add_pantry_item(item_name: str, quantity: float, unit: str) -> bool:
    try:
        response = requests.post(
            f"{API_URL}/pantry",
            json={"item_name": item_name, "quantity": quantity, "unit": unit},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        st.sidebar.error(f"Could not add pantry item: {exc}")
        return False


def remove_pantry_item(item_name: str) -> bool:
    try:
        response = requests.delete(
            f"{API_URL}/pantry/{requests.utils.quote(item_name, safe='')}",
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        st.sidebar.error(f"Could not remove pantry item: {exc}")
        return False


with st.sidebar:
    st.markdown("## 🥗 Nourish")
    st.caption("Your personal meal-planning workspace")
    available_budget = st.number_input(
        "Available budget ($)", min_value=0.0, value=20.0, step=1.0, key="available_budget"
    )
    st.divider()
    st.subheader("Add to pantry")
    with st.form("pantry_form", clear_on_submit=True):
        item_name = st.text_input("Ingredient", placeholder="e.g. Chicken Breast")
        quantity = st.number_input(
            "Quantity", min_value=0.0, value=1.0, step=0.5, key="pantry_quantity"
        )
        unit = st.selectbox("Unit", ["serving", "lb", "oz", "can", "bag", "dozen", "bottle"])
        submitted = st.form_submit_button("＋ Add ingredient", width="stretch")
    if submitted:
        if not item_name.strip():
            st.error("Enter an ingredient name.")
        elif add_pantry_item(item_name, quantity, unit):
            st.success(f"Added {item_name.strip()}.")
            st.rerun()

    st.divider()
    pantry = fetch_pantry()
    st.subheader(f"Pantry inventory · {len(pantry)} items")
    if pantry:
        for item in pantry:
            item_column, action_column = st.columns([4, 1], vertical_alignment="center")
            with item_column:
                st.markdown(
                    f"**{item['item_name']}**  \n"
                    f"<span class='source-note'>{item['quantity']:g} {item['unit']}</span>",
                    unsafe_allow_html=True,
                )
            with action_column:
                if st.button(
                    "-",
                    key=f"remove_{item['item_name']}",
                    help=f"Remove {item['item_name']} from the pantry",
                    width="stretch",
                ):
                    if remove_pantry_item(item["item_name"]):
                        st.rerun()
    else:
        st.info("Your pantry is empty. Add ingredients above.")

st.markdown(
    '<div class="hero"><h1>Personalized Nutrition Assistant</h1>'
    "<p>Plan affordable, protein-rich meals from your pantry and real food data.</p></div>",
    unsafe_allow_html=True,
)

metric_left, metric_right = st.columns(2)
with metric_left:
    st.markdown(
        f'<div class="metric-card"><b>Available budget</b><br><span style="font-size:1.5rem">${available_budget:.2f}</span></div>',
        unsafe_allow_html=True,
    )
with metric_right:
    st.markdown(
        '<div class="metric-card"><b>Data sources</b><br><span class="source-note">Recipes · Open Food Facts · SQLite pantry</span></div>',
        unsafe_allow_html=True,
    )

st.markdown("### What would you like to eat?")
st.caption("Try: “Give me dairy-free meals under $15” or “Show me dairy options with yogurt.”")

if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("meta"):
            st.caption(message["meta"])

if prompt := st.chat_input("Ask for a meal plan, ingredient swap, or nutrition check..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    request_text = f"{prompt} My available budget is ${available_budget:.2f}."
    with st.chat_message("assistant"):
        with st.spinner("Checking pantry, prices, and nutrition sources..."):
            try:
                response = requests.post(
                    f"{API_URL}/ask", json={"question": request_text}, timeout=120
                )
                response.raise_for_status()
                payload = response.json()
                answer = payload["answer"]
                product = payload.get("external_product")
                source_meta = (
                    f"Budget applied: ${payload.get('budget_used', 0):.2f} · "
                    "Sources: recipe KB + SQLite prices"
                )
                if product:
                    source_meta += f" · Open Food Facts: {product['product_name']}"
                st.markdown(answer)
                st.caption(source_meta)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "meta": source_meta}
                )
            except requests.RequestException as exc:
                st.error(f"Could not reach the nutrition backend: {exc}")
