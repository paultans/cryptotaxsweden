"""T2 form generation for Swedish tax reporting.

This module handles the generation of T2 forms in SRU (digital) format
for Skatteverket. T2 is used for hobby income (inkomst av tjänst).

T2 Field Codes (SKV 269 fältnamnstabell):
Field codes are in the 2200 range per SKV 269 documentation.
- Section A: Verksamhetens art (activity description) - field 7020
- Section B: Årets inkomster och utgifter (income and expenses) - fields 2201-2205
- Section C: Avdrag för tidigare års underskott (previous deficit deductions) - fields 2211-2223
- Section D: Egenavgifter (self-employment contributions) - fields 2230-2236
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import os


# T2 SRU Field Codes (from SKV 269 fältnamnstabell)

# Page/form metadata
T2_PAGE_NUMBER_FIELD = 7014  # Numrering vid flera T2

# Section A - Verksamhetens art
T2_VERKSAMHET_ART = 7020  # Beskriv din hobby (text description)

# Section B - Årets inkomster och utgifter
T2_B1_INKOMSTER = 2201          # B.1 Inkomster (+)
T2_B2_KONTANTA_UTGIFTER = 2202  # B.2 Kontanta utgifter (-)
T2_B3_FORSLITNING = 2203        # B.3 Förslitningsavdrag (-)
T2_B4_OVERSKOTT = 2204          # B.4 Överskott (=)
T2_B5_UNDERSKOTT = 2205         # B.5 Underskott (=)

# Section C - Avdrag för tidigare års underskott
T2_C1_ARETS_OVERSKOTT = 2211    # C.1 Årets överskott enligt B.4
T2_C2_AVDRAG_UNDERSKOTT = 2212  # C.2 Avdrag för underskott från tidigare år
T2_C3_OVERSKOTT = 2213          # C.3 Överskott

# Year checkboxes for deficit years
# NOTE: These codes shift each year - verify for current tax year
# For tax year 2025 (declaration 2026), deficits from 2020-2024 can be used
# The field codes below are based on the pattern from SKV 269
# They may need adjustment based on current year's fältnamnstabell
T2_C2_AR_2020 = 2219  # Underskott inkomstår 2020
T2_C2_AR_2021 = 2220  # Underskott inkomstår 2021
T2_C2_AR_2022 = 2221  # Underskott inkomstår 2022
T2_C2_AR_2023 = 2222  # Underskott inkomstår 2023
T2_C2_AR_2024 = 2223  # Underskott inkomstår 2024

# Section D - Egenavgifter m.m.
T2_D1_OVERSKOTT = 2230          # D.1 Överskott eller 0 kr
T2_D2_FOREGAENDE_SCHABLONAV = 2232  # D.2 Föregående års schablonavdrag
T2_D3_PAFORDA_EGENAVG = 2231    # D.3 Påförda egenavgifter enligt slutskattebesked
T2_D4_OVERSKOTT_UNDERSKOTT = 2233  # D.4 Överskott/Underskott
T2_D5_ARETS_SCHABLONAV = 2234   # D.5 Årets schablonavdrag
T2_D6_RESULTAT_OVERSKOTT = 2235  # D.6 Resultat - Överskott
T2_D6_RESULTAT_UNDERSKOTT = 2236  # D.6 Resultat - Underskott vid avstämning


@dataclass
class T2Data:
    """Data for a T2 form submission.

    For crypto hobby income, typically only section B income is used,
    with automatic calculation of egenavgifter in section D.
    """
    # Activity description
    verksamhet_art: str = "Kryptovaluta - hobby (staking, mining m.m.)"

    # Section B - Income and expenses
    inkomster: int = 0           # B.1 Total income
    kontanta_utgifter: int = 0   # B.2 Cash expenses
    forslitningsavdrag: int = 0  # B.3 Depreciation

    # Section C - Previous deficit deductions (optional)
    tidigare_underskott: int = 0  # C.2 Amount to deduct
    underskott_years: List[int] = None  # Years the deficit is from (2020-2024)

    # Section D - Previous year's egenavgifter reconciliation (for subsequent years)
    foregaende_schablonavdrag: int = 0  # D.2 Previous year standard deduction
    paforda_egenavgifter: int = 0        # D.3 Assessed contributions from slutskattebesked

    # Schablonavdrag percentage (default 25% for born 1959 or later)
    schablon_percent: float = 0.25

    def __post_init__(self):
        if self.underskott_years is None:
            self.underskott_years = []

    @property
    def b4_overskott(self) -> int:
        """Calculate B.4 surplus (if positive)."""
        result = self.inkomster - self.kontanta_utgifter - self.forslitningsavdrag
        return max(0, result)

    @property
    def b5_underskott(self) -> int:
        """Calculate B.5 deficit (if negative)."""
        result = self.inkomster - self.kontanta_utgifter - self.forslitningsavdrag
        return abs(min(0, result))

    @property
    def c3_overskott(self) -> int:
        """Calculate C.3 surplus after previous deficit deductions."""
        # Can only deduct up to this year's surplus
        deduction = min(self.tidigare_underskott, self.b4_overskott)
        return self.b4_overskott - deduction

    @property
    def d1_overskott(self) -> int:
        """Calculate D.1 - surplus to use for egenavgifter calc, or 0 if deficit."""
        if self.b5_underskott > 0:
            return 0
        return self.c3_overskott

    @property
    def d4_result(self) -> int:
        """Calculate D.4 surplus/deficit from egenavgifter reconciliation."""
        return (self.d1_overskott +
                self.foregaende_schablonavdrag -
                self.paforda_egenavgifter)

    @property
    def d5_schablonavdrag(self) -> int:
        """Calculate D.5 this year's standard deduction for egenavgifter."""
        if self.d4_result <= 0:
            return 0
        return round(self.d4_result * self.schablon_percent)

    @property
    def d6_overskott(self) -> int:
        """Calculate D.6 final surplus (for INK1 p.1.6)."""
        result = self.d4_result - self.d5_schablonavdrag
        return max(0, result)

    @property
    def d6_underskott(self) -> int:
        """Calculate D.6 deficit from egenavgifter (for INK1 p.2.3)."""
        result = self.d4_result - self.d5_schablonavdrag
        return abs(min(0, result))


