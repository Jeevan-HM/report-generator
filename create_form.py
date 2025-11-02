import asyncio
import glob
import hashlib
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Optional

import aiohttp
from PIL import Image

# --- CONFIGURATION ---
TEMPLATE_FILE = "latex/report.tex"
IMAGE_DIR = "latex/images"
CONTENT_MARKER = "% --- PYTHON CONTENT MARKER ---"

# Thread pool for CPU-bound operations
THREAD_POOL = ThreadPoolExecutor(max_workers=4)

# --- 1. LaTeX Helper Functions ---


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


def escape_latex(text):
    """Escapes special LaTeX characters in a string."""
    if not isinstance(text, str):
        return ""
    text = text.replace("\\", r"\textbackslash{}")
    text = text.replace("_", r"\_")
    text = text.replace("%", r"\%")
    text = text.replace("&", r"\&")
    text = text.replace("#", r"\#")
    text = text.replace("$", r"\$")
    text = text.replace("{", r"\{")
    text = text.replace("}", r"\}")
    text = text.replace("^", r"\^{}")
    text = text.replace("~", r"\~{}")
    return text


def get_checkboxes(status, is_deficient):
    """Returns the LaTeX string for the 4 checkboxes."""
    i_box = r"$\square$"
    ni_box = r"$\square$"
    np_box = r"$\square$"
    d_box = r"$\square$"

    if is_deficient:
        d_box = r"$\boxtimes$"
    elif status == "I":
        i_box = r"$\boxtimes$"
    elif status == "NI":
        ni_box = r"$\boxtimes$"
    elif status == "NP":
        np_box = r"$\boxtimes$"

    return f"{i_box} & {ni_box} & {np_box} & {d_box}"


# Global cache for downloaded images (URL -> filepath)
IMAGE_CACHE = {}
CACHE_LOCK = asyncio.Lock()


async def download_image_async(
    session: aiohttp.ClientSession, url: str
) -> Optional[str]:
    """
    Asynchronously downloads an image with aggressive optimization for fast downloads and small file size.
    Converts all images to JPEG with reduced quality for faster processing.
    """
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    filename_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    ext = ".jpg"
    filepath = os.path.join(IMAGE_DIR, filename_hash + ext)

    # Return if already cached
    if os.path.exists(filepath):
        return filepath

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"⚠️  Failed to download {url} (Status: {response.status})")
                return None

            image_data = await response.read()

            # Use Pillow to process the image
            try:
                img = Image.open(BytesIO(image_data))

                # Aggressive resize to reduce file size and speed up processing
                # Max dimensions for report images (maintains aspect ratio)
                max_width = 800  # Reduced from 1200
                max_height = 800  # Reduced from 1200

                if img.width > max_width or img.height > max_height:
                    # Use BILINEAR for faster resizing (vs LANCZOS)
                    img.thumbnail((max_width, max_height), Image.Resampling.BILINEAR)

                # Convert to RGB if necessary (all images become JPEG)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Save as JPEG with lower quality for faster processing and smaller size
                # Quality 70 is a good balance between size and visual quality
                img.save(filepath, "JPEG", quality=70, optimize=False)
                return filepath

            except Exception:
                # If image processing fails, save raw data
                with open(filepath, "wb") as f:
                    f.write(image_data)
                return filepath

        return filepath

    except asyncio.TimeoutError:
        print(f"⏱️  Timeout downloading {url}")
        return None
    except Exception as e:
        print(f"⚠️  Failed to download {url}. Error: {e}")
        return None


async def download_and_cache_image(session: aiohttp.ClientSession, url: str):
    """Downloads an image and caches it in the global IMAGE_CACHE."""
    filepath = await download_image_async(session, url)
    async with CACHE_LOCK:
        IMAGE_CACHE[url] = filepath


def get_cached_image(url: str) -> Optional[str]:
    """Gets an image from the cache (blocking call for sync context)."""
    return IMAGE_CACHE.get(url)


# --- 2. Main Content Generation ---


