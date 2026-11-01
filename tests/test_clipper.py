import unittest
from clipper import Speech, choose_windows, hook_text, score


class ClipperTests(unittest.TestCase):
    def test_non_overlapping_clips(self):
        text = [Speech(16, 20, "Wow look this is amazing!"),
                Speech(55, 62, "How does it work?"),
                Speech(105, 112, "Wait for the secret reveal!")]
        result = choose_windows(150, text, 3, 35)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(b[0] - a[0] >= 34.75 for a, b in zip(result, result[1:])))

    def test_short_video_not_repeated(self):
        self.assertEqual(len(choose_windows(30, [], 5, 35)), 1)

    def test_hook_language(self):
        speech = [Speech(0, 10, "This is a surprise")]
        self.assertIn("Wait", hook_text(speech, 0, 10, "en"))
        self.assertIn("بص", hook_text(speech, 0, 10, "ar"))

    def test_high_score_for_speech(self):
        self.assertGreater(score([Speech(0, 5, "Wow, look!")], 0, 8), score([], 0, 8))


if __name__ == "__main__":
    unittest.main()
