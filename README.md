# 🏡 Property Inspection Report Generator

A high-performance Flask web application that generates professional, TREC-compliant PDF property inspection reports from JSON data. Built with async processing, modern UI, and optimized for speed.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features

### 🤖 AI-Powered Analysis
- **Executive Summary**: AI-generated overview of property condition with key insights
- **Smart Deficiency Categorization**: Automatically sorts issues by priority (Safety, Urgent, Routine)
- **Priority Breakdown**: Visual counts and detailed analysis of issues by severity
- **Free Tier Available**: Uses Google Gemini 1.5 Flash API (1,500 requests/day free)
- **Optional**: Toggle on/off per analysis - doesn't affect regular PDF generation speed
- **Smart Integration**: Only 2 API calls per analysis for optimal efficiency

### 🚀 Performance
- **Lightning Fast**: Async image downloading with aiohttp and concurrent processing
- **Thread Pool Optimization**: CPU-intensive LaTeX generation runs in parallel
- **Smart Caching**: Images are cached to avoid redundant downloads
- **Batch Processing**: Handles multiple images and sections efficiently
- **Efficient AI**: Only 2 API calls per analysis (when enabled)

### 📄 PDF Generation
- **TREC-Compliant**: Follows Texas Real Estate Commission standards
- **Professional Layout**: Clean, organized sections with proper formatting
- **Rich Content**: Includes title page, inspection details, and comprehensive sections
- **Image Support**: Auto-converts WEBP, PNG, JPG formats and embeds in PDF
- **Dynamic Tables**: Uses LaTeX longtable for multi-page content

### 🎨 User Interface
- **Modern Design**: Gradient color scheme with smooth animations
- **Drag & Drop**: Easy file upload with visual feedback
- **AI Toggle**: Easy on/off switch for AI analysis
- **Results Display**: Beautiful, color-coded AI insights
- **Loading Animation**: Beautiful progress indicators with step tracking
- **Responsive**: Works seamlessly on desktop and mobile devices
- **Form Reset**: Automatically resets for multiple uploads

### 🖼️ Image Processing
- **Format Detection**: Uses Pillow to identify true image formats
- **Auto-Conversion**: Converts WEBP and unsupported formats to PNG
- **Optimization**: Resizes images to fit within report constraints
- **Error Handling**: Gracefully handles failed downloads

## 🛠️ Technology Stack

**Backend**
- Flask 3.0.0 - Modern web framework
- asyncio - Asynchronous processing for optimal performance
- aiohttp 3.9.1 - Async HTTP client for concurrent image downloads

**PDF Generation**
- LaTeX (pdflatex) - Professional typesetting system
- Custom template system - Dynamic content insertion with proper escaping
- Thread pool optimization - CPU-intensive operations run in parallel

**Image Processing**
- Pillow 10.1.0 - Image format detection and conversion
- Smart caching - Avoids redundant downloads
- Auto-conversion - WEBP, PNG, JPG formats supported

**AI Integration**
- Google Generative AI 0.3.2 - Gemini 1.5 Flash API
- JSON-mode responses - Structured, reliable outputs
- Error handling - Graceful fallbacks for API issues

**Frontend**
- HTML5, CSS3 - Modern responsive design
- Vanilla JavaScript - No framework dependencies, lightweight
- Google Fonts (Inter) - Professional typography
- Gradient UI - Modern color scheme with smooth animations

## 📋 Prerequisites

- Python 3.8 or higher
- LaTeX distribution (TeX Live, MiKTeX, or MacTeX)
- Modern web browser (Chrome, Firefox, Safari, Edge)
- (Optional) Google Gemini API key for AI analysis features

## 🐳 Quick Start with Docker

The easiest way to run the application:

```bash
# Build the Docker image
docker build -t property-inspector .

# Run the container
docker run -p 8080:8080 property-inspector

# Access the application at http://localhost:8080
```

