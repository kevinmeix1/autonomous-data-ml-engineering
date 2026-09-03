# Historical Incident: Late-arriving claims

The claims pipeline previously failed uniqueness tests after a source replay.
Duplicates appeared in fct_claims because the incremental watermark used loss_date
while late reports arrived with older loss_dates but newer report_dates.

Fix: watermark on report_date and add a dedupe unique_key merge on claim_id.
