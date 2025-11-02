import asyncio
import json
import os
import secrets
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from create_form import generate_pdf_from_json

# Load environment variables from .env file
load_dotenv()
from gemini_ai import get_gemini_analyzer

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max file size
# Use /tmp for serverless environments like Vercel
app.config["UPLOAD_FOLDER"] = "/tmp/uploads"
app.config["OUTPUT_FOLDER"] = "/tmp/outputs"

# Ensure directories exist
Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True, parents=True)
Path(app.config["OUTPUT_FOLDER"]).mkdir(exist_ok=True, parents=True)


def allowed_file(filename):
    """Check if file is a JSON file."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "json"


@app.route("/")
def index():
    """Main page with upload form."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handle JSON file upload and generate PDF."""
    if "file" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only JSON files are allowed", "error")
        return redirect(url_for("index"))

    try:
        # Read and parse JSON
        json_data = json.load(file.stream)

        # Generate unique output directory for this request
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(app.config["OUTPUT_FOLDER"], timestamp)
        os.makedirs(output_dir, exist_ok=True)

        # Copy template directory structure
        import shutil

        latex_output = os.path.join(output_dir, "latex")
        os.makedirs(latex_output, exist_ok=True)

        # Copy report.tex if it exists
        if os.path.exists("latex/report.tex"):
            shutil.copy("latex/report.tex", os.path.join(latex_output, "report.tex"))

        # Generate PDF asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pdf_path, cleanup_dir, cleanup_tex = loop.run_until_complete(
            generate_pdf_from_json(json_data, latex_output)
        )
        loop.close()

        if not os.path.exists(pdf_path):
            flash("Failed to generate PDF", "error")
            return redirect(url_for("index"))

        flash("Report generated successfully!", "success")
        
        # Import cleanup function
        from create_form import cleanup_temp_files
        
        # Send file and register cleanup after response
        response = send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"inspection_report_{timestamp}.pdf",
            mimetype="application/pdf",
        )
        
        # Schedule cleanup to happen after response is sent
        @response.call_on_close
        def cleanup_after_download():
            try:
                cleanup_temp_files(cleanup_dir, cleanup_tex)
            except Exception:
                pass  # Silently fail on cleanup errors
        
        return response

    except json.JSONDecodeError:
        flash("Invalid JSON file format", "error")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Error generating report: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/analyze", methods=["POST"])
def analyze_inspection():
    """
    AI-powered inspection analysis endpoint.
    Returns executive summary and deficiency categorization.
    Only called when user explicitly requests AI analysis.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not allowed_file(file.filename):
        return jsonify({"error": "Only JSON files allowed"}), 400

    try:
        # Parse JSON
        json_data = json.load(file.stream)

        # Get Gemini analyzer
        analyzer = get_gemini_analyzer()

        if not analyzer.is_enabled():
            return jsonify(
                {
                    "error": "AI analysis not available. Set GEMINI_API_KEY environment variable."
                }
            ), 503

        # Run AI analysis (2 API calls total)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            executive_summary = loop.run_until_complete(
                analyzer.generate_executive_summary(json_data)
            )
            deficiency_analysis = loop.run_until_complete(
                analyzer.analyze_deficiencies(json_data)
            )
        finally:
            loop.close()

        # Combine results (synchronous function, no loop needed)
        insights = analyzer.enhance_summary_insights_sync(
            deficiency_analysis, executive_summary
        )

        return jsonify({"success": True, "analysis": insights})

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON format"}), 400
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    analyzer = get_gemini_analyzer()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai_enabled": analyzer.is_enabled(),
    }


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
