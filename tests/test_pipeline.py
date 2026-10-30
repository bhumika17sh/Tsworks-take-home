"""
Unit tests for Movie Data Pipeline data transformations.
"""

import unittest
from etl import clean_movie_title, parse_box_office


class TestETLTransformations(unittest.TestCase):

    def test_clean_movie_title_standard(self):
        """Verifies extracting title, release year, and decade from standard titles."""
        title, year, decade = clean_movie_title("Toy Story (1995)")
        self.assertEqual(title, "Toy Story")
        self.assertEqual(year, 1995)
        self.assertEqual(decade, "1990s")

    def test_clean_movie_title_article_normalization(self):
        """Verifies moving trailing articles like ', The' to the front ('The Matrix')."""
        title, year, decade = clean_movie_title("Matrix, The (1999)")
        self.assertEqual(title, "The Matrix")
        self.assertEqual(year, 1999)
        self.assertEqual(decade, "1990s")

    def test_clean_movie_title_no_year(self):
        """Verifies handling movies without a release year in the title."""
        title, year, decade = clean_movie_title("Unknown Documentary")
        self.assertEqual(title, "Unknown Documentary")
        self.assertIsNone(year)
        self.assertIsNone(decade)

    def test_clean_movie_title_none_or_empty(self):
        """Verifies handling empty or null titles gracefully."""
        title, year, decade = clean_movie_title("")
        self.assertEqual(title, "Unknown")
        self.assertIsNone(year)
        self.assertIsNone(decade)

    def test_parse_box_office_valid_currency(self):
        """Verifies converting '$373,554,033' currency strings to float numbers."""
        self.assertEqual(parse_box_office("$373,554,033"), 373554033.0)
        self.assertEqual(parse_box_office("$1,200.50"), 1200.50)
        self.assertEqual(parse_box_office("150000"), 150000.0)

    def test_parse_box_office_invalid_or_na(self):
        """Verifies converting 'N/A' or missing box office values to None."""
        self.assertIsNone(parse_box_office("N/A"))
        self.assertIsNone(parse_box_office(""))
        self.assertIsNone(parse_box_office(None))


if __name__ == "__main__":
    unittest.main()
