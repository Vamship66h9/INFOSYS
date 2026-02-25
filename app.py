# ---------- IMPORTS ----------
from flask import Flask, request, jsonify, send_file
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from pyvis.network import Network
import networkx as nx
import json, os, re, spacy

# ---------- APP SETUP ----------
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'knowmap-secret'

jwt = JWTManager(app)
bcrypt = Bcrypt(app)

# ---------- DATABASE ----------
client = MongoClient("mongodb://localhost:27017/")
db = client['knowmap']
texts = db['texts']

# ---------- LOAD MODELS ----------
nlp = spacy.load("en_core_web_sm")
model = SentenceTransformer('all-MiniLM-L6-v2')

UPLOAD = "datasets"
os.makedirs(UPLOAD, exist_ok=True)

# ---------- HOME ----------
@app.route("/")
def home():
    return "KnowMap backend running"


# ---------- JSON USER DATABASE ----------
def load(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


# ---------- CLEAN TEXT ----------
def clean(text):
    text = re.sub(r"\W+", " ", text)
    return text.lower()


# ---------- REGISTER ----------
@app.route("/register", methods=["POST"])
def register():

    data = request.json
    users = load("users.json")

    if data["email"] in users:
        return jsonify({"msg": "User exists"}), 400

    users[data["email"]] = bcrypt.generate_password_hash(
        data["password"]
    ).decode("utf-8")

    save("users.json", users)

    return jsonify({"msg": "Registered"})


# ---------- LOGIN ----------
@app.route("/login", methods=["POST"])
def login():

    data = request.json
    users = load("users.json")

    if (
        data["email"] in users
        and bcrypt.check_password_hash(users[data["email"]], data["password"])
    ):

        token = create_access_token(identity=data["email"])
        return jsonify(access_token=token)

    return jsonify({"msg": "Invalid login"}), 401


# ---------- UPLOAD FILE + NLP ----------
@app.route('/upload', methods=['POST'])
@jwt_required()
def upload():

    email = get_jwt_identity()

    file = request.files['file']
    path = os.path.join(UPLOAD, file.filename)
    file.save(path)

    text = ""

    # SAFE TEXT READ
    if file.filename.endswith(".txt"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    else:
        text = "Uploaded successfully (preview works for TXT files)"

    cleaned = clean(text)

    # NLP entities
    doc = nlp(text)
    entities = [ent.text for ent in doc.ents]

    # AI embedding
    embedding = model.encode(text).tolist()

    # Save Mongo
    texts.insert_one({
        "user": email,
        "file": file.filename,
        "text": cleaned[:5000],
        "entities": entities,
        "embedding": embedding
    })

    return jsonify({
        "msg": "uploaded successfully",
        "preview": cleaned[:1000]
    })


# ---------- GENERATE GRAPH ----------
@app.route("/generate_graph")
@jwt_required()
def generate_graph():

    G = nx.DiGraph()

    for doc in texts.find():
        ents = doc.get("entities", [])

        for i in range(len(ents)-1):
            G.add_edge(ents[i], ents[i+1])

    net = Network(height="700px", width="100%")

    for node in G.nodes:
        net.add_node(node, label=node)

    for edge in G.edges:
        net.add_edge(edge[0], edge[1])

    net.save_graph("graph.html")

    return jsonify({"msg": "Graph generated"})


# ---------- VIEW GRAPH ----------
@app.route("/graph_view")
@jwt_required()
def graph_view():

    if not os.path.exists("graph.html"):
        return jsonify({"msg": "Graph not generated yet"}), 404

    return send_file("graph.html")


# ---------- SEMANTIC SEARCH ----------
@app.route("/search", methods=["POST"])
@jwt_required()
def search():

    query = request.json.get("query")
    query_embedding = model.encode(query)

    results = []

    for doc in texts.find():

        stored_embedding = doc.get("embedding")

        if stored_embedding:

            score = util.cos_sim(query_embedding, stored_embedding)[0][0].item()

            results.append({
                "file": doc.get("file"),
                "text": doc.get("text")[:200],
                "score": float(score)
            })

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return jsonify(results[:5])


# ---------- RUN ----------
if __name__ == "__main__":
    print("RUNNING KNOWMAP BACKEND...")
    app.run(debug=True, port=5000)
