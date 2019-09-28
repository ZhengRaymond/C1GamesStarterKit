import random
from operator import attrgetter
from collections import defaultdict
from copy import deepcopy

import gamelib
from constants import *

def remove_specific_unit_type(unit_type, locations, game_state):
    game_map = game_state.game_map
    for location in locations:
        if game_map[location].unit_type == unit_type:
            game_state.attempt_remove(location)


def build_complete(unit_types, locations, game_state):
    unit_types = set(unit_types)
    for location in locations:
        units_at_location = game_state.game_map[location]
        unit_types_at_location = set([u.unit_type for u in units_at_location])
        if len(unit_types_at_location & unit_types) == 0:
            return False
    return True
        

def split_resources_with_preference(num_needed, resources_available, preference, alternative):
    #assert(alternative.cost < preference.cost)

    # solve the following problem:
    # max
    #   num_alternative
    # s.t.
    #   num_preference * preference.cost + num_alternative * alternative.cost < resource_available
    #   num_preference + num_alternative == num_needed

    # first use cheap 
    num_preference = 0
    num_alternative = num_needed
    pref_cost, alt_cost = UNIT_TYPES[preference]["cost"], UNIT_TYPES[alternative]["cost"]
    resources_left = resources_available - num_needed * alt_cost
    while resources_left + alt_cost - pref_cost >= 0 and num_preference < num_needed:
        num_preference += 1
        num_alternative -= 1
        resources_left += alt_cost - pref_cost

    return num_preference, num_alternative


def locate_units(game_state, is_player):
    """ do not use, use the stored state """
    # TODO: modify so that we differentiate between units on the edges, in the center, or by the border center
    all_units = defaultdict(list) 
    locations = PLAYER_LOCATIONS if is_player else ENEMY_LOCATIONS
    tiles = get_tiles(game_state, locations)
    for tile in tiles:
        for unit in tile:
            all_units[unit.unit_type].append(unit)
    return all_units


def units_at(game_state, locations):
    return all(game_state.contains_stationary_unit(location) for location in locations)


def empty_at(game_state, locations):
    return not any(game_state.contains_stationary_unit(location) for location in locations)


def calculate_build_plan_cost(game_state, build_plan):
    cost = 0
    m = game_state.game_map
    for unit_type, locs in build_plan.items():
        for loc in locs:
            if m[loc].unit_type != unit_type:
                cost += unit_type.cost
    return cost


def get_tiles(game_state, locations):
    return (game_state.game_map[location] for location in locations)


def get_need_to_build(game_state, unit_type, locations):
    tiles = get_tiles(game_state, locations)
    tile_types = (attrgetter("unit_type")(tile[0]) for tile in tiles if tile)
    specific_tile_types = filter(lambda tile_type: tile_type == unit_type, tile_types)
    return len(locations) - len(list(specific_tile_types))


#def budget_spawn(game_state, budget, unit_type, locations, strategy="random"):
#    empty_locations = filter(lambda item: not game_state.contains_stationary_unit(item), locations) 
#    if strategy == "random":
#        chosen_locations = random.sample(empty_locations, budget)
#        game_state.attempt_spawn(unit_type, chosen_locations)
#    elif strategy == "even":
#        pass


def replace_unit(game_state, location, old_unit, new_unit):
    if UNIT_TYPES[new_unit]["cost"] > game_state.get_resource(game_state.CORES):
        return False
    tile = game_state.game_map[location]
    if tile and tile[0].unit_type == old_unit:
        game_state.attempt_remove(location)
    game_state.attempt_spawn(new_unit, [location])
    return True
        

def replace_and_update_wall(game_state, state, location, old_unit, new_unit):
    if UNIT_TYPES[new_unit]["cost"] > game_state.get_resource(game_state.CORES):
        return False
    tile = game_state.game_map[location]
    if tile and tile[0].unit_type == old_unit:
        game_state.attempt_remove(location)
    game_state.attempt_spawn(new_unit, [location])
    return True
        

def print_map(game_state):
    s = "\n"
    s += "Map:\n"
    s += "".join("=" * 112)
    s = "\n"
    m = game_state.game_map
    for x in range(28):
        for y in range(28):
            ch = ' '
            if abs(x - 13.5) + abs(y - 13.5) <= 14:
                ch = '.'
                tile = m[[y,27-x]]
                if tile:
                    ch = tile[0].unit_type
            s += "%4s" % ch
        s += "\n"
    s += "".join("=" * 112)
    s += "\n\n"
    gamelib.debug_write(s)


def split_evenly(n, buckets):
    sz = int(n / buckets)
    leftovers = n % buckets
    counts = [sz] * buckets
    for i in range(leftovers):
        counts[i] += 1
    return counts


def get_damage_in_path(game_state, path):
    return sum(len(game_state.get_attackers(loc, 0)) for loc in path)



def is_edge(loc):
    return abs(loc[0] - 13.5) + abs(loc[1] - 13.5) == 14


def get_hole(state):
    return state["hole"][state["emp_round"] % len(state["hole"])]


def set_budget(game_state, limit):
    num_cores = game_state.get_resource(game_state.CORES)
    game_state._GameState__set_resource(game_state.CORES, -num_cores) # zero out
    real_limit = min(limit, num_cores)
    game_state._GameState__set_resource(game_state.CORES, real_limit)
    return num_cores - real_limit

def unset_budget(game_state, saved):
    game_state._GameState__set_resource(game_state.CORES, saved)


def set_reserve(game_state, reserve):
    num_cores = game_state.get_resource(game_state.CORES)
    real_reserve = min(reserve, num_cores)
    game_state._GameState__set_resource(game_state.CORES, -real_reserve)
    return real_reserve

def unset_reserve(game_state, real_reserve):
    game_state._GameState__set_resource(game_state.CORES, real_reserve)


def get_loc(loc, reverse = False):
    x, y = loc
    if reverse:
        x = 27 - loc[0]
    return [x,y]

def emps_needed(game_state, reverse):
    edge = TOP_RIGHT if reverse else TOP_LEFT
    my_gs = deepcopy(game_state)
    curr_loc = get_loc([6,9], reverse)
    for x in range(1,9):
        while not is_edge(curr_loc) or x<=0:
            next_step = my_gs.find_path_to_edge(curr_loc, edge)[1] # index check
            for num in range(x):
                my_gs.game_map.add_unit(EMP, next_step, 0)
            units = my_gs.game_map[next_step[0],next_step[1]]
            for unit in units:
                my_gs.get_target(unit).stability-=15
            enemies = my_gs.game_map.get_locations_in_range(next_step, 3.5)
            for enemy in enemies:
                temp = my_gs.game_map[enemy[0],enemy[1]]
                if len(temp)>0 and my_gs.temp.unit_type==DESTRUCTOR:
                    my_gs.get_target(temp).stability-=8
            units= my_gs.game_map.game_map[next_step[0], next_step[1]]
            for unit in units:
                if unit.stability < 0:
                    x-=1
            my_gs.game_map.remove_unit(next_step)
            enemies = my_gs.game_map.get_locations_in_range(next_step, 4.5)
            for enemy in enemies:
                if enemy.stability<=0:
                    my_gs.game_map.remove_unit([enemy.x, enemy.y])
            curr_loc = next_step
        if x>0:
            return x
    return -1