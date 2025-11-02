import json
from datetime import datetime
from io import BytesIO
from urllib.request import Request, urlopen  # Added Request for headers

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader, simpleSplit  # Added ImageReader
from reportlab.pdfgen import canvas


# --- Helper function for Roman Numerals ---
def to_roman(n):
    """Converts an integer to a Roman numeral."""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ""
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman_num += syb[i]
            n -= val[i]
        i += 1
    return roman_num


# --- Helper function to draw the static page template ---
def draw_page_template(c, page_num, total_pages):
    """Draws the header and footer on every page."""
    c.saveState()
    width, height = letter

    # --- Header ---
    c.setFont("Helvetica", 9)
    c.drawString(72, height - 40, "Report Identification:")

    c.setFont("Helvetica-Bold", 9)
    header_text = "I=Inspected   NI=Not Inspected   NP=Not Present   D=Deficient"
    c.drawString(72, height - 55, header_text)

    # --- FOOTER ---

    # 1. Draw Page Number (Centered, Y=60)
    c.setFont("Helvetica", 9)
    page_text = f"Page {page_num} of {total_pages}"
    c.drawCentredString(width / 2, 60, page_text)

    # 2. Draw REI text (Line 2, left, Y=40)
    current_date = datetime.now().strftime("%m/%d/%Y")
    c.setFont("Helvetica", 9)
    footer_text1 = f"REI 7-6 ({current_date})"
    c.drawString(72, 40, footer_text1)  # Y=40 (bottom line)

    # 3. Draw Promulgated text (Line 2, RIGHT-ALIGNED, Clickable)
    y_pos = 40
    text_web = "www.trec.texas.gov"
    text_phone = "(512) 936-3000"
    text_sep = " • "
    text_intro = "Promulgated by the Texas Real Estate Commission • "

    width_web = c.stringWidth(text_web, "Helvetica", 9)
    width_sep = c.stringWidth(text_sep, "Helvetica", 9)
    width_phone = c.stringWidth(text_phone, "Helvetica", 9)

    x_pos = width - 72
    c.drawRightString(x_pos, y_pos, text_web)
    c.linkURL(
        f"https://{text_web}",
        (x_pos - width_web, y_pos - 2, x_pos, y_pos + 9),
        relative=0,
    )
    x_pos -= width_web

    c.drawRightString(x_pos, y_pos, text_sep)
    x_pos -= width_sep

    c.drawRightString(x_pos, y_pos, text_phone)
    c.linkURL(
        f"tel:512-936-3000",
        (x_pos - width_phone, y_pos - 2, x_pos, y_pos + 9),
        relative=0,
    )
    x_pos -= width_phone

    c.drawRightString(x_pos, y_pos, text_sep)
    x_pos -= width_sep

    c.drawRightString(x_pos, y_pos, text_intro)

    c.restoreState()


