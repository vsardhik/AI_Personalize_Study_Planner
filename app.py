from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_mail import Mail, Message
from fpdf import FPDF
from apscheduler.schedulers.background import BackgroundScheduler
import os
from dotenv import load_dotenv
import pytesseract
from PIL import Image
import pdfplumber
import nltk
import re
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json
import math
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import time

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sardhiksai.ai@gmail.com'
app.config['MAIL_PASSWORD'] = 'zpnrlnfhgzlhvand'
app.config['MAIL_DEFAULT_SENDER'] = 'sardhiksai.ai@gmail.com'

mail = Mail(app)

# Twilio Configuration for WhatsApp
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_AUTH_TOKEN'] = os.getenv('TWILIO_AUTH_TOKEN')
app.config['TWILIO_WHATSAPP_NUMBER'] = os.getenv('TWILIO_WHATSAPP_NUMBER')  # Format: whatsapp:+14155238886

# Initialize Twilio client
twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
PDF_FOLDER = 'generated_pdfs'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PDF_FOLDER'] = PDF_FOLDER

# Create necessary folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

# Download NLTK data
nltk.download('punkt')

# Topic complexity mapping
TOPIC_COMPLEXITY = {
    'asymptotic notations': 3,
    'searching algorithms': 2,
    'sorting algorithms': 2,
    'graph algorithms': 3,
    'binary search': 2,
    'exponential search': 2,
    'recursion': 3,
    'dynamic programming': 3,
    'greedy': 2,
    'dijkstra': 3,
    'bellman ford': 3,
    'master theorem': 3,
    'complexity': 2
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_topic_weight(topic):
    topic_lower = topic.lower()
    max_weight = 1
    
    for keyword, weight in TOPIC_COMPLEXITY.items():
        if keyword in topic_lower:
            max_weight = max(max_weight, weight)
    
    return max_weight

def extract_topics(text):
    print("Starting topic extraction from text:", text[:500])  # Debug log
    lines = text.split('\n')
    topics = []
    current_unit = None
    current_topic = None
    
    # Skip common headers
    skip_headers = ['UNIT', 'CONTENTS', 'CONTACT HRS', 'CONTACT', 'HRS']
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and headers
        if not line or line.upper() in skip_headers:
            continue
            
        # Clean up the text
        line = re.sub(r'\s+', ' ', line)
        
        # Check for Unit headers with roman numerals or numbers
        unit_match = re.search(r'Unit\s*[-–]?\s*[IVX\d]+', line, re.IGNORECASE)
        if unit_match:
            current_unit = unit_match.group(0)
            print(f"Found unit: {current_unit}")  # Debug log
            
            # Extract the rest of the line as a topic if it exists
            rest_of_line = line[unit_match.end():].strip()
            if rest_of_line and len(rest_of_line) > 5:
                if rest_of_line.startswith('-'):
                    rest_of_line = rest_of_line[1:].strip()
                current_topic = rest_of_line
                topic = f"{current_unit} - {current_topic}"
                if topic not in topics:
                    topics.append(topic)
                    print(f"Added unit topic: {topic}")  # Debug log
            continue
        
        # Check for main topic headers
        if any(keyword in line for keyword in ['Algorithms', 'Notations', 'Programming', 'Graph', 'Trees', 'Searching', 'Sorting']):
            current_topic = line.strip()
            if current_unit:
                topic = f"{current_unit} - {current_topic}"
            else:
                topic = current_topic
            if topic not in topics:
                topics.append(topic)
                print(f"Added main topic: {topic}")  # Debug log
            continue
        
        # Extract subtopics
        if len(line) > 5:
            # Split on common delimiters
            subtopics = re.split(r'[,;](?=[A-Za-z])', line)
            for subtopic in subtopics:
                subtopic = subtopic.strip()
                # Remove leading dashes, bullets, or numbers
                subtopic = re.sub(r'^[-•*\d.]+\s*', '', subtopic)
                
                if len(subtopic) > 5:
                    # Clean up the subtopic
                    subtopic = subtopic.strip('- ')
                    
                    # Skip if it's just a number or contact hours
                    if subtopic.isdigit() or subtopic.lower() == 'hrs':
                        continue
                    
                    # Add context from current topic/unit
                    if current_unit:
                        if current_topic:
                            topic = f"{current_unit} - {current_topic} - {subtopic}"
                        else:
                            topic = f"{current_unit} - {subtopic}"
                    else:
                        topic = subtopic
                        
                    if topic not in topics and not any(skip.upper() in topic.upper() for skip in skip_headers):
                        topics.append(topic)
                        print(f"Added subtopic: {topic}")  # Debug log
    
    print(f"Total topics found: {len(topics)}")  # Debug log
    return topics if topics else []

def extract_text_from_file(file_path):
    if file_path.endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            text = ''
            for page in pdf.pages:
                # Extract tables if present
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            # Filter out None and empty strings
                            row = [str(cell).strip() if cell is not None else '' for cell in row]
                            text += ' | '.join(row) + '\n'
                else:
                    # Extract regular text
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
        print("Extracted text from PDF:", text)  # Debug log
        return text
    else:
        try:
            image = Image.open(file_path)
            # Preprocess image for better OCR
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Increase contrast and sharpness
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)  # Increase contrast
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)  # Increase sharpness
            
            # Optimize OCR settings for table structure
            custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1 --dpi 300'
            text = pytesseract.image_to_string(image, config=custom_config)
            print("Extracted text from image:", text)  # Debug log
            return text
        except Exception as e:
            print(f"Error processing image: {str(e)}")  # Debug log
            raise

