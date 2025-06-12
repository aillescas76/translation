# PDF Translation and Viewing Tool

This project is a Python script that processes a PDF document by extracting its text and diagrams, translating the text from German to Spanish using the Gemini API, and generating a self-contained HTML viewer to display the original page image alongside its translation.

---

## English Instructions

### 1. Setup

#### Prerequisites
Before you begin, ensure you have the following installed on your system:
- **Python 3.8+**
- **Tesseract OCR**: This is required for extracting text from images.
  - [Installation Guide for Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)
  - **Important**: Make sure to also install the German language pack (`deu`) for Tesseract.
- **Poppler**: This is required by the `pdf2image` library to convert PDF pages into images.
  - For Windows: Download the [latest release](https://github.com/oschwartz10612/poppler-windows/releases/) and add the `bin` directory to your system's PATH.
  - For macOS (using Homebrew): `brew install poppler`
  - For Linux (Debian/Ubuntu): `sudo apt-get install poppler-utils`

#### Installation Steps
1.  **Clone the repository** (or download the files to a local directory):
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create and activate a virtual environment** (recommended):
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install the required Python libraries** using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your API Key**:
    - Rename the `.env.example` file to `.env`.
    - Open the `.env` file and replace `"your_api_key_here"` with your actual Google Gemini API key.
    ```
    GOOGLE_API_KEY="your_api_key_here"
    ```

### 2. Usage

Run the main script from your terminal, providing the path to your PDF file and specifying which steps to execute.

**Command format:**
```
python pdf_splitter.py <path_to_pdf> --steps <step1> [step2 ...]
```

Example to run all steps:
```
python pdf_splitter.py DOC-20250415-WA0039..pdf --steps all
```

### 3. Available Steps

The following steps can be run individually or together by including their names in the `--steps` argument. Alternatively, use `all` to run every step in sequence.

- `extract-text`: Converts each page of the PDF into an image and performs OCR to extract the original German text. The images and text files are saved in the `extraction/processed` directory.
- `extract-diagrams`: Analyzes each page image to detect and extract any diagrams (contours with significant area). Extracted diagrams are saved as separate images in the `extraction/processed/diagrams` directory. This step must be run after `extract-text`.
- `translate`: Translates the extracted German text files to Spanish using the Gemini API. Requires an API key in the `.env` file. The translations are saved as text files in the `extraction/processed/translations` directory. This step must be run after `extract-text`.
- `create-viewer-data`: Creates a `viewer-data.js` file that contains the paths to the page images and the translated text. This file is used by the HTML viewer to display the results. This step must be run after `translate`.
- `create-pdf`: Combines the translated text files into a single PDF document. The PDF is saved in the `extraction` directory. This step must be run after `translate`.
- `all`: Runs all the above steps in the required order: `extract-text`, `extract-diagrams`, `translate`, `create-viewer-data`, and `create-pdf`.

### 4. Viewing the Results

After running the `create-viewer-data` step, you can view the results by opening the `viewer/index.html` file in a web browser.

If you're viewing this README on GitHub, you can access the viewer directly here:  
[View Results](viewer/index.html)

You can either:
- Open it directly from your file explorer by double-clicking
- Or, from the command line, run:

```bash
# For Windows
start viewer/index.html

# For macOS
open viewer/index.html

# For Linux
xdg-open viewer/index.html
```

The viewer will display the original page images alongside their Spanish translations.
