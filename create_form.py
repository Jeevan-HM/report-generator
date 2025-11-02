import asyncio  # For async
import json
import ssl
from datetime import datetime
from io import BytesIO

import aiohttp  # For async HTTP requests
import certifi
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader, simpleSplit
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
    c.drawString(
        72, height - 55, "I=Inspected   NI=Not Inspected   NP=Not Present   D=Deficient"
    )

    # --- FOOTER ---
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 60, f"Page {page_num} of {total_pages}")
    c.setFont("Helvetica", 9)
    c.drawString(72, 40, f"REI 7-6 ({datetime.now().strftime('%m/%d/%Y')})")

    y_pos = 40
    text_web = "www.trec.texas.gov"
    text_phone = "(512) 936-3000"
    text_intro = "Promulgated by the Texas Real Estate Commission • "

    width_web = c.stringWidth(text_web, "Helvetica", 9)
    width_phone = c.stringWidth(text_phone, "Helvetica", 9)

    x_pos = width - 72
    c.drawRightString(x_pos, y_pos, text_web)
    c.linkURL(
        f"https://{text_web}",
        (x_pos - width_web, y_pos - 2, x_pos, y_pos + 9),
        relative=0,
    )
    x_pos -= width_web + c.stringWidth(" • ", "Helvetica", 9)

    c.drawRightString(x_pos, y_pos, text_phone)
    c.linkURL(
        f"tel:512-936-3000",
        (x_pos - width_phone, y_pos - 2, x_pos, y_pos + 9),
        relative=0,
    )
    x_pos -= width_phone + c.stringWidth(" • ", "Helvetica", 9)

    c.drawRightString(x_pos, y_pos, text_intro)
    c.restoreState()


# --- STEP 1: ASYNC IMAGE DOWNLOADING ---


async def fetch_image(session, url):
    """Fetches a single image URL, returns None on failure."""
    if not url:
        return None, None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return url, await response.read()
            else:
                print(f"Warning: Failed to fetch {url}. Status: {response.status}")
                return url, None
    except Exception as e:
        print(f"Warning: Could not load image from {url}. Error: {e}")
        return url, None


