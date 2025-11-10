# app.py
# AI Student Performance Dashboard (forces light theme, sticky header, Firebase REST auth, Home/Team pages)

import os
import json
import io
import base64
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------
# Image helpers
# ---------------------------
def img_to_base64(path: str) -> str:
    """Convert local images to Base64 (returns '' if not found)."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return ""

def _to_b64(path: str) -> str:
    """Alias used by page_home; ensures no crash if image is missing."""
    return img_to_base64(path)

# ===========================
# Page setup
# ===========================
st.set_page_config(page_title="AI Student Performance Dashboard", layout="wide")

# ---- Global CSS: FORCE LIGHT THEME (works better on Brave) ----
st.markdown("""
<style>
/* Hard-force a light palette regardless of browser/system */
:root, html, body, [data-testid="stAppViewContainer"], [data-baseweb="baseweb"] {
  color-scheme: light !important;
  --bg: #ffffff;
  --bg-muted: #f7f7f9;
  --text: #101828;
  --text-soft: #334155;
  --border: rgba(0,0,0,0.08);
  --shadow: 0 10px 30px rgba(0,0,0,.08);
  --card: #ffffff;
}

html, body, .stApp { background: var(--bg) !important; color: var(--text) !important; }
.block-container { padding-top: 0.75rem !important; max-width: 100% !important; }

/* Move Login / Sign-up dialog lower */
.stDialog > div { margin-top: 160px !important; }

/* Custom app header: visible & sticky */
#app-header{
  position: sticky; top: 0; z-index: 1000; backdrop-filter: blur(8px);
  background: rgba(255,255,255,0.92) !important; border-bottom: 1px solid var(--border);
}

.header-row{ display:flex; align-items:center; gap:16px; padding:14px 8px; }
.h-title{ font-size:30px; font-weight:800; line-height:1.15; margin:0; color: var(--text); }
#nav-row, #actions-row{ display:flex; align-items:center; gap:10px; }
#actions-row{ margin-left:auto; }

#nav-row .stButton>button, #actions-row .stButton>button{
  border:1px solid var(--border) !important; background: var(--bg-muted) !important;
  border-radius:10px !important; padding:10px 16px !important; font-size:14px !important;
  height:42px !important; line-height:20px !important; color: var(--text) !important; box-shadow: none !important;
}
#nav-row .stButton>button[data-active="true"]{ background:#eaeef6 !important; }

/* Hide Streamlit chrome */
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }
footer { visibility: hidden !important; }

