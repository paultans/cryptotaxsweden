"""Tests for T2 form generation."""

import pytest
from t2page import T2Data, T2Page, generate_t2_sru
import os
import tempfile


class TestT2Data:
    """Tests for T2Data calculations."""

    def test_simple_income_surplus(self):
        """Test simple income with no expenses results in surplus."""
        data = T2Data(inkomster=10000)
        assert data.b4_overskott == 10000
        assert data.b5_underskott == 0
        assert data.c3_overskott == 10000
        assert data.d1_overskott == 10000

    def test_income_with_expenses(self):
        """Test income minus expenses."""
        data = T2Data(inkomster=10000, kontanta_utgifter=3000)
        assert data.b4_overskott == 7000
        assert data.b5_underskott == 0

    def test_income_with_expenses_and_depreciation(self):
        """Test income minus expenses and depreciation."""
        data = T2Data(inkomster=10000, kontanta_utgifter=3000, forslitningsavdrag=2000)
        assert data.b4_overskott == 5000
        assert data.b5_underskott == 0

    def test_deficit_when_expenses_exceed_income(self):
        """Test deficit when expenses exceed income."""
        data = T2Data(inkomster=5000, kontanta_utgifter=8000)
        assert data.b4_overskott == 0
        assert data.b5_underskott == 3000
        assert data.d1_overskott == 0  # No surplus means 0 for egenavgifter calc

    def test_previous_deficit_deduction(self):
        """Test deduction of previous years' deficit."""
        data = T2Data(
            inkomster=10000,
            tidigare_underskott=3000,
            underskott_years=[2023, 2024]
        )
        assert data.b4_overskott == 10000
        assert data.c3_overskott == 7000  # 10000 - 3000

    def test_previous_deficit_capped_at_surplus(self):
        """Test that deficit deduction can't exceed current surplus."""
        data = T2Data(
            inkomster=5000,
            tidigare_underskott=10000,  # More than income
            underskott_years=[2023]
        )
        assert data.b4_overskott == 5000
        assert data.c3_overskott == 0  # Capped at surplus

    def test_schablonavdrag_calculation_25_percent(self):
        """Test 25% standard deduction for egenavgifter."""
        data = T2Data(inkomster=10000, schablon_percent=0.25)
        assert data.d1_overskott == 10000
        assert data.d4_result == 10000
        assert data.d5_schablonavdrag == 2500  # 25% of 10000
        assert data.d6_overskott == 7500  # 10000 - 2500

    def test_schablonavdrag_calculation_10_percent(self):
        """Test 10% standard deduction (for older taxpayers)."""
        data = T2Data(inkomster=10000, schablon_percent=0.10)
        assert data.d5_schablonavdrag == 1000  # 10% of 10000
        assert data.d6_overskott == 9000  # 10000 - 1000

    def test_egenavgifter_reconciliation(self):
        """Test reconciliation with previous year's egenavgifter."""
        data = T2Data(
            inkomster=10000,
            foregaende_schablonavdrag=2000,  # Last year's deduction
            paforda_egenavgifter=1800,       # Actual assessed amount
            schablon_percent=0.25
        )
        # D.4 = 10000 + 2000 - 1800 = 10200
        assert data.d4_result == 10200
        # D.5 = 25% of 10200 = 2550
        assert data.d5_schablonavdrag == 2550
        # D.6 = 10200 - 2550 = 7650
        assert data.d6_overskott == 7650

    def test_underskott_from_egenavgifter(self):
        """Test deficit result from egenavgifter reconciliation."""
        data = T2Data(
            inkomster=5000,
            foregaende_schablonavdrag=1000,
            paforda_egenavgifter=6500,  # More than expected
            schablon_percent=0.25
        )
        # D.4 = 5000 + 1000 - 6500 = -500
        assert data.d4_result == -500
        # No schablonavdrag when negative
        assert data.d5_schablonavdrag == 0
        # Deficit result
        assert data.d6_overskott == 0
        assert data.d6_underskott == 500


