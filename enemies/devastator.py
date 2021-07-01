# -*- coding: utf-8 -*-
from random import randint, choice, uniform, shuffle

import math
from astrobox.core import Drone, Asteroid
from astrobox.themes.default import MOTHERSHIP_HEALING_DISTANCE
from robogame_engine import GameObject
from robogame_engine.geometry import Point, Vector, normalise_angle
from robogame_engine.theme import theme


class Headquarters:
    """
    Штаб-кватриа.

    Раздаёт роли солдатам:
    collector - забирает элериум с ближайших астеройов и тащит его на баз;
    transport - собирает элериум с дальних астеройдов и подтаскивает его на астеройды, ближайшие к базе,
        откуда потом его забирает collector;
    combat - солдат с боевым оружием;
    spy - шпион-подрывник, атакует базы;
    base guard - ополчение, все ополченцы атакуют одного противника;
    turel - обороняет базу, под прикрытием базы ведет непрерывный огонь в сторону противника.

    Команды солдатам:
    move - двигаться к объекту;
    load - собрать элериум с объекта;
    unload - разгрузиться в объект;
    it is free - астеройд свободен для других дронов.
    Команды помещаются в очередь и выполняются последовательно.
    """
    roles = {}
    asteroids_for_basa = []
    moves_empty = 0
    moves_semi_empty = 0
    moves_full = 0

    def __init__(self):
        self.soldiers = []
        self.asteroids_in_work = []
        self.victims = []

    def new_soldier(self, soldier):
        number_drones = len(self.soldiers)
        self.get_roles(number_drones + 1, soldier.have_gun)
        self.add_soldier(soldier)
        for idx, soldier in enumerate(self.soldiers):
            self.give_role(soldier, idx)

    def give_role(self, soldier, index):
        all_roles = [Spy for _ in range(self.roles["spy"])]
        all_roles.extend([Transport for _ in range(self.roles["transport"])])
        all_roles.extend([CombatBot for _ in range(self.roles["combat"])])
        all_roles.extend([Collector for _ in range(self.roles["collector"])])
        all_roles.extend([BaseGuard for _ in range(self.roles["base guard"])])
        all_roles.extend([Turel for _ in range(self.roles["turel"])])
        this_role = all_roles[index]
        soldier.role = this_role(unit=soldier)

    def get_roles(self, number_drones, have_gun):
        if have_gun:
            transports = 0
            collectors = 5
            combats = 0
            spy = 0
            turel = 0
            guard = max(0, number_drones - collectors - spy - turel - transports - combats)
            Headquarters.roles["collector"] = collectors
            Headquarters.roles["transport"] = transports
            Headquarters.roles["spy"] = spy
            Headquarters.roles["combat"] = combats
            Headquarters.roles["base guard"] = guard
            Headquarters.roles["turel"] = turel
        else:
            collectors = number_drones
            Headquarters.roles["collector"] = collectors
            Headquarters.roles["transport"] = 0
            Headquarters.roles["spy"] = 0
            Headquarters.roles["combat"] = 0
            Headquarters.roles["base guard"] = 0
            Headquarters.roles["turel"] = 0

    def add_soldier(self, soldier):
        soldier.headquarters = self
        soldier.actions = []
        soldier.basa = None
        soldier.old_asteroid = None
        self.soldiers.append(soldier)

    def get_actions(self, soldier):

        enemies = self.get_enemies(soldier)
        if len([1 for s in self.soldiers if s.is_alive]) <= 2 \
                and not isinstance(soldier.role, Turel) \
                and len(enemies) > 0 \
                and soldier.have_gun:
            soldier.role.change_role(Turel)
            soldier.actions.append(['move', soldier.my_mothership, 1])
            return

        if (isinstance(soldier.role, Collector) and not isinstance(soldier.role, Transport)
                and soldier.have_gun and soldier.my_mothership.payload > 1000):
            enemies = self.get_enemies_by_base(soldier.my_mothership)
            for enemy in enemies:
                if not (enemy in self.victims):
                    soldier.role.change_role(Defender)
                    soldier.role.next_step(enemy)
                    self.victims = [enemy]
                    break

        if soldier.meter_2 < soldier.limit_health:
            soldier.actions.append(['move', soldier.my_mothership, 1])
            return

        purpose = soldier.role.next_purpose()
        if isinstance(soldier.role, BaseGuard):
            enemies = self.get_enemies_by_base(soldier.my_mothership, nearest=False)
            if enemies:
                purpose = enemies[0]
            else:
                purpose = None

        if purpose:
            soldier.role.next_step(purpose)
        else:
            soldier.role.change_role()

    def get_enemies_by_base(self, base, nearest=True):
        enemies = self.get_enemies(base)
        result = []
        for enemy in enemies:
            if enemy[1] < MOTHERSHIP_HEALING_DISTANCE * 2 or not nearest:
                result.append(enemy[0])
        return result

    def get_enemies(self, soldier):
        enemies = [(drone, soldier.distance_to(drone)) for drone in soldier.scene.drones if
                   soldier.team != drone.team and drone.is_alive]
        enemies.sort(key=lambda x: x[1])
        return enemies

    def get_bases(self, soldier):
        bases = [(base, soldier.distance_to(base)) for base in soldier.scene.motherships if
                 base.team != soldier.team and base.is_alive]
        bases.sort(key=lambda x: x[1])
        return bases

    def remove_item_asteroids_in_work(self, item):
        if item in self.asteroids_in_work:
            idx = self.asteroids_in_work.index(item)
            self.asteroids_in_work.pop(idx)

    def get_place_for_attack(self, soldier, target):
        """
        Выбор места для атаки цели, если цель не в радиусе атаки

        :param soldier: атакующий
        :param target: цель/объект атаки
        :return: Point  - место атаки или None - если не выбрано место атаки
        """
        if isinstance(target, GameObject):
            vec = Vector.from_points(target.coord, soldier.coord)
        elif isinstance(target, Point):
            vec = Vector.from_points(target, soldier.coord)
        else:
            raise Exception("target must be GameObject or Point!".format(target, ))

        dist = vec.module
        _koef = 1 / dist
        norm_vec = Vector(vec.x * _koef, vec.y * _koef)
        vec_gunshot = norm_vec * min(int(soldier.attack_range), int(dist))
        purpose = Point(target.coord.x + vec_gunshot.x, target.coord.y + vec_gunshot.y)
        angles = [0, 60, -60, 30, -30]
        shuffle(angles)
        for ang in angles:
            place = self.get_place_near(purpose, target, ang)
            if place and soldier.valide_place(place):
                return place
        return None

    def get_place_near(self, point, target, angle):
        """
        Расчет места рядом с point с отклонением angle от цели target
        :param point:
        :param target:
        :param angle:
        :return: new place point
        """
        vec = Vector(point.x - target.x, point.y - target.y)
        vec.rotate(angle)
        return Point(target.x + vec.x, target.y + vec.y)

    def get_place_near_mothership(self, soldier):
        center_field = Point(theme.FIELD_WIDTH // 2, theme.FIELD_HEIGHT // 2)
        vec = Vector.from_points(soldier.my_mothership.coord, center_field)
        dist = vec.module
        _koef = 1 / dist
        norm_vec = Vector(vec.x * _koef, vec.y * _koef)
        vec_position = norm_vec * MOTHERSHIP_HEALING_DISTANCE * 0.9
        position = Point(soldier.my_mothership.coord.x + vec_position.x, soldier.my_mothership.coord.y + vec_position.y)
        return position

    def save_static_move(self, soldier, purpose):
        length = soldier.distance_to(purpose)
        if soldier.is_empty:
            self.moves_empty += length
        elif soldier.free_space > 0:
            self.moves_semi_empty += length
        elif soldier.is_full:
            self.moves_full += length

    def print_statistic(self):
        print("\nСтатистика:")
        print("Пустой: ", round(self.moves_empty))
        print("Недогруженный: ", round(self.moves_semi_empty))
        print("Полный: ", round(self.moves_full))


class DevastatorDrone(Drone):
    actions = []
    headquarters = None
    attack_range = 0
    limit_health = 0.5
    cost_forpost = 0
    role = None

    # team_number нельзя переопределять - надо в библе сделать это _team_number а лучше __team_number

    def registration(self):
        if DevastatorDrone.headquarters is None:
            DevastatorDrone.headquarters = Headquarters()
        DevastatorDrone.headquarters.new_soldier(self)

    def born_soldier(self):
        self.registration()

        if self.have_gun:
            self.attack_range = self.gun.shot_distance
        self.limit_health = uniform(0.3, 0.5)

        if isinstance(self.role, Transport):
            candidats_asteroids_for_basa = min([(asteroid.distance_to(self.my_mothership), asteroid)
                                                for asteroid in self.asteroids if
                                                asteroid not in self.asteroids_for_basa])

            candidat_basa = candidats_asteroids_for_basa[1]
            self.add_basa(candidat_basa)
            self.basa = candidat_basa
        else:
            self.basa = self.my_mothership

    def next_action(self):
        i = 0
        while not self.actions:
            self.headquarters.get_actions(self)
            i += 1
            if i > 5:
                return

        action, object, is_performed = self.actions[0]
        if action == "move":
            if is_performed:
                self.actions[0][2] = 0
                self.move_to(object)
            else:
                self.actions.pop(0)
                self.next_action()

        elif action == "unload":
            self.actions.pop(0)
            self.unload_to(object)

        elif action == "load":
            self.actions.pop(0)
            self.load_from(object)

        elif action == "it is free":
            self.actions.pop(0)
            self.asteroid_is_free(object)
            self.next_action()

        elif action == "turn":
            self.actions.pop(0)
            self.turn_to(object)

        elif action == "shoot":
            self.actions.pop(0)
            self.shoot(object)
            self.next_action()

        elif action == "move to":
            if is_performed == 1:
                self.actions[0][2] = 2
                self.move_to_step(object)
            else:
                self.actions.pop(0)
                self.next_action()

        elif action == "pass":
            self.actions.pop(0)
            self.move_to_step(self.coord)

        else:
            # Пропускаем неизвестную команду
            self.actions.pop(0)
            self.next_action()

        if isinstance(object, Asteroid):
            self.old_asteroid = object

    def move_to(self, object):
        self.cost_forpost = 0
        self.headquarters.save_static_move(self, object)
        super().move_at(object)

    def move_to_step(self, object):
        distance = min(250, max(100, self.distance_to(object) - 50))
        vec = Vector.from_direction(self.direction, distance)
        new_coord = Point(x=self.coord.x + vec.x, y=self.coord.y + vec.y)
        self.move_to(new_coord)

    def shoot(self, object):

        if not self.have_gun:
            self.role.change_role(Collector)
            return

        if self.distance_to(self.my_mothership) < 150:
            self.actions.append(["pass", self, 1])
            return

        for partner in self.headquarters.soldiers:
            if not partner.is_alive or partner is self:
                continue

            if isinstance(object, GameObject) and self.distance_to(object) > partner.distance_to(object) \
                    and self.get_angle(partner, object) < 20 \
                    and self.distance_to(partner) < self.distance_to(object) \
                    and partner.distance_to(object) > 10 \
                    and not isinstance(self.role, Turel):
                point_attack = self.headquarters.get_place_for_attack(self, object)
                if point_attack and self.cost_forpost < 10:
                    self.actions.append(['move', point_attack, 1])
                return

        if not self.valide_place(self.coord):
            point_attack = self.headquarters.get_place_for_attack(self, object)
            if point_attack and self.cost_forpost < 10:
                self.actions.append(['move', point_attack, 1])

        self.cost_forpost += 1
        self.gun.shot(object)

    def valide_place(self, point: Point):
        """
        Подходит ли это место для атаки. Слишком рядом не должно быть партнеров и на линии огня тоже не должно быть
        партнеров.
        :param point: анализируемое место
        :return: True or False
        """
        # TODO - на линии огня не проанализирвать, т.к. не ясно где цель

        is_valide = 0 < point.x < theme.FIELD_WIDTH and 0 < point.y < theme.FIELD_HEIGHT
        for partner in self.headquarters.soldiers:
            if not partner.is_alive or partner is self:
                continue

            is_valide = is_valide and (partner.distance_to(point) >= self.save_distance)

        return is_valide

    @property
    def save_distance(self):
        return 50  # abs(2 * self.gun.shot_distance * math.sin(10))

    def get_angle(self, partner: GameObject, target: GameObject):
        """
        Получает угол между векторами self-target и partner-target
        """

        def scalar(vec1, vec2):
            return vec1.x * vec2.x + vec1.y * vec2.y

        v12 = Vector(self.coord.x - target.coord.x, self.coord.y - target.coord.y)
        v32 = Vector(partner.coord.x - target.coord.x, partner.coord.y - target.coord.y)
        _cos = scalar(v12, v32) / (v12.module * v32.module + 1.e-8)
        return math.degrees(math.acos(_cos))

    def add_basa(self, basa):
        self.headquarters.asteroids_for_basa.append(basa)

    def asteroid_is_free(self, asteroid):
        self.headquarters.remove_item_asteroids_in_work(asteroid)

    @property
    def asteroids_for_basa(self):
        if hasattr(self.headquarters, "asteroids_for_basa"):
            return self.headquarters.asteroids_for_basa
        else:
            return self.my_mothership

    # callbacks:
    def on_born(self):
        self.born_soldier()
        nearesst_aster = [(self.distance_to(aster), aster) for aster in self.asteroids]
        nearesst_aster.sort(key=lambda x: x[0])
        idx = len(self.headquarters.soldiers) - 1
        if self.have_gun:
            point_attack = self.headquarters.get_place_for_attack(self, nearesst_aster[idx][1])
            if point_attack:
                self.actions.append(['move to', point_attack, 1])
        else:
            self.actions.append(["move to", nearesst_aster[idx][1], 1])

        self.next_action()

    def on_stop_at_asteroid(self, asteroid):
        self.next_action()

    def on_load_complete(self):
        self.next_action()

    def on_stop_at_mothership(self, mothership):
        self.next_action()

    def on_unload_complete(self):
        self.next_action()

    def on_stop_at_point(self, target):
        self.next_action()

    def on_stop(self):
        self.next_action()

    def on_wake_up(self):
        self.actions = [["pass", self, 1]]
        self.next_action()


class Behavior:

    def __init__(self, unit: DevastatorDrone):
        self.unit = unit

    def change_role(self, role=None):
        soldier = self.unit
        if not role:
            soldier.role = soldier.role.next()
        else:
            soldier.role = role(soldier)

    def next(self):
        return Collector(self.unit)


class Collector(Behavior):

    def next_purpose(self):
        if self.unit.is_full:
            return self.unit.basa

        headquarters = self.unit.headquarters
        forbidden_asteroids = list(headquarters.asteroids_in_work)
        if isinstance(self, Transport):
            asteroids = [asteroid for asteroid in self.unit.scene.asteroids if asteroid not in forbidden_asteroids]
            free_elerium = sum([asteroid.payload for asteroid in asteroids])
            if free_elerium < 2000:
                headquarters.asteroids_for_basa = []
                self.unit.basa = self.unit.my_mothership
                return None
            else:
                forbidden_asteroids += headquarters.asteroids_for_basa

        if not hasattr(self.unit.scene, "asteroids"):
            return None

        asteroids = [asteroid for asteroid in self.unit.scene.asteroids if asteroid not in forbidden_asteroids]
        asteroids.extend([mothership for mothership in self.unit.scene.motherships
                          if not mothership.is_alive and not mothership.is_empty])
        asteroids.extend([drone for drone in self.unit.scene.drones
                          if not drone.is_alive and not drone.is_empty])

        first_purpose = self.find_nearest_purpose(asteroids=asteroids, threshold=self.unit.free_space)
        if first_purpose:
            return first_purpose

        purposes = [(asteroid.payload, asteroid) for asteroid in asteroids if asteroid.payload > 0]
        if purposes:
            second_purpose = max(purposes, key=lambda x: x[0])
            return second_purpose[1]
        return None

    def find_nearest_purpose(self, asteroids, threshold=1):
        soldier = self.unit
        purposes = [(soldier.distance_to(asteroid) + asteroid.distance_to(soldier.basa), asteroid)
                    for asteroid in asteroids if
                    asteroid.payload >= threshold]

        if purposes:
            if isinstance(self, Transport):
                purpose = max(purposes, key=lambda x: x[0])[1]
            else:
                purpose = min(purposes, key=lambda x: x[0])[1]
        else:
            purpose = None

        if purpose == soldier.old_asteroid:
            purpose = None

        return purpose

    def next_step(self, purpose):
        soldier = self.unit
        soldier.actions.append(['move', purpose, 1])
        if purpose == soldier.basa:
            if not soldier.is_empty:
                soldier.actions.append(['unload', purpose, 1])
            else:
                if soldier.my_mothership.payload > 1000:
                    soldier.role.change_role()
                return
        elif not soldier.is_full:
            soldier.headquarters.asteroids_in_work.append(purpose)
            soldier.actions.append(['load', purpose, 1])
        else:
            soldier.actions.append(['unload', soldier.my_mothership, 1])
        soldier.actions.append(['it is free', purpose, 1])

        if purpose == soldier.old_asteroid:
            soldier.next_action()
            if soldier.my_mothership.payload > 1000:
                self.change_role()

    def next(self):
        if self.unit.have_gun:
            return CombatBot(self.unit)
        return Demob(self.unit)


class Transport(Collector):
    def next(self):
        if self.unit.have_gun and self.unit.my_mothership.payload > 1000:
            return Spy(self.unit)
        return Collector(self.unit)


class Demob(Behavior):
    def next_purpose(self):
        return self.unit.my_mothership

    def next_step(self, purpose):
        soldier = self.unit
        if soldier.distance_to(soldier.my_mothership) > 10:
            soldier.actions = [['move', soldier.my_mothership, 1]]

        if not soldier.is_empty:
            soldier.actions.append(['unload', self.unit.my_mothership, 1])

    def next(self):
        return self


class Defender(Behavior):

    def __init__(self, unit: DevastatorDrone):
        super().__init__(unit)
        self.victim = None
        self.unit.actions = []

    def next_purpose(self):
        if self.victim and self.victim.is_alive:
            distance_victim = self.victim.distance_to(self.victim.my_mothership)
            if distance_victim > MOTHERSHIP_HEALING_DISTANCE:
                return self.victim
        self.victim = None
        return None

    def next_step(self, purpose):
        soldier = self.unit
        self.victim = purpose
        if soldier.distance_to(purpose) > soldier.attack_range:
            point_attack = soldier.headquarters.get_place_for_attack(soldier, purpose)
            if point_attack:
                soldier.actions.append(['move to', point_attack, 1])

        soldier.actions.append(['turn', purpose, 1])
        soldier.actions.append(['shoot', purpose, 1])

    def next(self):
        return Collector(self.unit)


class CombatBot(Defender):

    def next_purpose(self):
        self.victim = super().next_purpose()
        if self.victim and self.victim.distance_to(self.victim.my_mothership) > MOTHERSHIP_HEALING_DISTANCE:
            return self.victim

        soldier = self.unit
        enemies = soldier.headquarters.get_enemies(soldier)
        if enemies:
            self.victim = enemies[0][0]
            return self.victim

        self.victim = None
        return None

    def next(self):
        return Spy(self.unit)


class Spy(Defender):

    def next_purpose(self):
        if self.victim and self.victim.is_alive:
            return self.victim

        soldier = self.unit
        bases = soldier.headquarters.get_bases(soldier)
        if bases:
            self.victim = bases[0][0]
            return self.victim

        self.victim = None
        return None

    def next_step(self, target):
        soldier = self.unit
        self.victim = target
        if soldier.distance_to(target) > soldier.attack_range:
            point_attack = soldier.headquarters.get_place_for_attack(soldier, target)
            if point_attack:
                soldier.actions.append(['move to', point_attack, 1])

        soldier.actions.append(['turn', target, 1])
        soldier.actions.append(['shoot', target, 1])

    def next(self):
        soldier = self.unit
        enemies = soldier.headquarters.get_enemies(soldier)
        if enemies:
            return CombatBot(self.unit)
        return Collector(self.unit)


class BaseGuard(Defender):

    def next_purpose(self):
        if self.victim and self.victim.is_alive and self.victim.distance_to(
                self.victim.my_mothership) > MOTHERSHIP_HEALING_DISTANCE:
            return self.victim
        return None

    def next_step(self, target):
        soldier = self.unit
        self.victim = target
        if soldier.distance_to(target) > soldier.attack_range:
            point_attack = soldier.headquarters.get_place_for_attack(soldier, target)
            if point_attack:
                soldier.actions.append(['move to', point_attack, 1])
        soldier.actions.append(['turn', target, 1])
        soldier.actions.append(['shoot', target, 1])

    def next(self):
        soldier = self.unit
        enemies = soldier.headquarters.get_enemies(soldier)
        if len(enemies) == 0:
            return Collector(self.unit)
        return Spy(self.unit)


class Turel(Defender):

    def next_purpose(self):
        soldier = self.unit
        enemies = soldier.headquarters.get_enemies(soldier)
        if enemies:
            return enemies[0][0]

        return None

    def next_step(self, target):
        soldier = self.unit

        if target:
            soldier.actions.append(['turn', target, 1])
            soldier.actions.append(['shoot', target, 1])
        elif soldier.distance_to(soldier.my_mothership) > MOTHERSHIP_HEALING_DISTANCE * 0.95:
            point_attack = soldier.headquarters.get_place_near_mothership(soldier)
            soldier.actions.append(['move', point_attack, 1])

    def next(self):
        return Collector(self.unit)
