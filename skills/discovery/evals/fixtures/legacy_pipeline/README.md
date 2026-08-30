# orders-pipeline

A nightly batch job: read the day's orders from a CSV export, aggregate revenue per
region, and write a static HTML report for the ops team.

Run: `python -m pipeline.report orders.csv report.html`

Known pain (from the ops channel):

- The whole file is loaded into memory; the export passed 2 GB last quarter.
- A malformed row aborts the entire night's run; reruns are manual.
- The HTML is string-concatenated in code; every layout tweak is a code change.
- No metrics: when the job is slow nobody knows which stage it was.
