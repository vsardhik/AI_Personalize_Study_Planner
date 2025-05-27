# Study Plan Generator Chatbot

A modern web application that helps students create personalized study plans from their syllabus. Upload your syllabus (PDF or image), specify your study duration and daily hours, and get an AI-generated study plan that takes into account topic complexity and optimal learning patterns.

## Features

- 📚 Upload syllabus in PDF or image format
- 🤖 AI-powered topic extraction and complexity analysis
- ⏰ Customizable study duration and daily hours
- 📊 Smart distribution of topics based on complexity
- 💬 Interactive chatbot interface
- 📱 Responsive design for all devices

## Prerequisites

Before running the application, make sure you have the following installed:

- Python 3.7 or higher
- Tesseract OCR engine (for image processing)

### Installing Tesseract OCR

#### Windows
1. Download the installer from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer
3. Add the Tesseract installation directory to your system PATH

#### macOS
```bash
brew install tesseract
```

#### Linux
```bash
sudo apt-get install tesseract-ocr
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd study-plan-generator
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

## Usage

1. Click the upload area or drag and drop your syllabus file (PDF or image)
2. Set the number of days you want to study
3. Set the number of hours you can study per day
4. Click "Generate Plan"
5. Review your personalized study plan
6. Make adjustments if needed

## Project Structure

```
study-plan-generator/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── static/               # Static files
│   ├── index.html        # Main HTML file
│   ├── style.css         # Styles
│   ├── script.js         # Frontend JavaScript
│   └── upload-icon.svg   # Upload icon
├── uploads/              # Temporary file storage
└── README.md             # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 