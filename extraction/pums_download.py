"""
Shared PUMS/BLS file downloader with local caching.

Downloads Census PUMS CSV files and caches locally to avoid re-downloading.
Cache directory: extraction/pums_cache/ (gitignored)

Reference: HouseholdRNG/scripts/extract_pums.py lines 72-152
"""

# TODO: Port download_pums_files() and load_pums_data() from HouseholdRNG
