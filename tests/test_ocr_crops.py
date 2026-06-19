import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil
from PIL import Image

# We import the functions to test. Since they do not exist yet,
# running this test file initially will fail (Red phase).
from src.image.ocr_crops import run_ocr_on_crops, check_tesseract_availability


class TestOcrCrops(unittest.TestCase):
    def setUp(self):
        # Create a temporary crop image for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.crop_path = Path(self.temp_dir.name) / "test_crop.png"
        img = Image.new("RGB", (50, 20), "white")
        img.save(self.crop_path)

        self.crops_metadata = [
            {
                "region_id": "RED-001",
                "crop_path": str(self.crop_path),
                "bbox_image": [10, 10, 20, 20],
                "crop_bbox_image": [5, 5, 25, 25]
            }
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("shutil.which")
    def test_check_tesseract_availability_present(self, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"
        self.assertTrue(check_tesseract_availability())
        mock_which.assert_called_once_with("tesseract")

    @patch("shutil.which")
    def test_check_tesseract_availability_absent(self, mock_which):
        mock_which.return_value = None
        self.assertFalse(check_tesseract_availability())

    @patch("shutil.which")
    @patch("pytesseract.image_to_string")
    def test_run_ocr_successful_deu_eng(self, mock_image_to_string, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"
        mock_image_to_string.return_value = "  WDB 70/20 OK -60  \n"

        results = run_ocr_on_crops(self.crops_metadata, psm=6)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["region_id"], "RED-001")
        self.assertEqual(res["crop_path"], str(self.crop_path))
        self.assertEqual(res["ocr_text"], "WDB 70/20 OK -60")
        self.assertTrue(res["ocr_available"])
        self.assertEqual(res["requested_lang"], "deu+eng")
        self.assertEqual(res["used_lang"], "deu+eng")
        self.assertIsNone(res.get("warning"))

        mock_image_to_string.assert_called_once()
        # Ensure it was called with lang="deu+eng", config="--psm 6" (or equivalent)
        kwargs = mock_image_to_string.call_args[1]
        self.assertEqual(kwargs.get("lang"), "deu+eng")
        self.assertIn("--psm 6", kwargs.get("config", ""))

    @patch("shutil.which")
    @patch("pytesseract.image_to_string")
    def test_run_ocr_fallback_to_eng(self, mock_image_to_string, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"

        # Side effect: first call (deu+eng) fails, second call (eng) succeeds
        from pytesseract import TesseractError
        # A simple exception representing missing lang pack or other error
        err = TesseractError(1, "Error opening translation file")
        mock_image_to_string.side_effect = [err, "  WDB 70/20  "]

        results = run_ocr_on_crops(self.crops_metadata, psm=6)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["ocr_text"], "WDB 70/20")
        self.assertTrue(res["ocr_available"])
        self.assertEqual(res["used_lang"], "eng")
        self.assertIn("deu+eng failed", res["warning"])

        self.assertEqual(mock_image_to_string.call_count, 2)
        # Check call arguments
        call1_kwargs = mock_image_to_string.call_args_list[0][1]
        call2_kwargs = mock_image_to_string.call_args_list[1][1]
        self.assertEqual(call1_kwargs.get("lang"), "deu+eng")
        self.assertEqual(call2_kwargs.get("lang"), "eng")

    @patch("shutil.which")
    @patch("pytesseract.image_to_string")
    def test_run_ocr_fallback_to_default_no_lang(self, mock_image_to_string, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"

        # Side effect: first and second calls fail, third (no lang) succeeds
        from pytesseract import TesseractError
        err = TesseractError(1, "Error opening translation file")
        mock_image_to_string.side_effect = [err, err, "  WDB 70/20  "]

        results = run_ocr_on_crops(self.crops_metadata, psm=6)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["ocr_text"], "WDB 70/20")
        self.assertTrue(res["ocr_available"])
        self.assertIsNone(res["used_lang"])
        self.assertIn("eng failed", res["warning"])

        self.assertEqual(mock_image_to_string.call_count, 3)
        call3_kwargs = mock_image_to_string.call_args_list[2][1]
        self.assertNotIn("lang", call3_kwargs)

    @patch("shutil.which")
    @patch("pytesseract.image_to_string")
    def test_run_ocr_all_fallbacks_fail(self, mock_image_to_string, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"

        # Side effect: all calls fail
        from pytesseract import TesseractError
        err = TesseractError(1, "Error running tesseract")
        mock_image_to_string.side_effect = err

        results = run_ocr_on_crops(self.crops_metadata, psm=6)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["ocr_text"], "")
        self.assertFalse(res["ocr_available"])
        self.assertIsNone(res["used_lang"])
        self.assertIn("OCR completely failed", res["warning"])

    @patch("shutil.which")
    def test_run_ocr_missing_binary(self, mock_which):
        mock_which.return_value = None

        results = run_ocr_on_crops(self.crops_metadata, psm=6)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["ocr_text"], "")
        self.assertFalse(res["ocr_available"])
        self.assertIsNone(res["used_lang"])
        self.assertEqual(res["warning"], "Tesseract binary not found in PATH")

    @patch("shutil.which")
    @patch("pytesseract.image_to_string")
    def test_run_ocr_empty_text(self, mock_image_to_string, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"
        mock_image_to_string.return_value = "   \n  "

        results = run_ocr_on_crops(self.crops_metadata, psm=6)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["ocr_text"], "")
        self.assertTrue(res["ocr_available"])
        self.assertEqual(res["used_lang"], "deu+eng")

    @patch("shutil.which")
    @patch("pytesseract.image_to_string")
    def test_clean_red_mode_keeps_the_more_complete_original_ocr_result(
        self,
        mock_image_to_string,
        mock_which,
    ):
        mock_which.return_value = "/usr/bin/tesseract"
        mock_image_to_string.side_effect = [
            "RA -65 UKRD",
            "DDB HSI150 RA -65 UKRD",
        ]

        results = run_ocr_on_crops(self.crops_metadata, psm=11, clean_red=True)

        self.assertEqual(results[0]["ocr_text"], "DDB HSI150 RA -65 UKRD")
        self.assertEqual(mock_image_to_string.call_count, 2)
        for call in mock_image_to_string.call_args_list:
            self.assertIn("--psm 11", call.kwargs["config"])


if __name__ == "__main__":
    unittest.main()
