"""
Address Normalization Script
----------------------------
Reads a CSV exported from Google Sheets, normalizes US addresses,
and writes a new CSV ready to re-import.

Usage:
    pip install pandas usaddress
    python normalize_addresses.py --input addresses.csv --column "Address" --output normalized.csv

The script will:
  1. Trim whitespace
  2. Title-case street names and city
  3. Abbreviate street types (Street → St, Avenue → Ave, etc.)
  4. Abbreviate cardinal directions (North → N, Southwest → SW, etc.)
  5. Parse with usaddress and reassemble into a clean single-line format
  6. Flag rows that could not be parsed for manual review
"""

import argparse
import re
import pandas as pd
import usaddress

# ---------------------------------------------------------------------------
# Abbreviation maps (full name → abbreviation)
# ---------------------------------------------------------------------------
STREET_TYPES = {
    "Street": "St", "Avenue": "Ave", "Boulevard": "Blvd", "Drive": "Dr",
    "Road": "Rd", "Lane": "Ln", "Court": "Ct", "Place": "Pl",
    "Parkway": "Pkwy", "Highway": "Hwy", "Freeway": "Fwy",
    "Circle": "Cir", "Terrace": "Ter", "Trail": "Trl",
    "Square": "Sq", "Alley": "Aly", "Bend": "Bnd", "Bridge": "Brg",
    "Bypass": "Byp", "Crossing": "Xing", "Way": "Way", "Wy": "Way",
    # Rural / numbered road types — preserve as title case
    "Route": "Route", "County Road": "County Road", "Us Highway": "US Hwy",
    "State Highway": "State Hwy", "State Road": "State Rd", "Farm Road": "Farm Rd",
    "State Route": "SR",
    "Township Road": "Twp Rd", "Twp Road": "Twp Rd", "Twp Rd": "Twp Rd",
    "Township Rd": "Twp Rd",
}

CARDINAL_DIRECTIONS = {
    "North": "N", "South": "S", "East": "E", "West": "W",
    "Northeast": "NE", "Northwest": "NW", "Southeast": "SE", "Southwest": "SW",
    # Already-abbreviated inputs (title-cased by usaddress)
    "Ne": "NE", "Nw": "NW", "Se": "SE", "Sw": "SW",
    "N": "N", "S": "S", "E": "E", "W": "W",
}

UNIT_TYPES = {
    "Apartment": "Apt", "Suite": "Ste", "Floor": "Fl",
    "Room": "Rm", "Department": "Dept",
    # already short — keep as-is
    "Apt": "Apt", "Ste": "Ste", "Unit": "Unit", "Fl": "Fl", "Rm": "Rm",
}


# ---------------------------------------------------------------------------
# Core normalization helpers
# ---------------------------------------------------------------------------

def clean_whitespace(text: str) -> str:
    """Strip leading/trailing space and collapse internal whitespace."""
    return re.sub(r"\s+", " ", str(text).strip())



def remove_periods(text: str) -> str:
    """Remove all periods from an address string."""
    return text.replace(".", "")


def lowercase_ordinals(text: str) -> str:
    """Lowercase ordinal indicators: 1St -> 1st, 2Nd -> 2nd, 3Rd -> 3rd, 4Th -> 4th etc."""
    return re.sub(r"(\d+)(St|Nd|Rd|Th)\b", lambda m: m.group(1) + m.group(2).lower(), text)


def fix_highway_designators(text: str) -> str:
    """Uppercase known highway designators: Us -> US, Ih -> IH, Fm -> FM, Sh -> SH, Cr -> CR."""
    designators = ["Us", "Ih", "Fm", "Sh", "Cr", "Rr"]
    for d in designators:
        # Match designator followed by a hyphen, number, or known highway word
        text = re.sub(rf"\b{d}(?=-|\s+\d|\s+Hwy|\s+Highway)", d.upper(), text)
    return text


def fix_punctuation(text: str) -> str:
    """Fix apostrophe-s casing ('S -> 's) and remove space after # (# 101 -> #101)."""
    text = re.sub(r"'S\b", "'s", text)
    text = re.sub(r"#\s+", "#", text)
    return text

