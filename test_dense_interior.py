import json
from pathlib import Path
import tempfile
import unittest
from planner_destination import destination


class DenseInterior(unittest.TestCase):
    def test_actor_refresh_is_not_lost_behind_nearest_furniture_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'plan.json'
            path.write_text(json.dumps({'version':1,'expires_at':100,'scope':'casino',
                'objective_contains':'Benny','purpose':'Talk to Swank',
                'target':{'ref_id':'swank','name':'Swank','kind':42,'position':[1000,1000,0]}}))
            actor={'ref_id':'swank','name':'Swank','kind':42,'position':[50,100,0],
                   'same_space':True,'loaded':True}
            world={'cell_id':'casino','objectives':[{'text':'Benny'}],
                   'camera_position':[0,0,0],'camera_view':{'yaw':0},'nearby':[],'actors':[actor]}
            result=destination(world,path,now=50)
            self.assertTrue(result['loaded'])
            self.assertEqual(result['position'],[50,100,0])
            world['actors']=[];world['crosshair']=actor
            self.assertEqual(destination(world,path,now=50)['position'],[50,100,0])


if __name__=='__main__':unittest.main()
