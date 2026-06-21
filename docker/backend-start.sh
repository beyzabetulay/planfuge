#!/bin/sh
set -eu

if [ "${PLANFUGE_RUN_PIPELINE_ON_STARTUP:-1}" = "1" ]; then
    pdf_dir="/app/data/imports"
    output_dir="/app/outputs"
    pages_dir="/app/data/pages"
    needs_pipeline=0
    found_pdf=0

    if [ -d "$pdf_dir" ]; then
        for pdf_path in "$pdf_dir"/*.pdf; do
            [ -e "$pdf_path" ] || continue

            found_pdf=1
            plan_id="$(basename "$pdf_path" .pdf)"

            if [ ! -f "$output_dir/candidates/${plan_id}_candidates.json" ]; then
                needs_pipeline=1
            fi

            if [ ! -f "$pages_dir/${plan_id}.png" ] && [ ! -f "$output_dir/rendered/${plan_id}.png" ]; then
                needs_pipeline=1
            fi
        done
    fi

    if [ "$found_pdf" -eq 1 ] && [ "$needs_pipeline" -eq 1 ]; then
        echo "PlanFuge pipeline outputs are missing; running extraction pipeline."
        python scripts/run_pipeline_on_pdfs.py --pdf-dir "$pdf_dir" --out "$output_dir"
    elif [ "$found_pdf" -eq 1 ]; then
        echo "PlanFuge pipeline outputs already exist; skipping startup pipeline."
    else
        echo "No PDFs found in $pdf_dir; skipping startup pipeline."
    fi

    if [ -d "$output_dir/rendered" ]; then
        mkdir -p "$pages_dir"
        for rendered_png in "$output_dir"/rendered/*.png; do
            [ -e "$rendered_png" ] || continue
            cp "$rendered_png" "$pages_dir/"
        done
    fi
fi

exec "$@"
