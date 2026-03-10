# ==========================
# KNOWMAP BACKEND (Matches Streamlit UI)
# Routes: /register /login /upload /search /generate_graph /graph_view
# Storage: users.json (auth), in-memory docs+embeddings (search), Neo4j (graph)
# ==========================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import os
import re
import json
import time
import hashlib
import secrets

from neo4j import GraphDatabase

from sentence_transformers import SentenceTransformer, util

try:
    import spacy
    NLP = spacy.load("en_core_web_sm")
except Exception:
    NLP = None

from pyvis.network import Network


# ==========================
# APP CONFIG
# ==========================
app = Flask(__name__)
CORS(app)

# ==========================
# NEO4J CONFIG (edit if needed)
# ==========================
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "neo4j123")  # change if your password differs

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# ==========================
# LOCAL AUTH STORAGE
# ==========================
USERS_FILE = "users.json"
os.makedirs("datasets", exist_ok=True)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users_dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_dict, f, indent=2)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# sessions: token -> email
SESSIONS = {}

def get_bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    return None

def require_auth():
    token = get_bearer_token()
    if not token or token not in SESSIONS:
        return None
    return SESSIONS[token]


# ==========================
# SEMANTIC SEARCH STORAGE (Week-3)
# ==========================
MODEL = None
DOCS = []        # list of dict: {user, file, text}
EMBS = []        # list of embeddings (torch tensors or numpy arrays)

def get_model():
    global MODEL
    if MODEL is None:
        MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return MODEL

def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ==========================
# NEO4J HELPERS
# ==========================
def sanitize_rel(rel: str) -> str:
    rel = rel.strip().upper()
    rel = re.sub(r"[^A-Z0-9_]", "_", rel)
    if not rel:
        rel = "RELATED_TO"
    if rel[0].isdigit():
        rel = "_" + rel
    return rel

def store_triplet_tx(tx, subj: str, rel: str, obj: str):
    rel = sanitize_rel(rel)
    q = f"""
    MERGE (a:Entity {{name: $s}})
    MERGE (b:Entity {{name: $o}})
    MERGE (a)-[r:{rel}]->(b)
    """
    tx.run(q, s=subj, o=obj)

def save_triplets_to_neo4j(triplets):
    # triplets: [(s,r,o), ...]
    with driver.session() as session:
        for s, r, o in triplets:
            session.execute_write(store_triplet_tx, s, r, o)

def fetch_all_edges():
    with driver.session() as session:
        result = session.run("""
            MATCH (a)-[r]->(b)
            RETURN a.name AS source, type(r) AS relation, b.name AS target
            LIMIT 2000
        """)
        return [(rec["source"], rec["relation"], rec["target"]) for rec in result]


# ==========================
# ROUTES
# ==========================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "KnowMap Backend Running"})


# ==========================
# REGISTER (Streamlit sends email/password)
# ==========================
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or data.get("username") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    users = load_users()
    if email in users:
        return jsonify({"error": "User already exists"}), 400

    users[email] = hash_password(password)
    save_users(users)
    return jsonify({"message": "User registered successfully"})


# ==========================
# LOGIN (returns access_token as Streamlit expects)
# ==========================
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or data.get("username") or "").strip()
    password = data.get("password") or ""

    users = load_users()
    if email not in users or users[email] != hash_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = secrets.token_hex(16)
    SESSIONS[token] = email
    return jsonify({"access_token": token})


