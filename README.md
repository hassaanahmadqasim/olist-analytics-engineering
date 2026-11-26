# Olist Analytics Engineering Pipeline

Work in progress.

Data: Olist Brazilian E-Commerce (Kaggle), CC BY-NC-SA 4.0. Raw data is not committed.
## Simulation (read this)

Olist is a static snapshot, not a live system. The pipeline simulates incremental loads:

- Orders are sliced into a baseline batch (purchased before 2017-01-01) and weekly batches by purchase date.
- 300 delivered orders arrive first in a stale state (`shipped`, no delivery date). The correct row is re-delivered two batches later. The latest batch wins.
- 25 bad rows are injected: null order_id, invalid status, negative price, negative payment, invalid review score. All are listed in `injected_manifest.csv`.
- Stale states and bad rows are synthetic. Olist has no refunds or payment failures.
