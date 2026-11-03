import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from clipper import (Speech, choose_windows, hook_text, score, validate_media_url,
                     download_video, prepare_analysis_video)


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

    def test_direct_mp4_not_sent_to_youtube_extractor(self):
        with patch('clipper.download_direct_video', return_value=Path('/tmp/sample.mp4')) as fetch:
            result = download_video('https://example.com/sample.mp4?token=dummy')
        self.assertEqual(result, Path('/tmp/sample.mp4'))
        fetch.assert_called_once()

    def test_explicit_direct_download_supports_signed_urls(self):
        with patch('clipper.download_direct_video', return_value=Path('/tmp/sample.mp4')) as fetch:
            download_video('https://example.com/download?id=9', prefer_direct=True)
        fetch.assert_called_once()

    def test_rejects_private_ip_media_url(self):
        with self.assertRaises(ValueError):
            validate_media_url('https://127.0.0.1/video.mp4')
        with self.assertRaises(ValueError):
            validate_media_url('http://example.com/video.mp4')

    def test_long_source_trims_to_analysis_window(self):
        with patch('clipper.duration', side_effect=[5912]):
            with patch('clipper.cmd') as run:
                _, start = prepare_analysis_video(Path('video.mp4'), 420, 1800)
        self.assertEqual(start, 420)
        command = run.call_args.args
        self.assertIn(1800, command)
        self.assertIn(420, command)


if __name__ == "__main__":
    unittest.main()
