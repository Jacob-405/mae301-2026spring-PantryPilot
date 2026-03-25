import streamlit as st

# Always render something immediately
st.set_page_config(page_title="PantryPilot", page_icon="🍳")
st.title("🍳 PantryPilot")
st.write("Enter constraints, then click **Generate recipes**.")

# Inputs
col1, col2 = st.columns(2)
with col1:
    time_minutes = st.number_input("Time available (minutes)", min_value=5, max_value=180, value=20, step=5)
    budget = st.selectbox("Budget", ["low", "medium", "high"])
with col2:
    tools = st.text_input("Tools you have (comma separated)", value="microwave, skillet")
    preferences = st.text_input("Preferences (comma separated)", value="vegetarian, spicy")

# Lazy-load model only when needed
@st.cache_resource
def get_model():
    from nanogpt.src.generate import load_model
    return load_model("nanogpt/outputs/ckpt_best.pt")

def clean_output(text: str) -> str:
    # quick UI cleanup for the annoying "'S" artifact
    text = text.replace("Title: 'S ", "Title: ").replace("Title: \"S ", "Title: ")
    return text

if st.button("Generate recipes"):
    with st.spinner("Loading model + generating recipes..."):
        model, enc, device = get_model()
        from nanogpt.src.generate import generate_recipes

        recipes = generate_recipes(
            model=model,
            enc=enc,
            device=device,
            budget=budget,
            time_minutes=int(time_minutes),
            tools=tools,
            preferences=preferences,
            n=3,
            temperature=0.7,
            top_k=40,
        )

    for i, r in enumerate(recipes, 1):
        r = clean_output(r)
        st.subheader(f"Option {i}")
        st.code(r, language="markdown")

st.caption("Tip: If the outputs look repetitive, retrain longer or increase dataset size.")