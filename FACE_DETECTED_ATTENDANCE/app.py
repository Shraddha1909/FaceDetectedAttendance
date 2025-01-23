from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from mark_attendance import mark_attendance_bp
from flask import send_file
from flask import session, redirect, url_for
import pandas as pd
from db_connection import create_connection, close_connection

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
ATTENDANCE_FOLDER = 'attendance_records'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024  # 200 KB
app.secret_key = 'shraddhask'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ATTENDANCE_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/student-dashboard')
def student_dashboard():
    return render_template('student_dashboard.html')

@app.route('/register-student', methods=['GET', 'POST'])
def register_student():
    conn = None  
    try:
        if request.method == 'GET':
            return render_template('register_student.html')

        if request.method == 'POST':
            roll_number = request.form['roll_no']
            name = request.form['name']
            photo = request.files['photo']

            if not roll_number or not name or not photo:
                return jsonify({"status": "error", "message": "All fields are required"}), 400

            photo_filename = f"{roll_number}.jpeg"  
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            photo.save(photo_path)

            conn = create_connection()  
            cursor = conn.cursor()

            
            cursor.execute("SELECT * FROM students WHERE roll_number = %s", (roll_number,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "Roll number already exists"}), 400

            
            query = "INSERT INTO students (roll_number, name, image_path) VALUES (%s, %s, %s)"
            cursor.execute(query, (roll_number, name, photo_path))
            conn.commit()

            excel_file_path = 'student_registration.xlsx'
            photo_url = f'=HYPERLINK("{photo_path}", "{photo_path}")'
            student_data = {'Roll Number': [roll_number], 'Name': [name], 'Image Path': [photo_url]}

            if os.path.exists(excel_file_path):
                df = pd.read_excel(excel_file_path)
                new_row = pd.DataFrame(student_data)
                df = pd.concat([df, new_row], ignore_index=True)
            else:
                student_data = {'Serial No.': [1], 'Roll Number': [roll_number], 'Name': [name], 'Image Path': [photo_url]}
                df = pd.DataFrame(student_data)

            df = df[['Serial No.', 'Roll Number', 'Name', 'Image Path']] 
            df.to_excel(excel_file_path, index=False)

            return jsonify({"status": "success", "message": "Student registered successfully"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500
    finally:
        if conn:
            if 'cursor' in locals():
                cursor.close()
            close_connection(conn)


app.register_blueprint(mark_attendance_bp)

@app.route('/view-attendance', methods=['GET', 'POST'])
def view_attendance():
    if request.method == 'GET':
        return render_template('view_attendance.html')

    elif request.method == 'POST':
        roll_no = request.form.get('roll_no')

        if not roll_no:
            return render_template('view_attendance.html', error="Roll number is required.")

        try:
            attendance_records = []
            total_days = 0
            present_days = 0
            attendance_folder = os.path.join(os.getcwd(), 'attendance_records')

            if not os.path.exists(attendance_folder):
                return render_template('view_attendance.html', error="Attendance folder not found.")

            for file_name in os.listdir(attendance_folder):
                if file_name.endswith('.xlsx'):
                    file_path = os.path.join(attendance_folder, file_name)
                    df = pd.read_excel(file_path)

                    if 'Roll no' not in df.columns:
                        continue

                    student_records = df[df['Roll no'].astype(str).str.strip() == roll_no.strip()]
                    if student_records.empty:
                        continue

                    for _, row in student_records.iterrows():
                        for column_name, value in row.items():
                            if column_name in ['Roll no', 'Name']:
                                continue

                            try:
                                parsed_date = pd.to_datetime(column_name, format="%d/%b/%Y", dayfirst=True, errors='coerce')
                                if pd.isnull(parsed_date):
                                    continue

                                parsed_date = parsed_date.strftime('%Y-%m-%d')
                                total_days += 1

                                if value.lower() == 'present':
                                    present_days += 1
                                    attendance_records.append({"date": parsed_date, "status": "Present"})
                                elif value.lower() == 'absent':
                                    attendance_records.append({"date": parsed_date, "status": "Absent"})
                            except:
                                continue

            if not attendance_records:
                return render_template(
                    'view_attendance.html',
                    error=f"No attendance records found for Roll Number {roll_no}.",
                    roll_no=roll_no
                )

            attendance_percentage = round((present_days / total_days) * 100, 2) if total_days > 0 else 0

            return render_template(
                'view_attendance.html',
                roll_no=roll_no,
                attendance=attendance_records,
                total_days=total_days,
                present_days=present_days,
                attendance_percentage=attendance_percentage
            )

        except Exception as e:
            return render_template('view_attendance.html', error=f"An error occurred: {str(e)}")





@app.route('/teacher-login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'GET':
        return render_template('teacher_login.html')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM teachers WHERE username = %s", (username,))
            teacher = cursor.fetchone()

            if teacher and teacher['password'] == password: 
                session['teacher_id'] = teacher['id']
                session['teacher_username'] = teacher['username']
                return redirect(url_for('teacher_dashboard'))
            else:
                return render_template(
                    'teacher_login.html',
                    error="Invalid username or password."
                )
        except Exception as e:
            return render_template('teacher_login.html', error=f"Error: {str(e)}")
        finally:
            if 'cursor' in locals():
                cursor.close()
            close_connection(conn)

@app.route('/teacher-dashboard')
def teacher_dashboard():
    if 'teacher_id' not in session:
        return redirect(url_for('teacher_login'))
    return render_template('teacher_dashboard.html')


@app.route('/teacher/student_list')
def student_list():
    conn = create_connection()  
    cursor = conn.cursor()
    
    
    cursor.execute("SELECT roll_number, name, image_path FROM students")
    students = cursor.fetchall()  
    
    conn.close()  
    
    
    return render_template('student_list.html', students=students)



@app.route('/teacher/view-attendance', methods=['GET'])
def teacher_view_attendance():
    try:
        
        attendance_folder = os.path.join(os.getcwd(), 'attendance_records')

        
        files = [
            f for f in os.listdir(attendance_folder)
            if os.path.isfile(os.path.join(attendance_folder, f))
        ]

        
        return render_template('teacher_view_attendance.html', files=files)
    except Exception as e:
        
        return render_template('teacher_view_attendance.html', error=f"Error: {str(e)}")

@app.route('/attendance/<filename>')
def open_attendance_file(filename):
    try:
        
        attendance_folder = os.path.join(os.getcwd(), 'attendance_records')

        
        file_path = os.path.join(attendance_folder, filename)

        
        if not os.path.exists(file_path):
            return f"Error: File '{filename}' not found in 'attendance_records' folder.", 404

        
        return send_file(
            file_path,
            as_attachment=False,  
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        
        return f"Error: {str(e)}"

    
    return file_path





if __name__ == '__main__':
    app.run(debug=True)