def abbreviate_street_type(word: str) -> str:
    """Abbreviate a street type if recognised, otherwise return as-is."""
    return STREET_TYPES.get(word.rstrip(".").title(), word.title())


def abbreviate_direction(word: str) -> str:
    """Abbreviate a cardinal direction if recognised, otherwise return as-is."""
    if not word:
        return ""
    return CARDINAL_DIRECTIONS.get(word.rstrip(".").title(), word)


def normalize_zip(zipcode: str) -> str:
    """Keep only digits; return 5-digit or ZIP+4 format."""
    digits = re.sub(r"[^\d]", "", str(zipcode))
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    return digits[:5]


def assemble_from_tags(tagged: dict) -> str:
    """
    Turn a usaddress tag dict into a normalised single-line address string.
    Format: {number} {pre_dir} {street} {street_type} {post_dir}, {unit}, {city}, {state} {zip}
    """
    num      = tagged.get("AddressNumber", "")
    pre_dir  = abbreviate_direction(tagged.get("StreetNamePreDirectional", ""))
    pre_type = STREET_TYPES.get(tagged.get("StreetNamePreType", "").title(), tagged.get("StreetNamePreType", "").title())
    street   = tagged.get("StreetName", "").title()
    stype    = abbreviate_street_type(tagged.get("StreetNamePostType", ""))
    post_dir = abbreviate_direction(tagged.get("StreetNamePostDirectional", ""))

    occ_type  = tagged.get("OccupancyType", "")
    occ_id    = tagged.get("OccupancyIdentifier", "")
    # If there is no OccupancyType, usaddress likely misread a road number as a unit —
    # treat it as part of the street name but append after the street type
    road_number = ""
    if occ_id and not occ_type:
        road_number = occ_id
        occ_id = ""
    unit_type = UNIT_TYPES.get(occ_type.title(), occ_type.title())
    unit_id   = occ_id
    unit_part = f"{unit_type} {unit_id}".strip() if unit_type or unit_id else ""

    bldg_type = tagged.get("SubaddressType", "").title()
    bldg_id   = tagged.get("SubaddressIdentifier", "")
    bldg_part = f"{bldg_type} {bldg_id}".strip() if bldg_type or bldg_id else ""

    city  = tagged.get("PlaceName", "").title()
    state = tagged.get("StateName", "").strip().upper()
    zipp  = normalize_zip(tagged.get("ZipCode", ""))

    # Build street line
    street_parts = [p for p in [num, pre_dir, pre_type, street, stype, road_number, post_dir] if p]
    street_line  = " ".join(street_parts)

    # Build city/state/zip
    csz_parts = [p for p in [city, state] if p]
    csz = ", ".join(csz_parts)
    if zipp:
        csz = f"{csz} {zipp}".strip()

    # Final assembly
    components = [p for p in [street_line, bldg_part, unit_part, csz] if p]
    return ", ".join(components)



def smart_title(text: str) -> str:
    """Title-case an address string but keep 2-letter uppercase tokens (state codes) uppercased."""
    words = text.split()
    result = []
    for word in words:
        # Keep 2-letter all-alpha tokens as uppercase (state abbreviations like TX, NY)
        if len(word) == 2 and word.isalpha():
            result.append(word.upper())
        else:
            result.append(word.title())
    return " ".join(result)


def convert_leading_number_word(text: str) -> str:
    """Convert spelled-out address numbers one-ten at the start of an address to digits."""
    number_words = {
        "One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5",
        "Six": "6", "Seven": "7", "Eight": "8", "Nine": "9", "Ten": "10",
    }
    # Only match at the very start of the string, case-insensitive
    for word, digit in number_words.items():
        text = re.sub(rf"^{word}\b", digit, text, flags=re.IGNORECASE)
    return text


