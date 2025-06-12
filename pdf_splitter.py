import os
import sys
import argparse
import logging
import json
from pypdf import PdfReader
import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv
from fpdf import FPDF

# Create a logger specifically for translation
translation_logger = logging.getLogger('translation')

# A contour is considered part of a diagram if its area is larger than this.
# This helps filter out small contours from text and noise.
MIN_CONTOUR_AREA = 1000

# --- HELPER FUNCTIONS ---

def translate_text_with_gemini(model, current_text, prev_text=None, next_text=None):
    """
    Translates text from German to Spanish using the Gemini API, with context.
    """
    if not current_text.strip():
        print("  -> Page is empty, skipping translation.")
        return "" # Don't bother translating empty pages

    prev_context_str = f"Previous Page Context:\n---\n{prev_text}\n---\n" if prev_text else ""
    next_context_str = f"Next Page Context:\n---\n{next_text}\n---\n" if next_text else ""

    prompt = f"""
You are an expert translator specializing in technical documents. Your task is to translate the following German text to Spanish.
Use the "Previous Page Context" and "Next Page Context" to ensure terminological consistency and accurate translation of phrases that span across pages.
Only provide the Spanish translation for the "Main Text to Translate". Do not translate the context pages. Do not add any extra commentary, headers, or explanations.

{prev_context_str}
Main Text to Translate (German):
---
{current_text}
---
{next_context_str}
Spanish Translation:
"""
    translation_logger.info(f"Requesting translation for page content (length: {len(current_text)} chars).")
    translation_logger.debug(f"--- PROMPT START ---\n{prompt}\n--- PROMPT END ---")

    try:
        response = model.generate_content(prompt)
        translation_logger.info("Successfully received response from Gemini API.")
        translated_text = response.text.strip().replace("```", "").strip()
        translation_logger.debug(f"--- RESPONSE START ---\n{translated_text}\n--- RESPONSE END ---")
        return translated_text
    except Exception as e:
        print(f"  -> Gemini API call failed: {e}")
        translation_logger.error("Gemini API call failed.", exc_info=True)
        return None

def extract_diagrams(image_path, diagrams_dir, base_filename):
    """
    Analyzes an image to find and extract diagrams.
    Saves any found diagrams as separate image files.
    Returns a list of paths to the extracted diagram images.
    """
    extracted_files = []
    try:
        original_image = cv2.imread(image_path)
        if original_image is None:
            print(f"  -> Could not read image {os.path.basename(image_path)} for diagram extraction.")
            return extracted_files

        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        large_contours = [c for c in contours if cv2.contourArea(c) > MIN_CONTOUR_AREA]

        if not large_contours:
            return extracted_files

        all_points = np.vstack([c for c in large_contours])
        x, y, w, h = cv2.boundingRect(all_points)

        padding = 20
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(original_image.shape[1] - x, w + 2 * padding)
        h = min(original_image.shape[0] - y, h + 2 * padding)

        diagram_crop = original_image[y:y+h, x:x+w]
        diagram_filename = f"{base_filename}_diagram_0.png"
        diagram_path = os.path.join(diagrams_dir, diagram_filename)
        cv2.imwrite(diagram_path, diagram_crop)
        
        extracted_files.append(diagram_path)
        return extracted_files

    except Exception as e:
        print(f"  -> Could not extract diagrams from {os.path.basename(image_path)}: {e}")
        return extracted_files

# --- STEP EXECUTION FUNCTIONS ---

def run_text_extraction(input_pdf_path, processed_dir):
    """
    Converts PDF pages to images and performs OCR, saving images and text.
    """
    print("\n--- Running Step: Text Extraction ---")
    try:
        reader = PdfReader(input_pdf_path)
        num_pages = len(reader.pages)
        print(f"Processing {input_pdf_path} ({num_pages} pages)...")

        for i in range(num_pages):
            page_num = i + 1
            print(f"\nProcessing page {page_num}/{num_pages}...")
            
            images = convert_from_path(input_pdf_path, dpi=300, first_page=page_num, last_page=page_num, fmt='png')
            if not images:
                print(f"  -> Could not convert page {page_num} to image.")
                continue
            
            image = images[0]
            base_filename = f"page_{i:03d}"
            image_filename = f"{base_filename}.png"
            image_path = os.path.join(processed_dir, image_filename)
            image.save(image_path, "PNG")
            print(f"  -> Saved full page image to {image_path}")

            text = pytesseract.image_to_string(image, lang='deu')
            text_filename = f"{base_filename}.txt"
            text_path = os.path.join(processed_dir, text_filename)
            with open(text_path, "w", encoding="utf-8") as text_file:
                text_file.write(text)
            print(f"  -> Saved original German text to {text_path}")
        print("\n--- Text Extraction Complete ---")
    except Exception as e:
        print(f"An error occurred during text extraction: {e}")
        sys.exit(1)