# ==========================
# UPLOAD (Milestone 1 + starts Milestone 2 & 3)
# - saves file
# - extracts text (TXT/CSV basic)
# - NER + simple relation extraction -> Neo4j triplets
# - stores embeddings for semantic search
# ==========================
@app.route("/upload", methods=["POST"])
def upload():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    f = request.files["file"]
    filename = f.filename or f"upload_{int(time.time())}.txt"
    save_path = os.path.join("datasets", filename)
    f.save(save_path)

    text = ""
    try:
        if filename.lower().endswith(".txt"):
            with open(save_path, "r", encoding="utf-8", errors="ignore") as fp:
                text = fp.read()
        elif filename.lower().endswith(".csv"):
            import pandas as pd
            df = pd.read_csv(save_path)
        else:
            return jsonify({"error": "Unsupported file format"}), 400
    except Exception as e:
        return jsonify({"error": f"File read error: {str(e)}"}), 400

    if not text and "df" not in locals():
        return jsonify({"error": "No data extracted from file"}), 400

    row_sentences = []
    csv_triplets = []

    if "df" in locals():
    # clean column names
     df.columns = [str(c).strip() for c in df.columns]

    def add_triplet(s, r, o):
        s = str(s).strip()
        o = str(o).strip()
        if s and o and o.lower() not in ("nan", "none", ""):
            csv_triplets.append((s, r, o))

    for _, row in df.iterrows():
        # safer name lookup
        name = ""
        if "Name" in df.columns:
            name = str(row["Name"]).strip()
        elif "Patient_ID" in df.columns:
            name = f"Patient_{str(row['Patient_ID']).strip()}"

        if not name or name.lower() in ("nan", "none", ""):
            continue

        city = str(row["City"]).strip() if "City" in df.columns else ""
        gender = str(row["Gender"]).strip() if "Gender" in df.columns else ""
        age = str(row["Age"]).strip() if "Age" in df.columns else ""
        bmi = str(row["BMI"]).strip() if "BMI" in df.columns else ""
        chol = str(row["Cholesterol_Level"]).strip() if "Cholesterol_Level" in df.columns else ""
        bp = str(row["Blood_Pressure"]).strip() if "Blood_Pressure" in df.columns else ""
        diabetes = str(row["Diabetes"]).strip() if "Diabetes" in df.columns else ""
        heart = str(row["Heart_Disease"]).strip() if "Heart_Disease" in df.columns else ""
        smoke = str(row["Smoking_Status"]).strip() if "Smoking_Status" in df.columns else ""
        insurance = str(row["Insurance_Status"]).strip() if "Insurance_Status" in df.columns else ""
        credit = str(row["Credit_Score"]).strip() if "Credit_Score" in df.columns else ""
        visits = str(row["Hospital_Visits_Per_Year"]).strip() if "Hospital_Visits_Per_Year" in df.columns else ""

        sentence = (
            f"{name} is a {age} year old {gender} living in {city}. "
            f"BMI {bmi}, cholesterol {chol}, blood pressure {bp}. "
            f"Diabetes {diabetes}, heart disease {heart}, smoking status {smoke}. "
            f"Insurance {insurance}, credit score {credit}, hospital visits per year {visits}."
        )
        row_sentences.append(sentence)

        add_triplet(name, "LIVES_IN", city)
        add_triplet(name, "HAS_GENDER", gender)
        add_triplet(name, "AGE", age)
        add_triplet(name, "BMI", bmi)
        add_triplet(name, "CHOLESTEROL_LEVEL", chol)
        add_triplet(name, "BLOOD_PRESSURE", bp)
        add_triplet(name, "HAS_DIABETES", diabetes)
        add_triplet(name, "HAS_HEART_DISEASE", heart)
        add_triplet(name, "SMOKING_STATUS", smoke)
        add_triplet(name, "INSURANCE_STATUS", insurance)
        add_triplet(name, "CREDIT_SCORE", credit)
        add_triplet(name, "HOSPITAL_VISITS_PER_YEAR", visits)

    text = "\n".join(row_sentences) if row_sentences else "CSV uploaded (no valid rows found)."

    if csv_triplets:
        save_triplets_to_neo4j(csv_triplets)
        print("CSV columns:", list(df.columns))
        print("CSV rows:", len(df))

    # ----- Milestone 2: NER + basic relations -----
    triplets = []
    entities = []
    if NLP is not None and text and not text.startswith("Uploaded:"):
        doc = NLP(text)
        entities = [ent.text.strip() for ent in doc.ents if ent.text.strip()]

        # Simple relation heuristic: connect consecutive entities
        for i in range(len(entities) - 1):
            triplets.append((entities[i], "RELATED_TO", entities[i + 1]))

        # Save to Neo4j
        if triplets:
            try:
                save_triplets_to_neo4j(triplets)
            except Exception as e:
                # still allow upload even if neo4j fails
                return jsonify({"error": f"Neo4j error while saving triplets: {e}"}), 500

    # ----- Milestone 3: Embeddings for semantic search -----
    try:
        model = get_model()
        emb = model.encode(text)
        DOCS.append({"user": user, "file": filename, "text": text})
        EMBS.append(emb)
    except Exception as e:
        return jsonify({"error": f"Embedding error: {e}"}), 500

    return jsonify({
        "msg": "uploaded successfully",
        "file": filename,
        "entities_count": len(entities),
        "preview": text[:1000]
    })