class T2Page:
    """Represents a single T2 form page for SRU generation."""

    def __init__(
        self,
        year: int,
        personal_details,  # PersonalDetails from taxdata
        page_number: int,
        data: T2Data
    ):
        self._year = year
        self._personal_details = personal_details
        self._page_number = page_number
        self._data = data

    def generate_sru_lines(self) -> List[str]:
        """Generate SRU format lines for this T2 page.

        Returns:
            List of SRU-formatted strings for the blanketter.sru file.
        """
        blankettkod = f"T2-{self._year}P4"
        now = datetime.now()
        generated_date = now.strftime("%Y%m%d")
        generated_time = now.strftime("%H%M%S")

        lines: List[str] = []
        lines.append(f"#BLANKETT {blankettkod}")
        lines.append(
            f"#IDENTITET {self._personal_details.personnummer.replace('-', '')} "
            f"{generated_date} {generated_time}"
        )
        lines.append(f"#NAMN {self._personal_details.namn}")

        # Page number (if multiple T2 forms)
        if self._page_number > 1:
            lines.append(f"#UPPGIFT {T2_PAGE_NUMBER_FIELD} {self._page_number}")

        # Section A - Activity description
        # Note: Text fields in SRU may have length limits
        verksamhet = self._data.verksamhet_art[:50]  # Limit length
        lines.append(f"#UPPGIFT {T2_VERKSAMHET_ART} {verksamhet}")

        # Section B - Income and expenses
        if self._data.inkomster > 0:
            lines.append(f"#UPPGIFT {T2_B1_INKOMSTER} {self._data.inkomster}")

        if self._data.kontanta_utgifter > 0:
            lines.append(f"#UPPGIFT {T2_B2_KONTANTA_UTGIFTER} {self._data.kontanta_utgifter}")

        if self._data.forslitningsavdrag > 0:
            lines.append(f"#UPPGIFT {T2_B3_FORSLITNING} {self._data.forslitningsavdrag}")

        # B.4 or B.5 (surplus or deficit)
        if self._data.b4_overskott > 0:
            lines.append(f"#UPPGIFT {T2_B4_OVERSKOTT} {self._data.b4_overskott}")
        elif self._data.b5_underskott > 0:
            lines.append(f"#UPPGIFT {T2_B5_UNDERSKOTT} {self._data.b5_underskott}")

        # Section C - Previous deficit deductions (only if there's a surplus to deduct from)
        if self._data.b4_overskott > 0:
            lines.append(f"#UPPGIFT {T2_C1_ARETS_OVERSKOTT} {self._data.b4_overskott}")

            if self._data.tidigare_underskott > 0:
                deduction = min(self._data.tidigare_underskott, self._data.b4_overskott)
                lines.append(f"#UPPGIFT {T2_C2_AVDRAG_UNDERSKOTT} {deduction}")

                # Mark which years the deficit is from
                year_fields = {
                    2020: T2_C2_AR_2020,
                    2021: T2_C2_AR_2021,
                    2022: T2_C2_AR_2022,
                    2023: T2_C2_AR_2023,
                    2024: T2_C2_AR_2024,
                }
                for deficit_year in self._data.underskott_years:
                    if deficit_year in year_fields:
                        lines.append(f"#UPPGIFT {year_fields[deficit_year]} X")

            lines.append(f"#UPPGIFT {T2_C3_OVERSKOTT} {self._data.c3_overskott}")

        # Section D - Egenavgifter calculation
        lines.append(f"#UPPGIFT {T2_D1_OVERSKOTT} {self._data.d1_overskott}")

        if self._data.foregaende_schablonavdrag > 0:
            lines.append(f"#UPPGIFT {T2_D2_FOREGAENDE_SCHABLONAV} {self._data.foregaende_schablonavdrag}")

        if self._data.paforda_egenavgifter > 0:
            lines.append(f"#UPPGIFT {T2_D3_PAFORDA_EGENAVG} {self._data.paforda_egenavgifter}")

        if self._data.d4_result != 0:
            lines.append(f"#UPPGIFT {T2_D4_OVERSKOTT_UNDERSKOTT} {self._data.d4_result}")

        if self._data.d5_schablonavdrag > 0:
            lines.append(f"#UPPGIFT {T2_D5_ARETS_SCHABLONAV} {self._data.d5_schablonavdrag}")

        # D.6 Final result
        if self._data.d6_overskott > 0:
            lines.append(f"#UPPGIFT {T2_D6_RESULTAT_OVERSKOTT} {self._data.d6_overskott}")
        elif self._data.d6_underskott > 0:
            lines.append(f"#UPPGIFT {T2_D6_RESULTAT_UNDERSKOTT} {self._data.d6_underskott}")

        lines.append("#BLANKETTSLUT")

        return lines


