import unittest

from worlds.grounded.compass import describe, direction


class TestCompass(unittest.TestCase):
    player = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}

    def test_direction_relative_to_facing(self):
        self.assertEqual(direction(self.player, {"x": 1000, "y": 0}), "ahead")
        self.assertEqual(direction(self.player, {"x": 0, "y": 1000}), "right")   # +Y is to the right of +X
        self.assertEqual(direction(self.player, {"x": 0, "y": -1000}), "left")
        self.assertEqual(direction(self.player, {"x": -1000, "y": 0}), "behind")
        turned = dict(self.player, yaw=90.0)
        self.assertEqual(direction(turned, {"x": 0, "y": 1000}), "ahead")
        self.assertEqual(direction(turned, {"x": 1000, "y": 1000}), "ahead-left")

    def test_nearest_unchecked_in_radius(self):
        positions = {"POI_A": {"x": 5000, "y": 0, "z": 0}, "POI_B": {"x": 2000, "y": 0, "z": 2000},
                     "POI_C": {"x": 1000, "y": 0, "z": 0}}
        wanted = {"POI_A": "Alpha", "POI_B": "Bravo"}   # POI_C is checked already
        self.assertEqual(describe(self.player, positions, wanted, 100), "Bravo  ·  28 m ahead above")
        self.assertIsNone(describe(self.player, positions, wanted, 20))
        self.assertIsNone(describe(None, positions, wanted, 100))
