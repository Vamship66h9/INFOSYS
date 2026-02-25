import streamlit as st
import requests

API = "http://127.0.0.1:5000"

st.title("KnowMap Week-3")

# ---------- SAFE RESPONSE FUNCTION ----------
def show_response(r):
    try:
        st.json(r.json())
    except:
        st.error(r.text)


# ---------- CHECK BACKEND ----------
try:
    requests.get(API)
except:
    st.error("⚠ Backend not running. Start Flask first.")
    st.stop()


# ⭐ ADD SEARCH TO MENU
menu = st.sidebar.selectbox("Menu", ["Register","Login","Upload","Search"])


# ================= REGISTER =================
if menu == "Register":

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Register"):

        r = requests.post(
            API + "/register",
            json={"email": email, "password": password}
        )

        show_response(r)


# ================= LOGIN =================
elif menu == "Login":

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        r = requests.post(
            API + "/login",
            json={"email": email, "password": password}
        )

        try:
            data = r.json()
        except:
            st.error(r.text)
            st.stop()

        if "access_token" in data:
            st.session_state.token = data["access_token"]
            st.success("✅ Login successful")
        else:
            st.error(data)


# ================= UPLOAD =================
elif menu == "Upload":

    if "token" not in st.session_state:
        st.warning("⚠ Please login first")
    else:

        file = st.file_uploader("Upload PDF / TXT / DOCX")

        if file:

            headers = {
                "Authorization": f"Bearer {st.session_state.token}"
            }

            r = requests.post(
                API + "/upload",
                files={"file": file},
                headers=headers
            )

            show_response(r)


# ================= ⭐ WEEK-3 SEARCH =================
elif menu == "Search":

    if "token" not in st.session_state:
        st.warning("⚠ Please login first")

    else:

        query = st.text_input("Ask something about your files")

        if st.button("Search"):

            headers = {
                "Authorization": f"Bearer {st.session_state.token}"
            }

            r = requests.post(
                API + "/search",
                json={"query": query},
                headers=headers
            )

            try:
                results = r.json()

                if isinstance(results, list) and len(results) > 0:

                    st.success(f"Found {len(results)} results")

                    for i, doc in enumerate(results,1):
                        st.write(f"### Result {i}")
                        st.write(doc.get("content",""))

                else:
                    st.warning("No matching documents found")

            except:
                st.error(r.text)
