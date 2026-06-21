# PlanFuge

PlanFuge is a hackathon prototype for the Riedel Bau challenge. It supports the extraction, review and export of ceiling recesses and slab opening candidates from construction plans for concrete 3D printing preparation.

The project is intentionally human-in-the-loop: it does not claim fully automatic construction-plan understanding. It creates structured opening candidates, shows the evidence to a reviewer, and exports reviewable data for downstream planning.

## What Problem It Solves

Construction plans contain opening labels such as `WDB`, `DDB`, `UZDB`, `DDP`, `HSI150`, `RA`, `OK` and `UKRD`. The plans are available as PDFs and rendered images. Some information is visible as red annotations, while some text is available directly in the searchable PDF layer.

PlanFuge combines both sources:

- PDF rendering for visual inspection and computer vision.
- Red annotation detection for locating marked regions.
- OCR on cropped regions for text extraction.
- Searchable PDF word coordinates as a fallback when OCR is incomplete.
- Backend review and export so a human can verify the final result.

## Technology Stack

- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Lucide icons
- **Backend:** FastAPI, Pydantic
- **PDF processing:** PyMuPDF
- **Computer vision:** Pillow and NumPy
- **OCR:** Tesseract via `pytesseract`
- **Data processing/export:** pandas and Python CSV utilities
- **Tests:** Python `unittest`

## Repository Structure

```text
client/          React + Vite frontend
server/          FastAPI backend and export services
src/             CV, OCR, parsing and extraction modules
scripts/         Pipeline and utility scripts
data/            PDFs, rendered pages, metadata, annotations and word coordinates
outputs/         Generated candidates, crops, debug images and CSV exports
tests/           Python tests for CV, parsing and pipeline logic
docs/            Internal project notes and contracts
```

## Data Flow

### 1. Input Data

Input PDFs are stored in:

```text
data/imports/
```

Rendered plan images are stored in:

```text
data/pages/
```

Plan metadata is stored in:

```text
data/metadata/
```

Searchable PDF word coordinates are stored in:

```text
data/words/
```

### 2. Candidate Extraction

The extraction pipeline renders the first PDF page to a high-resolution PNG, detects red annotation regions, crops each region, runs OCR, parses labels and dimensions, and writes candidate JSON.

Important parsed fields include:

- `candidate_id`
- `source`
- `label_type`
- `raw_text`
- `bbox_image`
- `crop_path`
- `width_mm`
- `height_mm`
- `diameter_mm`
- `ra_value`
- `ok_value`
- `reference`
- `confidence`
- `status`

Candidate files are written to:

```text
outputs/candidates/<plan_id>_candidates.json
```

### 3. PDF Word Fallback

OCR can be noisy on construction drawings. For this reason, the project also uses pre-extracted searchable PDF word coordinates from `data/words/`.

This improves extraction when OCR misses small labels or reads characters incorrectly.

### 4. Review and Export

The backend loads candidates and exposes them to the frontend for review. The reviewer can inspect detected candidates, edit values and export structured data.

CSV exports are written to:

```text
outputs/contract_exports/
```

Candidates without parsed dimensions stay in the candidate JSON for review. They should not be trusted as final geometry until reviewed.

## Setup

Run these commands from the repository root.

### Python Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Dependencies

```bash
cd client
npm install
cd ..
```

### OCR System Dependency

`pytesseract` is only the Python wrapper. The Tesseract binary must also be installed on the system.

Examples:

```bash
# Fedora
sudo dnf install tesseract tesseract-langpack-deu tesseract-langpack-eng

# Debian/Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
```

## Run the Application

PlanFuge has two running parts: backend and frontend.

### Docker

Run both services with Docker Compose:

```bash
docker compose up --build
```

Default URLs:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
```

To avoid host port conflicts, override the bindings when starting Compose:

```bash
FRONTEND_PORT=5174 BACKEND_PORT=8001 docker compose up --build
```

The frontend container serves the production Vite build through Nginx and proxies
`/api` requests to the backend container. The backend mounts `./data` and
`./outputs` so generated plan assets and exports stay on the host. On startup,
the backend runs the extraction pipeline when PDFs exist in `data/imports` and
candidate/page outputs are missing. Set `PLANFUGE_RUN_PIPELINE_ON_STARTUP=0` to
skip this automatic pipeline step.

### 1. Start the Backend

Open the first terminal in the repository root:

```bash
source .venv/bin/activate
uvicorn server.app.api:app --host 127.0.0.1 --port 8000 --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

### 2. Start the Frontend

Open a second terminal:

```bash
cd client
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

The Vite frontend proxies API requests to the FastAPI backend on port `8000`.

## Useful Commands

Check backend input files for a plan:

```bash
python scripts/check_backend_inputs.py --plan-id SP_U1_0003
```

Extract candidates from pre-extracted PDF word coordinates:

```bash
python scripts/extract_candidates_from_words.py --words data/words/SP_U1_0003_words.json --out outputs/candidates
```

Validate generated candidates against manual examples:

```bash
python scripts/validate_candidates_against_examples.py --plan-id SP_U1_0003
```

## Run Tests

Run all Python tests:

```bash
python -m unittest discover
```

Build the frontend:

```bash
cd client
npm run build
```

## Current Limitations

- OCR quality depends on Tesseract and the quality of the crop.
- Some candidates require manual review before being trusted.
- Searchable PDF text improves coverage but can also include unrelated plan text.
- The project is a prototype and not a production construction automation system.
- The final export should be interpreted as review-assisted output, not as a fully verified engineering model.

## Demo Message

PlanFuge turns construction PDFs into reviewable opening candidates by combining searchable PDF text, red annotation detection, OCR and a human review workflow. The result is a practical bridge from raw construction plans to structured candidate data for concrete 3D printing preparation.
