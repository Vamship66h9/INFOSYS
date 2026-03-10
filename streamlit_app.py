import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from io import BytesIO
import re

API = "http://127.0.0.1:5000"

st.set_page_config(page_title="KnowMap", page_icon="🧠", layout="wide")

# -------------------- Professional CSS --------------------

# -------------------- Dark + Animated CSS --------------------
st.markdown("""
<style>

/* ===== FULL DARK BACKGROUND ===== */
html, body, [data-testid="stAppViewContainer"], .stApp {
  background: radial-gradient(circle at top left, #1e1b4b 0%, #0f172a 45%, #020617 100%) !important;
  color: #e5e7eb !important;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

[data-testid="stToolbar"] {
  right: 1.5rem;
}

/* ===== HEADER ===== */
.km-header{
  background: linear-gradient(90deg, rgba(91,47,191,0.85), rgba(37,99,235,0.82));
  padding: 16px 18px;
  border-radius: 18px;
  color: white;
  box-shadow: 0 12px 30px rgba(0,0,0,.45);
  margin-bottom: 14px;
  animation: fadeDown .7s ease-out;
}

.km-title{
  font-size: 24px;
  font-weight: 900;
  color: white;
  animation: glowText 2.5s ease-in-out infinite alternate;
}

.km-sub{
  font-size: 13px;
  opacity: .92;
  margin-top: 2px;
  color: #dbeafe;
}

@keyframes fadeDown {
  from { opacity: 0; transform: translateY(-12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes glowText {
  from { text-shadow: 0 0 4px rgba(255,255,255,0.15); }
  to { text-shadow: 0 0 16px rgba(147,197,253,0.55); }
}

/* ===== CARDS ===== */
.km-card{
  background: rgba(15,23,42,0.82);
  border-radius: 16px;
  padding: 16px;
  border: 1px solid rgba(148,163,184,0.18);
  box-shadow: 0 12px 24px rgba(0,0,0,0.30);
  backdrop-filter: blur(8px);
  animation: fadeUp .35s ease-out;
}

@keyframes fadeUp {
  from { opacity:0; transform: translateY(10px);}
  to { opacity:1; transform: translateY(0);}
}

.km-cardtitle{
  font-weight: 800;
  font-size: 16px;
  color: #f8fafc;
  margin-bottom: 8px;
}

.km-muted{
  color:#cbd5e1;
  font-size: 13px;
}

.km-pill{
  display:inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(59,130,246,0.15);
  color: #bfdbfe;
  border: 1px solid rgba(96,165,250,0.25);
}

.km-hr{
  border:none;
  border-top:1px solid rgba(148,163,184,0.18);
  margin: 10px 0;
}

/* ===== BUTTONS ===== */
div.stButton > button{
  background: linear-gradient(90deg,#7c3aed,#2563eb,#06b6d4);
  background-size: 200% 200%;
  border: none;
  color: white;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 700;
  box-shadow: 0 10px 20px rgba(37,99,235,0.28);
  transition: transform .15s ease, box-shadow .15s ease;
  animation: gradientShift 4s ease infinite;
}

div.stButton > button:hover{
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 14px 28px rgba(59,130,246,0.35);
}

div.stButton > button:active{
  transform: translateY(0px);
}

@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

/* ===== INPUTS ===== */
div[data-baseweb="input"] input,
textarea {
  background: rgba(2,6,23,0.90) !important;
  color: #f8fafc !important;
  border: 1px solid rgba(148,163,184,0.22) !important;
  border-radius: 12px !important;
}

/* ===== CHECKBOX / LABELS ===== */
label, .stMarkdown, p, span {
  color: #e5e7eb !important;
}

/* ===== DATAFRAME ===== */
[data-testid="stDataFrame"] {
  background: rgba(15,23,42,0.78) !important;
  border: 1px solid rgba(148,163,184,0.18) !important;
  border-radius: 14px !important;
}

/* ===== METRICS ===== */
[data-testid="stMetricLabel"] {
  color: #cbd5e1 !important;
}
[data-testid="stMetricValue"] {
  color: #22c55e !important;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar {
  width: 8px;
}
::-webkit-scrollbar-thumb {
  background: rgba(96,165,250,0.55);
  border-radius: 10px;
}

      .km-metric-card{
  background: linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.88));
  border: 1px solid rgba(148,163,184,0.18);
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.28);
  animation: metricFade .45s ease-out;
}

.km-metric-title{
  color: #cbd5e1;
  font-size: 13px;
  margin-bottom: 8px;
}

.km-metric-value{
  color: #22c55e;
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
}

.km-metric-sub{
  color: #93c5fd;
  font-size: 12px;
  margin-top: 6px;
}

@keyframes metricFade {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}      

</style>
""", unsafe_allow_html=True)