def assemble_intersection(tagged: dict) -> str:
    """Reassemble an intersection address from usaddress tags."""
    corner   = tagged.get("CornerOf", "").lower().capitalize()
    street1  = tagged.get("StreetName", "").title()
    type1    = abbreviate_street_type(tagged.get("StreetNamePostType", ""))
    pre_dir1 = abbreviate_direction(tagged.get("StreetNamePreDirectional", ""))
    post_dir1= abbreviate_direction(tagged.get("StreetNamePostDirectional", ""))

    sep      = tagged.get("IntersectionSeparator", "&")

    pre_type2= STREET_TYPES.get(tagged.get("SecondStreetNamePreType", "").title(), tagged.get("SecondStreetNamePreType", "").title())
    street2  = tagged.get("SecondStreetName", "").title()
    type2    = abbreviate_street_type(tagged.get("SecondStreetNamePostType", ""))
    pre_dir2 = abbreviate_direction(tagged.get("SecondStreetNamePreDirectional", ""))
    post_dir2= abbreviate_direction(tagged.get("SecondStreetNamePostDirectional", ""))

    city  = tagged.get("PlaceName", "").title()
    state = tagged.get("StateName", "").strip().upper()
    zipp  = normalize_zip(tagged.get("ZipCode", ""))

    side1_parts = [p for p in [pre_dir1, street1, type1, post_dir1] if p]
    side1 = " ".join(side1_parts)

    side2_parts = [p for p in [pre_type2, street2, type2, post_dir2, pre_dir2] if p]
    side2 = " ".join(side2_parts)

    intersection = f"{corner} {side1} {sep} {side2}".strip()

    csz_parts = [p for p in [city, state] if p]
    csz = ", ".join(csz_parts)
    if zipp:
        csz = f"{csz} {zipp}".strip()

    components = [p for p in [intersection, csz] if p]
    return ", ".join(components)

def normalize_address(raw: str) -> tuple[str, str]:
    """
    Normalize a single address string.
    Returns (normalized_address, status) where status is 'ok', 'review', or 'empty'.
    """
    raw = clean_whitespace(raw)
    raw = convert_leading_number_word(raw)
    raw = remove_periods(raw)
    if not raw:
        return ("", "empty")

    try:
        tagged, addr_type = usaddress.tag(raw)
        if addr_type == "Intersection":
            normalized = fix_punctuation(fix_highway_designators(lowercase_ordinals(assemble_intersection(tagged))))
        elif addr_type == "Street Address":
            normalized = fix_punctuation(fix_highway_designators(lowercase_ordinals(assemble_from_tags(tagged))))
        else:
            return (fix_punctuation(fix_highway_designators(lowercase_ordinals(smart_title(clean_whitespace(raw))))), "review")
        return (normalized, "ok")
    except usaddress.RepeatedLabelError:
        return (fix_punctuation(fix_highway_designators(lowercase_ordinals(smart_title(clean_whitespace(raw))))), "review")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(input_path: str, address_column: str, output_path: str) -> None:
    print(f"Reading '{input_path}' …")
    df = pd.read_csv(input_path, dtype=str).fillna("")

    if address_column not in df.columns:
        available = ", ".join(df.columns.tolist())
        raise ValueError(
            f"Column '{address_column}' not found. Available columns: {available}"
        )

    print(f"Normalizing {len(df):,} addresses in column '{address_column}' …")
    results = df[address_column].apply(normalize_address)

    df["Normalized_Address"] = results.apply(lambda x: x[0])
    df["Normalization_Status"] = results.apply(lambda x: x[1])

    ok_count     = (df["Normalization_Status"] == "ok").sum()
    review_count = (df["Normalization_Status"] == "review").sum()
    empty_count  = (df["Normalization_Status"] == "empty").sum()

    df.to_csv(output_path, index=False)
    print(f"\nDone! Results saved to '{output_path}'")
    print(f"  ✅  Normalized OK : {ok_count:,}")
    print(f"  ⚠️   Needs review  : {review_count:,}  (check Normalization_Status column)")
    print(f"  ⬜  Empty          : {empty_count:,}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize US addresses in a CSV file.")
    parser.add_argument("--input",   required=True,  help="Path to input CSV")
    parser.add_argument("--column",  required=True,  help="Name of the address column")
    parser.add_argument("--output",  required=True,  help="Path for the output CSV")
    args = parser.parse_args()

    run(args.input, args.column, args.output)
