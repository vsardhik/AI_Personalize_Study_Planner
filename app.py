from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_mail import Mail, Message
from fpdf import FPDF
import os
from dotenv import load_dotenv
import pytesseract
from PIL import Image
import pdfplumber
import nltk
import re
from werkzeug.utils import secure_filename
from datetime import datetime
import math
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import time
import traceback

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_AUTH_TOKEN'] = os.getenv('TWILIO_AUTH_TOKEN')
app.config['TWILIO_WHATSAPP_NUMBER'] = os.getenv('TWILIO_WHATSAPP_NUMBER')
twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])

UPLOAD_FOLDER = 'uploads'
PDF_FOLDER = 'generated_pdfs'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PDF_FOLDER'] = PDF_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

nltk.download('punkt')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path):
    if file_path.endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            text = ''
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
        return text
    else:
        image = Image.open(file_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        raw_text = pytesseract.image_to_string(image)
        lines = raw_text.split('\n')
        filtered = []
        for line in lines:
            l = line.strip()
            if not l or len(l) < 5:
                continue
            if re.match(r'^(unit|chapter|module)\s*[-–:]?\s*[ivx\d]+', l, re.I):
                continue
            if re.match(r'^(page|contact|footer|email|phone|university|syllabus)', l, re.I):
                continue
            if re.match(r'^\d+$', l):
                continue
            if l.isupper() and len(l.split()) <= 4:
                continue
            filtered.append(l)
        return '\n'.join(filtered)

def extract_topics(text):
    lines = text.split('\n')
    topics = []
    for line in lines:
        l = line.strip()
        if not l or len(l) < 5:
            continue
        if re.match(r'^(unit|chapter|module)\s*[-–:]?\s*[ivx\d]+', l, re.I):
            continue
        if re.match(r'^(page|contact|footer|email|phone|university|syllabus)', l, re.I):
            continue
        if re.match(r'^\d+$', l):
            continue
        if l.isupper() and len(l.split()) <= 4:
            continue
        if re.match(r'^(unit|chapter|module)\s*-?\s*$', l, re.I):
            continue
        if len(l.split()) == 1:
            continue
        topics.append(l)
    return topics if topics else []

def generate_study_plan(text, days, hours_per_day):
    topics = extract_topics(text)
    if not topics:
        return {'error': 'No topics found to generate a study plan.'}

    total_hours = days * hours_per_day
    topic_weights = [max(1, len(topic.split())) for topic in topics]
    total_weight = sum(topic_weights)
    hours_per_topic = [total_hours * (w / total_weight) for w in topic_weights]

    plan = {'study_plan': []}
    topic_queue = list(zip(topics, hours_per_topic))
    topic_progress = [0] * len(topic_queue)
    topic_idx = 0

    for day in range(1, days + 1):
        day_plan = {'day': f'Day {day}', 'topics': []}
        remaining_hours = hours_per_day
        while remaining_hours > 0 and topic_idx < len(topic_queue):
            topic, total_topic_hours = topic_queue[topic_idx]
            done = topic_progress[topic_idx]
            left = total_topic_hours - done
            if left <= 0:
                topic_idx += 1
                continue
            hours_to_study = min(left, remaining_hours)
            day_plan['topics'].append({
                'name': topic,
                'hours': round(hours_to_study, 2)
            })
            topic_progress[topic_idx] += hours_to_study
            remaining_hours -= hours_to_study
            if topic_progress[topic_idx] >= total_topic_hours:
                topic_idx += 1
        plan['study_plan'].append(day_plan)
    return plan

def clean_latin1(text):
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-', '\u2026': '...', '\u2022': '*'
    }
    for uni, ascii_ in replacements.items():
        text = text.replace(uni, ascii_)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_pdf(study_plan, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, clean_latin1('Your Study Plan'), 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 12)
    for day in study_plan['study_plan']:
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, clean_latin1(day['day']), 0, 1)
        pdf.set_font('Helvetica', '', 12)
        total_hours = 0
        for topic in day['topics']:
            pdf.cell(0, 8, clean_latin1(f"{topic['name']} - {topic['hours']} hours"), 0, 1)
            total_hours += topic['hours']
        total_hrs = int(total_hours)
        total_mins = int(round((total_hours - total_hrs) * 60))
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, f"Total for {day['day']}: {total_hrs}h {total_mins}m", 0, 1)
        pdf.ln(5)
    pdf_path = os.path.join(app.config['PDF_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

def send_whatsapp_reminder(whatsapp_number, message):
    try:
        if not whatsapp_number.startswith('whatsapp:'):
            whatsapp_number = f'whatsapp:{whatsapp_number}'
        msg = twilio_client.messages.create(
            body=message,
            from_=app.config['TWILIO_WHATSAPP_NUMBER'],
            to=whatsapp_number
        )
        print(f"WhatsApp reminder sent: {msg.sid}")
        return True
    except TwilioRestException as e:
        print(f"Error sending WhatsApp reminder: {str(e)}")
        return False

def send_long_whatsapp_message_job(whatsapp_number, full_text):
    MAX_LEN = 1600
    lines = full_text.split('\n')
    chunks = []
    current = ''
    for line in lines:
        while True:
            header = "📚 Your Study Plan!\n\n"
            max_body = MAX_LEN - len(header)
            if len(line) > max_body:
                part = line[:max_body]
                if current:
                    chunks.append(current)
                    current = ''
                chunks.append(part)
                line = line[max_body:]
            else:
                if len(current) + len(line) + 1 > max_body:
                    chunks.append(current)
                    current = ''
                current += (line + '\n')
                break
    if current:
        chunks.append(current)
    for idx, chunk in enumerate(chunks):
        header = f"📚 Your Study Plan (Part {idx+1}/{len(chunks)})\n\n" if len(chunks) > 1 else "📚 Your Study Plan!\n\n"
        max_body = MAX_LEN - len(header)
        start = 0
        while start < len(chunk):
            part = chunk[start:start+max_body]
            send_whatsapp_reminder(whatsapp_number, header + part)
            start += max_body
            if start < len(chunk):
                time.sleep(2)
        if idx < len(chunks) - 1:
            time.sleep(2)

def format_study_plan_text(study_plan):
    lines = []
    for day in study_plan['study_plan']:
        lines.append(f"{day['day']}")
        total_hours = 0
        for topic in day['topics']:
            lines.append(f"  - {topic['name']} ({topic['hours']} hours)")
            total_hours += topic['hours']
        total_hrs = int(total_hours)
        total_mins = int(round((total_hours - total_hrs) * 60))
        lines.append(f"Total for {day['day']}: {total_hrs}h {total_mins}m")
    return '\n'.join(lines)

@app.route('/')
def serve_static():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        files = request.files.getlist('file')
        days = int(request.form.get('days', 7))
        hours = int(request.form.get('hours', 4))
        email = request.form.get('email')
        whatsapp_number = request.form.get('whatsapp_number')
        
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No selected file'}), 400
            
        valid_files = [f for f in files if f and allowed_file(f.filename)]
        if not valid_files:
            return jsonify({'error': 'Invalid file type'}), 400
            
        filepaths = []
        all_text = ''
        
        for file in valid_files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            filepaths.append(filepath)
            text = extract_text_from_file(filepath)
            all_text += '\n\n' + text
            
        plan = generate_study_plan(all_text, days, hours)
        if 'error' in plan:
            return jsonify(plan), 400
            
        pdf_filename = f'study_plan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf_path = generate_pdf(plan, pdf_filename)
        pdf_url = f'/download/{pdf_filename}'
        
        if whatsapp_number:
            plan_text = format_study_plan_text(plan)
            send_long_whatsapp_message_job(whatsapp_number, plan_text)
            
        if email:
            msg = Message('Your Study Plan',
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[email])
            msg.body = "Here's your study plan!"
            with app.open_resource(pdf_path) as pdf:
                msg.attach('study_plan.pdf', 'application/pdf', pdf.read())
            mail.send(msg)
        
        for filepath in filepaths:
            if os.path.exists(filepath):
                os.remove(filepath)
                
        plan['pdf_url'] = pdf_url
        return jsonify(plan)
        
    except Exception as e:
        traceback.print_exc()
        for filepath in filepaths:
            if os.path.exists(filepath):
                os.remove(filepath)
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_pdf(filename):
    return send_file(
        os.path.join(app.config['PDF_FOLDER'], filename),
        as_attachment=True,
        download_name='study_plan.pdf'
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '').lower()
        study_plan = data.get('study_plan')

        if not study_plan:
            return jsonify({'error': 'No study plan available'}), 400

        response = ''
        updated_plan = None

        if 'adjust' in message and 'day' in message:
            import re
            day_match = re.search(r'day\s+(\d+)', message)
            if day_match:
                day_num = int(day_match[1]) - 1
                if 0 <= day_num < len(study_plan['study_plan']):
                    hours_match = re.search(r'(\d+)\s*hours?', message)
                    if hours_match:
                        new_hours = int(hours_match[1])
                        day = study_plan['study_plan'][day_num]
                        total_hours = sum(topic['hours'] for topic in day['topics'])
                        ratio = new_hours / total_hours if total_hours > 0 else 1
                        for topic in day['topics']:
                            topic['hours'] = round(topic['hours'] * ratio, 2)
                        updated_plan = study_plan
                        response = f"Adjusted Day {day_num + 1} schedule to {new_hours} hours."
                    else:
                        response = f"How many hours would you like to allocate for Day {day_num + 1}?"
                else:
                    response = f"Please enter a valid day number between 1 and {len(study_plan['study_plan'])}."
            else:
                response = "Please specify which day you want to adjust (e.g., 'adjust day 2')."

        elif 'busy' in message and 'day' in message:
            import re
            day_match = re.search(r'day\s+(\d+)', message)
            if day_match:
                day_num = int(day_match[1]) - 1
                if 0 <= day_num < len(study_plan['study_plan']):
                    hours_match = re.search(r'(\d+)\s*hours?', message)
                    if hours_match:
                        available_hours = int(hours_match[1])
                        day = study_plan['study_plan'][day_num]
                        total_hours = sum(topic['hours'] for topic in day['topics'])
                        ratio = available_hours / total_hours if total_hours > 0 else 1
                        for topic in day['topics']:
                            topic['hours'] = round(topic['hours'] * ratio, 2)
                        updated_plan = study_plan
                        response = f"Updated Day {day_num + 1} schedule to fit within {available_hours} hours."
                    else:
                        response = f"How many hours are you available on Day {day_num + 1}?"
                else:
                    response = f"Please enter a valid day number between 1 and {len(study_plan['study_plan'])}."
            else:
                response = "Please specify which day you're busy on (e.g., 'busy on day 2')."

        elif 'help' in message:
            response = """Here are the available commands:\n1. 'adjust day X to Y hours' - Modify hours for a specific day\n2. 'busy on day X, available Y hours' - Mark a day when you have less time\n3. 'help' - Show this help message"""

        else:
            response = "I can help you adjust your study plan. Try saying 'help' to see available commands."

        return jsonify({
            'response': response,
            'updated_plan': updated_plan
        })

    except Exception as e:
        print(f"Chat Error: {str(e)}")
        return jsonify({'error': 'An error occurred while processing your request'}), 500

if __name__ == '__main__':
    app.run(debug=True)
