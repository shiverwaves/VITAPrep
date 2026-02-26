"""
Weighted sampling utilities for household generation.

Port from HouseholdRNG/generator/sampler.py — that code is stable and tested.
All sampling uses weighted probabilities from PUMS/BLS distributions.
"""

# TODO: Port the following functions from HouseholdRNG/generator/sampler.py:
#
# - weighted_sample(df, weight_col, n) → sample rows by population weight
# - sample_from_bracket(bracket_str) → random value from "$25-50K" strings
# - parse_dollar_amount(s) → "$25K" to 25000
# - get_age_bracket(age, brackets) → find matching bracket
# - match_age_bracket(age, bracket) → check if age fits "25-34"
# - sample_age_from_bracket(bracket) → random age within bracket
# - set_random_seed(seed) → reproducibility