def generate_study_plan(text, days, hours_per_day):
    topics = extract_topics(text)
    if not topics:
        return {'error': 'No chapters/topics found to generate a study plan.'}

    topic_weights = [(topic, get_topic_weight(topic)) for topic in topics]
    topic_weights.sort(key=lambda x: x[1], reverse=True)

    total_hours = days * hours_per_day
    total_weight = sum(weight for _, weight in topic_weights)
    hours_per_topic = {topic: (weight / total_weight) * total_hours 
                      for topic, weight in topic_weights}

    plan = {'study_plan': []}
    topics_queue = list(topic_weights)
    topic_progress = {topic: 0 for topic, _ in topic_weights}

    for day in range(1, days + 1):
        day_plan = {'day': f'Day {day}', 'topics': []}
        remaining_hours = hours_per_day

        for topic, weight in topics_queue[:]:
            remaining_topic_hours = hours_per_topic[topic] - topic_progress[topic]
            if remaining_topic_hours <= 0:
                continue

            hours_to_study = min(remaining_topic_hours, remaining_hours)
            if hours_to_study <= 0:
                continue

            day_plan['topics'].append({
                'name': topic,
                'hours': round(hours_to_study, 2)
            })
            topic_progress[topic] += hours_to_study
            remaining_hours -= hours_to_study

            if topic_progress[topic] >= hours_per_topic[topic]:
                topics_queue = [(t, w) for t, w in topics_queue if t != topic]

            if remaining_hours <= 0:
                break

        plan['study_plan'].append(day_plan)

    return plan

