from .reaper import ReaperStrategy, ReaperDrone
from robogame_engine.theme import theme


class DrillerStrategy(ReaperStrategy):
    def distribute_harvest_sources(self, units):
        # Distribute enough amount of units to harvest a source
        for u in units:
            if u == self.unit.mothership:
                continue
            if u in self.data._targets.values():
                continue
            if sum([theme.DRONE_CARGO_PAYLOAD for t in self.data._targets if
                    self.data._targets[t] == u]) < u.cargo.payload:
                return u

    def get_harvest_target(self):
        self.unit.pathfind.update_units(func=lambda u: not u.cargo.is_empty)
        units = self.unit.pathfind.points
        if not units:
            return None
        units.sort(key=lambda u: u.distance_to(self.unit))

        u = self.distribute_harvest_sources(units)
        return u

    def get_unload_target(self):
        return self.unit.mothership


class DrillerDrone(ReaperDrone):
    _strategy_class = DrillerStrategy
