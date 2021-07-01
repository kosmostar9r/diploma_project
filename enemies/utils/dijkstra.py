import sys


class Dijkstra:
    def __init__(self, unit, points=None):
        self._unit = unit
        self._points = points if points else []
        self._weights = [[0.0 for _ in range(len(self._points))] for _ in range(len(self._points))]

    @staticmethod
    def maxint():
        return sys.maxsize

    @property
    def points(self):
        return self._points

    @property
    def weights(self):
        return self._weights

    def _get_closest(self):
        if not self._unit.is_alive:
            return
        uclosest = self._points[0]
        dclosest = self._points[0].distance_to(self._unit)
        for u in self._points:
            chkdist = self._unit.distance_to(u)
            if chkdist < dclosest:
                dclosest = chkdist
                uclosest = u
        return uclosest

    def update_units(self, func=None):
        if func is None:
            func = lambda a: True
        units = [self._unit.mothership, ]
        units = units + [a for a in self._unit.scene.asteroids if func(a)]
        units = units + [m for m in self._unit.scene.motherships if
                         not m.is_alive and m.team != self._unit.team and func(m)]
        units = units + [d for d in self._unit.scene.drones if not d.is_alive and func(d)]
        weights = [[0.0 for _ in range(len(units))] for _ in range(len(units))]

        self._weights, self._points = weights, units
        self._unit._path_closest = self._get_closest()

    def to_objects(self, indexes):
        return [self._points[n] for n in indexes]

    def weight_default_func(self, a, b):
        return float(a.distance_to(b))

    def calc_weights(self, func=None):
        if not self._unit.is_alive:
            return
        if func is None:
            func = self.weight_default_func
        dump = []
        for f, a in enumerate(self._points):
            def map_func(t, b):
                if f == t:
                    self._weights[f][t] = 0.0
                else:
                    d = float(func(a, b))
                    self._weights[f][t] = d

            map(map_func, *zip(*enumerate(self._points)))
            dump.append("%s %s" % (
                self._unit.id, ",".join(["%8.2f" % d if d < float("inf") else "%8s"
                                         for d in self._weights[f]])))
            dump.append("")

    def find_path(self, pt_from, pt_to, as_objects=False, info=None):
        if not self._unit.is_alive:
            return
        if pt_from not in self._points or pt_to not in self._points:
            print(pt_from, pt_to, self._points)
        fi = self._points.index(pt_from)
        fo = self._points.index(pt_to)
        if info:
            info = [
                "[{}:{}] {}->{} U:{} M:{}".format(
                    info, self._unit.id, fi, fo, self._unit, self._unit.mothership), ]
        if fi == fo:
            if as_objects:
                return self.to_objects([fi, ])
            else:
                return [fi, ]

        visited = []
        unvisited = [k for k, _ in enumerate(self._points)]

        FPREV = 0
        FCOST = 1
        table = [[-1, float("inf")] for p in range(len(self._points))]
        table[fi][FCOST] = 0.0
        root = fi
        lastroot = root
        while len(unvisited):
            visited.append(root)
            unvisited.pop(unvisited.index(root))
            if not unvisited:
                break

            neighbors = [uv for uv in unvisited if self._weights[root][uv] < float("inf")]
            midw = sum([self._weights[root][nb] for nb in neighbors]) / max(float(len(neighbors)), 1.0)
            for nb in neighbors:
                if root == fi and nb == fo:
                    continue
                if self._weights[root][nb] >= midw:
                    continue
                cost = table[root][FCOST] + self._weights[root][nb]
                if cost < table[nb][FCOST]:
                    table[nb][FCOST] = cost
                    table[nb][FPREV] = root

            shortest = float("inf")
            lastroot = root
            for uv in unvisited:
                if uv == lastroot:
                    continue
                # Found minimal cost vertex
                if table[uv][FCOST] < shortest:
                    shortest = table[uv][FCOST]
                    root = uv
            # FIXME
            if root == lastroot:
                if unvisited:
                    root = unvisited[0]
                else:
                    break
        if table[root][FCOST] == float("inf"):
            table[root][FCOST] = table[lastroot][FCOST] + self._weights[lastroot][root]
            table[root][FPREV] = lastroot
        if info:
            for k, t in enumerate(table):
                info.append("        {}\t{}\t{}".format(
                    k, t, self._unit.mothership.distance_to(self._points[k])))
        path = []
        root = fo  # back propagation
        while table[root][FPREV] > -1:
            path.insert(0, root)
            root = table[root][FPREV]
        path.insert(0, root)
        if info:
            info.append("        -----")
            for _, t in enumerate(path):
                info.append("        {}\t{}\t{}".format(
                    t, self._points[t], self._unit.mothership.distance_to(self._points[t])))
            print("\n".join(info))
        if as_objects:
            return self.to_objects(path)
        else:
            return path