def generate_trec_form_page(data):
    """
    Generates the TREC form page (standard first page with table).
    """
    inspection = data.get("inspection", {})
    client_info = inspection.get("clientInfo", {})
    address = inspection.get("address", {})
    inspector = inspection.get("inspector", {})
    schedule = inspection.get("schedule", {})

    # Format the inspection date
    inspection_date = format_timestamp(schedule.get("date"))

    # Get client name (buyer/seller)
    client_name = escape_latex(client_info.get("name", ""))

    # Get property address
    full_address = escape_latex(address.get("fullAddress", ""))

    # Get inspector information
    inspector_name = escape_latex(inspector.get("name", ""))

    trec_page = []

    # No header/footer on this page
    trec_page.append(r"\thispagestyle{empty}")
    trec_page.append(r"")

    # TREC form table
    trec_page.append(r"\noindent")
    trec_page.append(r"\begin{tabular}{|p{0.45\textwidth}|p{0.45\textwidth}|}")
    trec_page.append(r"\hline")
    trec_page.append(r"\textbf{Buyer Name} & \textbf{Date of Inspection} \\")
    trec_page.append(client_name + r" & " + inspection_date + r" \\")
    trec_page.append(r"\hline")
    trec_page.append(
        r"\multicolumn{2}{|p{0.93\textwidth}|}{\textbf{Address of Inspected Property}} \\"
    )
    trec_page.append(r"\multicolumn{2}{|p{0.93\textwidth}|}{" + full_address + r"} \\")
    trec_page.append(r"\hline")
    trec_page.append(r"\textbf{Name of Inspector} & \textbf{TREC License \#} \\")
    trec_page.append(inspector_name + r" &  \\")
    trec_page.append(r"\hline")
    trec_page.append(
        r"\textbf{Name of Sponsor (if applicable)} & \textbf{TREC License \#} \\"
    )
    trec_page.append(r" &  \\")
    trec_page.append(r"\hline")
    trec_page.append(r"\end{tabular}")
    trec_page.append(r"")
    trec_page.append(r"\vspace{1em}")
    trec_page.append(r"")
    trec_page.append(r"\begin{center}")
    trec_page.append(r"\textbf{\Large PROPERTY INSPECTION REPORT FORM}")
    trec_page.append(r"\end{center}")
    trec_page.append(r"")
    trec_page.append(r"\vspace{1em}")
    trec_page.append(r"")

    # PURPOSE OF INSPECTION section
    trec_page.append(r"\subsection*{PURPOSE OF INSPECTION}")
    trec_page.append(
        r"A real estate inspection is a visual survey of a structure and a basic performance evaluation of the systems and components of a building. It provides information regarding the general condition of a residence at the time the inspection was conducted."
    )
    trec_page.append(r"")
    trec_page.append(
        r"It is important that you carefully read ALL of this information. Ask the inspector to clarify any items or comments that are unclear."
    )
    trec_page.append(r"")

    # RESPONSIBILITY sections
    trec_page.append(r"\subsection*{RESPONSIBILITY OF THE INSPECTOR}")
    trec_page.append(
        r"This inspection is governed by the Texas Real Estate Commission (TREC) Standards of Practice (SOPs), which dictates the minimum requirements for a real estate inspection."
    )
    trec_page.append(r"")
    trec_page.append(r"\noindent\textbf{The inspector IS required to:}")
    trec_page.append(r"\begin{itemize}")
    trec_page.append(r"\setlength{\itemsep}{0pt}")
    trec_page.append(r"\setlength{\parskip}{0pt}")
    trec_page.append(
        r"\item use this Property Inspection Report form for the inspection;"
    )
    trec_page.append(
        r"\item inspect only those components and conditions that are present, visible, and accessible at the time of the inspection;"
    )
    trec_page.append(
        r"\item indicate whether each item was inspected, not inspected, or not present;"
    )
    trec_page.append(
        r"\item indicate an item as Deficient (D) if a condition exists that adversely and materially affects the performance of a system or component OR constitutes a hazard to life, limb or property as specified by the SOPs; and"
    )
    trec_page.append(
        r"\item explain the inspector's findings in the corresponding section in the body of the report form."
    )
    trec_page.append(r"\end{itemize}")
    trec_page.append(r"")
    trec_page.append(r"\noindent\textbf{The inspector IS NOT required to:}")
    trec_page.append(r"\begin{itemize}")
    trec_page.append(r"\setlength{\itemsep}{0pt}")
    trec_page.append(r"\setlength{\parskip}{0pt}")
    trec_page.append(r"\item identify all potential hazards;")
    trec_page.append(
        r"\item turn on decommissioned equipment, systems, utilities, or apply an open flame or light a pilot to operate any appliance;"
    )
    trec_page.append(r"\item climb over obstacles, move furnishings or stored items;")
    trec_page.append(
        r"\item prioritize or emphasize the importance of one deficiency over another;"
    )
    trec_page.append(
        r"\item provide follow-up services to verify that proper repairs have been made; or"
    )
    trec_page.append(
        r"\item inspect system or component listed under the optional section of the SOPs (22 TAC 535.233)."
    )
    trec_page.append(r"\end{itemize}")
    trec_page.append(r"")

    trec_page.append(r"\subsection*{RESPONSIBILITY OF THE CLIENT}")
    trec_page.append(
        r"While items identified as Deficient (D) in an inspection report DO NOT obligate any party to make repairs or take other actions, in the event that any further evaluations are needed, it is the responsibility of the client to obtain further evaluations and/or cost estimates from qualified service professionals regarding any items reported as Deficient (D). It is recommended that any further evaluations and/or cost estimates take place prior to the expiration of any contractual time limitations, such as option periods."
    )
    trec_page.append(r"")
    trec_page.append(
        r"\noindent\textbf{Please Note:} Evaluations performed by service professionals in response to items reported as Deficient (D) on the report may lead to the discovery of additional deficiencies that were not present, visible, or accessible at the time of the inspection. Any repairs made after the date of the inspection may render information contained in this report obsolete or invalid."
    )
    trec_page.append(r"")
    trec_page.append(r"\clearpage")
    trec_page.append(r"")

    return "\n".join(trec_page)


