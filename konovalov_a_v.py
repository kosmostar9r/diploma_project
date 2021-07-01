# -*- coding: utf-8 -*-
from random import uniform

from astrobox.core import Drone
from astrobox.themes.default import MOTHERSHIP_HEALING_DISTANCE
from robogame_engine.geometry import Point, Vector
from robogame_engine.theme import theme
from abc import ABC

ROTATIONS = [20, 40]
CONVERGENCE_KOEF = 0.95
MAX_DRONES_PER_ASTEROID = 2
SAFE_DEFENDER_DIST = 150


class Dispatcher:
    """
    Manager class that defining activity for groups of drones
    """

    def __init__(self):
        self.soldiers = []
        self.collectors = []
        self.defenders = []
        self.scavengers = []
        self.forwards = []
        self.defender_target_to_focus = None

    def new_soldier(self, soldier):
        soldier.dispatcher = self
        soldier.old_asteroid = None
        self.soldiers.append(soldier)
        soldier.idx = len(self.soldiers)

    def get_new_roles(self):
        """
        Drones changes roles after phase 1
        """
        alive_soldiers = [s for s in self.soldiers if s.is_alive]
        soldier_count = 0
        for soldier in alive_soldiers:
            if soldier_count == 0:
                soldier.change_state(MainDefender())
            elif soldier_count == 1:
                soldier.change_state(Defender())
            else:
                if not soldier.is_empty:
                    soldier.prev_state = Forward()
                    soldier.change_state(ToHeal())
                else:
                    soldier.change_state(Forward())
            soldier_count += 1

    def get_forward_target(self, forward):
        """
        Drones gets the nearest alive enemy base
        :param forward: Forward()
        :return: astrobox.core.MotherShip()
        """
        bases = [(base, forward.context.my_mothership.distance_to(base))
                 for base in forward.context.scene.motherships if base.team != forward.context.team and base.is_alive]
        bases.sort(key=lambda x: x[1])
        if bases:
            return bases[0][0]
        else:
            return None

    def get_position_forward(self, unit, target):
        """
        Forward gets the position to attack enemy base
        Each drone gets his own position to avoid friendly fire
        Method trying to find a position near the edge of the screen
        using information about a position of friendly base and enemy base
        :param unit: Forward()
        :param target: astrobox.core.MotherShip()
        """
        vec = Vector.from_points(unit.context.coord, target.coord)
        dist_vec = vec.module
        max_range_attack = (dist_vec - unit.context.attack_range)
        if max_range_attack < dist_vec - MOTHERSHIP_HEALING_DISTANCE:
            max_range_attack += MOTHERSHIP_HEALING_DISTANCE + 70
        koef = max_range_attack / dist_vec
        norm_vec = Vector(vec.x * koef, vec.y * koef)
        if unit.context.mothership.coord.x == 90 and unit.context.mothership.coord.y == 90:
            self.rotate_negative(unit, target, norm_vec)
        elif unit.context.mothership.coord.x == 90 and unit.context.mothership.coord.y != 90:
            self.rotate_positive(unit, target, norm_vec)
        elif unit.context.mothership.coord.x != 90 and unit.context.mothership.coord.y == 90:
            self.rotate_negative(unit, target, norm_vec)
        else:
            self.rotate_positive(unit, target, norm_vec)
        position = Point(unit.context.coord.x + norm_vec.x, unit.context.coord.y + norm_vec.y)
        unit.context.attack_position = position

    def rotate_positive(self, unit, target, norm_vec):
        """
        Rotating forwards position positively due to its and targets position
        :param unit: Forward()
        :param target: astrobox.core.MotherShip()
        :param norm_vec: robogame_engine.geometry.Vector()
        """
        if target.coord.x == 90:
            if unit.context.idx == 3:
                norm_vec.rotate(0)
            elif unit.context.idx == 4:
                norm_vec.rotate(ROTATIONS[0])
            else:
                norm_vec.rotate(ROTATIONS[1])
        else:
            if unit.context.idx == 3:
                norm_vec.rotate(0)
            elif unit.context.idx == 4:
                norm_vec.rotate(-ROTATIONS[0])
            else:
                norm_vec.rotate(-ROTATIONS[1])

    def rotate_negative(self, unit, target, norm_vec):
        """
        Rotating a forwards position negatively due to its and targets position
        :param unit: Forward()
        :param target: astrobox.core.MotherShip()
        :param norm_vec: robogame_engine.geometry.Vector()
        """
        if target.coord.x == 90:
            if unit.context.idx == 3:
                norm_vec.rotate(0)
            elif unit.context.idx == 4:
                norm_vec.rotate(-ROTATIONS[0])
            else:
                norm_vec.rotate(-ROTATIONS[1])
        else:
            if unit.context.idx == 3:
                norm_vec.rotate(0)
            elif unit.context.idx == 4:
                norm_vec.rotate(ROTATIONS[0])
            else:
                norm_vec.rotate(ROTATIONS[1])

    def get_scavenger_target(self, scavenger):
        """
        Scavengers gets the nearest dead and not empty enemy base
        :param scavenger: Scavenger()
        :return: astrobox.core.MotherShip()
        """
        dead_bases_w_eler = [(base, scavenger.context.distance_to(base))
                             for base in scavenger.context.scene.motherships
                             if base != scavenger.context.my_mothership and not base.is_alive and not base.is_empty]
        dead_bases_w_eler.sort(key=lambda x: x[1])
        if dead_bases_w_eler:
            return dead_bases_w_eler[0][0]
        else:
            return None


