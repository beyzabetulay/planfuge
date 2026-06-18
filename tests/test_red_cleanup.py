import unittest
import numpy as np
from PIL import Image
from src.image.red_cleanup import remove_red_pixels


class TestRedCleanup(unittest.TestCase):
    def test_remove_red_pixels(self):
        # Create a mock 10x10 RGB image with white background
        img = Image.new("RGB", (10, 10), "white")
        pixels = np.array(img)
        
        # Add a red box (pure red: [255, 0, 0])
        # Note: PIL stores as RGB, so [255, 0, 0] is red
        pixels[2:5, 2:5] = [255, 0, 0]
        
        # Add a black box (pure black: [0, 0, 0])
        pixels[7:9, 7:9] = [0, 0, 0]
        
        test_img = Image.fromarray(pixels)
        
        # Run cleanup without dilation first to test raw mask accuracy
        cleaned_img, mask_img = remove_red_pixels(test_img, dilation_iterations=0)
        
        cleaned_pixels = np.array(cleaned_img)
        mask_pixels = np.array(mask_img)
        
        # Verify the red pixels are turned white [255, 255, 255]
        for y in range(2, 5):
            for x in range(2, 5):
                np.testing.assert_array_equal(cleaned_pixels[y, x], [255, 255, 255])
                self.assertEqual(mask_pixels[y, x], 255)
                
        # Verify the black pixels remain black [0, 0, 0]
        for y in range(7, 9):
            for x in range(7, 9):
                np.testing.assert_array_equal(cleaned_pixels[y, x], [0, 0, 0])
                self.assertEqual(mask_pixels[y, x], 0)
                
        # Verify other white background remains white
        np.testing.assert_array_equal(cleaned_pixels[0, 0], [255, 255, 255])
        self.assertEqual(mask_pixels[0, 0], 0)


if __name__ == "__main__":
    unittest.main()
