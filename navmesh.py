"""Read-only single-cell triangle routing; normal input still performs movement."""
import heapq,math,struct

def distance(a,b):return math.dist(a[:2],b[:2])

def triangle_distance(point,vertices):
    a,b,c=vertices
    def cross(u,v,p):return (v[0]-u[0])*(p[1]-u[1])-(v[1]-u[1])*(p[0]-u[0])
    signs=[cross(a,b,point),cross(b,c,point),cross(c,a,point)]
    if all(s>=-.001 for s in signs) or all(s<=.001 for s in signs):return 0
    distances=[]
    for u,v in ((a,b),(b,c),(c,a)):
        dx,dy=v[0]-u[0],v[1]-u[1];den=dx*dx+dy*dy
        fraction=max(0,min(1,((point[0]-u[0])*dx+(point[1]-u[1])*dy)/den)) if den else 0
        distances.append(math.hypot(point[0]-u[0]-fraction*dx,point[1]-u[1]-fraction*dy))
    return min(distances)

class Mesh:
    def __init__(self,observer,cell):
        array=observer.u32(cell+0x64);data,count=struct.unpack('<II',observer.read(array+4,8))
        if count!=1:raise RuntimeError('Routing currently requires a single loaded navmesh')
        mesh=observer.u32(data)
        if observer.u32(mesh+0x24)!=cell:raise RuntimeError('Navmesh belongs to a different cell')
        vertices,nv=struct.unpack('<II',observer.read(mesh+0x2C,8))
        triangles,nt=struct.unpack('<II',observer.read(mesh+0x3C,8))
        if not 3<=nv<=15000 or not 1<=nt<=20000:raise RuntimeError('Navmesh count outside bounds')
        self.vertices=list(struct.iter_unpack('<3f',observer.read(vertices,nv*12)))
        records=list(struct.iter_unpack('<3H3h2H',observer.read(triangles,nt*16)))
        if any(any(index>=nv for index in row[:3]) or any(n< -1 or n>=nt for n in row[3:6]) for row in records):
            raise RuntimeError('Unsupported navmesh triangle layout')
        self.triangles=[tuple(self.vertices[i] for i in row[:3]) for row in records]
        self.edges=[tuple(n for n in row[3:6] if n>=0) for row in records]
        self.centers=[tuple(sum(v[k] for v in tri)/3 for k in range(3)) for tri in self.triangles]
        if not all(math.isfinite(v) for p in self.vertices for v in p):raise RuntimeError('Invalid navmesh vertex')

    def nearest(self,point):
        return min(range(len(self.triangles)),key=lambda i:(triangle_distance(point,self.triangles[i])+abs(point[2]-self.centers[i][2]),distance(point,self.centers[i])))

    def route(self,origin,target):
        start,finish=self.nearest(origin),self.nearest(target)
        costs={start:0};parents={};queue=[(0,start)]
        while queue:
            _,node=heapq.heappop(queue)
            if node==finish:
                chain=[node]
                while node in parents:node=parents[node];chain.append(node)
                return list(reversed(chain))
            for neighbor in self.edges[node]:
                cost=costs[node]+distance(self.centers[node],self.centers[neighbor])
                if cost<costs.get(neighbor,float('inf')):
                    costs[neighbor]=cost;parents[neighbor]=node
                    heapq.heappush(queue,(cost+distance(self.centers[neighbor],self.centers[finish]),neighbor))
        raise RuntimeError('No connected navmesh route to the objective')

    def waypoint(self,origin,target):
        chain=self.route(origin,target)
        if len(chain)==1:return None,chain
        center=self.centers[chain[0]]
        # Reach the current triangle center before crossing into its neighbor.
        if distance(origin,center)>35:return center,chain
        return self.centers[chain[1]],chain