class KonovalovDrone(Drone):
    """
    Main class of drones
    """
    my_team = []
    limit_health = 0.5
    attack_range = 0
    dispatcher = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.idx = None
        self.ready_to_shoot = False
        self._state = None
        self.old_asteroid = None
        self.prev_state = None
        self.forward_target = None
        self.scavenger_target = None
        self.attack_position = None

    def _remove_drone_from_lists(self):
        if self in self.dispatcher.defenders:
            self.dispatcher.defenders.remove(self)
        elif self in self.dispatcher.scavengers:
            self.dispatcher.scavengers.remove(self)
        elif self in self.dispatcher.forwards:
            self.dispatcher.forwards.remove(self)
        elif self in self.dispatcher.collectors:
            self.dispatcher.collectors.remove(self)

    def change_state(self, state):
        """
        Changing states
        :param state: on of (Collector(), MainDefender(), Defender(), Scavenger(), Scavenger())
        """
        self._state = state
        self._state.context = self
        self._remove_drone_from_lists()
        if isinstance(state, Collector):
            self.dispatcher.collectors.append(self)
        elif isinstance(state, MainDefender) or isinstance(state, Defender):
            self.dispatcher.defenders.append(self)
        elif isinstance(state, Scavenger):
            self.dispatcher.scavengers.append(self)
        elif isinstance(state, Scavenger):
            self.dispatcher.forwards.append(self)

    def registration(self):
        """
        Drones gets Dispatcher()
        """
        if KonovalovDrone.dispatcher is None:
            KonovalovDrone.dispatcher = Dispatcher()
        KonovalovDrone.dispatcher.new_soldier(self)

    def on_born(self):
        """
        Actions at the start of simulation
        """
        self.attack_range = self.gun.shot_distance
        self.limit_health = uniform(0.45, 0.65)
        self.my_team.append(self)
        self.registration()
        self.change_state(Collector())
        self._state.on_born()

    def on_stop_at_asteroid(self, asteroid):
        """
        Actions if drone stopped at asteroid
        Will be overwrited at states
        :param asteroid: astrobox.core.Asteroid()
        """
        self._state.on_stop_at_asteroid(asteroid)

    def on_stop_at_point(self, target):
        """
        Actions if drone stopped at target
        Will be overwrited at states
        :param target: robogame_engine.geometry.Point()
        """
        self._state.on_stop_at_point(target)

    def on_wake_up(self):
        """
        Actions if drone has no actions
        Will be overwrited at states
        """
        self._state.on_wake_up()

    def on_heartbeat(self):
        """
        Actions that should happens every n seconds
        Will be overwrited at states
        """
        self._state.on_heartbeat()

    def on_load_complete(self):
        """
        Actions if drone complete collecting resources from target
        Will be overwrited at states
        """
        self._state.on_load_complete()

    def on_stop_at_mothership(self, mothership):
        """
        Actions if drone stopped at mothership
        Will be overwrited at states
        :param mothership: astrobox.core.MotherShip()
        """
        self._state.on_stop_at_mothership(mothership)

    def on_unload_complete(self):
        """
        Actions if drone complete unloading resources
        Will be overwrited at states
        """
        self._state.on_unload_complete()

    def smart_target(self, target):
        """
        Adding new point at the drones path to check out if target is already empty
        :param target: astrobox.core.Asteroid()
        :return: list() of robogame_engine.geometry.Point()
        """
        path = self.distance_to(target)
        breakpoints_delta = path / 2
        breakpoints_coords = []
        cos = (target.x - self.coord.x) / path
        sin = (target.y - self.coord.y) / path
        bp_x = breakpoints_delta * cos + self.coord.x
        bp_y = breakpoints_delta * sin + self.coord.y
        bp_coords = Point(bp_x, bp_y)
        breakpoints_coords.append(bp_coords)
        breakpoints_coords.append(target)
        return breakpoints_coords

    def get_aster_edge_point(self, target):
        """
        Triyng to find out the edge point of the asteroid where drones still can collect resources
        :param target: astrobox.core.Asteroid()
        :return: robogame_engine.geometry.Point()
        """
        at_distance = theme.CARGO_TRANSITION_DISTANCE * CONVERGENCE_KOEF
        va = Vector.from_points(self.coord, target.coord)
        vb = Vector.from_direction(va.direction, at_distance)
        vb.rotate(180.0)
        return Point(self.coord.x + va.x + vb.x, self.coord.y + va.y + vb.y)

    def smart_moves(self, coords_list):
        """
        Moving at the point to check out if drone need to continue moving to the current target
        :param coords_list: self.smart_target()
        """
        target = coords_list[0]
        self.move_at(target)

    def go_to_target(self, target):
        """
        Moving at the target
        :param target: astrobox.core.Asteroid()
        """
        target = self.get_aster_edge_point(target)
        self.move_at(target)