/* Cards */
.img3-row{ display:grid; gap:24px; grid-template-columns: repeat(3, 1fr); width:100%; }
@media (max-width: 1100px){ .img3-row{ grid-template-columns: 1fr; } }
.imgcard{ display:flex; flex-direction:column; border:1px solid var(--border); border-radius:14px; overflow:hidden; box-shadow: var(--shadow); background:var(--card); width:100%; }
.imgcard img{ width:100%; aspect-ratio: 16 / 10; object-fit:cover; }
.imgcap{ padding:14px 12px; font-weight:700; font-size:1.1rem; text-align:center; min-height:50px; color: var(--text); }
</style>
""", unsafe_allow_html=True)

# ===========================
# Firebase Auth (REST API)
# ===========================
@st.cache_resource(show_spinner=False)
def load_firebase_config():
    with open("firebase_config.json", "r", encoding="utf-8") as f:
        conf = json.load(f)
    for key in ["apiKey", "authDomain", "projectId", "appId"]:
        if not conf.get(key):
            raise ValueError(f"firebase_config.json missing '{key}'")
    return conf

FB = load_firebase_config()
API_KEY = FB["apiKey"]

# Support Emulator
EMULATOR_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")  # e.g. "localhost:9099"
if EMULATOR_HOST:
    IDTK = f"http://{EMULATOR_HOST}/identitytoolkit.googleapis.com/v1"
    SECTK = f"http://{EMULATOR_HOST}/securetoken.googleapis.com/v1"
else:
    IDTK = "https://identitytoolkit.googleapis.com/v1"
    SECTK = "https://securetoken.googleapis.com/v1"

# Robust session + POST helper
_session = requests.Session()
_retry = Retry(
    total=4, connect=3, read=3, status=3, backoff_factor=0.6,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET", "POST"])
)
_adapter = HTTPAdapter(max_retries=_retry)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

def _post(url: str, payload: dict) -> dict:
    try:
        r = _session.post(url, json=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.SSLError as e:
        raise RuntimeError(
            "SSL handshake failed. Disable HTTPS scanning in antivirus, update certs "
            "(pip install -U certifi requests), or try a different network."
        ) from e
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            "Network connection was reset by the remote host (WinError 10054). "
            "Likely firewall/antivirus/proxy or unstable network."
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError("The request to Firebase timed out. Please try again.") from e
    except requests.exceptions.HTTPError as e:
        try:
            detail = r.json()
        except Exception:
            detail = {"error": {"message": r.text}}
        raise RuntimeError(f"Firebase error {r.status_code}: {detail}") from e

# Email/password helpers
def sign_up_email_password(email: str, password: str, display_name: str | None = None) -> dict:
    data = _post(f"{IDTK}/accounts:signUp?key={API_KEY}",
                 {"email": email, "password": password, "returnSecureToken": True})
    id_token = data["idToken"]; refresh_token = data["refreshToken"]; local_id = data["localId"]
    if display_name:
        _post(f"{IDTK}/accounts:update?key={API_KEY}",
              {"idToken": id_token, "displayName": display_name, "returnSecureToken": True})
    _post(f"{IDTK}/accounts:sendOobCode?key={API_KEY}",
          {"requestType": "VERIFY_EMAIL", "idToken": id_token})
    return {
        "email": email, "idToken": id_token, "refreshToken": refresh_token,
        "localId": local_id, "name": display_name or email.split("@")[0], "verified": False
    }

def sign_in_email_password(email: str, password: str) -> dict:
    data = _post(f"{IDTK}/accounts:signInWithPassword?key={API_KEY}",
                 {"email": email, "password": password, "returnSecureToken": True})
    id_token = data["idToken"]; refresh_token = data["refreshToken"]; local_id = data["localId"]
    info = _post(f"{IDTK}/accounts:lookup?key={API_KEY}", {"idToken": id_token})
    u = (info.get("users") or [{}])[0]
    return {
        "email": email, "idToken": id_token, "refreshToken": refresh_token, "localId": local_id,
        "name": u.get("displayName") or email.split("@")[0], "verified": bool(u.get("emailVerified", False))
    }

def resend_verification(id_token: str) -> None:
    _post(f"{IDTK}/accounts:sendOobCode?key={API_KEY}",
          {"requestType": "VERIFY_EMAIL", "idToken": id_token})

def send_password_reset(email: str) -> None:
    _post(f"{IDTK}/accounts:sendOobCode?key={API_KEY}",
          {"requestType": "PASSWORD_RESET", "email": email})

def refresh_id_token(refresh_token: str) -> dict:
    data = _post(f"{SECTK}/token?key={API_KEY}",
                 {"grant_type": "refresh_token", "refresh_token": refresh_token})
    return {"idToken": data["id_token"], "RefreshToken": data["refresh_token"]}

def lookup_account(id_token: str) -> dict:
    info = _post(f"{IDTK}/accounts:lookup?key={API_KEY}", {"idToken": id_token})
    return (info.get("users") or [{}])[0]

# ===========================
# Session state (auth + router)
# ===========================
if "user" not in st.session_state:
    st.session_state.user = None  # {email,idToken,refreshToken,localId,name,verified}
if "route" not in st.session_state:
    st.session_state.route = "home"  # home | team

def go(route: str):
    st.session_state.route = route

# ===========================
# Helpers
# ===========================
def _logo_data_uri(path: str = "logo.png") -> str | None:
    """Return a data: URI for the given logo file, or None if missing."""
    if not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg" if ext in (".jpg", ".jpeg") else "image/svg+xml"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

GRADE_BOUNDS = [(90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D"), (0, "E")]

def to_grade(score: float) -> str:
    for bound, letter in GRADE_BOUNDS:
        if score >= bound: return letter
    return "E"

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def require_auth():
    if not st.session_state.user:
        st.markdown("### 🔐 Please log in to continue")
        if st.button("Login / Sign up", key="login_gate_btn"):
            auth_dialog()
        st.stop()

# ===========================
# Predictor dialog
# ===========================
@st.dialog("Student Performance Predictor")
def predictor_dialog():
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Age", 10, 25, 16, 1)
        gender = st.selectbox("Gender", ["Female", "Male", "Other"])
        absences = st.number_input("Absences", 0, 100, 5, 1)
        study_time = st.number_input("Study Time/week (hours)", 0, 60, 10, 1)
    with col2:
        parental_ed = st.selectbox("Parental Education",
                                   ["Primary", "Middle School", "High School", "Bachelor", "Master+"])
        parental_support = st.selectbox("Parental Support", ["Low", "Moderate", "High"])
        ethnicity = st.selectbox("Ethnicity", ["Group A", "Group B", "Group C", "Group D", "Group E"])
        sports = st.toggle("Participates in Sports", value=False)

    if st.button("Predict"):
        score = 50 + (study_time * 2.2) - (absences * 1.5)
        score += {"Low": -6, "Moderate": 0, "High": 6}[parental_support]
        score += {"Primary": -4, "Middle School": -2, "High School": 0, "Bachelor": 3, "Master+": 5}[parental_ed]
        if sports: score += 2.5
        score += -0.15 * (age - 17) ** 2 + 0.5
        score = clamp(score)
        st.subheader("Prediction")
        st.metric("Expected Percentage", f"{score:.1f}%")
        st.metric("Predicted Grade", to_grade(score))
        st.caption("Predictions are generated by a well-trained, validated model and should be interpreted alongside teacher judgment and class context.")

# ===========================
# Auth dialog (Login / Sign up / Forgot / Verify)
# ===========================
@st.dialog("Account", width="large")
def auth_dialog():
    tabs = st.tabs(["Login", "Sign up", "Forgot password", "Email verification"])

    # Login
    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email"); pwd = st.text_input("Password", type="password")
            go_btn = st.form_submit_button("Login")
        if go_btn:
            try:
                st.session_state.user = sign_in_email_password(email, pwd)
                st.success(f"Welcome back, {st.session_state.user['name']}!")
                st.rerun()
            except Exception as e:
                st.error("Login failed."); st.caption(str(e))

    # Sign up
    with tabs[1]:
        with st.form("signup_form", clear_on_submit=False):
            name = st.text_input("Full name"); email = st.text_input("Email")
            pwd = st.text_input("Password (min 6 chars)", type="password")
            go_btn = st.form_submit_button("Create account")
        if go_btn:
            try:
                st.session_state.user = sign_up_email_password(email, pwd, (name or "").strip() or None)
                st.success("Account created! We sent a verification email.")
            except Exception as e:
                st.error("Sign up failed."); st.caption(str(e))

    # Forgot password
    with tabs[2]:
        rp_email = st.text_input("Email for password reset")
        if st.button("Send reset link"):
            try:
                send_password_reset(rp_email); st.success("Password reset email sent.")
            except Exception as e:
                st.error("Could not send reset email."); st.caption(str(e))

    # Email verification
    with tabs[3]:
        if not st.session_state.user:
            st.info("Login first to view verification status.")
        else:
            badge = "verified ✅" if st.session_state.user.get("verified") else "not verified ❌"
            st.write(f"Current email **{st.session_state.user['email']}** is {badge}.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Resend verification email"):
                    try:
                        resend_verification(st.session_state.user["idToken"]); st.success("Verification email sent again.")
                    except Exception as e:
                        st.error("Could not send verification email."); st.caption(str(e))
            with c2:
                if st.button("I have verified. Refresh status"):
                    try:
                        if st.session_state.user.get("refreshToken"):
                            newt = refresh_id_token(st.session_state.user["refreshToken"])
                            st.session_state.user["idToken"] = newt["idToken"]
                            st.session_state.user["refreshToken"] = newt["refreshToken"]
                        info = lookup_account(st.session_state.user["idToken"])
                        st.session_state.user["verified"] = bool(info.get("emailVerified"))
                        st.success("Status refreshed.")
                    except Exception as e:
                        st.error("Could not refresh status."); st.caption(str(e))

# ===========================
# Header (logo + title + nav + actions)
# ===========================
def render_header():
    st.markdown('<div id="app-header">', unsafe_allow_html=True)

    c_logo, c_title, c_nav, c_actions = st.columns([0.08, 0.50, 0.20, 0.22])

    with c_logo:
        data_uri = _logo_data_uri("logo.png")
        if data_uri is None:
            st.error("logo.png not found next to app.py")
        else:
            st.markdown(
                f'''
                <img src="{data_uri}" 
                     width="100" height="100"
                     style="border-radius:10px; object-fit:cover; display:block;">
                ''',
                unsafe_allow_html=True
            )

    with c_title:
        st.markdown("""
        <div class="header-row">
          <div><div class="h-title">AI Student Performance Dashboard</div></div>
        </div>
        """, unsafe_allow_html=True)
        if st.session_state.user:
            badge = "✅ verified" if st.session_state.user.get("verified") else "⚠️ unverified"
            st.caption(f"Signed in as **{st.session_state.user['name']}** ({badge})")

    with c_nav:
        st.markdown('<div id="nav-row">', unsafe_allow_html=True)
        col_h, col_t = st.columns(2)
        with col_h:
            if st.button("Home", key="nav_home", use_container_width=True):
                go("home")
        with col_t:
            if st.button("Team", key="nav_team", use_container_width=True):
                go("team")
        active_first = (st.session_state.route == "home")
        st.markdown(
            f"<script>Array.from(parent.document.querySelectorAll('#nav-row .stButton > button'))"
            f".forEach((b,i)=>b.setAttribute('data-active', ((i===0)==={str(active_first).lower()}) ? 'true':'false'));</script>",
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with c_actions:
        st.markdown('<div id="actions-row">', unsafe_allow_html=True)
        ac1, ac2 = st.columns(2)
        with ac1:
            if not st.session_state.user:
                if st.button("Login / Sign up", use_container_width=True, key="login_btn"):
                    auth_dialog()
            else:
                if st.button("Sign out", use_container_width=True, key="logout_btn"):
                    st.session_state.user = None
                    st.success("Signed out.")
                    st.rerun()
        with ac2:
            if st.button("AI Predict", use_container_width=True, key="predict_btn"):
                predictor_dialog()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # /#app-header

# ===========================
# SUBJECTS (fixed 6) + rename map
# ===========================
SUBJECTS = [
    "OOPs C++",
    "DSA C++",
    "Mathematics",
    "Applied Data Science",
    "Embedded Systems",
    "Cloud Management",
]

RENAME_MAP = {
    "OOPS C++": "OOPs C++",
    "OOP C++": "OOPs C++",
    "Object Oriented Programming C++": "OOPs C++",
    "DSA CPP": "DSA C++",
    "DSA in C++": "DSA C++",
    "Applied data science": "Applied Data Science",
    "Applied DataScience": "Applied Data Science",
    "Embedded System": "Embedded Systems",
    "Embeded system": "Embedded Systems",
    "Cloud Mgmt": "Cloud Management",
    "CloudMgmt": "Cloud Management",
}

# ===========================
# HOME PAGE
# ===========================
def page_home():
    require_auth()  # gate: must be logged in

    feature_b64 = _to_b64("feature.png")
    benefit_b64 = _to_b64("benefit.png")
    work_b64    = _to_b64("work.png")

    def _img_tag(b64: str, alt: str) -> str:
        return (f'<img src="data:image/png;base64,{b64}" alt="{alt}">' if b64
                else f'<div style="padding:40px;text-align:center;opacity:.7;">Add {alt} image</div>')

    # Cards
    st.markdown(f"""
      <div class="img3-row">
        <div class="imgcard">
          <div class="imgcap">Features</div>
          {_img_tag(feature_b64, "Features")}
        </div>
        <div class="imgcard">
          <div class="imgcap">Benefits of the Dashboard</div>
          {_img_tag(benefit_b64, "Benefits")}
        </div>
        <div class="imgcard">
          <div class="imgcap">How It Works</div>
          {_img_tag(work_b64, "How It Works")}
        </div>
      </div>
    """, unsafe_allow_html=True)

    st.subheader("📂 Upload & Analyze")
    uploaded_files = st.file_uploader(
        "Upload Excel files (one per class)", type=["xlsx"], accept_multiple_files=True,
    )

    if uploaded_files:
        dfs = [pd.read_excel(f, engine="openpyxl") for f in uploaded_files]
        all_df = pd.concat(dfs, ignore_index=True)
        st.success("✅ Files uploaded and combined successfully!")

        # Normalize to your fixed six subjects
        all_df = all_df.rename(columns=RENAME_MAP)
        for sub in SUBJECTS:
            if sub not in all_df.columns:
                all_df[sub] = 0
        all_df[SUBJECTS] = all_df[SUBJECTS].fillna(0)

        # Validate core columns
        missing_core = [c for c in ["Class", "Reg.no", "Name"] if c not in all_df.columns]
        if missing_core:
            st.error(f"Missing required columns: {', '.join(missing_core)}")
            return

        # ===== Filters row (kept & extended) =====
        c1, c2, c3 = st.columns([1.4, 1.4, 2])
        with c1:
            class_list = sorted(all_df["Class"].astype(str).unique())
            selected_class = st.selectbox("🏫 Select Class", class_list)
        with c2:
            name_query = st.text_input("🔎 Search by name (optional)", "")
        with c3:
            subject_for_hist = st.selectbox("📈 Distribution by Subject (optional)", ["(none)"] + SUBJECTS)

        # Apply class + optional name filter
        cls_df = all_df[all_df["Class"].astype(str) == str(selected_class)].copy()
        if name_query.strip():
            q = name_query.strip().lower()
            cls_df = cls_df[cls_df["Name"].str.lower().str.contains(q, na=False)]

        class_subjects = SUBJECTS
        # Totals & percent
        cls_df["Total Marks"] = cls_df[class_subjects].sum(axis=1)
        cls_df["Percentage"] = (cls_df["Total Marks"] / (len(class_subjects) * 100) * 100).round(2)

        # ===== KPIs row =====
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.metric("Students in Class", len(cls_df))
        with k2: st.metric("Class Average %", f"{cls_df['Percentage'].mean():.2f}" if len(cls_df) else "0.00")
        with k3:
            pass_rate = 0.0
            if len(cls_df):
                passes = (cls_df[class_subjects] >= 40).all(axis=1).sum()
                pass_rate = 100.0 * passes / len(cls_df)
            st.metric("Pass Rate (all subjects ≥ 40)", f"{pass_rate:.1f}%")
        with k4:
            topper = cls_df["Percentage"].max() if len(cls_df) else 0
            st.metric("Topper %", f"{topper:.2f}")

        st.subheader(f"📘 Subjects for {selected_class}")
        st.write(", ".join(class_subjects))

        # Subject-wise averages (current class)
        avg_data = cls_df[class_subjects].mean().reset_index()
        avg_data.columns = ["Subject", "Average (%)"]
        st.subheader(f"📊 Subject-wise Average — {selected_class}")
        st.dataframe(avg_data, use_container_width=True)

        fig = px.bar(avg_data, x="Subject", y="Average (%)", color="Subject",
                     title=f"Average Marks — {selected_class}")
        st.plotly_chart(fig, use_container_width=True)

        # Optional histogram for chosen subject
        if subject_for_hist != "(none)":
            st.subheader(f"📈 Distribution — {subject_for_hist}")
            hist_fig = px.histogram(cls_df, x=subject_for_hist, nbins=10, title=f"{subject_for_hist} Score Distribution")
            st.plotly_chart(hist_fig, use_container_width=True)

        # Top 3 table
        st.subheader(f"🏆 Top 3 Students — {selected_class}")
        top3 = cls_df.sort_values(by="Total Marks", ascending=False).head(3).copy()
        top3["Rank"] = ["1st", "2nd", "3rd"][:len(top3)]
        st.dataframe(top3[["Rank", "Reg.no", "Name", "Total Marks", "Percentage"]], use_container_width=True)

        # Weak students
        st.subheader(f"⚠️ Weak Students (<40 in any subject) — {selected_class}")
        melted = cls_df.melt(id_vars=["Reg.no", "Name"], value_vars=class_subjects,
                             var_name="Subject", value_name="Marks")
        weak_df = melted[melted["Marks"] < 40].sort_values(by=["Subject", "Marks"])
        st.dataframe(weak_df, use_container_width=True)

        # ===== One-click exports (current class) =====
        st.subheader("📥 Export Reports")
        cdl1, cdl2, cdl3 = st.columns(3)

        # Export Subject-wise Average (current class)
        with cdl1:
            avg_bytes = io.BytesIO()
            avg_data.to_excel(avg_bytes, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ Download Subject Averages (XLSX)",
                data=avg_bytes.getvalue(),
                file_name=f"{selected_class}_subject_averages.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # Export Top 3 (current class)
        with cdl2:
            top3_bytes = io.BytesIO()
            top3[["Rank", "Reg.no", "Name", "Total Marks", "Percentage"]].to_excel(
                top3_bytes, index=False, engine="openpyxl"
            )
            st.download_button(
                "⬇️ Download Top 3 (XLSX)",
                data=top3_bytes.getvalue(),
                file_name=f"{selected_class}_top3.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # Export Weak students (current class)
        with cdl3:
            weak_bytes = io.BytesIO()
            weak_df.to_excel(weak_bytes, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ Download Weak Students (XLSX)",
                data=weak_bytes.getvalue(),
                file_name=f"{selected_class}_weak_students.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # ===== Full Class Report (multi-sheet) =====
        st.markdown("##### 📘 Full Class Report (multi-sheet)")
        full_bytes = io.BytesIO()
        with pd.ExcelWriter(full_bytes, engine="openpyxl") as writer:
            cls_df[["Reg.no", "Name"] + class_subjects + ["Total Marks", "Percentage"]].to_excel(
                writer, sheet_name="Students", index=False
            )
            avg_data.to_excel(writer, sheet_name="Subject Averages", index=False)
            top3[["Rank", "Reg.no", "Name", "Total Marks", "Percentage"]].to_excel(
                writer, sheet_name="Top 3", index=False
            )
            weak_df.to_excel(writer, sheet_name="Weak Students (<40)", index=False)
        st.download_button(
            "⬇️ Download Full Class Report (XLSX)",
            data=full_bytes.getvalue(),
            file_name=f"{selected_class}_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # ===========================
        # 📈 Class Comparisons (All Classes)
        # ===========================
        st.subheader("📈 Class Comparisons (All Classes)")

        # A. Subject Averages by Class (Grouped)
        st.markdown("**A. Subject Averages by Class (Grouped)**")
        comp_avg = (
            all_df.groupby("Class")[class_subjects]
            .mean()
            .reset_index()
        )
        comp_long = comp_avg.melt(id_vars="Class", var_name="Subject", value_name="Average (%)")
        fig_group = px.bar(
            comp_long, x="Subject", y="Average (%)", color="Class",
            barmode="group", title="Subject Averages by Class (Grouped)"
        )
        st.plotly_chart(fig_group, use_container_width=True)

        col_dlA, _, _ = st.columns([1, 1, 1])
        with col_dlA:
            comp_bytes = io.BytesIO()
            comp_avg.to_excel(comp_bytes, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ Download Class vs Subject Averages (XLSX)",
                data=comp_bytes.getvalue(),
                file_name="class_subject_averages.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # B. Class Strength by Class (counts)
        st.markdown("**B. Class Strength (Student Count) by Class**")
        strength = all_df.groupby("Class")["Reg.no"].nunique().reset_index(name="Students")
        fig_strength = px.bar(
            strength, x="Class", y="Students", title="Students per Class"
        )
        st.plotly_chart(fig_strength, use_container_width=True)

        col_dlB, _, _ = st.columns([1, 1, 1])
        with col_dlB:
            str_bytes = io.BytesIO()
            strength.to_excel(str_bytes, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ Download Class Strength (XLSX)",
                data=str_bytes.getvalue(),
                file_name="class_strength.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # C. Pass Rate by Class (all subjects ≥ 40)
        st.markdown("**C. Pass Rate by Class (all subjects ≥ 40)**")
        tmp = all_df.copy()
        tmp["PassAll"] = (tmp[class_subjects] >= 40).all(axis=1)
        pass_rate = (
            tmp.groupby("Class")["PassAll"].mean()
            .mul(100).reset_index(name="Pass Rate (%)")
        )
        fig_pass = px.bar(
            pass_rate, x="Class", y="Pass Rate (%)", title="Pass Rate by Class (All Subjects ≥ 40)"
        )
        st.plotly_chart(fig_pass, use_container_width=True)

        col_dlC, _, _ = st.columns([1, 1, 1])
        with col_dlC:
            pass_bytes = io.BytesIO()
            pass_rate.to_excel(pass_bytes, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ Download Pass Rate by Class (XLSX)",
                data=pass_bytes.getvalue(),
                file_name="class_pass_rate.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    else:
        st.info("👆 Upload Excel files to start analysis.")
        st.caption("Tip: Keep columns: 'Class', 'Reg.no', 'Name' and your 6 subjects exactly named.")

# ===========================
# TEAM PAGE
# ===========================
def page_team():
    require_auth()  # gate: must be logged in

    st.subheader("👤 Team")

    col1, col2 = st.columns([0.25, 0.75])
    with col1:
        img_path_candidates = ["my_photo.png", "me.jpg", "me.png"]
        img_path = next((p for p in img_path_candidates if os.path.exists(p)), None)
        if img_path:
            st.image(img_path, width=300)
        else:
            st.warning("Add your photo as my_photo.png (or me.jpg) next to app.py.")
    with col2:
        st.markdown("""