def generate_title_page(data):
    """
    Generates a professional title page with property information and images.
    """
    inspection = data.get("inspection", {})
    client_info = inspection.get("clientInfo", {})
    address = inspection.get("address", {})
    inspector = inspection.get("inspector", {})
    schedule = inspection.get("schedule", {})
    booking_data = inspection.get("bookingFormData", {})
    property_info = booking_data.get("propertyInfo", {})

    # Format the inspection date
    inspection_date = format_timestamp(schedule.get("date"))

    # Get client name (buyer/seller)
    client_name = escape_latex(client_info.get("name", ""))

    # Get property address
    full_address = escape_latex(address.get("fullAddress", ""))

    # Get inspector information
    inspector_name = escape_latex(inspector.get("name", ""))
    inspector_email = escape_latex(inspector.get("email", ""))

    # Get agent information if available
    agents = inspection.get("agents", [])
    agent_name = ""
    agent_company = ""
    if agents:
        primary_agent = agents[0].get("agent", {})
        agent_name = escape_latex(primary_agent.get("name", ""))
        agent_company = escape_latex(primary_agent.get("company", {}).get("name", ""))

    # Building details
    square_footage = property_info.get("squareFootage", 0)

    title = []

    # No header/footer on title page
    title.append(r"\thispagestyle{empty}")
    title.append(r"")

    # Title page content
    title.append(r"\begin{center}")
    title.append(r"\vspace*{2cm}")
    title.append(r"\textbf{\Huge PROPERTY INSPECTION REPORT}")
    title.append(r"\vspace{1cm}")
    title.append(r"")
    title.append(r"\hrule")
    title.append(r"\vspace{0.5cm}")
    title.append(r"")
    title.append(r"\textbf{\Large Prepared For:}")
    title.append(r"")
    title.append(r"\textbf{\large " + client_name + "}")
    title.append(r"\vspace{0.5cm}")
    title.append(r"")
    title.append(r"\textbf{\Large Concerning:}")
    title.append(r"")
    title.append(r"\textbf{\large " + full_address + "}")
    title.append(r"\vspace{0.5cm}")
    title.append(r"")
    title.append(r"\hrule")
    title.append(r"\vspace{1cm}")
    title.append(r"")
    title.append(r"\textbf{\Large By:}")
    title.append(r"")
    title.append(r"\textbf{\large " + inspector_name + "}")

    if inspector_email:
        title.append(r"\vspace{0.3cm}")
        title.append(r"")
        title.append(r"\textbf{Email:} " + inspector_email)

    title.append(r"\vspace{1cm}")
    title.append(r"")
    title.append(r"\textbf{\Large Date of Inspection:}")
    title.append(r"")
    title.append(r"\textbf{\large " + inspection_date + "}")

    if agent_name:
        title.append(r"\vspace{1cm}")
        title.append(r"")
        title.append(r"\textbf{Real Estate Agent:} " + agent_name)
        if agent_company:
            title.append(r"")
            title.append(r"\textbf{Company:} " + agent_company)

    if square_footage > 0:
        title.append(r"\vspace{0.5cm}")
        title.append(r"")
        title.append(
            r"\textbf{Approximate Square Footage:} " + f"{square_footage:,} sq ft"
        )

    title.append(r"\vspace{1.5cm}")
    title.append(r"")

    # Add the images side by side
    # These images should be in the latex/ folder (not latex/images/)
    title.append(r"\begin{minipage}{0.48\textwidth}")
    title.append(r"\centering")
    title.append(
        r"\includegraphics[width=\textwidth, height=2.5in, keepaspectratio]{obstruction.png}"
    )
    title.append(r"\textit{\small Obstructed area example}")
    title.append(r"\end{minipage}")
    title.append(r"\hfill")
    title.append(r"\begin{minipage}{0.48\textwidth}")
    title.append(r"\centering")
    title.append(
        r"\includegraphics[width=\textwidth, height=2.5in, keepaspectratio]{scope.png}"
    )
    title.append(r"\textit{\small \\ Scope and Limitations}")
    title.append(r"\end{minipage}")

    title.append(r"\end{center}")
    title.append(r"\clearpage")
    title.append(r"")

    return "\n".join(title)


