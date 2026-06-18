# PDF Words Candidate Extraction

This path converts pre-extracted PDF word-coordinate JSON into opening candidate
JSON. It is separate from the PNG red-markup/OCR pipeline.

## Input

```text
data/words/<plan_id>_words.json
```

Each word entry should contain:

```json
{
  "text": "WDB",
  "x0": 120.5,
  "y0": 340.2,
  "x1": 145.8,
  "y1": 355.9,
  "page": 1
}
```

## Output

```text
outputs/candidates/<plan_id>_candidates.json
```

## Limitations

- This module does not extract words from raw PDFs.
- It uses a simple same-line proximity heuristic around `WDB`, `DDB`, `UZDB`,
  `DDP`, and `HSI` anchors.
- It does not infer real-world placement or scale.
- Complex multi-line labels may need later grouping improvements.