# --- Main PDF Generation Function ---
def create_trec_report(json_file_path, output_pdf):
    """
    Reads inspection.json and generates a PDF report
    using a TWO-PASS system to get the total page count.
    """

    # --- 1. Load JSON Data ---
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{json_file_path}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: The file '{json_file_path}' is not a valid JSON file.")
        return

    inspection_data = data.get("inspection")
    sections = inspection_data.get("sections")
    if not inspection_data or not sections:
        print("Error: 'inspection' or 'sections' key not found.")
        return

    # --- 2. DEFINE THE DRAWING LOGIC (will be run twice) ---
    def draw_content(c, total_pages=1, is_final_pass=False):
        """
        A function to draw all the content.
        If is_final_pass is True, it draws footers and form fields.
        If False, it's a dry run just for counting pages.
        """
        width, height = letter
        page_number = 1

        if is_final_pass:
            draw_page_template(c, page_number, total_pages)
            form = c.acroForm

        # --- Layout variables ---
        current_y = height - 75
        line_height = 18
        left_margin = 72
        bottom_margin = 75

        # --- Draw Headers ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin, current_y, "I")
        c.drawString(left_margin + 20, current_y, "NI")
        c.drawString(left_margin + 40, current_y, "NP")
        c.drawString(left_margin + 60, current_y, "D")
        current_y -= line_height * 1.5

        # --- Loop through JSON data ---
        for i, section in enumerate(sections, start=1):
            section_number = to_roman(i)
            section_name = section.get("name", "Unnamed Section").upper()

            # --- Handle Page Breaks ---
            if current_y < bottom_margin + line_height * 2:
                c.showPage()
                page_number += 1
                if is_final_pass:
                    draw_page_template(c, page_number, total_pages)
                    form = c.acroForm
                current_y = height - 75

                c.setFont("Helvetica-Bold", 10)
                c.drawString(left_margin, current_y, "I")
                c.drawString(left_margin + 20, current_y, "NI")
                c.drawString(left_margin + 40, current_y, "NP")
                c.drawString(left_margin + 60, current_y, "D")
                current_y -= line_height * 1.5

            # --- SECTION CENTERING ---
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(
                width / 2, current_y, f"{section_number}. {section_name}"
            )
            current_y -= line_height * 1.5

            line_items = section.get("lineItems", [])
            for j, item in enumerate(line_items, start=0):
                item_letter = chr(ord("A") + j)
                item_title = item.get("title", "Unnamed Line Item")
                item_id = item.get("id", f"{i}-{j}")

                if current_y < bottom_margin + line_height:
                    c.showPage()
                    page_number += 1
                    if is_final_pass:
                        draw_page_template(c, page_number, total_pages)
                        form = c.acroForm
                    current_y = height - 75

                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(left_margin, current_y, "I")
                    c.drawString(left_margin + 20, current_y, "NI")
                    c.drawString(left_margin + 40, current_y, "NP")
                    c.drawString(left_margin + 60, current_y, "D")
                    current_y -= line_height * 1.5

                # --- Apply I/NI/NP/D logic ---
                i_check, ni_check, np_check, d_check = False, False, False, False
                is_deficient = item.get("isDeficient", False)
                if is_deficient:
                    d_check = True
                else:
                    status = item.get("inspectionStatus")
                    if status == "I":
                        i_check = True
                    elif status == "NI":
                        ni_check = True
                    elif status == "NP":
                        np_check = True

                if is_final_pass:
                    # --- Draw the 4 Checkboxes (only on final pass) ---
                    cb_y = current_y - 2
                    form.checkbox(
                        name=f"{item_id}_I",
                        x=left_margin + 2,
                        y=cb_y,
                        checked=i_check,
                        buttonStyle="check",
                        size=10,
                    )
                    form.checkbox(
                        name=f"{item_id}_NI",
                        x=left_margin + 22,
                        y=cb_y,
                        checked=ni_check,
                        buttonStyle="check",
                        size=10,
                    )
                    form.checkbox(
                        name=f"{item_id}_NP",
                        x=left_margin + 42,
                        y=cb_y,
                        checked=np_check,
                        buttonStyle="check",
                        size=10,
                    )
                    form.checkbox(
                        name=f"{item_id}_D",
                        x=left_margin + 62,
                        y=cb_y,
                        checked=d_check,
                        buttonStyle="check",
                        size=10,
                    )

                # --- Draw Line Item Title ---
                c.setFont("Helvetica-Bold", 10)
                c.drawString(
                    left_margin + 90, current_y, f"{item_letter}. {item_title}"
                )
                current_y -= line_height * 1.2

                # --- Draw Comments (AND PHOTOS) ---
                comments = item.get("comments", [])
                if comments:
                    c.setFont("Helvetica", 9)
                    comment_indent = left_margin + 100

                    # --- LOGIC FIX: Loop comment by comment ---
                    for k, comment in enumerate(comments, start=1):
                        label = comment.get("label", "No comment text")
                        text_line = f"{k}. {label}"

                        # --- 1. Draw comment text ---
                        lines = simpleSplit(
                            text_line,
                            "Helvetica",
                            9,
                            width - comment_indent - left_margin,
                        )
                        required_height = len(lines) * (line_height * 0.8)

                        if current_y - required_height < bottom_margin:
                            c.showPage()
                            page_number += 1
                            if is_final_pass:
                                draw_page_template(c, page_number, total_pages)
                                form = c.acroForm
                            current_y = height - 75

                        for line in lines:
                            c.drawString(comment_indent, current_y, line)
                            current_y -= line_height * 0.8

                        # --- 2. Draw photos FOR THIS COMMENT ---
                        photos = comment.get("photos", [])
                        if photos:
                            current_y -= line_height * 0.5  # Padding
                            for photo in photos:
                                photo_url = photo.get("url")
                                if not photo_url:
                                    continue

                                try:
                                    # --- Add User-Agent header to mimic a browser ---
                                    # This *might* help with 403 errors, but no guarantee
                                    headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
                                    }
                                    req = Request(photo_url, headers=headers)

                                    with urlopen(req) as img_url:
                                        img_data = img_url.read()

                                    img_reader = ImageReader(BytesIO(img_data))
                                    img_width, img_height = img_reader.getSize()

                                    display_width = 2.5 * 72  # 2.5 inches wide
                                    aspect = img_height / float(img_width)
                                    display_height = display_width * aspect

                                    if current_y - display_height < bottom_margin:
                                        c.showPage()
                                        page_number += 1
                                        if is_final_pass:
                                            draw_page_template(
                                                c, page_number, total_pages
                                            )
                                            form = c.acroForm
                                        current_y = height - 75

                                    if is_final_pass:
                                        c.drawImage(
                                            img_reader,
                                            x=comment_indent,
                                            y=current_y - display_height,
                                            width=display_width,
                                            height=display_height,
                                            preserveAspectRatio=True,
                                        )
                                    current_y -= display_height + line_height * 0.5

                                except Exception as e:
                                    # Still print warning, but also draw placeholder
                                    print(
                                        f"Warning: Could not load image from {photo_url}. Error: {e}"
                                    )
                                    if current_y < bottom_margin:
                                        c.showPage()
                                        page_number += 1
                                        if is_final_pass:
                                            draw_page_template(
                                                c, page_number, total_pages
                                            )
                                            form = c.acroForm
                                        current_y = height - 75

                                    if is_final_pass:
                                        c.setFont("Helvetica-Oblique", 9)
                                        c.drawString(
                                            comment_indent,
                                            current_y,
                                            "[Image failed to load]",
                                        )
                                        current_y -= line_height

                            current_y -= line_height * 0.5  # Padding after photos

                current_y -= line_height  # Space after line item

        return page_number  # Return the total count

    # --- 3. PASS 1: DRY RUN (to get total page count) ---
    dummy_buffer = BytesIO()
    c_dry_run = canvas.Canvas(dummy_buffer, pagesize=letter)
    total_page_count = draw_content(c_dry_run, is_final_pass=False)
    c_dry_run.save()
    dummy_buffer.close()

    print(f"Report has a total of {total_page_count} pages.")

    # --- 4. PASS 2: FINAL RENDER (with correct page count) ---
    c_final = canvas.Canvas(output_pdf, pagesize=letter)
    draw_content(c_final, total_pages=total_page_count, is_final_pass=True)
    c_final.save()

    print(f"Successfully created fillable PDF: {output_pdf}")


# --- ---
# HOW TO RUN
# --- ---
# 1. Make sure 'inspection.json' is in the same folder.
# 2. Make sure you have 'reportlab' installed (pip install reportlab)
# 3. Run this script.
# 4. Open 'final_report.pdf' in Adobe Acrobat Reader.

json_filename = "inspection.json"
output_filename = "final_report.pdf"
create_trec_report(json_filename, output_filename)