# -------------------- Helpers --------------------
def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {"error": r.text}

def backend_alive():
    try:
        r = requests.get(API, timeout=2)
        return r.status_code < 500
    except Exception:
        return False

def auth_headers():
    token = st.session_state.get("token")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}

def require_login():
    if "token" not in st.session_state:
        st.warning("⚠ Please login first.")
        st.stop()

def set_page(name: str):
    st.session_state.page = name
    st.rerun()

# -------------------- Init session state --------------------
if "page" not in st.session_state:
    st.session_state.page = "Authentication"

if "last_upload" not in st.session_state:
    st.session_state.last_upload = None  # dict with file meta + preview info

# -------------------- Header --------------------
st.markdown("""
<div class="km-header">
  <div class="km-title">KnowMap: Cross-Domain Knowledge Mapping Tool</div>
  <div class="km-sub">Milestone UI (Professional) • Streamlit + Flask</div>
</div>
""", unsafe_allow_html=True)

# Stop if backend down (but DO NOT show a “system status” box)
if not backend_alive():
    st.error("Backend not running. Start Flask first: `python app.py`")
    st.stop()

# -------------------- TOP HORIZONTAL NAV (Titles) --------------------
nav_items = ["Authentication", "Upload", "NLP Pipeline", "Knowledge Graph", "Semantic Search", "Admin Dashboard"]

c = st.columns(len(nav_items))
for i, name in enumerate(nav_items):
    with c[i]:
        if st.button(name, use_container_width=True, key=f"nav_{name}"):
            set_page(name)

