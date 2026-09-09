"""Parsers turn raw PHD files into a long 'staging' table with these columns:

    option_name, section, subsection, holding_name, security_id, units, value, weight,
    currency, maturity, coupon, face_value, manager, reporting_date, source_file, sheet, row

Fund-specific adapters (parse/adapters) can override the generic parser when a fund's layout
defeats the heuristics. The parser never classifies; classification happens in normalise.py.
"""
from .generic import parse_file  # noqa: F401
