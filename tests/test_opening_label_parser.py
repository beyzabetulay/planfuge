import unittest

from src.candidates.opening_label_parser import parse_opening_label


class OpeningLabelParserTest(unittest.TestCase):
    def test_parse_wdb_dimensions_and_ok_reference(self):
        parsed = parse_opening_label("WDB 70/20 OK -60 UKRD")

        self.assertEqual(
            parsed,
            {
                "label_type": "WDB",
                "width_mm": 700,
                "height_mm": 200,
                "diameter_mm": None,
                "ra_value": None,
                "ok_value": -60,
                "reference": "UKRD",
            },
        )

    def test_parse_compact_ddb_dimensions(self):
        parsed = parse_opening_label("DDB130/140")

        self.assertEqual(parsed["label_type"], "DDB")
        self.assertEqual(parsed["width_mm"], 1300)
        self.assertEqual(parsed["height_mm"], 1400)
        self.assertIsNone(parsed["diameter_mm"])

    def test_parse_short_wd_and_dd_aliases(self):
        wd = parse_opening_label("WD 40/20 UKD")
        dd = parse_opening_label("DD 80/15 (H)")
        wd_ocr_zero = parse_opening_label("WD 20/2C UKD")

        self.assertEqual(wd["label_type"], "WDB")
        self.assertEqual(wd["width_mm"], 400)
        self.assertEqual(wd["height_mm"], 200)
        self.assertEqual(dd["label_type"], "DDB")
        self.assertEqual(dd["width_mm"], 800)
        self.assertEqual(dd["height_mm"], 150)
        self.assertEqual(wd_ocr_zero["label_type"], "WDB")
        self.assertEqual(wd_ocr_zero["width_mm"], 200)
        self.assertEqual(wd_ocr_zero["height_mm"], 200)

    def test_parse_diameter_symbol(self):
        parsed = parse_opening_label("DDP Ø150 RA -45 UKRD")

        self.assertEqual(parsed["label_type"], "DDP")
        self.assertEqual(parsed["diameter_mm"], 150)
        self.assertEqual(parsed["ra_value"], -45)
        self.assertIsNone(parsed["ok_value"])
        self.assertEqual(parsed["reference"], "UKRD")

    def test_parse_short_diameter_as_centimeters(self):
        parsed = parse_opening_label("WDB Ø15 RA -80 UKRD")

        self.assertEqual(parsed["label_type"], "WDB")
        self.assertEqual(parsed["diameter_mm"], 150)
        self.assertEqual(parsed["ra_value"], -80)
        self.assertEqual(parsed["reference"], "UKRD")

    def test_parse_ddp_hsi_diameter(self):
        parsed = parse_opening_label("DDP HSI150 RA -50 UKRD")

        self.assertEqual(parsed["label_type"], "DDP")
        self.assertEqual(parsed["diameter_mm"], 150)
        self.assertEqual(parsed["ra_value"], -50)
        self.assertEqual(parsed["reference"], "UKRD")

    def test_parse_hsi_diameter(self):
        parsed = parse_opening_label("HSI150 OK 0 UKRD")

        self.assertEqual(parsed["label_type"], "HSI")
        self.assertEqual(parsed["diameter_mm"], 150)
        self.assertEqual(parsed["ok_value"], 0)
        self.assertEqual(parsed["reference"], "UKRD")

    def test_parse_non_candidate_returns_none(self):
        self.assertIsNone(parse_opening_label("Scale 1:50 UKRD"))

    def test_parse_other_reference_values(self):
        self.assertEqual(parse_opening_label("WDB 20/30 OKRB")["reference"], "OKRB")
        self.assertEqual(parse_opening_label("WDB 20/30 UKRB")["reference"], "UKRB")

    def test_parse_ocr_misread_diameter_symbols(self):
        # 1. WDB @25 -> label_type WDB, diameter_mm 250
        parsed1 = parse_opening_label("WDB @25")
        self.assertEqual(parsed1["label_type"], "WDB")
        self.assertEqual(parsed1["diameter_mm"], 250)

        # 2. WDB @15 -> label_type WDB, diameter_mm 150
        parsed2 = parse_opening_label("WDB @15")
        self.assertEqual(parsed2["label_type"], "WDB")
        self.assertEqual(parsed2["diameter_mm"], 150)

        # 3. WDB 015 RA -97 UKRD -> label_type WDB, diameter_mm 150, ra_value -97, reference UKRD
        parsed3 = parse_opening_label("WDB 015 RA -97 UKRD")
        self.assertEqual(parsed3["label_type"], "WDB")
        self.assertEqual(parsed3["diameter_mm"], 150)
        self.assertEqual(parsed3["ra_value"], -97)
        self.assertEqual(parsed3["reference"], "UKRD")

        # 4. WDB @25 RA -125 UKRD -> label_type WDB, diameter_mm 250, ra_value -125, reference UKRD
        parsed4 = parse_opening_label("WDB @25 RA -125 UKRD")
        self.assertEqual(parsed4["label_type"], "WDB")
        self.assertEqual(parsed4["diameter_mm"], 250)
        self.assertEqual(parsed4["ra_value"], -125)
        self.assertEqual(parsed4["reference"], "UKRD")

        # 5. DDB 916 -> label_type DDB, diameter_mm 160
        parsed5 = parse_opening_label("DDB 916")
        self.assertEqual(parsed5["label_type"], "DDB")
        self.assertEqual(parsed5["diameter_mm"], 160)

        # 6. DDB Bio -> label_type DDB, diameter_mm 100
        parsed6 = parse_opening_label("DDB Bio")
        self.assertEqual(parsed6["label_type"], "DDB")
        self.assertEqual(parsed6["diameter_mm"], 100)

    def test_parse_rectangular_separator_variations(self):
        # 1. 65 \ 38 -> width_mm 650, height_mm 380, label_type None
        p1 = parse_opening_label("65 \\ 38")
        self.assertIsNone(p1["label_type"])
        self.assertEqual(p1["width_mm"], 650)
        self.assertEqual(p1["height_mm"], 380)

        # 2. WDB 65/38 -> width_mm 650, height_mm 380, label_type WDB
        p2 = parse_opening_label("WDB 65/38")
        self.assertEqual(p2["label_type"], "WDB")
        self.assertEqual(p2["width_mm"], 650)
        self.assertEqual(p2["height_mm"], 380)

        # 3. DDB 65x38 -> width_mm 650, height_mm 380, label_type DDB
        p3 = parse_opening_label("DDB 65x38")
        self.assertEqual(p3["label_type"], "DDB")
        self.assertEqual(p3["width_mm"], 650)
        self.assertEqual(p3["height_mm"], 380)

        # 4. 65 l 38 -> width_mm 650, height_mm 380, label_type None
        p4 = parse_opening_label("65 l 38")
        self.assertIsNone(p4["label_type"])
        self.assertEqual(p4["width_mm"], 650)
        self.assertEqual(p4["height_mm"], 380)

        # 5. 65|38 -> width_mm 650, height_mm 380, label_type None
        p5 = parse_opening_label("65|38")
        self.assertIsNone(p5["label_type"])
        self.assertEqual(p5["width_mm"], 650)
        self.assertEqual(p5["height_mm"], 380)



if __name__ == "__main__":
    unittest.main()