async def download_all_images(sections):
    """Finds and downloads all unique image URLs concurrently."""
    urls = set()
    for section in sections:
        for item in section.get("lineItems", []):
            for comment in item.get("comments", []):
                for photo in comment.get("photos", []):
                    if photo.get("url"):
                        urls.add(photo.get("url"))

    print(f"Found {len(urls)} unique images to download.")
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_image(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    print("All image downloads attempted.")
    image_cache = {url: data for url, data in results if data}
    return image_cache


# --- STEP 2: PDF DRAWING (now uses the cache) ---


def draw_content(c, sections, image_cache, total_pages=1, is_final_pass=False):
    """
    A function to draw all the content.
    Reads images from the pre-filled 'image_cache'.
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

    # --- NO LONGER NEED I/NI/NP/D HEADERS ---
    # c.setFont('Helvetica-Bold', 10)
    # ...

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

        # --- SECTION CENTERING ---
        c.setFont("Helvetica-Bold", 11)  # Font Fix
        c.drawCentredString(width / 2, current_y, f"{section_number}. {section_name}")
        current_y -= line_height * 1.5

        line_items = section.get("lineItems", [])
        for j, item in enumerate(line_items, start=0):
            item_letter = chr(ord("A") + j)
            item_title = item.get("title", "Unnamed Line Item")

            if current_y < bottom_margin + line_height:
                c.showPage()
                page_number += 1
                if is_final_pass:
                    draw_page_template(c, page_number, total_pages)
                    form = c.acroForm
                current_y = height - 75

            # --- Apply I/NI/NP/D logic FROM PARENT ITEM ---
            # We save this to apply to the comments below
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

            # --- Draw Line Item Title (No Checkboxes) ---
            c.setFont("Helvetica-Bold", 10)  # Font Fix
            c.drawString(left_margin, current_y, f"{item_letter}. {item_title}")
            current_y -= line_height * 1.2

            # --- Draw Comments (AND PHOTOS) ---
            comments = item.get("comments", [])
            if comments:
                comment_indent = left_margin + 20  # Indent for comments
                text_indent = comment_indent + 80  # Indent for text, after checkboxes

                for k, comment in enumerate(comments, start=1):
                    comment_id = comment.get("id", f"{i}-{j}-{k}")
                    label = comment.get("label", "No comment text")
                    text_line = f"{k}. {label}"

                    # --- 1. Calculate height for text ---
                    lines = simpleSplit(
                        text_line, "Helvetica", 9, width - text_indent - left_margin
                    )
                    required_height = len(lines) * (line_height * 0.8)

                    # --- 2. Calculate height for photos ---
                    photos = comment.get("photos", [])
                    if photos:
                        required_height += line_height * 0.5  # Padding
                        for photo in photos:
                            img_data = image_cache.get(photo.get("url"))
                            if img_data:
                                try:
                                    img_reader = ImageReader(BytesIO(img_data))
                                    img_width, img_height = img_reader.getSize()
                                    display_width = 2.5 * 72  # 2.5 inches wide
                                    display_height = display_width * (
                                        img_height / float(img_width)
                                    )
                                    required_height += (
                                        display_height + line_height * 0.5
                                    )
                                except:
                                    required_height += line_height  # Placeholder height
                            else:
                                required_height += line_height  # Placeholder height

                    # --- 3. Check if the whole block fits ---
                    if current_y - required_height < bottom_margin:
                        c.showPage()
                        page_number += 1
                        if is_final_pass:
                            draw_page_template(c, page_number, total_pages)
                            form = c.acroForm
                        current_y = height - 75

                    # --- 4. Draw the content ---

                    # --- DRAW 4 CHECKBOXES FOR COMMENT ---
                    # Uses the status from the parent line item
                    if is_final_pass:
                        cb_y = current_y - 2
                        form.checkbox(
                            name=f"{comment_id}_I",
                            x=comment_indent + 2,
                            y=cb_y,
                            checked=i_check,
                            buttonStyle="check",
                            size=10,
                        )
                        form.checkbox(
                            name=f"{comment_id}_NI",
                            x=comment_indent + 22,
                            y=cb_y,
                            checked=ni_check,
                            buttonStyle="check",
                            size=10,
                        )
                        form.checkbox(
                            name=f"{comment_id}_NP",
                            x=comment_indent + 42,
                            y=cb_y,
                            checked=np_check,
                            buttonStyle="check",
                            size=10,
                        )
                        form.checkbox(
                            name=f"{comment_id}_D",
                            x=comment_indent + 62,
                            y=cb_y,
                            checked=d_check,
                            buttonStyle="check",
                            size=10,
                        )

                    c.setFont("Helvetica", 9)  # Font Fix
                    for line in lines:
                        c.drawString(text_indent, current_y, line)
                        current_y -= line_height * 0.8

                    if photos:
                        current_y -= line_height * 0.5  # Padding
                        for photo in photos:
                            img_data = image_cache.get(photo.get("url"))
                            if img_data:
                                try:
                                    img_reader = ImageReader(BytesIO(img_data))
                                    img_width, img_height = img_reader.getSize()
                                    display_width = 2.5 * 72
                                    display_height = display_width * (
                                        img_height / float(img_width)
                                    )

                                    if is_final_pass:
                                        c.drawImage(
                                            img_reader,
                                            x=text_indent,  # Align with text
                                            y=current_y - display_height,
                                            width=display_width,
                                            height=display_height,
                                            preserveAspectRatio=True,
                                        )
                                    current_y -= display_height + line_height * 0.5
                                except Exception as e:
                                    print(
                                        f"Warning: Could not draw image {photo.get('url')}. Error: {e}"
                                    )
                            else:
                                if is_final_pass:
                                    c.setFont("Helvetica-Oblique", 9)  # Font Fix
                                    c.drawString(
                                        text_indent,
                                        current_y,
                                        "[Image failed to load or was forbidden]",
                                    )
                                    current_y -= line_height
                        current_y -= line_height * 0.5

            current_y -= line_height  # Space after line item

    return page_number  # Return the total count


# --- Main PDF Generation Function ---
def create_trec_report(json_file_path, output_pdf):
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

    sections = data.get("inspection", {}).get("sections")
    if not sections:
        print("Error: 'inspection' or 'sections' key not found.")
        return

    # --- 2. STEP 1: Download all images concurrently ---
    print("--- Starting concurrent image download ---")
    image_cache = asyncio.run(download_all_images(sections))
    print(f"--- Successfully cached {len(image_cache)} images ---")

    # --- 3. PASS 1 (Dry Run) ---
    print("--- Starting PDF Pass 1 (Counting pages) ---")
    dummy_buffer = BytesIO()
    c_dry_run = canvas.Canvas(dummy_buffer, pagesize=letter)
    total_page_count = draw_content(
        c_dry_run, sections, image_cache, is_final_pass=False
    )
    c_dry_run.save()
    dummy_buffer.close()

    print(f"Report has a total of {total_page_count} pages.")

    # --- 4. PASS 2 (Final Render) ---
    print("--- Starting PDF Pass 2 (Drawing final file) ---")
    c_final = canvas.Canvas(output_pdf, pagesize=letter)
    draw_content(
        c_final, sections, image_cache, total_pages=total_page_count, is_final_pass=True
    )
    c_final.save()

    print(f"Successfully created fillable PDF: {output_pdf}")


# --- ---
# HOW TO RUN
# --- ---
# 1. Make sure 'inspection.json' is in the same folder.
# 2. Install required libraries: pip install reportlab aiohttp certifi
# 3. Run this script.
# 4. Open 'final_report.pdf' in Adobe Acrobat Reader.

json_filename = "inspection.json"
output_filename = "final_report.pdf"
create_trec_report(json_filename, output_filename)
