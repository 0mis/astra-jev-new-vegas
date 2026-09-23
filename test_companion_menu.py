"""Regression cases from Veronica's observed companion command wheel."""
import unittest
from jev_loop import controls
from observe_game import MENUS


class CompanionMenu(unittest.TestCase):
    def setUp(self):
        self.exit = {'text': 'Exit', 'target': 1, 'highlighted': False,
                     'path': '/CompanionWheelMenu/NOGLOW_BRANCH/CWM_MainRect/CWM_Button_Exit',
                     'x': 824.33, 'y': 399, 'width': 68, 'height': 52, 'tile': 'observed-exit'}
        self.menu = {'name': MENUS[1075], 'labels': [self.exit]}

    def test_observed_exit_survives_hover_preview_without_exposing_orders(self):
        self.menu['labels'].extend([
            dict(self.exit, text='Dismiss', path='/CompanionWheelMenu/CWM_Button_Dismiss'),
            dict(self.exit, target=0, path='/CompanionWheelMenu/CWM_ButtonPreviewText')])
        self.assertEqual(controls({'menus': [self.menu]})[0], [self.exit])

    def test_visible_exit_text_is_not_enough_without_clickable_exit_parent(self):
        self.menu['labels'] = [dict(self.exit, target=0),
                               dict(self.exit, path='/CompanionWheelMenu/OtherButton')]
        self.assertEqual(controls({'menus': [self.menu]})[0], [])

    def test_confirmation_overlay_has_priority_over_companion_exit(self):
        confirmation = dict(self.exit, text='Cancel', path='/MessageMenu/Cancel')
        state = {'menus': [self.menu, {'name': 'message', 'labels': [confirmation]}]}
        self.assertEqual(controls(state)[0], [confirmation])


if __name__ == '__main__':
    unittest.main()