def generate_latex_body(data):
    """
    Loops through the JSON data and builds the LaTeX string for the report body.
    """
    body = []

    # Add the title page first (page 1)
    body.append(generate_title_page(data))

    # Add the TREC form page (page 2)
    body.append(generate_trec_form_page(data))

    sections = data.get("inspection", {}).get("sections", [])

    comment_col = r"p{0.65\textwidth}"

    # Add header/footer setup before the inspection sections start
    # This ensures it starts from section 1 (which is page 3 after title and TREC pages)
    header_setup = []
    header_setup.append(
        r"% Start the fancy header/footer from section 1 onwards (page 3)"
    )
    header_setup.append(r"\pagestyle{fancy}")
    header_setup.append(r"\fancyhf{}")
    header_setup.append(r"")
    header_setup.append(r"\fancyhead[L]{%")
    header_setup.append(
        r"    Report Identification: \TextField[name=reportid, width=3in, height=12pt, bordercolor={}, backgroundcolor={}, borderstyle=U, borderwidth=1]{} \\"
    )
    header_setup.append(
        r"    \textbf{I=Inspected \quad NI=Not Inspected \quad NP=Not Present \quad D=Deficient}"
    )
    header_setup.append(r"}")
    header_setup.append(r"\renewcommand{\headrulewidth}{0pt}")
    header_setup.append(r"")
    header_setup.append(r"\fancyfoot[L]{REI 7-6 (\mmddyyyydate\today)}")
    header_setup.append(r"\fancyfoot[C]{}")
    header_setup.append(r"\fancyfoot[R]{%")
    header_setup.append(
        r"    Promulgated by the Texas Real Estate Commission \textbullet{}"
    )
    header_setup.append(r"    \href{tel:512-936-3000}{(512) 936-3000} \textbullet{}")
    header_setup.append(r"    \href{https://www.trec.texas.gov}{www.trec.texas.gov}")
    header_setup.append(r"}")
    header_setup.append(r"\renewcommand{\footrule}{%")
    header_setup.append(r"    \vspace{5pt}")
    header_setup.append(r"    \begin{center}")
    header_setup.append(r"        Page \thepage\ of \pageref{LastPage}")
    header_setup.append(r"    \end{center}")
    header_setup.append(r"    \vspace{2pt}")
    header_setup.append(r"    \hrulefill")
    header_setup.append(r"    \vspace{2pt}")
    header_setup.append(r"}")
    header_setup.append(r"")

    body.append("\n".join(header_setup))

    for i, section in enumerate(sections, start=1):
        section_name = escape_latex(section.get("name", "").upper())
        section_num = to_roman(i)

        body.append(r"\section*{\centering " + f"{section_num}. {section_name}" + "}\n")

        line_items = section.get("lineItems", [])
        for j, item in enumerate(line_items, start=0):
            item_letter = chr(ord("A") + j)
            item_title = escape_latex(item.get("title", ""))

            body.append(r"\subsection*{" + f"{item_letter}. {item_title}" + "}\n")

            status = item.get("inspectionStatus")
            is_deficient = item.get("isDeficient", False)
            checkbox_str = get_checkboxes(status, is_deficient)

            comments = item.get("comments", [])

            # Scenario 1: No comment AND inspection status is not null → Table with "No comment"
            if not comments and status is not None:
                body.append(r"\begin{longtable}{c c c c p{0.65\textwidth}}")
                body.append(
                    r"\textbf{I} & \textbf{NI} & \textbf{NP} & \textbf{D} & \textbf{Comments} \\ \hline \endhead"
                )
                body.append(f"{checkbox_str} & No comment \\\\")
                body.append(r"\end{longtable}" + "\n")
            # Scenario 2: There is comment BUT inspection status is null → Just the value, no table
            elif comments and status is None:
                for comment in comments:
                    comment_value = comment.get("value")
                    if comment_value:
                        value_latex = escape_latex(str(comment_value))
                        body.append(value_latex + r"\\" + "\n")
                body.append(r"\vspace{1em}" + "\n")
            # Scenario 3: No comment AND no inspection status → Just mention "No comment"
            elif not comments and status is None:
                body.append("No comment" + r"\\" + "\n")
                body.append(r"\vspace{1em}" + "\n")
            # Scenario 4: Has comments AND has inspection status → Full table
            elif comments:
                body.append(r"\begin{longtable}{c c c c " + comment_col + "}")
                # Add a header that will repeat if the table spans pages
                body.append(
                    r"\textbf{I} & \textbf{NI} & \textbf{NP} & \textbf{D} & \textbf{Comments} \\ \hline \endhead"
                )

                for k, comment in enumerate(comments, start=1):
                    label_text = f"{k}. {comment.get('label', '')}"
                    label = r"\textbf{" + escape_latex(label_text) + "}"
                    body.append(f"{checkbox_str} & {label} \\\\")

                    photos = comment.get("photos", [])
                    if photos:
                        valid_image_data = []
                        for photo in photos:
                            url = photo.get("url")
                            if url:
                                img_path = get_cached_image(url)
                                if img_path:
                                    img_filename = os.path.basename(img_path)
                                    relative_img_path = os.path.join(
                                        "images", img_filename
                                    ).replace("\\", "/")
                                    caption = photo.get("caption", "")
                                    valid_image_data.append({
                                        "path": relative_img_path,
                                        "caption": caption
                                    })
                                else:
                                    print(
                                        f"⚠️  Image not yet cached, skipping: {url[:60]}..."
                                    )

                        if valid_image_data:
                            num_photos = len(valid_image_data)

                            # Calculate image width to fit within comment column
                            if num_photos == 1:
                                img_width = "3.0in"
                                max_height = "2.5in"
                            elif num_photos == 2:
                                img_width = "1.8in"
                                max_height = "2.0in"
                            elif num_photos == 3:
                                img_width = "1.3in"
                                max_height = "1.8in"
                            else:  # 4 or more
                                img_width = "1.0in"
                                max_height = "1.5in"

                            # Build images with captions in a row
                            image_parts = []
                            for img_data in valid_image_data:
                                img_path = img_data["path"]
                                caption = img_data["caption"]
                                
                                # Create image with caption below
                                img_with_caption = (
                                    r"\begin{minipage}[t]{" + img_width + r"}" + "\n"
                                    r"                                \centering" + "\n"
                                    r"                                \includegraphics[width=" + img_width + 
                                    ", height=" + max_height + 
                                    r", keepaspectratio]{" + img_path + r"}"
                                )
                                
                                # Add caption if it exists
                                if caption:
                                    caption_latex = escape_latex(caption)
                                    img_with_caption += (
                                        "\n" + r"                                \vspace{0.1cm} \\" + "\n"
                                        r"                                {\small\itshape " + caption_latex + r"}"
                                    )
                                
                                img_with_caption += "\n" + r"                                \end{minipage}"
                                image_parts.append(img_with_caption)

                            # Join images with spacing
                            all_images = r" \hspace{0.2cm} ".join(image_parts)

                            # Add images to the comment column
                            body.append(
                                r"& & & & \parbox{\linewidth}{\centering "
                                + all_images
                                + r"} \\[0.3em]"
                            )

                    # If the comment has a 'value', display it in a new row
                    comment_value = comment.get("value")
                    if comment_value:
                        value_latex = escape_latex(str(comment_value))
                        # Span the comment column only
                        body.append(
                            r"\multicolumn{4}{c}{} & " + value_latex + r" \\[0.5em]"
                        )

                body.append(r"\end{longtable}" + "\n")

            body.append(r"\vspace{1em}")

        body.append(r"\clearpage")

    return "\n".join(body)


