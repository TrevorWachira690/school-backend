from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app, origins=["https://schoolmaagementsystem.netlify.app", "http://localhost"])

# ---------- SUPABASE CONFIG ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://msyyfpscbdtwtillsawx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1zeXlmcHNjYmR0d3RpbGxzYXd4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTIxNzA4NSwiZXhwIjoyMDk0NzkzMDg1fQ.cs5N17mE7yKhdD8rZ534UzQbhmUWPRgU9vMUHTZFh3A")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "school@admin2024")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    res = requests.get(url, headers=HEADERS)
    return res.json()

def sb_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    res = requests.post(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data)
    return res

def sb_patch(table, params, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    res = requests.patch(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data)
    return res

def sb_delete(table, params):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    res = requests.delete(url, headers=HEADERS)
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
        "D+": "Please pull up your socks - you're at risk of failing.",
        "D":  "You are at a terrible risk of failing. You need to improve.",
        "F":  "You failed. Please seek help immediately."
    }
    return messages.get(grade, "")


# ---------- ROUTES ----------

# Health check
@app.route("/", methods=["GET"])
def health_check():
    try:
        data = sb_get("students", "?limit=1")
        return jsonify({"status": "ok", "supabase": "connected", "sample": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---- AUTH ----
@app.route("/auth/admin", methods=["POST"])
def admin_login():
    body = request.get_json()
    password = body.get("password", "")
    if not password:
        return jsonify({"error": "Please enter a password."}), 400
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Incorrect password. Please try again."}), 401
    return jsonify({"success": True, "message": "Welcome, Admin!"})


# ---- STUDENTS ----
@app.route("/students", methods=["GET"])
def get_students():
    cls = request.args.get("class")
    if cls:
        data = sb_get("students", f"?class=eq.{cls}&order=name.asc")
    else:
        data = sb_get("students", "?order=class.asc,name.asc")
    return jsonify(data)

@app.route("/students/find", methods=["GET"])
def find_student():
    cls = request.args.get("class")
    adm = request.args.get("admission_number")
    if not cls or not adm:
        return jsonify({"error": "Please provide both class and admission_number."}), 400
    data = sb_get("students", f"?class=eq.{cls}&admission_number=eq.{adm}")
    if not data:
        return jsonify({"error": f"Admission number {adm} not found in {cls}."}), 404
    return jsonify(data[0])

@app.route("/students", methods=["POST"])
def add_student():
    body = request.get_json()
    name = body.get("name", "").strip().title()
    adm  = body.get("admission_number")
    cls  = body.get("class", "").lower().replace(" ", "")
    subject_ids = body.get("subject_ids", [])

    if not name:
        return jsonify({"error": "Please enter a student name."}), 400
    if not adm or not str(adm).isdigit():
        return jsonify({"error": "Admission number must be a valid number."}), 400
    if cls not in ["form1", "form2", "form3", "form4"]:
        return jsonify({"error": "Invalid class. Choose form1, form2, form3, or form4."}), 400
    if not subject_ids:
        return jsonify({"error": "Please assign at least one subject to the student."}), 400

    existing_name = sb_get("students", f"?class=eq.{cls}&name=eq.{name}")
    if existing_name:
        return jsonify({"error": f'A student named "{name}" already exists in {cls}.'}), 409

    existing_adm = sb_get("students", f"?admission_number=eq.{adm}")
    if existing_adm:
        return jsonify({"error": f"Admission number {adm} is already assigned to another student."}), 409

    res = sb_post("students", {
        "name": name,
        "admission_number": int(adm),
        "class": cls,
        "grade": None
    })

    if res.status_code not in [200, 201]:
        return jsonify({"error": "Failed to add student. Please try again."}), 500

    student = res.json()[0]
    student_id = student["id"]

    # Assign subjects
    for sid in subject_ids:
        sb_post("student_subjects", {
            "student_id": student_id,
            "subject_id": int(sid),
            "score": None
        })

    return jsonify({"message": f'Student "{name}" added successfully to {cls}.'}), 201


@app.route("/students/<int:student_id>", methods=["PATCH"])
def update_student(student_id):
    body = request.get_json()
    updates = {}

    if "name" in body:
        updates["name"] = body["name"].strip().title()
    if "class" in body:
        cls = body["class"].lower().replace(" ", "")
        if cls not in ["form1", "form2", "form3", "form4"]:
            return jsonify({"error": "Invalid class."}), 400
        updates["class"] = cls
    if "admission_number" in body:
        adm = body["admission_number"]
        existing = sb_get("students", f"?admission_number=eq.{adm}&id=neq.{student_id}")
        if existing:
            return jsonify({"error": f"Admission number {adm} is already taken."}), 409
        updates["admission_number"] = int(adm)

    if not updates:
        return jsonify({"error": "No valid fields to update."}), 400

    res = sb_patch("students", f"?id=eq.{student_id}", updates)
    if res.status_code in [200, 204]:
        return jsonify({"message": "Student updated successfully."})
    return jsonify({"error": "Failed to update student."}), 500


@app.route("/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    res = sb_delete("students", f"?id=eq.{student_id}")
    if res.status_code in [200, 204]:
        return jsonify({"message": "Student deleted successfully."})
    return jsonify({"error": "Failed to delete student."}), 500


# ---- SUBJECTS ----
@app.route("/subjects", methods=["GET"])
def get_subjects():
    data = sb_get("subjects", "?order=name.asc")
    return jsonify(data)

@app.route("/subjects", methods=["POST"])
def add_subject():
    body = request.get_json()
    name = body.get("name", "").strip().title()
    if not name:
        return jsonify({"error": "Please enter a subject name."}), 400

    existing = sb_get("subjects", f"?name=eq.{name}")
    if existing:
        return jsonify({"error": f'Subject "{name}" already exists.'}), 409

    res = sb_post("subjects", {"name": name})
    if res.status_code in [200, 201]:
        return jsonify({"message": f'Subject "{name}" added successfully.'}), 201
    return jsonify({"error": "Failed to add subject."}), 500

@app.route("/subjects/<int:subject_id>", methods=["DELETE"])
def delete_subject(subject_id):
    res = sb_delete("subjects", f"?id=eq.{subject_id}")
    if res.status_code in [200, 204]:
        return jsonify({"message": "Subject deleted successfully."})
    return jsonify({"error": "Failed to delete subject."}), 500


# ---- STUDENT SUBJECTS ----
@app.route("/students/<int:student_id>/subjects", methods=["GET"])
def get_student_subjects(student_id):
    data = sb_get("student_subjects", f"?student_id=eq.{student_id}&order=subject_id.asc")
    if not data:
        return jsonify([])
    # Get subject names
    result = []
    for row in data:
        subject = sb_get("subjects", f"?id=eq.{row['subject_id']}")
        if subject:
            result.append({
                "id": row["id"],
                "subject_id": row["subject_id"],
                "subject_name": subject[0]["name"],
                "score": row["score"]
            })
    return jsonify(result)


# ---- GRADES ----
@app.route("/students/grade", methods=["POST"])
def submit_grade():
    body = request.get_json()
    cls  = body.get("class")
    adm  = body.get("admission_number")
    scores = body.get("scores", {})  # {subject_id: score}

    if not cls or not adm:
        return jsonify({"error": "Class and admission number are required."}), 400
    if not scores:
        return jsonify({"error": "No scores provided."}), 400

    # Validate scores
    for sid, val in scores.items():
        if not isinstance(val, (int, float)) or val < 0 or val > 100:
            return jsonify({"error": f"All scores must be between 0 and 100."}), 400

    data = sb_get("students", f"?class=eq.{cls}&admission_number=eq.{adm}")
    if not data:
        return jsonify({"error": "Student not found."}), 404

    student = data[0]
    student_id = student["id"]

    # Save each score
    for sid, score in scores.items():
        sb_patch("student_subjects", f"?student_id=eq.{student_id}&subject_id=eq.{sid}", {"score": int(score)})

    # Calculate mean
    total = sum(scores.values())
    mean  = round(total / len(scores))
    grade = calc_grade(mean)
    message = grade_message(grade)

    # Save grade
    sb_patch("students", f"?id=eq.{student_id}", {"grade": grade})

    return jsonify({
        "name":    student["name"],
        "class":   cls,
        "admission_number": adm,
        "mean":    mean,
        "total":   total,
        "subjects_count": len(scores),
        "grade":   grade,
        "message": message
    })


if __name__ == "__main__":
    app.run(debug=True)
