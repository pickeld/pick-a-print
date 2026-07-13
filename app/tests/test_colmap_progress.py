from __future__ import annotations

import unittest

from app.models.enums import JobStage
from app.pipeline.colmap_progress import ColmapProgressReporter


class ColmapProgressReporterTests(unittest.TestCase):
    def test_feature_extraction_progress(self) -> None:
        reporter = ColmapProgressReporter(JobStage.COLMAP_FEATURES)
        msg, sub = reporter.feed_line("Processed file [10/90]")
        self.assertEqual(msg, "Extracting features: image 10/90")
        self.assertAlmostEqual(sub, 10 / 90)

    def test_matching_block_progress(self) -> None:
        reporter = ColmapProgressReporter(JobStage.COLMAP_MATCHING)
        msg, sub = reporter.feed_line("Matching block [2/5, 3/5]")
        self.assertEqual(msg, "Matching features: block 2/5")
        self.assertAlmostEqual(sub, 0.4)

    def test_dense_patch_match_substep_scaling(self) -> None:
        reporter = ColmapProgressReporter(JobStage.DENSE_RECONSTRUCTION)
        reporter.set_dense_substep("patch_match")
        reporter.feed_line("Configuration has 56 problems...")
        msg, sub = reporter.feed_line("Processing problem [28/56]")
        self.assertEqual(msg, "Dense stereo: depth map 28/56")
        self.assertIsNotNone(sub)
        assert sub is not None
        # patch_match spans 0.12–0.88; halfway = 0.5 -> 0.12 + 0.76*0.5 = 0.5
        self.assertAlmostEqual(sub, 0.5, places=2)

    def test_dense_fusion_substep(self) -> None:
        reporter = ColmapProgressReporter(JobStage.DENSE_RECONSTRUCTION)
        reporter.set_dense_substep("fusion")
        msg, sub = reporter.feed_line("Fusing image [45/56]")
        self.assertEqual(msg, "Fusing point cloud: image 45/56")
        assert sub is not None
        self.assertGreater(sub, 0.88)

    def test_duplicate_message_suppressed(self) -> None:
        reporter = ColmapProgressReporter(JobStage.COLMAP_FEATURES)
        msg1, _ = reporter.feed_line("Processed file [1/10]")
        msg2, sub2 = reporter.feed_line("Processed file [1/10]")
        self.assertEqual(msg1, "Extracting features: image 1/10")
        self.assertIsNone(msg2)
        self.assertAlmostEqual(sub2, 0.1)


if __name__ == "__main__":
    unittest.main()
