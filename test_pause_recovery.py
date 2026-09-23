"""A swallowed pause input must not leave recovery running under fire."""
import tempfile
import unittest
from itertools import chain,repeat
from pathlib import Path
from unittest.mock import Mock,patch
import game_input

HUD={'interface_mode':1,'player':{'cell_id':'0xabc'},'menus':[{'name':'hud','labels':[]}]}
PAUSED={'interface_mode':2,'player':{'cell_id':'0xabc'},'menus':[{'name':'hud','labels':[]},{'name':'start','labels':[{'text':'Continue'}]}]}

class PauseRecovery(unittest.TestCase):
 def run_pause(self,snapshot,foreground=lambda:123):
  observer=Mock();observer.snapshot.side_effect=snapshot
  with tempfile.TemporaryDirectory() as directory, patch.object(game_input,'ROOT',Path(directory)),patch.object(game_input,'Observer',return_value=observer),patch.object(game_input,'foreground_pid',side_effect=foreground),patch.object(game_input,'send') as send,patch.object(game_input,'key_event',side_effect=lambda name,up=False:(name,up)),patch.object(game_input.msvcrt,'locking'),patch.object(game_input.time,'sleep'),patch.object(game_input.time,'monotonic',side_effect=iter(range(100))):
   result=game_input.pause_world(123)
   return result,send.call_args_list

 def test_swallowed_first_escape_reobserves_then_pauses_once(self):
  snapshots=chain([HUD,HUD,HUD],repeat(PAUSED))
  result,calls=self.run_pause(lambda:next(snapshots))
  self.assertTrue(result['verified_paused']);self.assertEqual(result['escape_attempts'],2)
  self.assertEqual([c.args[0] for c in calls],[('escape',False),('escape',True)]*2)

 def test_already_paused_never_toggles_back_to_game(self):
  result,calls=self.run_pause(lambda:PAUSED)
  self.assertTrue(result['verified_paused']);self.assertEqual(calls,[])

 def test_closing_menu_is_not_reported_as_paused(self):
  snapshots=chain([dict(PAUSED,interface_mode=1),HUD],repeat(PAUSED))
  result,calls=self.run_pause(lambda:next(snapshots))
  self.assertTrue(result['verified_paused']);self.assertEqual(len(calls),2)

 def test_new_modal_blocks_retry(self):
  modal={'player':{'cell_id':'0xabc'},'menus':[{'name':'message','labels':[]}]}
  snapshots=iter([HUD,modal,modal])
  result,calls=self.run_pause(lambda:next(snapshots))
  self.assertFalse(result['verified_paused']);self.assertEqual(len(calls),2)
  self.assertIn('Unknown menu',result['error'])

 def test_focus_loss_blocks_second_escape(self):
  snapshots=iter([HUD,HUD,HUD]);foreground=iter([123,123,999])
  result,calls=self.run_pause(lambda:next(snapshots),lambda:next(foreground))
  self.assertFalse(result['verified_paused']);self.assertEqual(len(calls),2)
  self.assertIn('foreground',result['error'])

if __name__=='__main__':unittest.main()
