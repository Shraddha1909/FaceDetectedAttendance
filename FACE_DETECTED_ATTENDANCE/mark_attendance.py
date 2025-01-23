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
    """Get the current date in 'dd/mm/yyyy' format."""
    return datetime.now().strftime('%d/%m/%Y')

def get_valid_dates():
    """Generate valid dates up to the current day of the month."""
    today = datetime.now()
    year = today.year
    month = today.month
    days_in_month = [datetime(year, month, day).strftime('%d/%m/%Y') 
                     for day in range(1, today.day + 1)]
    return days_in_month

def create_or_update_attendance_excel(roll_no):
    """Create or update the attendance Excel file for the current month."""
    month_name = datetime.now().strftime('%B')
    year = datetime.now().strftime('%Y')
    file_name = f"attendance_records/{month_name}_{year}.xlsx"
    current_date = get_current_date()

    # Ensure the attendance_records folder exists
    os.makedirs("attendance_records", exist_ok=True)

    # Fetch all students from the database
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT roll_number, name FROM students")
    students_db = cursor.fetchall()
    conn.close()

    # Load existing Excel file or create a new one
    if os.path.exists(file_name):
        df = pd.read_excel(file_name)
    else:
        # Initialize a new DataFrame with Roll no and Name for all students
        valid_dates = get_valid_dates()
        student_data = [{'Roll no': student['roll_number'], 'Name': student['name']} for student in students_db]
        df = pd.DataFrame(student_data)
        for date in valid_dates:  # Initialize all valid dates as 'absent'
            df[date] = 'absent'

    # Add the current date column if it doesn't exist
    if current_date not in df.columns:
        df[current_date] = 'absent'

    # Mark attendance as 'present' for the given roll number
    df.loc[df['Roll no'] == roll_no, current_date] = 'present'

    # Save the updated DataFrame back to the Excel file
    df.to_excel(file_name, index=False)



@mark_attendance_bp.route('/mark-attendance', methods=['GET', 'POST'])
def mark_attendance():
    if request.method == 'GET':
        return render_template('mark_attendance.html')

    if request.method == 'POST':
        try:
            roll_no = request.form.get('roll_no')
            photo_base64 = request.form.get('photo')

            if not roll_no or not photo_base64:
                return jsonify({"status": "error", "message": "Roll number and photo are required"}), 400

            # Decode the photo and save it temporarily
            photo_data = base64.b64decode(photo_base64.split(',')[1])
            uploaded_image = Image.open(BytesIO(photo_data))
            temp_photo_path = os.path.join('static/uploads', f"temp_{roll_no}.jpg")
            uploaded_image.save(temp_photo_path, format='JPEG')

            # Check for stored photo in both `.jpg` and `.jpeg` formats
            stored_photo_path = None
            for ext in ['jpg', 'jpeg']:
                potential_path = os.path.join('static/uploads', f"{roll_no}.{ext}")
                if os.path.exists(potential_path):
                    stored_photo_path = potential_path
                    break

            if not stored_photo_path:
                return jsonify({"status": "error", "message": f"Stored photo not found for Roll Number {roll_no}"}), 404

            # Perform face recognition
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

            if not results[0] or face_distance > 0.6:
                return jsonify({"status": "error", "message": "Face does not match"}), 401

            # Update the attendance Excel file
            create_or_update_attendance_excel(roll_no)

            # Remove the temporary photo
            os.remove(temp_photo_path)

            return jsonify({"status": "success", "message": f"Attendance marked successfully for Roll Number {roll_no}"}), 200

        except Exception as e:
            return jsonify({"status": "error", "message": f"Error marking attendance: {str(e)}"}), 500

