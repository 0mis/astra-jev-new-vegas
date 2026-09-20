"""Read-only loaded-floor routing; normal input still performs movement.

Join triangles only across matching floor edges, including edges shared by two
loaded exterior cells. Interior coordinate frames are never combined.
"""
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
        self.triangles=[];self.mesh_count=0;self.cell_count=0;seen=set()
        for parent in observer.loaded_cells(cell):
            array=observer.u32(parent+0x64)
            if not array:continue
            data,count=struct.unpack('<II',observer.read(array+4,8))
            if not 0<=count<=128:raise RuntimeError('Navmesh array outside bounds')
            if not count:continue
            self.cell_count+=1
            for mesh in struct.unpack('<'+'I'*count,observer.read(data,count*4)):
                if not mesh or mesh in seen:continue
                seen.add(mesh)
                if observer.u32(mesh+0x24)!=parent:raise RuntimeError('Navmesh parent changed')
                vertices,nv=struct.unpack('<II',observer.read(mesh+0x2C,8))
                triangles,nt=struct.unpack('<II',observer.read(mesh+0x3C,8))
                if not 3<=nv<=15000 or not 1<=nt<=20000:raise RuntimeError('Navmesh count outside bounds')
                points=list(struct.iter_unpack('<3f',observer.read(vertices,nv*12)))
                records=list(struct.iter_unpack('<3H3h2H',observer.read(triangles,nt*16)))
                if any(any(index>=nv for index in row[:3]) for row in records):raise RuntimeError('Invalid triangle vertex index')
                if not all(math.isfinite(v) for point in points for v in point):raise RuntimeError('Invalid navmesh vertex')
                self.triangles.extend(tuple(points[i] for i in row[:3]) for row in records)
                self.mesh_count+=1
        if not self.triangles:raise RuntimeError('No loaded floor triangles')
        self.edges=[set() for _ in self.triangles];self.portals={};owners={}
        for index,triangle in enumerate(self.triangles):
            for a,b in ((0,1),(1,2),(2,0)):
                # Float precision at exterior coordinates is below this tolerance.
                key=tuple(sorted(tuple(round(v,1) for v in triangle[k]) for k in (a,b)))
                owners.setdefault(key,[]).append(index)
        for edge,linked in owners.items():
            if len(linked)==2:
                a,b=linked;self.edges[a].add(b);self.edges[b].add(a)
                midpoint=tuple((edge[0][k]+edge[1][k])/2 for k in range(3))
                self.portals[a,b]=midpoint;self.portals[b,a]=midpoint
        self.centers=[tuple(sum(v[k] for v in tri)/3 for k in range(3)) for tri in self.triangles]

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

    def path_points(self,chain):
        # Shared-edge midpoints stay on both adjacent floor triangles. Starting
        # at the next edge avoids backtracking to a centroid whenever an NPC moves.
        return [self.portals[a,b] for a,b in zip(chain,chain[1:])]+[self.centers[chain[-1]]] if len(chain)>1 else []

    def waypoint(self,origin,target):
        chain=self.route(origin,target)
        if len(chain)==1:return None,chain
        center=self.centers[chain[0]]
        # Reach the current triangle center before crossing into its neighbor.
        if distance(origin,center)>35:return center,chain
        return self.centers[chain[1]],chain