# ==========================
# SEMANTIC SEARCH (Milestone 3)
# Streamlit calls /search with {"query": "..."} and Bearer token
# ==========================
@app.route("/search", methods=["POST"])
def search():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify([])

    if not DOCS:
        return jsonify([])

    model = get_model()
    q_emb = model.encode(query)

    results = []
    # search only user's docs
    for i, d in enumerate(DOCS):
        if d["user"] != user:
            continue
        score = float(util.cos_sim(q_emb, EMBS[i])[0][0].item())
        results.append({
            "file": d.get("file"),
            "text": (d.get("text") or "")[:200],
            "score": score
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(results[:5])


# ==========================
# GENERATE GRAPH (Milestone 3)
# Creates graph.html using edges in Neo4j
# ==========================
@app.route("/generate_graph", methods=["GET"])
def generate_graph():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        edges = fetch_all_edges()
        if not edges:
            return jsonify({"msg": "No edges found. Upload CSV/TXT first."})

        # Remove duplicates
        edges = list(dict.fromkeys(edges))

        # Build degree maps to identify "root" nodes (subjects/patients)
        out_deg = {}
        in_deg = {}
        for s, r, t in edges:
            out_deg[s] = out_deg.get(s, 0) + 1
            in_deg[t] = in_deg.get(t, 0) + 1

        net = Network(height="460px", width="100%", bgcolor="#ffffff", font_color="#1f2937", directed=True)

        # Add nodes/edges with colors (patient/root = green, values = blue)
        for s, r, t in edges:
            s_is_root = out_deg.get(s, 0) > 0

            if s_is_root:
                net.add_node(
                    s,
                    label=s,
                    color="#34d399",   # green
                    font={"color": "#0f172a"},
                    shape="dot",
                    size=18
                )
            else:
                net.add_node(
                    s,
                    label=s,
                    color="#93c5fd",   # blue
                    font={"color": "#0f172a"},
                    shape="dot",
                    size=14
                )

            # target typically attribute/value
            net.add_node(
                t,
                label=t,
                color="#93c5fd",     # blue
                font={"color": "#0f172a"},
                shape="dot",
                size=14
            )

            net.add_edge(s, t, title=r, label=r)

        # ✅ Professional force layout (NO green navigation arrows)
        net.set_options("""
{
  "layout": {
    "hierarchical": {
      "enabled": true,
      "direction": "LR",
      "sortMethod": "directed",
      "nodeSpacing": 160,
      "levelSeparation": 200,
      "treeSpacing": 200
    }
  },
  "physics": {
    "enabled": false
  },
  "interaction": {
    "hover": true,
    "navigationButtons": false,
    "zoomView": true,
    "dragView": false,
    "dragNodes": false
  },
  "nodes": {
    "shape": "box",
    "margin": 10,
    "font": {
      "size": 14
    }
  },
  "edges": {
    "arrows": {
      "to": {
        "enabled": true,
        "scaleFactor": 0.6
      }
    },
    "smooth": false
  }
}
""")

        net.save_graph("graph.html")
        return jsonify({"msg": "Graph generated", "edges": len(edges)})

    except Exception as e:
        return jsonify({"error": f"Graph generation error: {str(e)}"}), 500

# ==========================
# VIEW GRAPH (Streamlit embeds this HTML)
# ==========================
@app.route("/graph_view", methods=["GET"])
def graph_view():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if not os.path.exists("graph.html"):
        return jsonify({"msg": "Graph not generated yet"}), 404

    return send_file("graph.html")


# ==========================
# FEEDBACK (Milestone 4 basic)
# ==========================
FEEDBACK = []

@app.route("/feedback", methods=["POST"])
def feedback():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "Empty feedback"}), 400
    FEEDBACK.append({"user": user, "message": msg, "ts": int(time.time())})
    return jsonify({"message": "Feedback submitted"})

