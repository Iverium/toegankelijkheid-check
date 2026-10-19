"""Quick automatic accessibility (WCAG) check, with Dutch reports. https://github.com/Iverium/toegankelijkheid-check"""
from ._common import CheckError, format_report
from .check import analyse, check_accessibility

__version__ = "1.0.0"
__all__ = ["CheckError", "analyse", "check_accessibility", "format_report"]