# -------------------- AUTH PAGE --------------------
if st.session_state.page == "Authentication":
    left, right = st.columns(2)

    with left:
        st.markdown("<div class='km-card'><div class='km-cardtitle'>👤 Sign In</div>"
                    "<div class='km-muted'>Login and you will be redirected directly to Upload.</div></div>",
                    unsafe_allow_html=True)
        email = st.text_input("Email", placeholder="user@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        remember = st.checkbox("Remember me", value=True)

        if st.button("Sign In"):
            r = requests.post(f"{API}/login", json={"email": email, "password": password})
            data = safe_json(r)
            if "access_token" in data:
                st.session_state.token = data["access_token"]
                st.success("✅ Login successful")
                # (4) Redirect directly to Upload
                st.session_state.page = "Upload"
                st.rerun()
            else:
                st.error(data)

    with right:
        st.markdown("<div class='km-card'><div class='km-cardtitle'>🆕 Create Account</div>"
                    "<div class='km-muted'>Create a new account using email + password.</div></div>",
                    unsafe_allow_html=True)

        r_email = st.text_input("New Email", key="reg_email")
        r_pass = st.text_input("New Password", type="password", key="reg_pass")

        if st.button("Create account"):
            r = requests.post(f"{API}/register", json={"email": r_email, "password": r_pass})
            st.json(safe_json(r))

    if "token" in st.session_state:
        st.markdown("<div style='margin-top:10px;' class='km-muted'>You are logged in.</div>", unsafe_allow_html=True)

# -------------------- UPLOAD PAGE --------------------
elif st.session_state.page == "Upload":
    require_login()

    st.markdown(
        "<div class='km-card'><div class='km-cardtitle'>🗂️ Dataset Upload</div>"
        "<div class='km-muted'>Upload CSV and preview it professionally with column selection, search, and row filters.</div></div>",
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    left, right = st.columns([0.38, 0.62], gap="large")

    # ---------------- LEFT: Upload + dataset choices ----------------
    with left:
        st.markdown(
            "<div class='km-card'><div class='km-cardtitle'>Upload & Source</div>"
            "<div class='km-muted'>Choose the dataset type and upload your CSV.</div><hr class='km-hr'/></div>",
            unsafe_allow_html=True
        )

        # Dataset selection (screenshot-style choices)
        ds1 = st.checkbox("Wikipedia Articles", value=False)
        ds2 = st.checkbox("Scientific Papers (Arxiv)", value=False)
        ds3 = st.checkbox("News Articles", value=False)
        st.markdown("<div class='km-muted' style='margin-top:6px;'>Custom Upload (CSV)</div>", unsafe_allow_html=True)

        file = st.file_uploader("Upload CSV file", type=["csv"])

        if st.button("Process Selected Datasets"):
            chosen = []
            if ds1: chosen.append("Wikipedia")
            if ds2: chosen.append("Arxiv")
            if ds3: chosen.append("News")
            chosen = chosen if chosen else ["Custom Upload"]
            st.success("Selected: " + ", ".join(chosen))

        if file is not None:
            # Upload to backend FIRST (keeps your pipeline + embeddings + neo4j updated)
            headers = auth_headers()
            with st.spinner("Uploading & processing via backend..."):
                # ✅ Read bytes once (so it works for both upload + preview)
                file_bytes = file.getvalue()

                r = requests.post(
                    f"{API}/upload",
                    files={"file": (file.name, file_bytes, "text/csv")},
                    headers=headers
                )
                backend_resp = safe_json(r)

                # ✅ Build DataFrame from bytes (not from `file` again)
                try:
                    df = pd.read_csv(BytesIO(file_bytes))
                    preview_info = {
                        "filename": file.name,
                        "type": "csv",
                        "backend": backend_resp,
                        "df": df
                    }
                except Exception as e:
                    preview_info = {
                        "filename": file.name,
                        "type": "error",
                        "backend": backend_resp,
                        "error": str(e),
                        "df": None
                    }

                st.session_state.last_upload = preview_info

                if "error" in backend_resp:
                    st.error(backend_resp)
                else:
                    st.success("✅ Uploaded and processed")

    # ---------------- RIGHT: Professional preview + tools ----------------
    with right:
        st.markdown(
            "<div class='km-card'><div class='km-cardtitle'>📄 Structured Preview</div>"
            "<div class='km-muted'>Filter rows, select columns, search, and sort.</div></div>",
            unsafe_allow_html=True
        )

        info = st.session_state.last_upload
        if not info or info.get("type") != "csv" or info.get("df") is None:
            st.info("Upload a CSV to see a structured preview here.")
        else:
            df = info["df"]

            # Header details (professional stats row)
            top1, top2, top3, top4 = st.columns(4)
            top1.metric("Rows", f"{len(df):,}")
            top2.metric("Columns", f"{len(df.columns):,}")
            top3.metric("Missing Cells", f"{int(df.isna().sum().sum()):,}")
            ent_count = (info.get("backend") or {}).get("entities_count", "—")
            top4.metric("Entities (backend)", ent_count)

            st.markdown("<hr class='km-hr'/>", unsafe_allow_html=True)

            # Controls
            c1, c2 = st.columns([0.55, 0.45])
            with c1:
                selected_cols = st.multiselect(
                    "Select columns",
                    list(df.columns),
                    default=list(df.columns)[: min(6, len(df.columns))]
                )
            with c2:
                sort_col = st.selectbox("Sort by", ["(none)"] + list(df.columns))

            search_text = st.text_input("Search in table (contains)", placeholder="type a keyword...")

            # Row range
            max_rows = len(df)
            if max_rows > 1:
                start, end = st.slider(
                    "Row range",
                    0, max_rows - 1,
                    (0, min(max_rows - 1, 200))
                )
            else:
                start, end = 0, 0

            view = df.copy()

            # Apply search filter
            if search_text.strip():
                s = search_text.strip().lower()
                view = view[view.astype(str).apply(lambda r: r.str.lower().str.contains(s, na=False)).any(axis=1)]

            # Apply column selection
            if selected_cols:
                view = view[selected_cols]
            else:
                st.warning("Select at least one column to display.")
                st.stop()

            # Apply sort
            if sort_col != "(none)" and sort_col in view.columns:
                try:
                    view = view.sort_values(by=sort_col)
                except:
                    pass

            # Apply row slicing after filtering
            view = view.iloc[start:end+1]

            st.dataframe(view, use_container_width=True, height=520)

            # Backend preview text (optional)
            backend = info.get("backend") or {}
            if isinstance(backend, dict) and "preview" in backend:
                st.markdown("<hr class='km-hr'/>", unsafe_allow_html=True)
                st.markdown("**Backend Text Preview (used for embeddings/search):**")
                st.write(backend["preview"])

                
# -------------------- NLP PIPELINE PAGE --------------------
elif st.session_state.page == "NLP Pipeline":
    require_login()

    st.markdown("<div class='km-card'><div class='km-cardtitle'>🧪 NLP Pipeline</div>"
                "<div class='km-muted'>This page is now functional: it extracts Entities and basic Relations.</div></div>",
                unsafe_allow_html=True)

    left, right = st.columns([0.58, 0.42], gap="large")

    # Working NLP in Streamlit (so you see results immediately)
    # We try spaCy locally; if not installed, we show friendly message.
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        spacy_ok = True
    except Exception:
        spacy_ok = False
        nlp = None

    with left:
        st.markdown("<div class='km-card'><div class='km-cardtitle'>1) Text Input</div>"
                    "<div class='km-muted'>Paste text and run extraction (instant output).</div></div>",
                    unsafe_allow_html=True)

        sample = "Albert Einstein developed the theory of relativity in Bern."
        text = st.text_area("Enter text", value=sample, height=140)

        run = st.button("Run NLP Pipeline")

        if run:
            if not spacy_ok:
                st.error("spaCy model not available in Streamlit environment. Install & run:\n"
                         "`pip install spacy` then `python -m spacy download en_core_web_sm`")
            else:
                doc = nlp(text)

                entities = [{"Entity": ent.text, "Label": ent.label_} for ent in doc.ents]
                ents_only = [e["Entity"] for e in entities]

                # Basic relation: connect consecutive entities (demo / milestone-friendly)
                relations = []
                for i in range(len(ents_only) - 1):
                    relations.append({"Subject": ents_only[i], "Relation": "RELATED_TO", "Object": ents_only[i+1]})

                st.session_state.nlp_entities = entities
                st.session_state.nlp_relations = relations

    with right:
        st.markdown("<div class='km-card'><div class='km-cardtitle'>2) Output</div>"
                    "<div class='km-muted'>Entities + Relations shown in structured tables.</div></div>",
                    unsafe_allow_html=True)

        entities = st.session_state.get("nlp_entities", [])
        relations = st.session_state.get("nlp_relations", [])

        st.markdown("**Named Entity Recognition (NER):**")
        if entities:
            st.dataframe(pd.DataFrame(entities), use_container_width=True, height=220)
        else:
            st.info("Run pipeline to see extracted entities.")

        st.markdown("<hr class='km-hr'/>", unsafe_allow_html=True)
        st.markdown("**Relation Extraction (basic demo):**")
        if relations:
            st.dataframe(pd.DataFrame(relations), use_container_width=True, height=220)
        else:
            st.info("Run pipeline to see relations.")

# -------------------- KNOWLEDGE GRAPH PAGE --------------------
elif st.session_state.page == "Knowledge Graph":

    require_login()
    headers = auth_headers()

    st.markdown("""
    <div class='km-card'>
      <div class='km-cardtitle'>🧩 Knowledge Graph</div>
      <div class='km-muted'>Generate and explore connections. Use zoom buttons, hover nodes for details.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Top row: actions + info
    a, b, c = st.columns([0.18, 0.42, 0.40], gap="large")

    with a:
        if st.button("Generate Graph"):
            with st.spinner("Generating graph..."):
                r = requests.get(f"{API}/generate_graph", headers=headers)
            data = safe_json(r)
            st.session_state.last_graph_meta = data
            st.json(data)

    with b:
        meta = st.session_state.get("last_graph_meta", {})
        edges = meta.get("edges", "—")
        st.markdown(f"""
        <div class='km-card'>
          <div class='km-cardtitle'>Graph Summary</div>
          <div class='km-muted'>Edges created: <b>{edges}</b></div>
          <div class='km-muted'>Tip: Upload more CSV rows → regenerate graph.</div>
        </div>
        """, unsafe_allow_html=True)

    with c:
        st.markdown("""
        <div class='km-card'>
          <div class='km-cardtitle'>Controls</div>
          <div class='km-muted'>
            • Zoom: use +/− buttons<br/>
            • Hover: view node details<br/>
            • Drag: move nodes<br/>
            • Scroll: zoom in/out
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Graph container (smaller & clean)
    st.markdown("""
    <div class='km-card'>
      <div class='km-cardtitle'>Visualization</div>
      <div class='km-muted'>If it looks cluttered, regenerate after uploading fewer/more relevant columns.</div>
    </div>
    """, unsafe_allow_html=True)

    try:
        r = requests.get(f"{API}/graph_view", headers=headers)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            # ✅ smaller height, no massive empty box
            components.html(r.text, height=520, scrolling=True)
        else:
            st.info("Graph not generated yet. Click Generate Graph.")
    except Exception as e:
        st.error(f"Graph load failed: {e}")
# -------------------- SEMANTIC SEARCH PAGE --------------------
elif st.session_state.page == "Semantic Search":
    require_login()
    headers = auth_headers()

    st.markdown("<div class='km-card'><div class='km-cardtitle'>🔎 Semantic Search</div>"
                "<div class='km-muted'>Search across uploaded documents (professional result cards).</div></div>",
                unsafe_allow_html=True)

    q = st.text_input("Search for concepts across domains...", placeholder="e.g., electric cars, transformers, cancer detection")

    if st.button("Search"):
        with st.spinner("Searching..."):
            r = requests.post(f"{API}/search", json={"query": q}, headers=headers)
        data = safe_json(r)

        if isinstance(data, list) and len(data) > 0:
            for i, item in enumerate(data, 1):
                st.markdown(f"""
<div class="km-card" style="margin-top:10px;">
  <div class="km-cardtitle">Result {i} <span class="km-pill">score: {item.get('score',0):.3f}</span></div>
  <div class="km-muted"><b>File:</b> {item.get('file')}</div>
  <div style="margin-top:8px;">{item.get('text','')}</div>
</div>
""", unsafe_allow_html=True)
        else:
            st.warning("No results found. Upload more documents first.")

# -------------------- ADMIN DASHBOARD --------------------
elif st.session_state.page == "Admin Dashboard":

    require_login()
    headers = auth_headers()

    st.markdown("""
    <div class='km-card'>
        <div class='km-cardtitle'>⚙️ Admin Dashboard</div>
        <div class='km-muted'>Overview, pipeline performance, graph editor, feedback, and settings</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ===== LOAD STATS =====
    try:
        r = requests.get(f"{API}/stats", headers=headers)
        data = safe_json(r)
    except Exception:
        data = {}

    total_entities = data.get("total_entities", 0)
    total_relations = data.get("total_relations", 0)
    data_sources = data.get("data_sources", 0)
    extraction_accuracy = data.get("extraction_accuracy", 0)
    status = data.get("pipeline_status", {})

    # ===== TOP METRIC CARDS =====
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="km-metric-card">
            <div class="km-metric-title">Total Entities</div>
            <div class="km-metric-value">{total_entities}</div>
            <div class="km-metric-sub">Nodes in Neo4j</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="km-metric-card">
            <div class="km-metric-title">Total Relations</div>
            <div class="km-metric-value">{total_relations}</div>
            <div class="km-metric-sub">Edges in graph</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="km-metric-card">
            <div class="km-metric-title">Data Sources</div>
            <div class="km-metric-value">{data_sources}</div>
            <div class="km-metric-sub">Uploaded files</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="km-metric-card">
            <div class="km-metric-title">Extraction Accuracy</div>
            <div class="km-metric-value">{extraction_accuracy}%</div>
            <div class="km-metric-sub">Current demo score</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ===== PIPELINE STATUS =====
    st.markdown("""
    <div class='km-card'>
        <div class='km-cardtitle'>✅ Pipeline Status</div>
        <div class='km-muted'>Current status of ingestion, NLP, graph generation, and semantic search</div>
    </div>
    """, unsafe_allow_html=True)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Ingestion", "✅" if status.get("ingestion") else "❌")
    s2.metric("NLP", "✅" if status.get("nlp") else "❌")
    s3.metric("Graph", "✅" if status.get("graph") else "❌")
    s4.metric("Search", "✅" if status.get("search") else "❌")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ===== PROCESSING PIPELINE PERFORMANCE =====
    st.markdown("""
    <div class='km-card'>
        <div class='km-cardtitle'>📈 Processing Pipeline Performance</div>
        <div class='km-muted'>Visual progress of major system components</div>
    </div>
    """, unsafe_allow_html=True)

    perf_df = pd.DataFrame({
        "Stage": ["Ingestion", "NLP", "Graph", "Search"],
        "Progress": [
            100 if status.get("ingestion") else 20,
            100 if status.get("nlp") else 20,
            100 if status.get("graph") else 20,
            100 if status.get("search") else 20,
        ]
    }).set_index("Stage")

    st.bar_chart(perf_df)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ===== TABS =====
    tab1, tab2, tab3, tab4 = st.tabs(["🧩 Graph Editor", "💬 Feedback", "⚙️ Settings", "📌 Recent Feedback"])

    # ---------------- GRAPH EDITOR ----------------
    with tab1:
        st.markdown("""
        <div class='km-card'>
            <div class='km-cardtitle'>Graph Editor</div>
            <div class='km-muted'>Rename entities, merge duplicate nodes, and regenerate graph</div>
        </div>
        """, unsafe_allow_html=True)

        g1, g2 = st.columns(2)

        with g1:
            old_name = st.text_input("Old Entity Name", key="admin_old_name")
            new_name = st.text_input("New Entity Name", key="admin_new_name")

            if st.button("Update Entity Name", key="admin_update_btn"):
                r = requests.post(
                    f"{API}/edit_entity",
                    json={"old_name": old_name, "new_name": new_name},
                    headers=headers
                )
                st.json(safe_json(r))

        with g2:
            name1 = st.text_input("Entity 1", key="admin_merge_name1")
            name2 = st.text_input("Entity 2", key="admin_merge_name2")

            if st.button("Merge Entities", key="admin_merge_btn"):
                r = requests.post(
                    f"{API}/merge_entities",
                    json={"name1": name1, "name2": name2},
                    headers=headers
                )
                st.json(safe_json(r))

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        if st.button("Regenerate Graph", key="admin_regen_graph"):
            r = requests.get(f"{API}/generate_graph", headers=headers)
            st.json(safe_json(r))

    # ---------------- FEEDBACK ----------------
    with tab2:
        st.markdown("""
        <div class='km-card'>
            <div class='km-cardtitle'>Submit Feedback</div>
            <div class='km-muted'>Give your comments about graph quality, search quality, or UI improvements</div>
        </div>
        """, unsafe_allow_html=True)

        feedback_msg = st.text_area("Write feedback", key="admin_feedback_msg")

        if st.button("Submit Feedback", key="admin_feedback_btn"):
            r = requests.post(
                f"{API}/feedback",
                json={"message": feedback_msg},
                headers=headers
            )
            st.json(safe_json(r))

    # ---------------- SETTINGS ----------------
    with tab3:
        st.markdown("""
        <div class='km-card'>
            <div class='km-cardtitle'>Settings</div>
            <div class='km-muted'>Administrative controls for the project</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Clear Entire Graph", key="admin_clear_graph"):
            r = requests.post(f"{API}/clear_graph", headers=headers)
            st.json(safe_json(r))

        st.info("After clearing the graph, upload the dataset again and regenerate the graph.")

    # ---------------- RECENT FEEDBACK ----------------
    with tab4:
        st.markdown("""
        <div class='km-card'>
            <div class='km-cardtitle'>Recent Feedback</div>
            <div class='km-muted'>Latest submitted feedback messages</div>
        </div>
        """, unsafe_allow_html=True)

        try:
            r = requests.get(f"{API}/feedback", headers=headers)
            fb_data = safe_json(r)
            fb_items = fb_data.get("items", [])
        except Exception:
            fb_items = []

        if not fb_items:
            st.info("No feedback submitted yet.")
        else:
            for item in fb_items:
                st.markdown(f"""
                <div class="km-card" style="margin-top:10px;">
                    <div class="km-cardtitle">{item.get("user", "User")}</div>
                    <div class="km-muted">{item.get("message", "")}</div>
                </div>
                """, unsafe_allow_html=True)
