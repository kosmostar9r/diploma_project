# -*- coding: utf-8 -*-


from astrobox.space_field import SpaceField
from enemies.driller import DrillerDrone
from enemies.reaper import ReaperDrone
from enemies.devastator import DevastatorDrone
from konovalov_a_v import KonovalovDrone

NUMBER_OF_DRONES = 5

if __name__ == '__main__':
    scene = SpaceField(
        field=(1200, 800),
        speed=5,
        asteroids_count=27,
        can_fight=True,
    )

    team_1 = [KonovalovDrone() for _ in range(NUMBER_OF_DRONES)]
    team_2 = [ReaperDrone() for _ in range(NUMBER_OF_DRONES)]
    team_3 = [DrillerDrone() for _ in range(NUMBER_OF_DRONES)]
    team_4 = [DevastatorDrone() for _ in range(NUMBER_OF_DRONES)]

    scene.go()

