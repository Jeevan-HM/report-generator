import asyncio
import hashlib
import json
import os
import subprocess
import urllib
from io import BytesIO
from typing import Optional

import aiohttp
from PIL import Image  # Requires 'pip install Pillow'

# --- CONFIGURATION (Updated for 'latex' folder) ---
JSON_FILE = "inspection.json"  # Assumes this is in the root, with the script
TEMPLATE_FILE = "latex/report.tex"
FINAL_TEX_FILE = "latex/final_report.tex"
FINAL_PDF_FILE = "latex/final_report.pdf"
IMAGE_DIR = "latex/images"  # <-- Images now INSIDE latex folder
CONTENT_MARKER = "% --- PYTHON CONTENT MARKER ---"

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
    Asynchronously downloads an image, checks its REAL format using Pillow,
    converts unsupported formats (like WEBP) to PNG,
    saves it to the IMAGE_DIR, and returns the local path.
    """
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    filename_hash = hashlib.md5(url.encode("utf-8")).hexdigest()

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status != 200:
                print(f"⚠️  Failed to download {url} (Status: {response.status})")
                return None

            image_data = await response.read()

            # Use Pillow to identify and process the image format
            try:
                img = Image.open(BytesIO(image_data))
                file_format = img.format.lower() if img.format else "unknown"

                # Convert WEBP and other unsupported formats to PNG
                if file_format in ["webp", "svg", "bmp", "tiff"]:
                    ext = ".png"
                    filepath = os.path.join(IMAGE_DIR, filename_hash + ext)

                    if os.path.exists(filepath):
                        return filepath

                    # Convert to RGB if necessary
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")

                    img.save(filepath, "PNG")
                    print(
                        f"✓ Converted {file_format.upper()} → PNG: {os.path.basename(filepath)}"
                    )
                    return filepath

                if file_format == "jpeg":
                    ext = ".jpg"
                elif file_format == "png":
                    ext = ".png"
                else:
                    # Default to PNG for unknown formats
                    ext = ".png"
                    filepath = os.path.join(IMAGE_DIR, filename_hash + ext)

                    if os.path.exists(filepath):
                        return filepath

                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")

                    img.save(filepath, "PNG")
                    print(f"✓ Converted unknown → PNG: {os.path.basename(filepath)}")
                    return filepath

            except Exception as e:
                print(
                    f"⚠️  Could not identify image {url}. Defaulting to .jpg. Error: {e}"
                )
                ext = ".jpg"

            filepath = os.path.join(IMAGE_DIR, filename_hash + ext)

            if os.path.exists(filepath):
                return filepath

            with open(filepath, "wb") as f:
                f.write(image_data)

        print(f"✓ Downloaded: {os.path.basename(filepath)}")
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


def generate_latex_body(data):
    """
    Loops through the JSON data and builds the LaTeX string for the report body.
    """
    body = []
    sections = data.get("inspection", {}).get("sections", [])

    comment_col = r"p{0.7\textwidth}"

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
            if comments:
                body.append(r"\begin{longtable}{c c c c " + comment_col + "}")
                # Add a header that will repeat if the table spans pages
                body.append(
                    r"\textbf{I} & \textbf{NI} & \textbf{NP} & \textbf{D} & \textbf{Comments} \\ \hline \endhead"
                )

                for k, comment in enumerate(comments, start=1):
                    label_text = f"{k}. {comment.get('label', '')}"
                    label = r"\textbf{" + escape_latex(label_text) + "}"
                    body.append(f"{checkbox_str} & {label} \\\\")

                    # --- UPDATED LOGIC FOR SAFER IMAGE SIZING ---
                    # START
                    photos = comment.get("photos", [])
                    if photos:
                        valid_image_paths = []
                        for photo in photos:
                            url = photo.get("url")
                            if url:
                                img_path = get_cached_image(url)
                                if img_path:
                                    img_filename = os.path.basename(img_path)
                                    relative_img_path = os.path.join(
                                        "images", img_filename
                                    ).replace("\\", "/")
                                    valid_image_paths.append(relative_img_path)
                                else:
                                    print(
                                        f"⚠️  Image not yet cached, skipping: {url[:60]}..."
                                    )

                        if valid_image_paths:
                            image_latex_parts = []
                            num_photos = len(valid_image_paths)

                            # --- NEW, SAFER SIZES ---
                            # These widths are smaller and should fit side-by-side
                            # within the 0.7\textwidth column.
                            if num_photos == 1:
                                img_width = "2.5in"
                            elif num_photos == 2:
                                img_width = "2.0in"  # Total 4.0in
                            elif num_photos == 3:
                                img_width = "1.5in"  # Total 4.5in
                            else:  # 4 or more
                                img_width = "1.1in"  # Total 4.4in for 4

                            # --- CRITICAL FIX ---
                            # Set a maximum height for all images to prevent
                            # tall/portrait images from running into the footer.
                            max_img_height = "2.5in"

                            for path in valid_image_paths:
                                # Use width, max height, and keepaspectratio
                                # This scales the image to fit BOTH constraints.
                                image_latex_parts.append(
                                    r"\includegraphics[width="
                                    + img_width
                                    + ", height="
                                    + max_img_height
                                    + r", keepaspectratio]{"
                                    + path
                                    + "}"
                                )

                            # Join them with a small horizontal space
                            all_images_latex = r" \hspace{0.5em} ".join(
                                image_latex_parts
                            )

                            # --- CRITICAL FIX ---
                            # 1. Use {\centering ... \par} to center the images
                            #    in the table cell.
                            # 2. Removed the \hspace{1cm} which was pushing
                            #    images out of the column.
                            body.append(
                                r"& & & & "
                                + r"{\centering "
                                + all_images_latex
                                + r" \par} \\[0.5em]"  # Add vertical space after images
                            )

                    # If the comment has a 'value', display it in a new row
                    comment_value = comment.get("value")
                    if comment_value:
                        value_latex = escape_latex(str(comment_value))
                        # Span all columns except the first four (checkboxes)
                        body.append(r"& & & & " + value_latex + r" \\")
                    # --- UPDATED LOGIC FOR SAFER IMAGE SIZING ---
                    # END

                body.append(r"\end{longtable}" + "\n")

            body.append(r"\vspace{1.5em}")  # Increased space between items

        body.append(r"\clearpage")

    return "\n".join(body)


# --- 3. Main Execution ---


async def collect_all_image_urls(data) -> list[str]:
    """Collects all unique image URLs from the JSON data."""
    urls = set()
    sections = data.get("inspection", {}).get("sections", [])

    for section in sections:
        line_items = section.get("lineItems", [])
        for item in line_items:
            comments = item.get("comments", [])
            for comment in comments:
                photos = comment.get("photos", [])
                for photo in photos:
                    url = photo.get("url")
                    if url:
                        urls.add(url)

    return list(urls)


async def download_images_background(urls: list[str]):
    """Downloads all images in the background concurrently."""
    if not urls:
        return

    print(f"\n🚀 Starting background download of {len(urls)} images...")

    timeout = aiohttp.ClientTimeout(total=60, connect=10)
    connector = aiohttp.TCPConnector(limit=10)  # Max 10 concurrent connections

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [download_and_cache_image(session, url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

    successful = sum(1 for path in IMAGE_CACHE.values() if path is not None)
    print(f"✅ Downloaded {successful}/{len(urls)} images successfully\n")


async def main_async():
    """Main async function that downloads images while building the report."""
    print(f"Loading JSON data from {JSON_FILE}...")
    try:
        with open(JSON_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {JSON_FILE}: {e}")
        return

    print(f"Loading LaTeX template from {TEMPLATE_FILE}...")
    try:
        with open(TEMPLATE_FILE, "r") as f:
            template_content = f.read()
    except Exception as e:
        print(f"Error loading {TEMPLATE_FILE}: {e}")
        return

    # Collect all image URLs
    print("📥 Collecting image URLs...")
    image_urls = await collect_all_image_urls(data)
    print(f"Found {len(image_urls)} unique images")

    # Download all images first before generating the report
    print("⏳ Downloading all images...")
    await download_images_background(image_urls)

    # Generate report body with all cached images
    print("📝 Generating report body with all images...")
    report_body = generate_latex_body(data)

    final_content = template_content.replace(CONTENT_MARKER, report_body)

    print(f"💾 Saving populated LaTeX to {FINAL_TEX_FILE}...")
    os.makedirs(os.path.dirname(FINAL_TEX_FILE), exist_ok=True)
    with open(FINAL_TEX_FILE, "w") as f:
        f.write(final_content)

    print("\n📄 Running pdflatex (Pass 1)...")
    try:
        run_directory = os.path.dirname(FINAL_TEX_FILE)
        if run_directory == "":
            run_directory = "."

        tex_filename_only = os.path.basename(FINAL_TEX_FILE)

        # Run from within the 'latex/' directory
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_filename_only],
            check=True,
            cwd=run_directory,
        )

        print("📄 Running pdflatex (Pass 2)...")
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_filename_only],
            check=True,
            cwd=run_directory,
        )

        print("\n✅ Done! ✅")
        print(f"Successfully generated {FINAL_PDF_FILE}")

    except subprocess.CalledProcessError:
        print(f"\n❌ PDFLATEX FAILED ❌")
        print(
            f"A LaTeX error occurred. Python script is OK, but the .tex file is invalid."
        )
        print(
            f"To find the error, open the file 'latex/final_report.log' and scroll to the bottom."
        )
        print(f"Look for a line starting with '!'")

    except FileNotFoundError:
        print("\n❌ PDFLATEX NOT FOUND ❌")
        print(
            "Error: 'pdflatex' command not found. Is TeX Live (or MiKTeX) installed and in your system's PATH?"
        )


def main():
    """Entry point - runs the async main function."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