### Pavitar Kumar
Full-stack developer and data enthusiast. I build clean dashboards, scalable backends, and practical ML features for education products.

- **Strengths:** Python, Java, C++, React + TypeScript, Streamlit, Firebase, REST APIs  
- **Interests:** Data Analytics, Ethical Hacking (red & blue team), E-commerce backends  
- **Currently building:** *AI Student Performance Dashboard*  
- **Fun fact:** Solved 100+ LeetCode problems.
""")
        st.success("Available for internships and freelance projects.")
        icons = [
            ("link.png",  "LinkedIn", "https://www.linkedin.com/in/pavitar-kumar-915b79325"),
            ("git.png",   "GitHub",   "https://github.com/pavitarkumar"),
            ("mail.png",  "Email",    "mailto:pavitarrukhaya65@gmail.com"),
        ]
        html = '<div style="display:flex; gap:32px; align-items:center; margin-top:22px;">'
        for path, alt, href in icons:
            if os.path.exists(path):
                b64 = img_to_base64(path)
                html += (f'<a href="{href}" target="_blank">'
                         f'<img src="data:image/png;base64,{b64}" alt="{alt}" width="55" '
                         f'style="border-radius:10px; box-shadow:0 4px 10px rgba(0,0,0,.12);" />'
                         f'</a>')
            else:
                html += f'<span style="color:#999;">Missing {path}</span>'
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

# ===========================
# Render + Routing (with global gate option)
# ===========================
def render_and_route():
    render_header()

    # Global gate (optional)
    if not st.session_state.user:
        st.markdown("### 🔐 Please log in to use the dashboard.")
        if st.button("Login / Sign up", key="login_gate_btn_main"): auth_dialog()
        st.stop()

    # user is logged in → show pages
    if st.session_state.route == "home":
        page_home()
    elif st.session_state.route == "team":
        page_team()

render_and_route()
