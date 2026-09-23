"""Measure a small normal camera movement during verified recorded gameplay."""
import argparse,json,math,pathlib
from observe_game import Observer
from game_input import act

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pid',required=True,type=int)
    parser.add_argument('--recording',required=True);args=parser.parse_args()
    observer=Observer(args.pid)
    try:state=observer.snapshot()
    finally:observer.close()
    if not (state.get('player') or {}).get('cell_name') or any(m['name']!='hud' for m in state['menus']):
        raise RuntimeError('Calibration requires ordinary unpaused gameplay, with no menu')
    before=state['player']['rotation_radians']
    result=act(args.pid,args.recording,dx=40,dy=10,seconds=.2)
    after=result['after']['player']['rotation_radians']
    delta=[(b-a+math.pi)%(2*math.pi)-math.pi for a,b in zip(before,after)]
    calibration={'before':before,'after':after,'delta':delta,'yaw_per_dx':delta[2]/40,
                 'pitch_per_dy':delta[0]/10,'measured_at':result['after']['observed_at']}
    if not all(.0001<calibration[key]<.02 for key in ('yaw_per_dx','pitch_per_dy')):
        raise RuntimeError('Unexpected camera response; calibration not saved')
    pathlib.Path(__file__).with_name('mouse-calibration.json').write_text(json.dumps(calibration,indent=2))
    print(json.dumps(calibration))

if __name__=='__main__':main()
