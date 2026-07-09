# Source

**Dataset:** Traffic Volumes - Provincial Highway System
**Portal page:** https://data.novascotia.ca/d/8524-ec3n
**Resource CSV:** https://data.novascotia.ca/resource/8524-ec3n.csv
**Resource id (4x4):** `8524-ec3n`
**Category:** Roads, Driving and Transport

## Licence

Nova Scotia Open Government Licence (Open Government Licence - Nova Scotia). The licence permits reuse with attribution to the information provider, the Province of Nova Scotia. Licence text: https://novascotia.ca/opendata/licence.asp

## Pull

**Pull date:** 2026-07-05
**Snapshot file:** `data/raw/ns_traffic-volumes_2026-07-05.csv`
**Snapshot row count:** 11,721 count rows

The snapshot was pulled once from the Socrata CSV endpoint above, ordered by `section_id` then `date` for a stable sequence, in a single request under the row cap. The file is committed so the ranking reproduces from a fixed input. No application token is needed for a one-off pull of this size.

The `8524-ec3n` resource id resolved on the pull date and returned the full table, so no correction was needed. This is catalog idea #17 in the Nova Scotia Open Data SQL series.
