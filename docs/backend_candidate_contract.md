# Backend Candidate Contract

This document defines the JSON contract between CV output and the backend review
flow. The backend accepts minimal candidates and richer CV candidates. Unknown
extra fields are preserved so CV can add non-breaking metadata.

## Candidate Payload

Candidate files should use this shape:

```json
{
  "plan_id": "SP_U1_0003",
  "candidate_count": 1,
  "candidates": [
    {
      "candidate_id": "cand-001",
      "source": "cv",
      "bbox_image": [100, 200, 50, 60],
      "status": "needs_review"
    }
  ]
}
```

`candidate_count` is informational. Backend validation counts the loaded
candidate objects after validation.

## Required Candidate Fields

- `candidate_id`: stable identifier for review, save and export
- `source`: origin of the candidate, for example `cv` or `sample`
- `bbox_image`: bounding box in image pixel coordinates
- `status`: current review status

Missing required fields make that candidate invalid.

## Optional Candidate Fields

Missing optional fields are filled with `null` and reported as warnings.

- `label_type`
- `raw_text`
- `crop_path`
- `width_mm`
- `height_mm`
- `diameter_mm`
- `ra_value`
- `ok_value`
- `reference`
- `confidence`
- `review_comment`

## Allowed Status Values

- `needs_review`
- `verified`
- `rejected`
- `duplicate_candidate`

Invalid status values make that candidate invalid.

## Rich Candidate Example

```json
{
  "plan_id": "SP_U1_0003",
  "candidate_count": 1,
  "candidates": [
    {
      "candidate_id": "cand-002",
      "source": "cv",
      "label_type": "WDB",
      "raw_text": "WDB 20/50 d=25",
      "bbox_image": [100, 200, 50, 60],
      "crop_path": "outputs/crops/SP_U1_0003/cand-002.png",
      "width_mm": 200,
      "height_mm": 500,
      "diameter_mm": null,
      "ra_value": null,
      "ok_value": null,
      "reference": "H-17",
      "confidence": 0.91,
      "review_comment": null,
      "status": "needs_review"
    }
  ]
}
```
