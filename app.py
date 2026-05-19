from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# ---------- SUPABASE CONFIG ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://msyyfpscbdtwtillsawx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1zeXlmcHNjYmR0d3RpbGxzYXd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkyMTcwODUsImV4cCI6MjA5NDc5MzA4NX0.WEU7j0ydID4L6fcdmWX057fTVCwFVqhGvViCoK8wt-g")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def supabase_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    res = requests.get(url, headers=HEADERS)
    return res.json()

def supabase_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    res = requests.post(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data)
    return res

def supabase_patch(table, params, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    res = requests.patch(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data)
    return res


# ---------- GRADE LOGIC ----------
def calc_grade(mean):
    if mean >= 80: return "A"
    elif mean >= 75: return "A-"
    elif mean >= 70: return "B+"
    elif mean >= 65: return "B"
    elif mean >= 60: return "B-"
    elif mean >= 50: return "C+"
    elif mean >= 40: return "C"
    elif mean >= 30: return "C-"
    elif mean >= 20: return "D+"
    elif mean >= 10: return "D"
    else: return "F"

def grade_message(grade):
    messages = {
        "A":  "Excellent! Keep this up.",
        "A-": "Great job! You're doing so nicely.",
        "B+": "You're getting there.",
        "B":  "Wonderful! But don't give up yet.",
        "B-": "Great job but improve this grade.",
        "C+": "You're passing but you're not there yet.",
        "C":  "You can do better.",
        "C-": "You need to work harder.",
        "D+": "Please pull up your socks — you're at risk of failing.",
        "D":  "You are at a terrible risk of failing. You need to improve.",
        "F":  "You failed. Please seek help immediately."
    }
    return messages.get(grade, "")


# ---------- ROUTES ----------

# GET all students (optionally filter by class)
@app.route("/students", methods=["GET"])
def get_students():
    cls = request.args.get("class")
    if cls:
        data = supabase_get("students", f"?class=eq.{cls}&order=name.asc")
    else:
        data = supabase_get("students", "?order=class.asc,name.asc")
    return jsonify(data)


# GET single student by admission number + class
@app.route("/students/find", methods=["GET"])
def find_student():
    cls = request.args.get("class")
    adm = request.args.get("admission_number")

    if not cls or not adm:
        return jsonify({"error": "Please provide both class and admission_number."}), 400

    data = supabase_get("students", f"?class=eq.{cls}&admission_number=eq.{adm}")

    if not data:
        return jsonify({"error": f"Admission number {adm} not found in {cls}."}), 404

    return jsonify(data[0])


# POST add a new student
@app.route("/students", methods=["POST"])
def add_student():
    body = request.get_json()
    name = body.get("name", "").strip().title()
    adm  = body.get("admission_number")
    cls  = body.get("class", "").lower().replace(" ", "")

    if not name:
        return jsonify({"error": "Please enter a student name."}), 400
    if not adm or not str(adm).isdigit():
        return jsonify({"error": "Admission number must be a valid number."}), 400
    if cls not in ["form1", "form2", "form3", "form4"]:
        return jsonify({"error": "Invalid class. Choose form1, form2, form3, or form4."}), 400

    # Check duplicate name in same class
    existing_name = supabase_get("students", f"?class=eq.{cls}&name=eq.{name}")
    if existing_name:
        return jsonify({"error": f'A student named "{name}" already exists in {cls}.'}), 409

    # Check duplicate admission number across all classes
    existing_adm = supabase_get("students", f"?admission_number=eq.{adm}")
    if existing_adm:
        return jsonify({"error": f"Admission number {adm} is already assigned to another student."}), 409

    res = supabase_post("students", {
        "name": name,
        "admission_number": int(adm),
        "class": cls,
        "grade": None
    })

    if res.status_code in [200, 201]:
        return jsonify({"message": f'Student "{name}" added successfully to {cls}.'}), 201
    else:
        return jsonify({"error": "Failed to add student. Please try again."}), 500


# POST calculate and save grade for a student
@app.route("/students/grade", methods=["POST"])
def submit_grade():
    body = request.get_json()
    cls  = body.get("class")
    adm  = body.get("admission_number")
    scores = body.get("scores", {})

    if not cls or not adm:
        return jsonify({"error": "Class and admission number are required."}), 400

    # Validate all 12 subjects are present and valid
    required = ["maths","english","kiswahili","physics","chemistry","biology",
                "agriculture","computer","business","history","geography","cre"]

    for subject in required:
        val = scores.get(subject)
        if val is None:
            return jsonify({"error": f"Missing score for {subject}."}), 400
        if not isinstance(val, (int, float)) or val < 0 or val > 100:
            return jsonify({"error": f"Score for {subject} must be between 0 and 100."}), 400

    total = sum(scores[s] for s in required)
    mean  = round(total / 12)
    grade = calc_grade(mean)
    message = grade_message(grade)

    # Find student
    data = supabase_get("students", f"?class=eq.{cls}&admission_number=eq.{adm}")
    if not data:
        return jsonify({"error": "Student not found."}), 404

    student = data[0]

    # Save grade
    supabase_patch("students", f"?id=eq.{student['id']}", {"grade": grade})

    return jsonify({
        "name":    student["name"],
        "class":   cls,
        "admission_number": adm,
        "mean":    mean,
        "total":   total,
        "grade":   grade,
        "message": message
    })


if __name__ == "__main__":
    app.run(debug=True)