def generate_t2_sru(
    pages: List[T2Page],
    personal_details,
    destination_folder: str,
    append_to_blanketter: bool = True
) -> None:
    """Generate T2 SRU files for digital submission.

    Args:
        pages: List of T2Page objects to generate.
        personal_details: PersonalDetails object with taxpayer info.
        destination_folder: Directory to write SRU files.
        append_to_blanketter: If True, append to existing blanketter.sru
                             (for combining with K4). If False, create new file.
    """
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Generate T2 blankett lines
    t2_lines: List[str] = []
    for page in pages:
        t2_lines.extend(page.generate_sru_lines())

    blanketter_path = os.path.join(destination_folder, "blanketter.sru")

    if append_to_blanketter and os.path.exists(blanketter_path):
        # Read existing file and insert T2 before #FIL_SLUT
        with open(blanketter_path, "r", encoding="iso-8859-1") as f:
            existing = f.read()

        # Remove #FIL_SLUT and trailing newlines
        existing = existing.rstrip()
        if existing.endswith("#FIL_SLUT"):
            existing = existing[:-9].rstrip()

        # Combine and write
        all_lines = existing + "\n" + "\n".join(t2_lines) + "\n#FIL_SLUT\n"
        with open(blanketter_path, "w", encoding="iso-8859-1") as f:
            f.write(all_lines)
    else:
        # Write new file
        t2_lines.append("#FIL_SLUT")
        t2_lines.append("")
        with open(blanketter_path, "w", encoding="iso-8859-1") as f:
            f.write("\n".join(t2_lines))

        # Also need to create info.sru if not appending
        if not append_to_blanketter:
            info_lines: List[str] = []
            info_lines.append("#DATABESKRIVNING_START")
            info_lines.append("#PRODUKT SRU")
            info_lines.append("#FILNAMN BLANKETTER.SRU")
            info_lines.append("#DATABESKRIVNING_SLUT")
            info_lines.append("#MEDIELEV_START")
            info_lines.append(f"#ORGNR {personal_details.personnummer}")
            info_lines.append(f"#NAMN {personal_details.namn}")
            info_lines.append(f"#POSTNR {personal_details.postnummer}")
            info_lines.append(f"#POSTORT {personal_details.postort}")
            info_lines.append("#MEDIELEV_SLUT")
            info_lines.append("")

            with open(os.path.join(destination_folder, "info.sru"), "w", encoding="iso-8859-1") as f:
                f.write("\n".join(info_lines))