class Behavior(ABC):
    """
    Abstract class that defining methods that may be used in states
    """

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, context):
        self._context = context

    def on_born(self):
        pass

    def on_stop_at_asteroid(self, asteroid):
        pass

    def on_stop_at_point(self, target):
        pass

    def on_wake_up(self):
        pass

    def on_heartbeat(self):
        pass

    def on_load_complete(self):
        pass

    def on_stop_at_mothership(self, mothership):
        pass

    def on_unload_complete(self):
        pass


class Collector(Behavior):
    """
    Drones collecting resources from asteroids
    """

    @property
    def get_my_first_asteroid(self):
        distances = [self.context.distance_to(i) for i in self.context.asteroids]
        sorted_dist = sorted(distances)
        target = self.context.asteroids[distances.index(sorted_dist[self.context.idx - 1])]
        return target

    @property
    def get_my_asteroid(self):
        if self.context.old_asteroid:
            distances = [self.context.old_asteroid.distance_to(i) for i in self.context.asteroids]
        else:
            distances = [self.context.distance_to(i) for i in self.context.asteroids]
        sorted_dist = sorted(distances)
        for asteroid in sorted_dist:
            target = self.context.asteroids[distances.index(asteroid)]
            self.context.old_asteroid = target
            if target.payload == 0:
                continue
            else:
                targ_counter = 0
                for friend in self.context.dispatcher.collectors:
                    if friend.target == target:
                        targ_counter += 1
                if len([i.payload > 0 for i in self.context.asteroids]) == 1:
                    return target
                if targ_counter >= MAX_DRONES_PER_ASTEROID:
                    continue
                else:
                    return target
        else:
            return self.context.mothership

    def on_born(self):
        self.context.target = self.get_my_first_asteroid
        self.context.go_to_target(self.context.target)

    def on_stop_at_asteroid(self, asteroid):
        if sum(i.payload for i in self.context.asteroids) == 0:
            self.context.go_to_target(self.context.mothership)
        if self.context.payload + asteroid.payload > 100:
            next_target = self.context.mothership
        else:
            next_target = self.get_my_asteroid
        self.context.turn_to(next_target)
        self.context.load_from(asteroid)

    def on_stop_at_point(self, target):
        self.context.target = self.get_my_asteroid
        self.context.go_to_target(self.context.target)

    def on_wake_up(self):
        self.context.target = self.get_my_asteroid
        self.context.go_to_target(self.context.target)

    def on_load_complete(self):
        if self.context.is_full:
            self.context.target = self.context.mothership
        else:
            self.context.target = self.get_my_asteroid
        self.context.go_to_target(self.context.target)

    def on_stop_at_mothership(self, mothership):
        self.context.target = self.get_my_asteroid
        self.context.turn_to(self.context.target)
        self.context.unload_to(mothership)

    def on_unload_complete(self):
        self.context.target = self.get_my_asteroid
        if self.context.distance_to(self.context.target) < MOTHERSHIP_HEALING_DISTANCE:
            self.context.go_to_target(self.context.target)
        else:
            self.context.smart_moves(self.context.smart_target(self.context.target))

    def on_heartbeat(self):
        if all(i.is_empty for i in self.context.asteroids):
            self.context.dispatcher.get_new_roles()


