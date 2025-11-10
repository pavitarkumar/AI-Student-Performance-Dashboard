# main.py
import json
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Student Performance Dashboard", layout="wide")

# ---------- Firebase ----------
@st.cache_resource(show_spinner=False)
def _init_firebase():
    with open("firebase_config.json", "r", encoding="utf-8") as f:
        conf = json.load(f)
    project_id = conf.get("projectId")
    if "databaseURL" not in conf:
        conf["databaseURL"] = f"https://{project_id}.firebaseio.com"
    import pyrebase
    fb = pyrebase.initialize_app(conf)
    return fb.auth()

auth = _init_firebase()

if "user" not in st.session_state:
    st.session_state.user = None

def _account_info(id_token):
    try:
        info = auth.get_account_info(id_token)
        users = info.get("users", [])
        return users[0] if users else {}
    except Exception:
        return {}

# ---------- Small helpers ----------
def grade_from_score(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"

def predict_percentage(age:int, gender:str, absences:int, study_time:int,
                       parental_edu:str, parental_support:str,
                       ethnicity:str, sports:bool) -> float:
    # simple heuristic demo
    score = 45.0
    score += min(study_time, 25) * 1.8
    score -= min(absences, 30) * 1.4
    edu_boost = {"Middle School": 0, "High School": 3, "Diploma": 5,
                 "Bachelor's": 7, "Master's": 8, "PhD": 9}.get(parental_edu, 3)
    support_boost = {"Low": -4, "Moderate": 2, "High": 5, "Very High": 7}.get(parental_support, 2)
    score += edu_boost + support_boost
    if sports: score += 3
    score -= abs(age - 16.5) * 0.8
    return max(0.0, min(100.0, score))

# ---------- Header ----------
with st.container():
    col_title, col_spacer, col_actions = st.columns([6, 2, 6])
    with col_title:
        st.markdown("## 🎓 Student Performance Dashboard")
    with col_actions:
        a1, a2, a3 = st.columns([1, 1, 2])

        # --- Auth dialog (tabs) ---
        def auth_dialog():
            @st.dialog("Account", width="large")
            def _dlg():
                tabs = st.tabs(["Login", "Sign up", "Forgot password", "Email verification"])

                # Login
                with tabs[0]:
                    with st.form("login_form_m", clear_on_submit=False):
                        email = st.text_input("Email", key="m_login_email")
                        pwd = st.text_input("Password", type="password", key="m_login_pwd")
                        sub = st.form_submit_button("Login")
                    if sub:
                        try:
                            user = auth.sign_in_with_email_and_password(email, pwd)
                            info = _account_info(user["idToken"])
                            verified = bool(info.get("emailVerified"))
                            name = info.get("displayName") or email.split("@")[0]
                            st.session_state.user = {
                                "email": email,
                                "idToken": user["idToken"],
                                "refreshToken": user["refreshToken"],
                                "localId": user.get("localId") or info.get("localId"),
                                "name": name,
                                "verified": verified,
                            }
                            st.success(f"Logged in as {name}")
                            st.rerun()
                        except Exception as e:
                            st.error("Login failed.")
                            st.caption(str(e))

                # Sign up
                with tabs[1]:
                    with st.form("signup_form_m", clear_on_submit=False):
                        name = st.text_input("Full name", key="m_su_name")
                        email = st.text_input("Email", key="m_su_email")
                        pwd = st.text_input("Password (min 6 chars)", type="password", key="m_su_pwd")
                        sub = st.form_submit_button("Create account")
                    if sub:
                        try:
                            user = auth.create_user_with_email_and_password(email, pwd)
                            auth.send_email_verification(user["idToken"])
                            st.session_state.user = {
                                "email": email,
                                "idToken": user["idToken"],
                                "refreshToken": user["refreshToken"],
                                "localId": user.get("localId"),
                                "name": name or email.split("@")[0],
                                "verified": False,
                            }
                            st.success("Account created! Verification email sent.")
                        except Exception as e:
                            st.error("Sign up failed.")
                            st.caption(str(e))

                # Forgot password
                with tabs[2]:
                    rp_email = st.text_input("Email for password reset", key="m_rp_email")
                    if st.button("Send reset link"):
                        try:
                            auth.send_password_reset_email(rp_email)
                            st.success("Password reset email sent.")
                        except Exception as e:
                            st.error("Could not send reset email.")
                            st.caption(str(e))

                # Verify email
                with tabs[3]:
                    if st.session_state.user:
                        v = "verified ✅" if st.session_state.user.get("verified") else "not verified ❌"
                        st.write(f"**{st.session_state.user['email']}** is {v}.")
                        if st.button("Resend verification email"):
                            try:
                                auth.send_email_verification(st.session_state.user["idToken"])
                                st.success("Verification email sent.")
                            except Exception as e:
                                st.error("Could not send verification email.")
                                st.caption(str(e))
                        if st.button("I have verified. Refresh status"):
                            info = _account_info(st.session_state.user["idToken"])
                            st.session_state.user["verified"] = bool(info.get("emailVerified"))
                            st.experimental_rerun()
                    else:
                        st.info("Login first to check verification status.")
            _dlg()

        if st.session_state.user:
            a1.write(f"**👋 {st.session_state.user['name']}**")
            if a2.button("Log out", use_container_width=True):
                st.session_state.user = None
                st.rerun()
        else:
            if a1.button("Login / Sign up", use_container_width=True):
                auth_dialog()

        # --- Predictor button ---
        def predictor_dialog():
            @st.dialog("Student Performance Predictor", width="large")
            def _dlg():
                colL, colR = st.columns(2)
                with colL:
                    age = st.number_input("Age", min_value=10, max_value=25, value=16, step=1)
                    gender = st.selectbox("Gender", ["Female", "Male", "Other"])
                    absences = st.number_input("Absences", min_value=0, max_value=60, value=5, step=1)
                    study = st.number_input("Study Time/wk (hours)", min_value=0, max_value=50, value=10, step=1)
                    parental_edu = st.selectbox(
                        "Parental Education",
                        ["Middle School", "High School", "Diploma", "Bachelor's", "Master's", "PhD"], index=1
                    )
                    parental_support = st.selectbox(
                        "Parental Support",
                        ["Low", "Moderate", "High", "Very High"], index=1
                    )
                    ethnicity = st.selectbox("Ethnicity", ["Group A", "Group B", "Group C", "Group D", "Prefer not to say"], index=2)
                    sports = st.toggle("Participates in Sports", value=False)

                    if st.button("Predict", type="primary"):
                        pct = predict_percentage(
                            age, gender, absences, study, parental_edu, parental_support, ethnicity, sports
                        )
                        letter = grade_from_score(pct)
                        st.success(f"**Predicted Final %:** {pct:.1f}%  •  **Grade:** {letter}")
                        st.caption("Note: Gender/Ethnicity are shown for parity but not used in prediction.")
                with colR:
                    st.markdown("""
                        #### How it works
                        - Study time (+), Absences (–)  
                        - Parental education & support (+)  
                        - Sports participation (+ small)  
                        - Mild regularization by age
                    """)
            _dlg()

        if a3.button("🔮 Predict Performance", use_container_width=True):
            predictor_dialog()

st.write("Upload your class Excel files to analyze performance by class and subject.")

# ---------- Upload & Analysis ----------
uploaded_files = st.file_uploader(
    "📂 Upload Excel files (one per class)",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    # Read & combine
    dfs = [pd.read_excel(f, engine="openpyxl") for f in uploaded_files]
    all_df = pd.concat(dfs, ignore_index=True)
    st.success("✅ Files uploaded and combined successfully!")

    # ✅ Your fixed 6 subjects
    possible_subjects = [
        "OOPs C++",
        "DSA C++",
        "Mathematics",
        "Applied Data Science",
        "Embedded Systems",
        "Cloud Management"
    ]

    # Optional: normalize common column variations to your exact names
    rename_map = {
        "OOPS C++": "OOPs C++",
        "OOPs CPP": "OOPs C++",
        "DSA CPP": "DSA C++",
        "Applied data science": "Applied Data Science",
        "Embedded System": "Embedded Systems",
        "Cloud Mgmt": "Cloud Management",
        "Reg No": "Reg.no",
        "Reg_No": "Reg.no",
        "Registration No": "Reg.no",
    }
    all_df = all_df.rename(columns=rename_map)

    # Guard rails for required base columns
    required_base = ["Reg.no", "Name", "Class"]
    missing_base = [c for c in required_base if c not in all_df.columns]
    if missing_base:
        st.error(f"Missing required column(s): {', '.join(missing_base)}")
        st.stop()

    # Ensure each subject column exists; fill empties with 0
    for sub in possible_subjects:
        if sub not in all_df.columns:
            all_df[sub] = 0
    all_df[possible_subjects] = all_df[possible_subjects].fillna(0)

    # Class selection
    class_list = sorted(all_df["Class"].astype(str).unique())
    selected_class = st.selectbox("🏫 Select Class", class_list)
    cls_df = all_df[all_df["Class"].astype(str) == str(selected_class)].copy()

    # ✅ Always use your 6 subjects
    class_subjects = possible_subjects[:]

    # Totals & percentage
    cls_df["Total Marks"] = cls_df[class_subjects].sum(axis=1)
    cls_df["Percentage"] = (cls_df["Total Marks"] / (len(class_subjects) * 100) * 100).round(2)

    st.subheader(f"📘 Subjects for {selected_class}")
    st.write(", ".join(class_subjects))

    # --- Subject-wise average ---
    avg_data = cls_df[class_subjects].mean().reset_index()
    avg_data.columns = ["Subject", "Average (%)"]
    st.subheader(f"📊 Subject-wise Average - {selected_class}")
    st.dataframe(avg_data, use_container_width=True)

    fig = px.bar(
        avg_data,
        x="Subject",
        y="Average (%)",
        color="Subject",
        title=f"Average Marks - {selected_class}"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Top 3 ---
    st.subheader(f"🏆 Top 3 Students - {selected_class}")
    top3 = cls_df.sort_values(by="Total Marks", ascending=False).head(3).copy()
    top3["Rank"] = ["1st", "2nd", "3rd"][:len(top3)]
    st.dataframe(top3[["Rank", "Reg.no", "Name", "Total Marks", "Percentage"]], use_container_width=True)

    # --- Weak students ---
    st.subheader(f"⚠️ Weak Students (<40 in any subject) - {selected_class}")
    weak = cls_df.melt(
        id_vars=["Reg.no", "Name"],
        value_vars=class_subjects,
        var_name="Subject",
        value_name="Marks"
    )
    weak_df = weak[weak["Marks"] < 40].sort_values(by=["Subject", "Marks"])
    st.dataframe(weak_df, use_container_width=True)

else:
    st.info("👆 Upload Excel files to start analysis.")
    st.caption("Tip: Keep columns as: Reg.no, Name, Class, and the 6 subjects exactly as named above.")
