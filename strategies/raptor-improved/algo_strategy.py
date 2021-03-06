from operator import itemgetter
import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from misc import *
from constants import *
from standard_strategy import execute_standard_strategy

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        # set some global constants, for ease of use
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER, UNIT_TYPES
        unit_type_names = [itemgetter("shorthand")(item) for item in config["unitInformation"][:6]]
        FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER = unit_type_names
        # python object lol
        for k,v in zip(unit_type_names, config["unitInformation"][:6]):
            UNIT_TYPES[k] = v

        self.config = config
        self.state = {
            "attack_log": {
                "PING": [0,0],
                "EMP": [0,0],
                "SCRAMBLER": [0,0],
            },
            "emp_mode": UNLOADED,
            "emp_round": 0,
            "danger_unit": PING, # TODO update this to whoever deals lots of damage, enemy attack patterns, etc.
            "opponent_battlefield_pattern": None,
            "navigator": gamelib.navigation.ShortestPathFinder(),
            "breaches": {
                "inner": {
                    3: [],
                    4: [],
                    5:[],
                },
                "outerL":  {
                    3: [],
                    4: [],
                    5:[],
                },
                "outerR":  {
                    3: [],
                    4: [],
                    5:[],
                },
                "wallL":  {
                    3: [],
                    4: [],
                    5:[],
                },
                "wallR":  {
                    3: [],
                    4: [],
                    5:[],
                },
                "total": [],
            },
        }


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """

        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write("Turn {}:".format(game_state.turn_number))
        # if len(self.state["breaches"]["total"])>1:
        #     gamelib.debug_write(f"""o: {self.state["breaches"]["outerR"][3][-1]}""")
        #     gamelib.debug_write(f"""o: {self.state["breaches"]["outerR"][4][-1]}""")
        #     gamelib.debug_write(f"""o: {self.state["breaches"]["outerR"][5][-1]}""")
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.
        
        for reg in MAP_REGIONS:
            self.state["breaches"][reg][3].append(0)
            self.state["breaches"][reg][4].append(0)
            self.state["breaches"][reg][5].append(0)
        self.state["breaches"]["total"].append(0)

        # gather some state
        self.analyze_board(game_state)

        ####### Can specify which type of gameplay we want to use here: ########
        # TODO:
        # read opponent turn 1 placements
        # opponent_type = classification_function.classify(placements)
        # our_strategy = get_counter(opponent_type)
        # execute(our_strategy)

        execute_standard_strategy(game_state, self.state)

        game_state.submit_turn()

    ############################ ANALYZE BOARD #################################
    def analyze_board(self, game_state):
        self.state["player_units"] = locate_units(game_state, is_player = True)
        self.state["enemy_units"] = locate_units(game_state, is_player = False)
        # collect pattern every round for a better understanding of their pattern, 
        # ignore if it's over 25 rounds as it unlikely to change its defensive config
        turn = game_state.turn_number
        if turn <= 25:
            self.state["opponent_battlefield_pattern"] = get_opp_def_setup(game_state)

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at: https://docs.c1games.com/json-docs.html
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                region = get_edge_region(location[0], location[1])
                cur=self.state["breaches"][region][breach[2]]
                total=self.state["breaches"]["total"]
                cur[-1]+=1
                total[-1]+=1

    ################### SCRAMBLER DEFENSE AGAINST PING RUSH ####################
    def launch_scrambler_defense(self, game_state):
        # defend against ping rush with scramblers:
        potential_enemy_pings = game_state.get_resource(game_state.BITS, 1)
        hp_per_ping = len(self.enemy_units[ENCRYPTOR]) * 3 + 15
        destructor_hits_per_ping = math.ceil(hp_per_ping / 16)
        #TODO only count destructors in the center:
        destructor_kill_count = int(len(self.player_units[DESTRUCTOR]) * 6 / destructor_hits_per_ping)
        surviving_pings = potential_enemy_pings - destructor_kill_count
        scramblers_needed = 0
        if surviving_pings > 2:
            scrambler_hits_per_ping = math.ceil(hp_per_ping / 20)
            scrambler_fire_rate = 7
            # purposely round down:
            scramblers_needed = int(scrambler_hits_per_ping * surviving_pings / scrambler_fire_rate) 
        # anti emp measures:
        if game_state.get_resource(game_state.BITS, 1) >= 15:
            scramblers_needed = 2

        # more risk:
        scramblers_needed -= 1 

        # don't spoil a attack for scrambling:
        my_bits = game_state.get_resource(game_state.BITS) 
        if self.mode == ATTACK_MODE and game_state.project_future_bits(1, 0, my_bits - scramblers_needed) < 12: 
            # TODO dunno what best strat is here, to focus on defense or offense?
            #scramblers_needed = 0
            if random.random() < 0.7: scramblers_needed = 0 # focus on attack 70% of time
        # unless we about to get rickity rekt:
        if scramblers_needed > 0:
            gamelib.debug_write(f"Generating {scramblers_needed} scramblers.")
            if units_at(game_state, [[13,1], [14,2]]):
                scrambler_locs = [[9,4]]
            elif units_at(game_state, [[13,2], [14,1]]):
                scrambler_locs = [[18,4]]
            else:
                scrambler_locs = [[9,4], [18,4]]
            for i in range(scramblers_needed):
                game_state.attempt_spawn(SCRAMBLER, [scrambler_locs[i % len(scrambler_locs)]])



    ########################### EMERGENCY RESPONSE #############################

    def wall_emergency(self, game_state):
        # TODO
        pass


    def central_emergency(self, game_state):
        # TODO
        pass


    def outer_emergency(self, game_state):
        # TODO
        pass


    
if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
