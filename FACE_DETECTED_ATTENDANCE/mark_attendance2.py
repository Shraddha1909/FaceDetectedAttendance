from flask import Blueprint, render_template, request, jsonify
import os
import base64
from PIL import Image
from io import BytesIO
import face_recognition
from datetime import datetime
import pandas as pd
from db_connection import create_connection

mark_attendance_bp = Blueprint('mark_attendance_bp', __name__)

def get_current_date():
    return datetime.now().strftime('%d/%m/%Y')

def get_valid_dates():
    today = datetime.now()
    year = today.year
    month = today.month
    days_in_month = [datetime(year, month, day).strftime('%d/%b/%Y') 
                     for day in range(1, today.day + 1)]
    return days_in_month

def update_attendance_excel(roll_no, date, students_db):
    month_name = datetime.now().strftime('%B')
    year = datetime.now().strftime('%Y')
    file_name = f"attendance_records/{month_name}_{year}.xlsx"
    
    if os.path.exists(file_name):
        df = pd.read_excel(file_name)
    else:
        student_data = [(student['roll_number'], student['name']) for student in students_db]
        df = pd.DataFrame(student_data, columns=['Roll no', 'Name'])
        valid_dates = get_valid_dates()
        for day in valid_dates:
            df[day] = 'absent'

    if date not in df.columns:
        df[date] = 'absent'

    df.loc[df['Roll no'] == roll_no, date] = 'present'
    df.to_excel(file_name, index=False)

@mark_attendance_bp.route('/mark-attendance', methods=['GET', 'POST'])
def mark_attendance():
    if request.method == 'GET':
        return render_template('mark_attendance.html')

    if request.method == 'POST':
        conn = None
        try:
            roll_no = request.form.get('roll_no')
            photo_base64 = request.form.get('photo')

            if not roll_no or not photo_base64:
                return jsonify({"status": "error", "message": "Roll number and photo are required"}), 400

            photo_data = base64.b64decode(photo_base64.split(',')[1])
            uploaded_image = Image.open(BytesIO(photo_data))
            temp_photo_path = os.path.join('static/uploads', f"temp_{roll_no}.jpg")
            uploaded_image.save(temp_photo_path, format='JPEG')

            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM students WHERE roll_number = %s", (roll_no,))
            student = cursor.fetchone()

            if not student:
                return jsonify({"status": "error", "message": "Roll number not found"}), 404

            stored_photo_path = os.path.join('static/uploads', f"{roll_no}.jpg")
            if not os.path.exists(stored_photo_path):
                original_photo_path = student['image_path']
                if os.path.exists(original_photo_path):
                    os.rename(original_photo_path, stored_photo_path)
                    student['image_path'] = stored_photo_path
                else:
                    return jsonify({"status": "error", "message": f"Stored photo not found for Roll Number {roll_no}"}), 404

            stored_image = face_recognition.load_image_file(stored_photo_path)
            uploaded_image = face_recognition.load_image_file(temp_photo_path)

            stored_encodings = face_recognition.face_encodings(stored_image)
            uploaded_encodings = face_recognition.face_encodings(uploaded_image)

            if not stored_encodings:
                return jsonify({"status": "error", "message": "No face found in the stored photo"}), 400
            if not uploaded_encodings:
                return jsonify({"status": "error", "message": "No face found in the uploaded photo"}), 400

            stored_encoding = stored_encodings[0]
            uploaded_encoding = uploaded_encodings[0]

            results = face_recognition.compare_faces([stored_encoding], uploaded_encoding)
            face_distance = face_recognition.face_distance([stored_encoding], uploaded_encoding)[0]

            if not results[0] or face_distance > 0.6:  # Threshold set to 0.6 for strict matching
                return jsonify({"status": "error", "message": "Face does not match"}), 401

            cursor.execute("SELECT roll_number, name FROM students")
            students_db = cursor.fetchall()

            update_attendance_excel(roll_no, get_current_date(), students_db)

            os.remove(temp_photo_path)

            return jsonify({"status": "success", "message": f"Attendance marked successfully for Roll Number {roll_no}"}), 200

        except Exception as e:
            return jsonify({"status": "error", "message": f"Error marking attendance: {str(e)}"}), 500

        finally:
            if conn:
                conn.close()
