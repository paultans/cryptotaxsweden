"""Unit tests for k4page.py module."""

import pytest
import os
import tempfile
import shutil

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from k4page import K4Page, K4Section


class MockPersonalDetails:
    """Mock personal details for testing."""
    def __init__(self):
        self.namn = "Test Person"
        self.personnummer = "19800101-1234"


class TestGetTemplatePath:
    """Tests for K4Page._get_template_path method."""

    def test_returns_specific_template_when_exists(self):
        """Should return year-specific template when it exists."""
        page = K4Page(
            year=2019,
            personal_details=MockPersonalDetails(),
            page_number=1,
            section_a=None,
            section_c=None,
            section_d=None
        )
        # Change to repo root for relative path resolution
        original_cwd = os.getcwd()
        os.chdir(Path(__file__).parent.parent)
        try:
            template_path = page._get_template_path()
            assert template_path == "docs/K4-template-2019.pdf"
            assert os.path.exists(template_path)
        finally:
            os.chdir(original_cwd)

    def test_falls_back_to_latest_template_for_future_year(self):
        """Should fall back to most recent template for years without specific template."""
        page = K4Page(
            year=2030,  # Far future year without template
            personal_details=MockPersonalDetails(),
            page_number=1,
            section_a=None,
            section_c=None,
            section_d=None
        )
        # Change to repo root for relative path resolution
        original_cwd = os.getcwd()
        os.chdir(Path(__file__).parent.parent)
        try:
            template_path = page._get_template_path()
            # Should fall back to 2025 (the latest available)
            assert "K4-template-2025.pdf" in template_path
            assert os.path.exists(template_path)
        finally:
            os.chdir(original_cwd)

    def test_raises_exception_when_no_templates_exist(self):
        """Should raise exception when no templates are available."""
        page = K4Page(
            year=2024,
            personal_details=MockPersonalDetails(),
            page_number=1,
            section_a=None,
            section_c=None,
            section_d=None
        )
        # Use a temp directory with no templates
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "docs"))
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with pytest.raises(Exception) as exc_info:
                    page._get_template_path()
                assert "No K4 template PDFs available" in str(exc_info.value)
            finally:
                os.chdir(original_cwd)


class TestK4Section:
    """Tests for K4Section class."""

    def test_section_creation(self):
        """K4Section should store lines and sums."""
        lines = [["1", "BTC", "100", "50", "50", None]]
        sums = [100, 50, 50, None]
        section = K4Section(lines=lines, sums=sums)
        assert section.lines == lines
        assert section.sums == sums
