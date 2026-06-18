# PRD: Plan Grid Coordinate and Color Zone Detection

## Problem Statement

The user is currently exporting opening candidate tables where grid coordinates are default `grid_unknown` and color zones are default `zone_unknown`. Some dimensions of rectangular openings (such as `65 \ 38`) are also not parsed correctly and default to `0.0`. The user wants these fields populated automatically and correctly based on plan configuration, layout calibration, and improved OCR parsing.

## Solution

We will enhance the Plan2Print backend and candidate extraction pipeline to support:
1. Configuring grid coordinate anchors (reference points) and color zone boundaries (geometric polygons and HSV values) per plan.
2. Automating the interpolation of candidate coordinates relative to the grid coordinate system.
3. Automatically mapping each candidate's color zone by checking which boundary polygon its center falls into.
4. Improving OCR normalization rules to support rectangular dimensions like `65 \ 38`.
5. Enhancing the CSV export to deduplicate close openings, apply status warnings for heavy items (>25 kg), and flag low confidence detections (<0.60) for manual review.

## User Stories

1. As a project estimator, I want openings to have grid coordinates, so that I can easily locate them on the physical layout.
2. As a project estimator, I want openings to be classified by color zones, so that I can group them by construction phase.
3. As a project estimator, I want rectangular dimensions like `65 \ 38` to be parsed, so that I don't get empty/zero dimensions in my final table.
4. As an estimator, I want the exported CSV to deduplicate adjacent openings of the same type and size, so that the total counts are accurate.
5. As an estimator, I want heavy openings (over 25 kg) to be flagged for review, so that I can plan special handling or split them.

## Implementation Decisions

- **Configuration Schema**: Add a configuration format (YAML or JSON) for each PDF/PNG plan detailing the scale factor, grid anchor coordinate mappings, and color zone boundary coordinates.
- **Pipeline Extractor Update**: Enhance the candidate extraction pipeline to compute `grid_coordinate` and `color_zone_id` using the geometric definitions.
- **OCR Normalizer Enhancements**: Add regex and text cleaning rules to convert common OCR misreadings of rectangular dimensions (e.g. `65 \ 38`, `65/38`) to standard `[width] x [height]` millimeter metrics.
- **CSV Export Deduplication**: Group candidates with matching types and dimensions that are spatially close in the CSV serializer.
- **Calculations/Models**: Map the `Opening` objects using the configured scale, compute correct `Length/cm` and `Width/cm`, and flag reviews.

## Testing Decisions

- Test the coordinate interpolation function with mock anchor configurations.
- Test the color zone mapping function with mock polygon zones.
- Test the OCR normalizer with various noisy rectangular text patterns.
- Test the deduplication logic in the CSV exporter.

## Out of Scope

- Automatic extraction of grid line drawings directly from pixel lines (relying on anchor points configuration).
- User interface for editing anchor points (handled via server backend/JSON configurations for now).

## Further Notes
