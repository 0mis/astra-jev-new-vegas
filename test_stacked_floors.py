import unittest
from world_controller import needs_floor_route,waypoint_reached

class StackedFloorTests(unittest.TestCase):
    def test_lucky38_lower_terminal_requires_route_from_upper_room(self):
        self.assertTrue(needs_floor_route({'distance':113.5,'position':[-1700,7122,19007]},[-1622,7192,19196]))

    def test_return_to_lower_approach_when_xy_already_close(self):
        self.assertTrue(needs_floor_route({'distance':108,'position':[-940,6276,18902]},[-1025,6207,19194]))

    def test_same_floor_terminal_is_reachable_without_floor_route(self):
        self.assertFalse(needs_floor_route({'distance':110,'position':[-1700,7122,19007]},[-1622,7192,18902]))

    def test_stacked_waypoint_not_consumed(self):
        self.assertFalse(waypoint_reached([-1025,6207,19194],[-1005,6184,18901]))
        self.assertTrue(waypoint_reached([-1025,6207,18902],[-1005,6184,18901]))

if __name__=='__main__':unittest.main()