class Scavenger(Behavior):
    """
    Drones collecting resources from dead bases
    """

    def on_stop_at_mothership(self, mothership):
        if not mothership.is_alive:
            self.context.load_from(mothership)
        else:
            self.context.unload_to(mothership)

    def on_stop_at_point(self, target):
        if self.context.scavenger_target.payload > 0:
            self.context.load_from(self.context.scavenger_target)

    def on_load_complete(self):
        if self.context.scavenger_target.is_empty:
            new_scav_target = self.context.dispatcher.get_scavenger_target(self)
            new_forw_target = self.context.dispatcher.get_forward_target(self)
            if new_scav_target:
                self.context.scavenger_target = new_scav_target
            else:
                if new_forw_target:
                    self.context.forward_target = new_forw_target
                    self.context.change_state(Forward())
                else:
                    self.context.stop()
        else:
            self.context.move_at(self.context.my_mothership)

    def on_unload_complete(self):
        if not self.context.is_full:
            self.context.move_at(self.context.scavenger_target)
        else:
            self.context.move_at(self.context.my_mothership)

    def on_heartbeat(self):
        if self.context.meter_2 < self.context.limit_health:
            self.context.prev_state = Scavenger()
            self.context.change_state(ToHeal())
        else:
            if self.context.is_full:
                self.context.move_at(self.context.my_mothership)
            else:
                if self.context.scavenger_target:
                    self.context.move_at(self.context.scavenger_target)


class Forward(Behavior):
    """
    Drones attacks enemy base
    """

    def attack(self):
        self.context.turn_to(self.context.forward_target)
        self.context.gun.shot(self.context.forward_target)

    def prepare_attack(self):
        if self.context.forward_target:
            self.context.ready_to_shoot = True
            self.attack()
        else:
            self.at_position()

    def at_position(self):
        if self.context.attack_position:
            self.context.move_at(self.context.attack_position)
        else:
            self.context.forward_target = self.context.dispatcher.get_forward_target(self)
            self.context.dispatcher.get_position_forward(self, self.context.forward_target)
            self.context.move_at(self.context.attack_position)

    def on_stop_at_asteroid(self, asteroid):
        self.prepare_attack()

    def on_stop_at_point(self, target):
        self.prepare_attack()

    def on_load_complete(self):
        self.at_position()

    def on_stop_at_mothership(self, mothership):
        self.at_position()

    def on_unload_complete(self):
        self.at_position()

    def on_heartbeat(self):
        if self.context.ready_to_shoot:
            if self.context.meter_2 < self.context.limit_health:
                self.context.prev_state = Forward()
                self.context.ready_to_shoot = False
                self.context.change_state(ToHeal())
            else:
                if self.context.forward_target:
                    self.attack()
                    if not self.context.forward_target.is_alive:
                        self.context.scavenger_target = self.context.forward_target
                        self.context.change_state(Scavenger())
        else:
            self.at_position()