## 💻 Local Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Jeevan-HM/Startup-Village-2025.git
cd Startup-Village-2025
```

### 2. Install LaTeX

**macOS:**
```bash
brew install --cask mactex
# Or use BasicTeX for a smaller install:
brew install --cask basictex
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install texlive-latex-base texlive-latex-extra texlive-fonts-recommended
```

**Windows:**
- Download and install [MiKTeX](https://miktex.org/download)
- Or use [TeX Live](https://www.tug.org/texlive/)

**Verify Installation:**
```bash
pdflatex --version
```

### 3. Set Up Python Environment

**Using pip:**
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Using uv (faster):**
```bash
# Install uv if you haven't
pip install uv

# Create environment and install dependencies
uv sync
```

### 4. Run the Application

```bash
# Using Flask directly
python app.py

# Or using the start script
chmod +x start.sh
./start.sh
```

The application will be available at `http://localhost:8080`

### 5. (Optional) Set Up AI Analysis

To enable AI-powered analysis features:

1. Get a free API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a `.env` file in the project root:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```
3. The AI toggle will automatically appear in the web interface

**Note**: Without an API key, the app works perfectly fine - you just won't have AI analysis features.

## 📁 Project Structure

```
Startup-Village-2025/
├── app.py                  # Flask application and routes
├── create_form.py          # PDF generation logic with async processing
├── gemini_ai.py           # AI analysis integration
├── requirements.txt        # Python dependencies
├── pyproject.toml         # Project configuration (uv)
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker compose setup
│
├── templates/
│   └── index.html         # Modern responsive web interface
│
├── static/
│   └── css/
│       └── style.css      # Gradient UI with animations
│
├── latex/
│   ├── report.tex         # LaTeX template
│   ├── obstruction.png    # Static template image
│   └── scope.png          # Static template image
│
├── uploads/               # Temporary JSON uploads
└── outputs/               # Generated PDFs (timestamped folders)
```

## 🎯 Usage

### 1. Prepare Your JSON Data

Your JSON file should follow this structure:

```json
{
  "inspection": {
    "clientInfo": {
      "name": "John Doe"
    },
    "address": {
      "fullAddress": "123 Main St, City, State 12345"
    },
    "inspector": {
      "name": "Inspector Name",
      "email": "inspector@example.com"
    },
    "schedule": {
      "date": 1699123200000
    },
    "sections": [
      {
        "name": "SECTION NAME",
        "lineItems": [
          {
            "title": "Item Title",
            "inspectionStatus": "I",
            "isDeficient": false,
            "comments": [
              {
                "label": "Comment label",
                "value": "Comment text",
                "photos": [
                  {
                    "url": "https://example.com/image.jpg"
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### 2. Upload and Generate

#### Standard PDF Generation:
1. Open the application in your browser (`http://localhost:8080`)
2. Click "Choose JSON file" or drag and drop your file
3. Click "Generate Report"
4. Wait for the progress animation to complete
5. Your PDF will automatically download

#### With AI Analysis:
1. Enable the "AI-Powered Analysis" toggle
2. Upload your JSON file
3. Click "Get AI Analysis" to see insights
4. Review the AI-generated summary and recommendations
5. Click "Generate Report" to create the PDF
6. Both buttons work independently - analyze first, then generate, or just generate directly

### 3. Multiple Reports

After generation completes:
- The form automatically resets
- Simply select another JSON file
- Toggle AI analysis on/off as needed
- Generate as many reports as needed

## 🔧 Configuration

### Environment Variables

Create a `.env` file (optional):

```bash
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-here
MAX_CONTENT_LENGTH=52428800  # 50MB in bytes
```

### Customization

**Change Port:**
Edit `app.py`:
```python
app.run(debug=True, host="0.0.0.0", port=YOUR_PORT)
```

**Modify LaTeX Template:**
Edit `latex/report.tex` to customize PDF appearance.

**Adjust Image Sizes:**
Edit `create_form.py` in the `generate_latex_body()` function.

## 🐛 Troubleshooting

### PDF Generation Fails

**Issue**: "PDFLaTeX compilation failed"

**Solutions:**
1. Verify LaTeX is installed: `pdflatex --version`
2. Check LaTeX packages are installed
3. Review error logs in `outputs/[timestamp]/latex/` folder
4. Ensure images URLs are accessible

### Images Not Appearing

**Issue**: Images don't show in PDF or show as text labels

**Solutions:**
1. Verify image URLs are publicly accessible and start with `http://` or `https://`
2. Check internet connection
3. Look for download errors in console output (shows "✓ Downloaded X/Y images")
4. Static images (obstruction.png, scope.png) are automatically copied from latex/ folder
5. Supported formats: JPG, PNG, WEBP (auto-converted to PNG)
6. Check `outputs/[timestamp]/images/` folder to verify images were downloaded

### Loading Animation Stuck

**Issue**: Animation doesn't disappear after generation

**Solutions:**
1. Refresh the page (F5)
2. Check browser console for JavaScript errors
3. Ensure Flask is running without errors
4. Verify PDF was generated in `outputs/` folder

### Port Already in Use

**Issue**: "Address already in use"

**Solution:**
```bash
# Find and kill process using port 8080
lsof -ti:8080 | xargs kill -9

# Or change port in app.py
```

## 🚀 Deployment

> **⚠️ Important**: This application requires LaTeX (`pdflatex`) to generate PDFs. Vercel and other serverless platforms do NOT support LaTeX. Use Docker-based hosting instead.

### ✅ Recommended: Render.com (Free Tier Available)

1. **Push your code to GitHub**
2. **Connect to Render.com**:
   - Go to [Render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect the `render.yaml` configuration

3. **Deploy automatically**: Render will build and deploy using Docker

**Render.yaml is already configured!** ✅

### 🐳 Alternative: Railway.app

1. **Push code to GitHub**
2. **Deploy on Railway**:
   - Go to [Railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Railway will auto-detect and use the Dockerfile

### 🖥️ Self-Hosted with Docker

```bash
# Build production image
docker build -t property-inspector:latest .

# Run with Docker
docker run -d \
  -p 8080:8080 \
  --name property-inspector \
  property-inspector:latest

# Or use Docker Compose
docker-compose up -d
```

### 🚫 Why Not Vercel?

Vercel's serverless functions have a **read-only file system** (except `/tmp`) and **do not include LaTeX**. While we've updated the code to use `/tmp` directories, LaTeX compilation will fail on Vercel.

**If you must use Vercel**, consider:
- Using an external LaTeX API (Overleaf API, LaTeX.Online)
- Pre-generating PDFs elsewhere
- Using a different PDF generation library (WeasyPrint, ReportLab)

### Traditional Deployment (VPS/Cloud)

Use a production WSGI server:

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

### Environment Configuration

For production, set these environment variables:
```bash
export FLASK_ENV=production
export FLASK_DEBUG=False
export GEMINI_API_KEY="generate-a-secure-random-key"
```

## 📊 Performance

- **Average Generation Time**: 3-8 seconds (depends on image count and complexity)
- **Concurrent Image Downloads**: Up to 10 parallel connections with aiohttp
- **AI Analysis Time**: 2-4 seconds (2 API calls via Gemini Flash)
- **Maximum File Size**: 50MB JSON files
- **PDF Size**: Typically 2-15MB depending on images and content
- **Thread Pool**: 4 workers for parallel LaTeX processing
- **Image Caching**: Smart caching prevents redundant downloads

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👨‍💻 Author

**Jeevan-HM**
- GitHub: [@Jeevan-HM](https://github.com/Jeevan-HM)

<div align="center">
Made with ❤️ for property inspectors
</div>

## ⚠️ License & Ownership

This project was built for the VillageHacks hackathon.

**This code is proprietary and all rights are reserved by Jeevan Hebbal Manjunath.** It is not open source. You may not use, copy, modify, or distribute this code for any purpose, especially for commercial use, without express written permission.

Please see the [LICENSE](LICENSE) file for full details.
