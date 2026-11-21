"""PS45 - Career Path Advisor
Suggests 3 career paths with a 3-month learning roadmap each,
based on a short questionnaire (interests, skills, subjects liked).
"""
import json
import os
import re

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """You are a friendly, realistic career counsellor for Indian engineering students.
Given a student's profile, suggest exactly 3 suitable career paths.
Rules:
- Base every suggestion on the student's stated interests, skills and liked subjects.
- Give a 3-month roadmap for each role (Month 1, 2, 3), starting from the student's current skill level.
- Roadmap tasks must be concrete (topics, tools, a small project), not vague advice.
- Do NOT invent salaries, company names or statistics.
- Reply with ONLY valid JSON, no markdown fences, in exactly this format:
{
  "careers": [
    {
      "role": "string",
      "why_it_fits": "2-3 sentences linking to the student's profile",
      "skills_you_have": ["..."],
      "skills_to_build": ["..."],
      "roadmap": {
        "month_1": {"focus": "string", "tasks": ["...", "..."], "outcome": "string"},
        "month_2": {"focus": "string", "tasks": ["...", "..."], "outcome": "string"},
        "month_3": {"focus": "string", "tasks": ["...", "..."], "outcome": "string"}
      },
      "starter_project": "string"
    }
  ]
}"""


def build_user_prompt(p: dict) -> str:
    return (
        f"Student profile:\n"
        f"- Education: {p['education']}\n"
        f"- Interests: {', '.join(p['interests']) or 'not given'}\n"
        f"- Current skills: {p['skills'] or 'not given'}\n"
        f"- Subjects liked: {p['subjects'] or 'not given'}\n"
        f"- Work style preference: {p['work_style']}\n"
        f"- Hours per week available for learning: {p['hours']}\n"
        f"- Extra notes: {p['notes'] or 'none'}"
    )


def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        st.error("GEMINI_API_KEY not found. Create a .env file (see .env.example).")
        st.stop()
    return genai.Client(api_key=key)


def parse_json(text: str) -> dict:
    """Parse model output as JSON, tolerating accidental ``` fences."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def get_advice(profile: dict) -> dict:
    client = get_client()
    last_err = None
    for _ in range(2):  # one retry if the JSON is malformed
        resp = client.models.generate_content(
            model=MODEL,
            contents=build_user_prompt(profile),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        try:
            return parse_json(resp.text)
        except (json.JSONDecodeError, TypeError) as e:
            last_err = e
    raise ValueError(f"Model returned invalid JSON: {last_err}")


def to_markdown(data: dict) -> str:
    out = ["# My Career Path Advice\n"]
    for c in data["careers"]:
        out.append(f"## {c['role']}\n{c['why_it_fits']}\n")
        out.append(f"**Skills you have:** {', '.join(c['skills_you_have'])}  ")
        out.append(f"**Skills to build:** {', '.join(c['skills_to_build'])}\n")
        for i in (1, 2, 3):
            m = c["roadmap"][f"month_{i}"]
            out.append(f"### Month {i}: {m['focus']}")
            out += [f"- {t}" for t in m["tasks"]]
            out.append(f"**Outcome:** {m['outcome']}\n")
        out.append(f"**Starter project:** {c['starter_project']}\n")
    return "\n".join(out)


def show_career(c: dict):
    st.subheader(c["role"])
    st.write(c["why_it_fits"])
    col1, col2 = st.columns(2)
    col1.markdown("**Skills you already have**")
    col1.write(", ".join(c["skills_you_have"]) or "-")
    col2.markdown("**Skills to build**")
    col2.write(", ".join(c["skills_to_build"]) or "-")
    st.markdown("#### 3-Month Roadmap")
    for i in (1, 2, 3):
        m = c["roadmap"][f"month_{i}"]
        with st.expander(f"Month {i}: {m['focus']}", expanded=(i == 1)):
            for t in m["tasks"]:
                st.markdown(f"- {t}")
            st.success(f"Outcome: {m['outcome']}")
    st.info(f"Starter project: {c['starter_project']}")


# ---------------- UI ----------------
st.set_page_config(page_title="Career Path Advisor", page_icon="🧭", layout="wide")
st.title("🧭 Career Path Advisor")
st.caption("Answer a few questions and get 3 career paths with a 3-month learning roadmap each. "
           "AI-generated guidance - verify with mentors before big decisions.")

with st.form("questionnaire"):
    education = st.selectbox(
        "Current education",
        ["B.E./B.Tech - 1st year", "B.E./B.Tech - 2nd year", "B.E./B.Tech - 3rd year",
         "B.E./B.Tech - 4th year", "Graduate (other)", "Post-graduate"],
        index=3,
    )
    interests = st.multiselect(
        "Interests",
        ["Web development", "AI / Machine Learning", "Data analysis", "Cybersecurity",
         "Mobile apps", "Cloud / DevOps", "Game development", "Embedded / IoT",
         "UI/UX design", "Teaching / Research", "Entrepreneurship", "Finance / Fintech"],
    )
    skills = st.text_area("Your current skills", placeholder="e.g. Python, HTML/CSS, SQL, basic Java")
    subjects = st.text_input("Subjects you liked", placeholder="e.g. DBMS, Maths, Operating Systems")
    work_style = st.radio("Preferred work style",
                          ["Solo / deep focus", "Team collaboration", "Client-facing", "No preference"],
                          horizontal=True)
    hours = st.slider("Hours per week you can spend learning", 2, 40, 10)
    notes = st.text_input("Anything else? (optional)", placeholder="e.g. want a remote job, prefer startups")
    submitted = st.form_submit_button("Get my career paths")

if submitted:
    if not interests and not skills.strip() and not subjects.strip():
        st.warning("Please fill in at least interests, skills or subjects.")
    else:
        profile = dict(education=education, interests=interests, skills=skills.strip(),
                       subjects=subjects.strip(), work_style=work_style, hours=hours, notes=notes.strip())
        with st.spinner("Thinking about your best paths..."):
            try:
                st.session_state["result"] = get_advice(profile)
            except Exception as e:
                st.session_state.pop("result", None)
                st.error(f"Something went wrong: {e}")

if "result" in st.session_state:
    data = st.session_state["result"]
    careers = data.get("careers", [])
    tabs = st.tabs([c["role"] for c in careers])
    for tab, c in zip(tabs, careers):
        with tab:
            show_career(c)
    st.download_button("Download as Markdown", to_markdown(data), file_name="career_advice.md")