@app.route("/stats", methods=["GET"])
def stats():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    # Neo4j counts
    total_entities = 0
    total_relations = 0
    try:
        with driver.session() as session:
            q1 = session.run("MATCH (n) RETURN count(n) AS c")
            total_entities = int(q1.single()["c"])

            q2 = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
            total_relations = int(q2.single()["c"])
    except Exception:
        # If Neo4j temporarily unavailable, don't crash dashboard
        total_entities = 0
        total_relations = 0

    # Data sources from uploaded docs (DOCS list)
    data_sources = len(set([d.get("file") for d in DOCS])) if DOCS else 0

    # Accuracy is usually a placeholder unless you compute it
    extraction_accuracy = 94  # demo value (or compute later)

    # Pipeline status
    pipeline_status = {
        "ingestion": data_sources > 0,
        "nlp": total_entities > 0,
        "graph": os.path.exists("graph.html"),
        "search": len(DOCS) > 0 and len(EMBS) > 0
    }

    return jsonify({
        "total_entities": total_entities,
        "total_relations": total_relations,
        "data_sources": data_sources,
        "extraction_accuracy": extraction_accuracy,
        "pipeline_status": pipeline_status
    })

@app.route("/feedback", methods=["GET"])
def get_feedback():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"items": FEEDBACK[-10:][::-1]})

@app.route("/edit_entity", methods=["POST"])
def edit_entity():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    old_name = (data.get("old_name") or "").strip()
    new_name = (data.get("new_name") or "").strip()

    if not old_name or not new_name:
        return jsonify({"error": "old_name and new_name required"}), 400

    try:
        with driver.session() as session:
            session.run(
                "MATCH (n:Entity {name:$old}) SET n.name=$new",
                old=old_name, new=new_name
            )
        return jsonify({"message": "Entity updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/merge_entities", methods=["POST"])
def merge_entities():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    name1 = (data.get("name1") or "").strip()
    name2 = (data.get("name2") or "").strip()
    keep = (data.get("keep") or name1).strip()  # keep node name

    if not name1 or not name2:
        return jsonify({"error": "name1 and name2 required"}), 400
    if name1 == name2:
        return jsonify({"error": "Both names are the same"}), 400

    try:
        with driver.session() as session:
            # check both nodes exist
            row = session.run("""
                OPTIONAL MATCH (a:Entity {name:$keep})
                OPTIONAL MATCH (b:Entity {name:$drop})
                RETURN a IS NOT NULL AS a_ok, b IS NOT NULL AS b_ok
            """, keep=keep, drop=name2).single()

            if not row["a_ok"]:
                return jsonify({"error": f"Entity not found: {keep}"}), 404
            if not row["b_ok"]:
                return jsonify({"error": f"Entity not found: {name2}"}), 404

            # Move OUTGOING relationships of b -> y  to a -> y
            session.run("""
                MATCH (a:Entity {name:$keep}), (b:Entity {name:$drop})
                MATCH (b)-[r]->(y)
                MERGE (a)-[:RELATED_TO]->(y)
            """, keep=keep, drop=name2)

            # Move INCOMING relationships of x -> b  to x -> a
            session.run("""
                MATCH (a:Entity {name:$keep}), (b:Entity {name:$drop})
                MATCH (x)-[r]->(b)
                MERGE (x)-[:RELATED_TO]->(a)
            """, keep=keep, drop=name2)

            # Delete the duplicate node
            session.run("""
                MATCH (b:Entity {name:$drop})
                DETACH DELETE b
            """, drop=name2)

        return jsonify({"message": f"Merged '{name2}' into '{keep}' successfully"})

    except Exception as e:
        return jsonify({"error": f"Merge error: {str(e)}"}), 500

@app.route("/clear_graph", methods=["POST"])
def clear_graph():
    user = require_auth()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        # remove html
        if os.path.exists("graph.html"):
            os.remove("graph.html")
        return jsonify({"message": "Graph cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ==========================
# RUN
# ==========================
if __name__ == "__main__":
    print("KnowMap Backend Running...")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
