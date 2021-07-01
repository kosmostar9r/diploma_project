# -*- coding: utf-8 -*-

import math
from operator import mul

from robogame_engine.geometry import Point
from robogame_engine.theme import theme

from .utils.dijkstra import Dijkstra
from .utils.states import DroneStateIdle
from .utils.strategies import Strategy, DroneUnitWithStrategies


class ReaperStrategy(Strategy):
    _distance_max = None
    _distance_limit = None

    # Data contains information for team. It useful when
    # have more than one drone with that strategy
    class Data:
        def __init__(self):
            self._targets = {}
            self._drones = []

    _data = {}

    @property
    def data(self):
        if ReaperStrategy._data.get(self.unit.team) is None:
            ReaperStrategy._data[self.unit.team] = ReaperStrategy.Data()
        return ReaperStrategy._data[self.unit.team]

    def __init__(self, *args, **kwargs):
        self._stepnum = 0
        super(ReaperStrategy, self).__init__(*args, **kwargs)
        if ReaperStrategy._distance_max is None:
            ReaperStrategy._distance_max = math.sqrt(
                theme.FIELD_HEIGHT * theme.FIELD_HEIGHT + theme.FIELD_WIDTH * theme.FIELD_WIDTH)
        if ReaperStrategy._distance_limit is None:
            ReaperStrategy._distance_limit = 0.25 * ReaperStrategy._distance_max

        self.data._drones.append(self.unit)

        # PathFinder
        if self.unit.pathfind is None:
            self.unit.pathfind = Dijkstra(self.unit)
        if self.unit.pathfind_unload is None:
            self.unit.pathfind_unload = Dijkstra(self.unit)
        self.data._enemy_drones = [d for d in self.unit.scene.drones if d.team != self.unit.team]

    def weight_harvest_func(self, a, b):
        dist = a.distance_to(b)
        distlim = self._distance_limit
        if b.cargo.fullness == 0.0 or b.__class__ == self.unit.mothership.__class__:
            return float("inf")
        amdist = a.distance_to(self.unit.mothership)
        bmdist = b.distance_to(self.unit.mothership)
        abdist = a.distance_to(b)
        k = float(self._distance_max)
        coef = [1.0 / distlim, 1.0]
        values = [dist, 1.0 - b.cargo.fullness]
        return sum(map(mul, coef, values))

    def get_harvest_source(self):
        center_of_scene = Point(theme.FIELD_WIDTH / 2, theme.FIELD_HEIGHT / 2)
        units = self.unit.pathfind.points
        units.sort(key=lambda u: u.distance_to(self.unit.mothership))
        units = [u for u in units if u != self.unit.mothership]
        return units[0] if units else None

    def distribute_harvest_sources(self, units):
        # Distribute enought amount of units to harvest a source
        for u in units:
            if u == self.unit.mothership:
                continue
            if sum([theme.DRONE_CARGO_PAYLOAD for t in self.data._targets if
                    self.data._targets[t] == u]) < u.cargo.payload:
                return u
        return None

    def get_harvest_target(self):
        self.unit.pathfind.update_units(func=lambda u: not u.cargo.is_empty)

        didx = self.data._drones.index(self.unit)
        if didx < 3:
            center_of_scene = self.unit.mothership.coord.copy()
            units = [p for p in self.unit.pathfind.points if p != self.unit.mothership]
            if not units:
                return None
            units.sort(key=lambda u: u.distance_to(self.unit))
            return units[didx] if len(units) - 1 >= didx else units[0]

        self.unit.pathfind.calc_weights(func=self.weight_harvest_func)
        fat_source = self.get_harvest_source()
        if not fat_source:
            return None

        path = self.unit.pathfind.find_path(self.unit.mothership, fat_source, as_objects=True)
        if path is None:
            return None

        u = self.distribute_harvest_sources(path)
        if u:
            return u

        pos = self.data._drones.index(self.unit)
        sz = len(path)
        idx = min(sz, (pos % (sz - 1)) + 1 if sz > 1 else 0)
        return path[idx]

    def weight_unload_func(self, a, b):
        if a == self.unit.mothership or b == self.unit.mothership:
            return 0.0
        dist = a.distance_to(b)
        adist = self.unit.mothership.distance_to(a)
        bdist = self.unit.mothership.distance_to(b)
        coef = [bdist / adist, 1.0]
        values = [dist, 1.0 - b.cargo.fullness]
        return sum(map(mul, coef, values))

    def get_unload_target(self):
        if self.data._drones.index(self.unit) < 2:
            return self.unit.mothership
        if len([a for a in self.unit.scene.asteroids if a.cargo.payload > 0]) == 0:
            return self.unit.mothership

        self.unit.pathfind_unload.update_units(func=lambda u: u.cargo.fullness < 1.0)

        uclosest = self.unit.closest_in_path
        self.unit.pathfind_unload.calc_weights(func=self.weight_unload_func)

        path_unload = self.unit.pathfind_unload.find_path(uclosest, self.unit.mothership,
                                                          as_objects=True)  # , info="unld")
        if path_unload is None:
            return None

        pos = self.data._drones.index(self.unit)
        sz = len(path_unload)
        # Возврат, проекция бинарного поиска в отношении path-finding
        idx = min(len(path_unload) - 1, int(len(path_unload) / 2) + 1) if sz > 1 else 0
        return path_unload[-idx]

    @property
    def is_finished(self):
        return False

    @property
    def fsm_state(self):
        return self.unit.fsm_state

    def game_step(self, *args, **kwargs):
        self._stepnum = self._stepnum + 1
        super(ReaperStrategy, self).game_step(*args, **kwargs)

        newState = self.fsm_state.make_transition()
        if newState != self.fsm_state.__class__:
            self.data._targets[self.unit.id] = None
            self.unit.set_fsm_state(newState(self))

        if self.unit.fsm_state:
            self.unit.fsm_state.game_step()


class ReaperDrone(DroneUnitWithStrategies):
    _strategy_class = ReaperStrategy
    _logging = False

    def __init__(self, *args, **kwargs):
        super(ReaperDrone, self).__init__(*args, **kwargs)
        self.pathfind = None
        self.pathfind_unload = None
        self.__fsm_state = None
        self._strategy = None
        self._path_closest = None

    @property
    def closest_in_path(self):
        return self._path_closest

    @property
    def fsm_state(self):
        return self.__fsm_state

    def set_fsm_state(self, new_fsm_state):
        self.__fsm_state = new_fsm_state

    def on_born(self):
        super(ReaperDrone, self).on_born()
        self._strategy = self._strategy_class(unit=self)
        self.set_fsm_state(DroneStateIdle(self._strategy))
        self.append_strategy(self._strategy)