def generate_pdf(study_plan, filename):
    pdf = FPDF()
    pdf.add_page()
    
    # Set margins
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    
    # Add title
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Your Study Plan', 0, 1, 'C')
    pdf.ln(10)
    
    # Add content
    pdf.set_font('Helvetica', '', 12)
    for day in study_plan['study_plan']:
        # Add day header
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, day['day'], 0, 1)
        pdf.set_font('Helvetica', '', 12)
        
        # Add topics
        total_hours = 0
        for topic in day['topics']:
            hours = math.floor(topic['hours'])
            minutes = round((topic['hours'] - hours) * 60)
            
            # Clean the text and split into smaller chunks if needed
            clean_text = "".join(c if ord(c) < 128 else ' ' for c in topic['name'])
            # Calculate available width
            available_width = pdf.w - 2 * pdf.l_margin
            # Split text into lines that fit the page width
            lines = []
            current_line = ""
            words = clean_text.split()
            
            for word in words:
                test_line = current_line + " " + word if current_line else word
                if pdf.get_string_width(test_line) < available_width - 20:  # -20 for time part
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Print each line
            for i, line in enumerate(lines):
                if i == len(lines) - 1:  # Last line
                    pdf.cell(0, 8, f"{line} - {hours}h {minutes}m", 0, 1)
                else:
                    pdf.cell(0, 8, line, 0, 1)
            
            total_hours += topic['hours']
        
        # Add total time
        pdf.ln(5)
        total_hrs = math.floor(total_hours)
        total_mins = round((total_hours - total_hrs) * 60)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, f"Total: {total_hrs}h {total_mins}m", 0, 1)
        pdf.ln(10)
    
    # Save PDF
    pdf_path = os.path.join(app.config['PDF_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

def send_reminder_email(email, topic, start_time):
    msg = Message('Study Reminder',
                 sender=app.config['MAIL_USERNAME'],
                 recipients=[email])
    msg.body = f"Reminder: It's time to study {topic}! Your scheduled study time starts at {start_time}."
    mail.send(msg)

def format_study_plan_text(study_plan):
    lines = []
    for day in study_plan['study_plan']:
        lines.append(f"{day['day']}")
        for topic in day['topics']:
            lines.append(f"  - {topic['name']} ({topic['hours']} hours)")
        lines.append("")
    return '\n'.join(lines)

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
        # Always split so header+part <= MAX_LEN
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
    # Now, send each chunk with correct header and delay
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

def schedule_reminders(email, whatsapp_number, study_plan, pdf_url):
    scheduler.remove_all_jobs()
    current_date = datetime.now()
    for day in study_plan['study_plan']:
        day_num = int(day['day'].split()[1]) - 1
        study_date = current_date + timedelta(days=day_num)
        topics = day['topics']
        for idx, topic in enumerate(topics):
            reminder_time = study_date.replace(hour=9, minute=0)  # 9 AM
            # Email reminder
            if email:
                scheduler.add_job(
                    send_reminder_email,
                    'date',
                    run_date=reminder_time - timedelta(minutes=15),
                    args=[email, topic['name'], reminder_time.strftime('%I:%M %p')]
                )
            # WhatsApp topic reminder
            if whatsapp_number:
                topic_msg = f"⏰ Reminder!\nToday, study: {topic['name']} ({topic['hours']} hours).\nYou got this! 💡"
                scheduler.add_job(
                    send_whatsapp_reminder,
                    'date',
                    run_date=reminder_time - timedelta(minutes=15),
                    args=[whatsapp_number, topic_msg]
                )
                # Break message after each topic except the last
                if idx < len(topics) - 1:
                    break_msg = "⏸️ Time for a short break! Stretch, hydrate, and get ready for the next topic! 🚀"
                    break_time = reminder_time + timedelta(minutes=int(topic['hours']*60))
                    scheduler.add_job(
                        send_whatsapp_reminder,
                        'date',
                        run_date=break_time,
                        args=[whatsapp_number, break_msg]
                    )
        # Day completion message
        if whatsapp_number:
            day_complete_time = study_date.replace(hour=9, minute=0) + timedelta(minutes=int(sum(t['hours'] for t in topics)*60))
            congrats_msg = f"🎉 Congrats! You've completed {day['day']} of your study plan! Keep up the great work! 💪"
            scheduler.add_job(
                send_whatsapp_reminder,
                'date',
                run_date=day_complete_time,
                args=[whatsapp_number, congrats_msg]
            )

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
        whatsapp_number = request.form.get('whatsapp_number')  # Get WhatsApp number from request
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No selected file'}), 400
        valid_files = [f for f in files if f and allowed_file(f.filename)]
        if not valid_files:
            return jsonify({'error': 'Invalid file type'}), 400
        filepaths = []
        try:
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
            # Generate PDF
            pdf_filename = f'study_plan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            try:
                pdf_path = generate_pdf(plan, pdf_filename)
                pdf_url = f'/download/{pdf_filename}'
            except Exception as pdf_error:
                print(f"PDF Generation Error: {str(pdf_error)}")
                return jsonify({'error': 'Failed to generate PDF. Please try again.'}), 500
            # Schedule reminders if email or WhatsApp is provided
            if email or whatsapp_number:
                try:
                    schedule_reminders(email, whatsapp_number, plan, pdf_url)
                    # Send initial email with PDF if email is provided
                    if email:
                        msg = Message('Your Study Plan',
                                    sender=app.config['MAIL_USERNAME'],
                                    recipients=[email])
                        msg.body = "Here's your study plan! You will receive reminders before each study session."
                        with app.open_resource(pdf_path) as pdf:
                            msg.attach('study_plan.pdf', 'application/pdf', pdf.read())
                        mail.send(msg)
                    # Send initial WhatsApp message with full plan text if WhatsApp number is provided
                    if whatsapp_number:
                        plan_text = format_study_plan_text(plan)
                        scheduler.add_job(
                            send_long_whatsapp_message_job,
                            'date',
                            run_date=datetime.now() + timedelta(seconds=1),
                            args=[whatsapp_number, plan_text]
                        )
                except Exception as notification_error:
                    print(f"Notification Error: {str(notification_error)}")
                    return jsonify({
                        'warning': 'Study plan generated but notifications could not be sent. Please check your configuration.',
                        'plan': plan,
                        'pdf_url': pdf_url
                    })
            # Clean up the uploaded files
            for filepath in filepaths:
                if os.path.exists(filepath):
                    os.remove(filepath)
            # Add PDF download URL to the response
            plan['pdf_url'] = pdf_url
            return jsonify(plan)
        except Exception as e:
            print(f"Processing Error: {str(e)}")
            for filepath in filepaths:
                if os.path.exists(filepath):
                    os.remove(filepath)
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
        # Should not reach here
        return jsonify({'error': 'Unknown error'}), 500
    except Exception as e:
        print(f"General Error: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_pdf(filename):
    return send_file(
        os.path.join(app.config['PDF_FOLDER'], filename),
        as_attachment=True,
        download_name='study_plan.pdf'
    )

@app.route('/test-email')
def test_email_route():
    try:
        # Create test message
        msg = Message('Test Email from Study Plan Generator',
                     sender=app.config['MAIL_USERNAME'],
                     recipients=[app.config['MAIL_USERNAME']])  # Send to self
        msg.body = "This is a test email to verify your email configuration is working correctly."
        
        # Try to send
        mail.send(msg)
        return jsonify({'message': 'Test email sent successfully! Check your inbox.'})
    except Exception as e:
        print(f"Email test error: {str(e)}")
        return jsonify({
            'error': f'Email configuration error: {str(e)}',
            'config': {
                'server': app.config['MAIL_SERVER'],
                'port': app.config['MAIL_PORT'],
                'username': app.config['MAIL_USERNAME'],
                'password_set': bool(app.config['MAIL_PASSWORD']),
                'tls': app.config['MAIL_USE_TLS']
            }
        }), 500

@app.route('/test-whatsapp')
def test_whatsapp_route():
    try:
        # Get the WhatsApp number from the request
        whatsapp_number = request.args.get('number')
        if not whatsapp_number:
            return jsonify({'error': 'Please provide a WhatsApp number'}), 400

        # Send a test message
        message = twilio_client.messages.create(
            body="🚀 Test Message from Study Plan Generator!\n\nThis is a test message to verify WhatsApp integration is working correctly.",
            from_=app.config['TWILIO_WHATSAPP_NUMBER'],
            to=whatsapp_number
        )
        
        return jsonify({
            'message': 'Test WhatsApp message sent successfully!',
            'message_sid': message.sid,
            'config': {
                'account_sid': app.config['TWILIO_ACCOUNT_SID'],
                'whatsapp_number': app.config['TWILIO_WHATSAPP_NUMBER'],
                'to_number': whatsapp_number
            }
        })
    except Exception as e:
        print(f"WhatsApp test error: {str(e)}")
        return jsonify({
            'error': f'WhatsApp configuration error: {str(e)}',
            'config': {
                'account_sid': app.config['TWILIO_ACCOUNT_SID'],
                'whatsapp_number': app.config['TWILIO_WHATSAPP_NUMBER']
            }
        }), 500

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

        # Handle different types of messages
        if 'adjust' in message and 'day' in message:
            # Extract day number
            day_match = re.search(r'day\s+(\d+)', message)
            if day_match:
                day_num = int(day_match[1]) - 1
                if 0 <= day_num < len(study_plan['study_plan']):
                    # Extract hours if provided
                    hours_match = re.search(r'(\d+)\s*hours?', message)
                    if hours_match:
                        new_hours = int(hours_match[1])
                        # Adjust the day's schedule
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
            # Extract day number
            day_match = re.search(r'day\s+(\d+)', message)
            if day_match:
                day_num = int(day_match[1]) - 1
                if 0 <= day_num < len(study_plan['study_plan']):
                    # Extract available hours
                    hours_match = re.search(r'(\d+)\s*hours?', message)
                    if hours_match:
                        available_hours = int(hours_match[1])
                        # Adjust the day's schedule
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
            response = """Here are the available commands:
1. "adjust day X to Y hours" - Modify hours for a specific day
2. "busy on day X, available Y hours" - Mark a day when you have less time
3. "help" - Show this help message"""

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