def run_diagram_extraction(processed_dir, diagrams_dir):
    """
    Iterates over page images and extracts diagrams from them.
    """
    print("\n--- Running Step: Diagram Extraction ---")
    all_extracted_diagrams = []
    image_files = sorted([f for f in os.listdir(processed_dir) if f.endswith('.png')])

    for image_filename in image_files:
        print(f"Analyzing {image_filename} for diagrams...")
        image_path = os.path.join(processed_dir, image_filename)
        base_filename = os.path.splitext(image_filename)[0]
        extracted = extract_diagrams(image_path, diagrams_dir, base_filename)
        if extracted:
            print(f"  -> Extracted {len(extracted)} diagram(s) from {image_filename}.")
            all_extracted_diagrams.extend(extracted)

    if all_extracted_diagrams:
        print("\n--- Diagram Extraction Complete: Found Diagrams ---")
        for path in sorted(all_extracted_diagrams):
            print(os.path.relpath(path))
        print("--------------------------------------------------")
    else:
        print("\n--- Diagram Extraction Complete: No diagrams found. ---")

def run_translation(processed_dir, translations_dir):
    """
    Translates extracted text files from German to Spanish.
    """
    print("\n--- Running Step: Translation ---")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Warning: GOOGLE_API_KEY not set. Skipping translation.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')

    text_files = sorted([f for f in os.listdir(processed_dir) if f.endswith('.txt')])
    all_pages_text = []
    for text_file in text_files:
        with open(os.path.join(processed_dir, text_file), 'r', encoding='utf-8') as f:
            all_pages_text.append(f.read())
    
    num_pages = len(all_pages_text)
    for i, current_text in enumerate(all_pages_text):
        page_num = i + 1
        print(f"Translating page {page_num}/{num_pages}...")

        prev_text = all_pages_text[i-1] if i > 0 else None
        next_text = all_pages_text[i+1] if i < num_pages - 1 else None

        translated_text = translate_text_with_gemini(model, current_text, prev_text, next_text)

        if translated_text is not None:
            base_filename = f"page_{i:03d}"
            translated_filename = f"{base_filename}_translated.txt"
            translated_path = os.path.join(translations_dir, translated_filename)
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            print(f"  -> Saved translation to {translated_path}")
        else:
            print(f"  -> Failed to translate page {page_num}.")
    print("\n--- Translation Complete ---")