class Defender(Behavior):
    """
    Drones defend their base
    """

    @property
    def get_defend_position(self):
        position = Point(self.context.mothership.coord.x, self.context.mothership.coord.y + SAFE_DEFENDER_DIST)
        if position.y > theme.FIELD_HEIGHT:
            position = Point(self.context.mothership.coord.x, self.context.mothership.coord.y - SAFE_DEFENDER_DIST)
        return position

    def attack(self):
        if self.context.distance_to(self.context.dispatcher.defender_target_to_focus) > self.context.attack_range + 60:
            self.context.turn_to(self.context.dispatcher.defender_target_to_focus)
        else:
            self.context.turn_to(self.context.dispatcher.defender_target_to_focus)
            self.context.gun.shot(self.context.dispatcher.defender_target_to_focus)

    def at_position(self):
        self.context.target = self.get_defend_position
        self.context.move_at(self.context.target)

    def on_heartbeat(self):
        if self.context.ready_to_shoot:
            if self.context.dispatcher.defender_target_to_focus:
                self.attack()
        else:
            self.at_position()

    def on_stop_at_mothership(self, mothership):
        self.at_position()

    def on_unload_complete(self):
        self.at_position()

    def on_stop_at_point(self, target):
        self.context.ready_to_shoot = True
        if self.context.dispatcher.defender_target_to_focus:
            self.context.turn_to(self.context.dispatcher.defender_target_to_focus)
            self.context.gun.shot(self.context.dispatcher.defender_target_to_focus)

    def on_load_complete(self):
        self.at_position()

    def on_stop_at_asteroid(self, asteroid):
        self.at_position()


class MainDefender(Defender):
    """
    Drone that defining target to shoot
    """

    @property
    def get_enemy(self):
        drones = [(drone, self.context.distance_to(drone)) for drone in self.context.scene.drones if
                  self.context.team != drone.team and drone.is_alive
                  and drone.distance_to(self.context.scene.get_mothership(drone.team)) > 10]
        drones.sort(key=lambda x: x[1])
        if drones:
            return drones[0][0]
        else:
            return None

    @property
    def get_defend_position(self):
        position = Point(self.context.mothership.coord.x + SAFE_DEFENDER_DIST, self.context.mothership.coord.y)
        if position.x > theme.FIELD_WIDTH:
            position = Point(self.context.mothership.coord.x - SAFE_DEFENDER_DIST, self.context.mothership.coord.y)
        return position

    def on_heartbeat(self):
        if self.context.ready_to_shoot:
            self.context.dispatcher.defender_target_to_focus = self.get_enemy
            if self.context.dispatcher.defender_target_to_focus:
                self.attack()
            else:
                self.context.stop()
        else:
            self.at_position()

    def on_stop_at_point(self, target):
        self.context.ready_to_shoot = True
        self.context.dispatcher.defender_target_to_focus = self.get_enemy
        self.context.turn_to(self.context.dispatcher.defender_target_to_focus)
        self.context.gun.shot(self.context.dispatcher.defender_target_to_focus)


class ToHeal(Behavior):
    """
    Drones that need to be healed
    """

    def on_heartbeat(self):
        self.context.move_at(self.context.my_mothership)

    def on_stop_at_mothership(self, mothership):
        if not self.context.is_empty:
            self.context.unload_to(mothership)
        else:
            if isinstance(self.context.prev_state, Forward):
                self.context.forward_target = self.context.dispatcher.get_forward_target(self)
                self.context.dispatcher.get_position_forward(self, self.context.forward_target)
            self.context.change_state(self.context.prev_state)

    def on_unload_complete(self):
        self.context.change_state(self.context.prev_state)
