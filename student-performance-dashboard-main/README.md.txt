🎓 AI Student Performance Dashboard

An advanced Streamlit dashboard that helps teachers and institutes analyze student marks, compare class performance, detect weak learners, and generate automated Excel reports.
The dashboard includes Firebase Authentication, AI-based performance prediction, and multi-class analytics with modern visualizations.

✅ Features
📂 Data Upload & Processing

Upload multiple Excel files (one per class)

Automatic cleaning, merging, and normalization

Supports fixed 6 subjects:

OOPs C++

DSA C++

Mathematics

Applied Data Science

Embedded Systems

Cloud Management

📊 Performance Analytics

Subject-wise averages

Class average percentage

Student total marks & percentage

Top 3 students

Weak student detection (<40 in any subject)

📈 Advanced Visualizations

Subject-wise averages (bar charts)

Score distribution histograms

Class comparison dashboards:

Subject-wise class averages

Class strength (student count)

Pass rate by class

🤖 AI Prediction Model

Predict student performance using:

Study time

Absences

Parental education

Parental support

Sports participation

Demographics

Outputs:

Expected percentage

Predicted grade

🔐 Secure Login System

Firebase Auth provides:

Email + Password login

Signup

Password reset

Email verification

Session handling

📥 One-Click Reports

Automatically export:

Subject averages

Top 3 students

Weak students

Complete multi-sheet class report

🎨 Modern UI

Light theme with custom styling

Sticky header

Feature/Benefits/How It Works image cards

Clean metrics and responsive layout

🧰 Tech Stack

🐍 Python 3.10+

⚡ Streamlit

🧮 Pandas

📊 Plotly

🔐 Firebase Auth (REST API)

📦 OpenPyXL (Excel export)

🚀 Run Locally
1. Clone the repository
git clone https://github.com/your-username/student-performance-dashboard.git
cd student-performance-dashboard

2. Create virtual environment (optional but recommended)
python -m venv venv
venv/Scripts/activate   # Windows
source venv/bin/activate  # Linux/Mac

3. Install dependencies
pip install -r requirements.txt

4. Add your Firebase config

Create a file:

firebase_config.json


Inside it, paste your Firebase project keys.

5. Run the app
streamlit run app.py


Your dashboard will open at:
👉 http://localhost:8501

📄 Example Excel Format
Reg.no	Name	Class	OOPs C++	DSA C++	Mathematics	Applied Data Science	Embedded Systems	Cloud Management
1001	Amit	CSE AIFT - A	78	82	69	88	77	85
1002	Rahul	CSE AIFT - B	67	71	74	81	69	72
☁️ Deployment Guide
✅ Recommended: Streamlit Community Cloud (free)

Push project to GitHub

Go to: https://share.streamlit.io

Connect GitHub → Select your repo

Set Main file = app.py

Add firebase_config.json as a secret

Deploy

Your app will be live at:

https://your-app-name.streamlit.app

✅ Other Deployment Options

Vercel (with Streamlit wrapper)

Render (free tier available)

Railway.app

Local hosting

Docker deployment

📄 License

This project is licensed under the MIT License.
You may modify, distribute, and use it freely.

👤 Author
Pavitar Kumar

Full-Stack Developer | Data & AI Enthusiast

📧 Email: pavitarrukhaya65@gmail.com

🌐 GitHub: https://github.com/pavitarkumar

🔗 LinkedIn: https://www.linkedin.com/in/pavitar-kumar-915b79325

💡 “Analyze. Visualize. Improve.”
Empowering educators with AI-driven performance insights.