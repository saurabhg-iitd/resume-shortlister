import json
import os

JD_FILE = "jd.json"
RESUMES_FILE = "resumes.json"

def save_jd(jd):
    with open(JD_FILE, "w") as f:
        json.dump(jd, f)

def load_jd():
    if not os.path.exists(JD_FILE):
        return None
    with open(JD_FILE, "r") as f:
        return json.load(f)

def save_resume(resume):
    resumes = load_resumes()
    resumes.append(resume)
    with open(RESUMES_FILE, "w") as f:
        json.dump(resumes, f)

def load_resumes():
    if not os.path.exists(RESUMES_FILE):
        return []
    with open(RESUMES_FILE, "r") as f:
        return json.load(f)

def clear_resumes():
    with open(RESUMES_FILE, "w") as f:
        json.dump([], f) 