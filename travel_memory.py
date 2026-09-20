"""Remember observed exterior entrances; never mix unrelated coordinate frames."""
import json,math,pathlib,time,os

ROOT=pathlib.Path(__file__).resolve().parent

class TravelMemory:
    def __init__(self,root=ROOT):
        self.path=pathlib.Path(root)/'travel-landmarks.json';self.doors={};self.dirty=False;self.last_write=0
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version')==1:
                for row in data.get('doors',[]):
                    if self.valid(row):self.doors[(row['worldspace_id'],row['ref_id'])]=row
        except (OSError,ValueError,TypeError):pass

    @staticmethod
    def valid(row):
        if not isinstance(row,dict) or row.get('kind')!=28:return False
        position=row.get('position');destination=row.get('destination')
        return (isinstance(row.get('ref_id'),str) and isinstance(row.get('worldspace_id'),str)
                and isinstance(row.get('cell_id'),str) and isinstance(row.get('name'),str)
                and isinstance(position,list) and len(position)==3
                and all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<1e7 for v in position)
                and isinstance(destination,dict) and isinstance(destination.get('cell_id'),str)
                and isinstance(destination.get('cell_name'),str))

    def entrances(self,world):
        for row in world.get('nearby',[])+world.get('travel_targets',[]):
            if not row.get('loaded') or not row.get('worldspace_id') or not self.valid(row):continue
            record={k:row.get(k) for k in ('ref_id','kind','name','position','worldspace_id','cell_id','destination','locked','lock_level')}
            key=(record['worldspace_id'],record['ref_id'])
            if self.doors.get(key)!=record:self.doors[key]=record;self.dirty=True
        if self.dirty and time.monotonic()-self.last_write>=5:
            temporary=self.path.with_suffix('.'+str(os.getpid())+'.next.json')
            temporary.write_text(json.dumps({'version':1,'doors':list(self.doors.values())},indent=2),encoding='utf-8')
            temporary.replace(self.path);self.dirty=False;self.last_write=time.monotonic()
        current={row['ref_id']:row for row in world.get('travel_targets',[])}
        wanted={row['cell_id'] for objective in world.get('objectives',[]) for row in objective['targets'] if row['cell_id'] and not row['same_space']}
        origin=world.get('camera_position');camera=world.get('camera_view')
        if not origin or not camera:return list(current.values())
        for (space,ident),row in self.doors.items():
            if space!=world.get('worldspace_id') or row['destination']['cell_id'] not in wanted or ident in current:continue
            delta=[a-b for a,b in zip(row['position'],origin)]
            current[ident]=dict(row,same_space=True,same_cell=False,loaded=False,remembered=True,
                distance=round(math.hypot(*delta[:2]),1),heading_error=round((math.atan2(delta[0],delta[1])-camera['yaw']+math.pi)%(2*math.pi)-math.pi,5))
        return sorted(current.values(),key=lambda row:row['distance'])