class TestT2Page:
    """Tests for T2Page SRU generation."""

    def test_generate_sru_lines_basic(self):
        """Test basic SRU line generation."""
        from taxdata import PersonalDetails

        personal = PersonalDetails(
            namn="Test Person",
            personnummer="19850101-1234",
            postnummer="12345",
            postort="Stockholm"
        )
        data = T2Data(
            verksamhet_art="Kryptovaluta - hobby",
            inkomster=50000
        )
        page = T2Page(2024, personal, 1, data)
        lines = page.generate_sru_lines()

        # Check structure
        assert lines[0] == "#BLANKETT T2-2024P4"
        assert "#IDENTITET" in lines[1]
        assert "198501011234" in lines[1]  # Personnummer without dash
        assert "#NAMN Test Person" in lines
        assert "#BLANKETTSLUT" == lines[-1]

        # Check that income is included (field 2201)
        income_line = [l for l in lines if "2201" in l]
        assert len(income_line) == 1
        assert "50000" in income_line[0]

    def test_generate_sru_lines_with_expenses(self):
        """Test SRU generation with expenses."""
        from taxdata import PersonalDetails

        personal = PersonalDetails("Test", "19850101-1234", "12345", "Stockholm")
        data = T2Data(
            inkomster=50000,
            kontanta_utgifter=10000,
            forslitningsavdrag=5000
        )
        page = T2Page(2024, personal, 1, data)
        lines = page.generate_sru_lines()

        # Find expense lines (fields 2202, 2203)
        sru_text = "\n".join(lines)
        assert "2202" in sru_text  # Expenses field
        assert "10000" in sru_text
        assert "2203" in sru_text  # Depreciation field
        assert "5000" in sru_text


class TestGenerateT2Sru:
    """Tests for T2 SRU file generation."""

    def test_creates_standalone_sru_file(self):
        """Test creating standalone T2 SRU files."""
        from taxdata import PersonalDetails

        personal = PersonalDetails("Test", "19850101-1234", "12345", "Stockholm")
        data = T2Data(inkomster=10000)
        page = T2Page(2024, personal, 1, data)

        with tempfile.TemporaryDirectory() as tmpdir:
            generate_t2_sru([page], personal, tmpdir, append_to_blanketter=False)

            # Check files exist
            assert os.path.exists(os.path.join(tmpdir, "blanketter.sru"))
            assert os.path.exists(os.path.join(tmpdir, "info.sru"))

            # Check content
            with open(os.path.join(tmpdir, "blanketter.sru"), "r", encoding="iso-8859-1") as f:
                content = f.read()
            assert "#BLANKETT T2-2024P4" in content
            assert "#FIL_SLUT" in content

    def test_appends_to_existing_file(self):
        """Test appending T2 to existing blanketter.sru (e.g., after K4)."""
        from taxdata import PersonalDetails

        personal = PersonalDetails("Test", "19850101-1234", "12345", "Stockholm")
        data = T2Data(inkomster=10000)
        page = T2Page(2024, personal, 1, data)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an existing file with K4-like content
            existing_content = """#BLANKETT K4-2024P4
#IDENTITET 198501011234 20240501 120000
#NAMN Test
#UPPGIFT 7014 1
#BLANKETTSLUT
#FIL_SLUT
"""
            blanketter_path = os.path.join(tmpdir, "blanketter.sru")
            with open(blanketter_path, "w", encoding="iso-8859-1") as f:
                f.write(existing_content)

            # Append T2
            generate_t2_sru([page], personal, tmpdir, append_to_blanketter=True)

            # Check combined content
            with open(blanketter_path, "r", encoding="iso-8859-1") as f:
                content = f.read()

            assert "#BLANKETT K4-2024P4" in content  # Original K4 preserved
            assert "#BLANKETT T2-2024P4" in content  # T2 added
            assert content.count("#FIL_SLUT") == 1   # Only one file end marker
            assert content.strip().endswith("#FIL_SLUT")  # File ends correctly