def run_create_viewer_data(processed_dir, translations_dir):
    """
    Creates a viewer-data.js file with all necessary content for the web viewer.
    """
    print("\n--- Running Step: Create Viewer Data ---")
    viewer_data = {"pages": []}
    
    image_files = sorted([f for f in os.listdir(processed_dir) if f.endswith('.png')])
    
    # The viewer's HTML is in the 'viewer' subdirectory. Paths should be relative to it.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    viewer_dir = os.path.join(script_dir, 'viewer')

    for image_filename in image_files:
        base_filename = os.path.splitext(image_filename)[0]
        
        image_path_abs = os.path.abspath(os.path.join(processed_dir, image_filename))
        translation_filename = f"{base_filename}_translated.txt"
        translation_path = os.path.join(translations_dir, translation_filename)

        if os.path.exists(translation_path):
            with open(translation_path, 'r', encoding='utf-8') as f:
                translation_content = f.read()
            
            page_data = {
                # Generate path relative to the viewer directory
                "image": os.path.relpath(image_path_abs, viewer_dir).replace("\\", "/"),
                "translation": translation_content
            }
            viewer_data["pages"].append(page_data)
        else:
            print(f"  -> Warning: Skipping page {base_filename}, translation file not found.")

    # The output file goes inside the viewer directory
    viewer_data_path = os.path.join(viewer_dir, 'viewer-data.js')
    
    # Use json.dumps to safely serialize the data to a string, then wrap it in JS
    js_content = f"const viewerData = {json.dumps(viewer_data, indent=2)};"
    
    with open(viewer_data_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print(f"Viewer data file created with {len(viewer_data['pages'])} pages.")
    print(f"Saved viewer data to {viewer_data_path}")
    print("\n--- Create Viewer Data Complete ---")

def run_create_pdf(translations_dir, base_output_dir, input_pdf_path):
    """
    Creates a PDF file from the translated text files.
    """
    print("\n--- Running Step: Create PDF from Translations ---")
    
    translated_files = sorted([f for f in os.listdir(translations_dir) if f.endswith('_translated.txt')])
    if not translated_files:
        print("No translated files found. Skipping PDF creation.")
        return

    pdf = FPDF()
    font_name = "NotoSans"
    font_path = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
    pdf.add_font(font_name, "", font_path, uni=True)
    pdf.set_font(font_name, size=12)

    
    for filename in translated_files:
        page_num_str = filename.split('_')[1]
        print(f"  -> Adding page {int(page_num_str) + 1} to PDF...")
        
        filepath = os.path.join(translations_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            
        pdf.add_page()
        # Use multi_cell to handle line breaks and long text automatically
        pdf.multi_cell(0, 5, text)

    # Construct output filename
    base_name = os.path.splitext(os.path.basename(input_pdf_path))[0]
    output_filename = f"{base_name}_translated.pdf"
    output_path = os.path.join(base_output_dir, output_filename)
    
    try:
        pdf.output(output_path)
        print(f"\nTranslated PDF created successfully at: {output_path}")
    except Exception as e:
        print(f"  -> Failed to create PDF: {e}")

    print("\n--- Create PDF Complete ---")

# --- MAIN APPLICATION ---

def main():
    """
    Main function to parse arguments and orchestrate the PDF processing steps.
    """
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extract text, diagrams, and translate content from a PDF file.")
    parser.add_argument("pdf_path", help="The path to the input PDF file.")
    parser.add_argument("--steps", nargs='+', required=True, 
                        choices=['extract-text', 'extract-diagrams', 'translate', 'create-viewer-data', 'create-pdf', 'all'],
                        help="Specify which processing steps to run.")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Error: The file '{args.pdf_path}' was not found.")
        sys.exit(1)

    base_output_dir = "extraction"
    processed_dir = os.path.join(base_output_dir, "processed")
    diagrams_dir = os.path.join(processed_dir, "diagrams")
    translations_dir = os.path.join(processed_dir, "translations")
    os.makedirs(diagrams_dir, exist_ok=True)
    os.makedirs(translations_dir, exist_ok=True)

    # --- Setup Logging ---
    log_file = os.path.join(base_output_dir, "translation.log")
    translation_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    translation_logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('    -> LOG: %(message)s')
    console_handler.setFormatter(console_formatter)
    translation_logger.addHandler(console_handler)

    steps_to_run = args.steps
    if 'all' in steps_to_run:
        steps_to_run = ['extract-text', 'extract-diagrams', 'translate', 'create-viewer-data', 'create-pdf']

    if 'extract-text' in steps_to_run:
        run_text_extraction(args.pdf_path, processed_dir)

    if 'extract-diagrams' in steps_to_run:
        if not any(f.endswith('.png') for f in os.listdir(processed_dir)):
            print("\nError: Cannot run diagram extraction. Page images not found.", file=sys.stderr)
            print("Please run the 'extract-text' step first or use 'all'.", file=sys.stderr)
            sys.exit(1)
        run_diagram_extraction(processed_dir, diagrams_dir)

    if 'translate' in steps_to_run:
        if not any(f.endswith('.txt') for f in os.listdir(processed_dir) if f.endswith('.txt')):
            print("\nError: Cannot run translation. Original text files not found.", file=sys.stderr)
            print("Please run the 'extract-text' step first or use 'all'.", file=sys.stderr)
            sys.exit(1)
        run_translation(processed_dir, translations_dir)
    
    if 'create-viewer-data' in steps_to_run:
        if not any(f.endswith('.txt') for f in os.listdir(translations_dir)):
             print("\nError: Cannot create viewer data. Translated text files not found.", file=sys.stderr)
             print("Please run the 'translate' step first or use 'all'.", file=sys.stderr)
             sys.exit(1)
        run_create_viewer_data(processed_dir, translations_dir)

    if 'create-pdf' in steps_to_run:
        if not any(f.endswith('_translated.txt') for f in os.listdir(translations_dir)):
             print("\nError: Cannot create PDF. Translated text files not found.", file=sys.stderr)
             print("Please run the 'translate' step first or use 'all'.", file=sys.stderr)
             sys.exit(1)
        run_create_pdf(translations_dir, base_output_dir, args.pdf_path)


if __name__ == "__main__":
    main()
