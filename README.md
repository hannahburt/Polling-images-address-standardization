# Address Normalization Script

A Python script that standardizes US address formatting in bulk. Designed for CSV files exported from Google Sheets, with output ready to re-import.

---

## Requirements

- Python 3.8 or higher
- The following libraries:

```bash
pip3 install pandas usaddress
```

---

## Usage

```bash
python3 normalize_addresses.py --input addresses.csv --column "Address" --output normalized.csv
```

### Arguments

| Argument | Description |
|---|---|
| `--input` | Path to your input CSV file |
| `--column` | Name of the column containing addresses |
| `--output` | Path for the output CSV file |

---

## How to Use with Google Sheets

1. In Google Sheets, go to **File → Download → Comma Separated Values (.csv)**
2. Save the script and your CSV to the same folder (e.g. Downloads)
3. Open Terminal and navigate to that folder:
   ```bash
   cd ~/Downloads
   ```
4. Run the script:
   ```bash
   python3 normalize_addresses.py --input addresses.csv --column "Address" --output normalized.csv
   ```
5. Re-import the output into Google Sheets via **File → Import → Upload**

---

## What the Script Does

1. **Reads your CSV** and finds the address column you specify
2. **Cleans up whitespace** — trims leading/trailing spaces and collapses any double spaces
3. **Converts spelled-out address numbers** — converts one through ten at the start of an address to digits (e.g. `One Main St` → `1 Main St`). Numbers eleven and above are left as-is
4. **Removes periods** — strips any periods from the address (e.g. `N.W.` → `NW`)
5. **Parses the address** using the `usaddress` library, which breaks it into components like street number, street name, street type, city, state, and zip
6. **Abbreviates street types** — e.g. `Street → St`, `Avenue → Ave`, `Boulevard → Blvd`. Unrecognized street types are title-cased
7. **Abbreviates cardinal directions** — e.g. `North → N`, `Southeast → SE`. Handles both fully spelled-out and already-abbreviated inputs
8. **Preserves rural and highway road types** — `Route`, `County Road`, `US Hwy`, `State Hwy`, etc. are kept intact
9. **Fixes casing:**
   - Street names and city are title-cased
   - State is uppercased
   - Ordinal indicators are lowercased (`1St → 1st`, `23Rd → 23rd`)
   - Highway designators are uppercased (`Us → US`, `Ih → IH`, `Fm → FM`, `Sh → SH`)
   - Apostrophe-s is lowercased (`McDonald'S → McDonald's`)
10. **Fixes # formatting** — removes the extra space between `#` and the unit number (`# 101 → #101`)
11. **Reassembles the address** into a single clean line in a consistent format
12. **Flags problem rows** — anything it can't confidently parse (PO boxes, ambiguous addresses, etc.) gets marked as `review` in a status column so you can check them manually. Review rows go through the same casing and punctuation fixes as normal rows
13. **Writes the output CSV** with two new columns added: the normalized address and the status, ready to re-import into Google Sheets

---

## Output

The output CSV will contain all your original columns plus two new ones:

| Column | Description |
|---|---|
| `Normalized_Address` | The cleaned and standardized address |
| `Normalization_Status` | `ok` — parsed successfully, `review` — needs manual check, `empty` — no address found |

To quickly find rows that need attention, filter the `Normalization_Status` column to `review` in Google Sheets.

---

## Examples

| Input | Output |
|---|---|
| `123 NORTH MAIN STREET, AUSTIN, TX 78701` | `123 N Main St, Austin, TX 78701` |
| `456 2ND AVENUE APT # 4B` | `456 2nd Ave, Apt #4B` |
| `One University Way, Boston MA 02115` | `1 University Way, Boston, MA 02115` |
| `6322 US HWY 87 E, SAN ANTONIO TX 78222` | `6322 US Hwy 87 E, San Antonio, TX 78222` |
| `404 COUNTY ROAD 519, AUSTIN TX 78701` | `404 County Road 519, Austin, TX 78701` |
| `5145 N FM 620, AUSTIN TX 78732` | `5145 N FM 620, Austin, TX 78732` |

---

## Limitations

- Designed for **US addresses only**
- Spelled-out address numbers **eleven and above** are not converted to digits
- Addresses that are ambiguous or non-standard (e.g. PO boxes, rural routes without enough detail) will be flagged as `review` rather than normalized
- Does not validate whether an address actually exists — for that, consider a geocoding API like Google Maps or SmartyStreets
