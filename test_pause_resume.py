import unittest
from jev_loop import pause_resume_key


class PauseResume(unittest.TestCase):
    def setUp(self):
        self.state = {'menus': [{'name': 'hud'}, {'name': 'start'}],
                      'player': {'cell_id': '0x10e429', 'life_state': 0}}
        self.selected = {'text': 'Continue', 'highlighted': True,
                         'path': '/StartMenu/NOGLOW_BRANCH/main_container/lb_item_hotrect'}

    def test_observed_loaded_pause_uses_working_resume_key(self):
        self.assertEqual(pause_resume_key(self.state, self.selected), 'escape')

    def test_main_menu_and_dead_player_do_not_resume(self):
        for state in ({'menus': [{'name': 'start'}]},
                      dict(self.state, player={'cell_id': '0x10e429', 'life_state': 2})):
            self.assertIsNone(pause_resume_key(state, self.selected))

    def test_other_choices_confirmations_and_unselected_rows_are_unchanged(self):
        for selected in (dict(self.selected, text='Load'),
                         dict(self.selected, highlighted=False),
                         dict(self.selected, path='/StartMenu/NOGLOW_BRANCH/confirm_container/Continue')):
            self.assertIsNone(pause_resume_key(self.state, selected))

    def test_additional_modal_blocks_resume(self):
        state = dict(self.state, menus=self.state['menus'] + [{'name': 'message'}])
        self.assertIsNone(pause_resume_key(state, self.selected))


if __name__ == '__main__':
    unittest.main()