# --- 3. Main Execution ---


async def collect_all_image_urls(data) -> list[str]:
    """Collects all unique image URLs from the JSON data."""
    urls = set()
    sections = data.get("inspection", {}).get("sections", [])

    for section in sections:
        # Collect section-level media (e.g., obstruction.png, scope.png)
        section_media = section.get("media", [])
        for media_item in section_media:
            url = media_item.get("url")
            # Only add if it's a valid URL (starts with http:// or https://)
            if url and url.startswith(("http://", "https://")):
                urls.add(url)

        line_items = section.get("lineItems", [])
        for item in line_items:
            comments = item.get("comments", [])
            for comment in comments:
                photos = comment.get("photos", [])
                for photo in photos:
                    url = photo.get("url")
                    if url and url.startswith(("http://", "https://")):
                        urls.add(url)

    return list(urls)


async def download_images_background(urls: list[str]):
    """Downloads all images in the background concurrently with aggressive optimization."""
    if not urls:
        return

    print(f"\n🚀 Starting fast download of {len(urls)} images...")

    # Aggressive timeout settings for faster failure and retry
    timeout = aiohttp.ClientTimeout(total=20, connect=5, sock_read=10)
    # Increase concurrent connections from 10 to 30 for faster parallel downloads
    connector = aiohttp.TCPConnector(
        limit=30, force_close=True, enable_cleanup_closed=True
    )

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [download_and_cache_image(session, url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

    successful = sum(1 for path in IMAGE_CACHE.values() if path is not None)
    print(f"✅ Downloaded {successful}/{len(urls)} images successfully\n")


def format_timestamp(timestamp_ms):
    """Converts millisecond timestamp to formatted date string."""
    if not timestamp_ms:
        return ""
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%m/%d/%Y %I:%M%p")


def populate_header_data(template_content, data):
    """Populates the header information in the template."""
    inspection = data.get("inspection", {})

    # Extract data
    client_name = escape_latex(inspection.get("clientInfo", {}).get("name", ""))
    inspection_date = format_timestamp(inspection.get("schedule", {}).get("date"))
    property_address = escape_latex(
        inspection.get("address", {}).get("fullAddress", "")
    )
    inspector_name = escape_latex(inspection.get("inspector", {}).get("name", ""))
    trec_license = ""  # Not in JSON
    sponsor_name = ""  # Not in JSON
    sponsor_license = ""  # Not in JSON

    # Additional info
    occupancy = "Occupied"  # Default, could be added to JSON
    attendance = "Buyer"  # Could extract from clientInfo.userType
    temperature = "70 to 80"  # Not in JSON
    building_type = "Single Family"  # Not in JSON
    weather = "Clear"  # Not in JSON
    orientation = "North"  # Not in JSON
    inaccessible = ""  # Not in JSON
    additional_info = ""  # Can add custom text here

    # Replace placeholders
    replacements = {
        "% PYTHON_BUYER_NAME %": client_name,
        "% PYTHON_INSPECTION_DATE %": inspection_date,
        "% PYTHON_PROPERTY_ADDRESS %": property_address,
        "% PYTHON_INSPECTOR_NAME %": inspector_name,
        "% PYTHON_TREC_LICENSE %": trec_license,
        "% PYTHON_SPONSOR_NAME %": sponsor_name,
        "% PYTHON_SPONSOR_LICENSE %": sponsor_license,
        "% PYTHON_OCCUPANCY %": occupancy,
        "% PYTHON_ATTENDANCE %": attendance,
        "% PYTHON_TEMPERATURE %": temperature,
        "% PYTHON_BUILDING_TYPE %": building_type,
        "% PYTHON_WEATHER %": weather,
        "% PYTHON_ORIENTATION %": orientation,
        "% PYTHON_INACCESSIBLE %": inaccessible,
        "% PYTHON_ADDITIONAL_INFO %": additional_info,
    }

    for placeholder, value in replacements.items():
        template_content = template_content.replace(placeholder, value)

    return template_content


def compress_pdf(input_pdf: str) -> str:
    """
    Compress PDF using Ghostscript for faster downloads.
    Returns path to compressed PDF, or original if compression fails.
    """
    output_pdf = input_pdf.replace(".pdf", "_compressed.pdf")

    try:
        # Try using Ghostscript for compression
        # Settings: screen = lowest quality (72dpi), ebook = medium (150dpi), printer = high (300dpi)
        gs_command = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",  # Good balance of quality and size
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-dDetectDuplicateImages=true",
            "-dCompressFonts=true",
            "-dDownsampleColorImages=true",
            "-dColorImageResolution=150",
            "-dDownsampleGrayImages=true",
            "-dGrayImageResolution=150",
            "-dDownsampleMonoImages=true",
            "-dMonoImageResolution=150",
            f"-sOutputFile={output_pdf}",
            input_pdf,
        ]

        result = subprocess.run(
            gs_command,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and os.path.exists(output_pdf):
            # Replace original with compressed version
            os.remove(input_pdf)
            os.rename(output_pdf, input_pdf)
            return input_pdf
        else:
            print(
                f"⚠️  Ghostscript compression failed: {result.stderr[:100] if result.stderr else 'Unknown error'}"
            )
            # Try alternative method with PyPDF2
            return compress_pdf_pypdf(input_pdf)

    except FileNotFoundError:
        print("⚠️  Ghostscript not found, trying alternative compression...")
        return compress_pdf_pypdf(input_pdf)
    except subprocess.TimeoutExpired:
        print("⚠️  PDF compression timed out")
        return input_pdf
    except Exception as e:
        print(f"⚠️  PDF compression error: {e}")
        return input_pdf


def compress_pdf_pypdf(input_pdf: str) -> str:
    """
    Alternative PDF compression using PyPDF2 (lighter compression).
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)

        # Write to temporary file
        temp_pdf = input_pdf.replace(".pdf", "_temp.pdf")
        with open(temp_pdf, "wb") as output_file:
            writer.write(output_file)

        # Replace original with compressed
        if os.path.exists(temp_pdf):
            os.remove(input_pdf)
            os.rename(temp_pdf, input_pdf)
            print("✓ Used PyPDF2 compression (lighter)")

        return input_pdf
    except ImportError:
        print("⚠️  PyPDF2 not available, skipping compression")
        return input_pdf
    except Exception as e:
        print(f"⚠️  PyPDF2 compression error: {e}")
        return input_pdf


async def generate_pdf_from_json(json_data: dict, output_dir: str = "latex") -> tuple[str, str, str]:
    """
    Optimized function to generate PDF from JSON data.
    Returns the path to the generated PDF file.
    """
    global IMAGE_CACHE, IMAGE_DIR
    IMAGE_CACHE = {}  # Reset cache for each generation

    # Update IMAGE_DIR to be relative to the output directory
    IMAGE_DIR = os.path.join(output_dir, "images")

    final_tex_file = os.path.join(output_dir, "final_report.tex")
    final_pdf_file = os.path.join(output_dir, "final_report.pdf")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Copy static images (obstruction.png and scope.png) to output directory
    static_images = ["obstruction.png", "scope.png"]
    for img in static_images:
        src_path = os.path.join("latex", img)
        if os.path.exists(src_path):
            dst_path = os.path.join(output_dir, img)
            try:
                shutil.copy2(src_path, dst_path)
                print(f"✓ Copied static image: {img}")
            except Exception as e:
                print(f"⚠️  Failed to copy {img}: {e}")

    # Load template
    template_file_path = (
        TEMPLATE_FILE
        if os.path.exists(TEMPLATE_FILE)
        else os.path.join(output_dir, "report.tex")
    )
    with open(template_file_path, "r") as f:
        template_content = f.read()

    # Populate header data in parallel with image collection
    template_content = populate_header_data(template_content, json_data)
    image_urls = await collect_all_image_urls(json_data)

    # Download images concurrently
    if image_urls:
        await download_images_background(image_urls)

    # Copy static images (obstruction.png and scope.png) to output directory
    static_images = ["obstruction.png", "scope.png"]
    for img_name in static_images:
        src_path = os.path.join("latex", img_name)
        dst_path = os.path.join(output_dir, img_name)
        if os.path.exists(src_path):
            try:
                shutil.copy2(src_path, dst_path)
                print(f"✓ Copied {img_name} to output directory")
            except Exception as e:
                print(f"⚠️  Failed to copy {img_name}: {e}")

    # Generate report body (CPU-intensive, run in thread pool)
    loop = asyncio.get_event_loop()
    report_body = await loop.run_in_executor(
        THREAD_POOL, generate_latex_body, json_data
    )

    final_content = template_content.replace(CONTENT_MARKER, report_body)

    # Save LaTeX file
    os.makedirs(output_dir, exist_ok=True)
    with open(final_tex_file, "w") as f:
        f.write(final_content)

    # Run pdflatex (suppress console output)
    tex_filename_only = os.path.basename(final_tex_file)
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", tex_filename_only],
        cwd=output_dir,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", tex_filename_only],
        cwd=output_dir,
        capture_output=True,
        text=True,
    )

    # Check if PDF was actually generated (more reliable than exit code)
    if not os.path.exists(final_pdf_file):
        # Try to extract meaningful error from log file
        log_file = os.path.join(output_dir, "final_report.log")
        error_msg = "PDFLaTeX compilation failed - PDF not generated."

        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as log:
                    log_content = log.read()
                    # Look for error indicators
                    if "!" in log_content:
                        lines = log_content.split("\n")
                        for i, line in enumerate(lines):
                            if line.startswith("!"):
                                # Get error line and next few lines for context
                                error_context = "\n".join(lines[i : i + 3])
                                error_msg = f"LaTeX Error: {error_context}"
                                break
            except Exception:
                pass

        msg = f"{error_msg}\nReturn code: {result.returncode}\nStderr: {result.stderr[:200] if result.stderr else 'None'}"
        raise Exception(msg)

    # Compress PDF to reduce file size
    print(f"📦 Compressing PDF...")
    compressed_pdf = compress_pdf(final_pdf_file)
    if compressed_pdf and os.path.exists(compressed_pdf):
        # Get file sizes for comparison
        original_size = os.path.getsize(final_pdf_file) / (1024 * 1024)  # MB
        compressed_size = os.path.getsize(compressed_pdf) / (1024 * 1024)  # MB
        reduction = ((original_size - compressed_size) / original_size) * 100
        print(
            f"✓ PDF compressed: {original_size:.2f}MB → {compressed_size:.2f}MB ({reduction:.1f}% reduction)"
        )
        final_pdf_file = compressed_pdf

    # Don't cleanup yet - will be cleaned after PDF download
    # Return both PDF path and cleanup info
    return final_pdf_file, output_dir, tex_filename_only


def cleanup_temp_files(output_dir: str, tex_filename: str):
    """Clean up temporary LaTeX and image files."""
    # Remove images from the output directory's images folder
    image_dir = os.path.join(output_dir, "images")
    if os.path.exists(image_dir):
        image_files = glob.glob(os.path.join(image_dir, "*"))
        for file_path in image_files:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception:
                pass

    # Remove LaTeX temporary files including .tex and .log
    base_name = tex_filename.replace(".tex", "")
    latex_temp_files = [
        f"{base_name}.tex",
        # f"{base_name}.aux",
        f"{base_name}.log",
        f"{base_name}.out",
        # f"{base_name}.toc",
        f"{base_name}.fls",
        f"{base_name}.fdb_latexmk",
        f"{base_name}.synctex.gz",
    ]
    for filename in latex_temp_files:
        temp_file = os.path.join(output_dir, filename)
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
