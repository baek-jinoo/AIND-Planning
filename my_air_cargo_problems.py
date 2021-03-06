from aimacode.logic import PropKB
from aimacode.planning import Action
from aimacode.search import (
    Node, Problem,
)
from aimacode.utils import (expr, Expr)
from lp_utils import (
    FluentState, encode_state, decode_state,
)
from my_planning_graph import PlanningGraph

from functools import lru_cache


class AirCargoProblem(Problem):
    def __init__(self, cargos, planes, airports, initial: FluentState, goal: list):
        """

        :param cargos: list of str
            cargos in the problem
        :param planes: list of str
            planes in the problem
        :param airports: list of str
            airports in the problem
        :param initial: FluentState object
            positive and negative literal fluents (as expr) describing initial state
        :param goal: list of expr
            literal fluents required for goal test
        """
        self.state_map = initial.pos + initial.neg
        self.initial_state_TF = encode_state(initial, self.state_map)
        Problem.__init__(self, self.initial_state_TF, goal=goal)
        self.cargos = cargos
        self.planes = planes
        self.airports = airports
        self.actions_list = self.get_actions()

    def get_actions(self):
        """
        This method creates concrete actions (no variables) for all actions in the problem
        domain action schema and turns them into complete Action objects as defined in the
        aimacode.planning module. It is computationally expensive to call this method directly;
        however, it is called in the constructor and the results cached in the `actions_list` property.

        Returns:
        ----------
        list<Action>
            list of Action objects
        """

        # TODO create concrete Action objects based on the domain action schema for: Load, Unload, and Fly
        # concrete actions definition: specific literal action that does not include variables as with the schema
        # for example, the action schema 'Load(c, p, a)' can represent the concrete actions 'Load(C1, P1, SFO)'
        # or 'Load(C2, P2, JFK)'.  The actions for the planning problem must be concrete because the problems in
        # forward search and Planning Graphs must use Propositional Logic

        def load_actions():
            """Create all concrete Load actions and return a list

            :return: list of Action objects
            """
            loads = []
            for cargo in self.cargos:
                for plane in self.planes:
                    for airport in self.airports:
                        precond_pos = [
                            expr("At({}, {})".format(cargo, airport)),
                            expr("At({}, {})".format(plane, airport)),
                        ]
                        precond_neg = []
                        effect_add = [expr("In({}, {})".format(cargo, plane))]
                        effect_neg = [expr("At({}, {})".format(cargo, airport))]
                        load = Action(expr("Load({}, {}, {})".format(cargo, plane, airport)),
                                      [precond_pos, precond_neg],
                                      [effect_add, effect_neg])
                        loads.append(load)
            return loads

        def unload_actions():
            """Create all concrete Unload actions and return a list

            :return: list of Action objects
            """
            unloads = []
            for cargo in self.cargos:
                for plane in self.planes:
                    for airport in self.airports:
                        precond_pos = [
                            expr("In({}, {})".format(cargo, plane)),
                            expr("At({}, {})".format(plane, airport)),
                        ]
                        precond_neg = []
                        effect_add = [expr("At({}, {})".format(cargo, airport))]
                        effect_neg = [expr("In({}, {})".format(cargo, plane))]
                        unload = Action(expr("Unload({}, {}, {})".format(cargo, plane, airport)),
                                      [precond_pos, precond_neg],
                                      [effect_add, effect_neg])
                        unloads.append(unload)
            return unloads

        def fly_actions():
            """Create all concrete Fly actions and return a list

            :return: list of Action objects
            """
            flys = []
            for fr in self.airports:
                for to in self.airports:
                    if fr != to:
                        for p in self.planes:
                            precond_pos = [expr("At({}, {})".format(p, fr)), ]
                            precond_neg = []
                            effect_add = [expr("At({}, {})".format(p, to))]
                            effect_rem = [expr("At({}, {})".format(p, fr))]
                            fly = Action(expr("Fly({}, {}, {})".format(p, fr, to)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            flys.append(fly)
            return flys

        return load_actions() + unload_actions() + fly_actions()

    def actions(self, state: str) -> list:
        """ Return the actions that can be executed in the given state.

        :param state: str
            state represented as T/F string of mapped fluents (state variables)
            e.g. 'FTTTFF'
        :return: list of Action objects
        """
        kb = self.loaded_kb(state)
        possible_actions = []
        for action in self.actions_list:
            if action.check_precond(kb, action.args):
                possible_actions.append(action)

        return possible_actions

    def result(self, state: str, action: Action):
        """ Return the state that results from executing the given
        action in the given state. The action must be one of
        self.actions(state).

        :param state: state entering node
        :param action: Action applied
        :return: resulting state after action
        """
        kb = self.loaded_kb(state)
        action(kb, action.args)
        new_state = FluentState(kb.clauses, [])
        return encode_state(new_state, self.state_map)

    def loaded_positive_kb(self, state: str):
        """ Return the knowledge base loaded
        with state and state_map with only positive clauses

        :param state: state entering node
        :return: knowledge base with state loaded
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        return kb

    def loaded_kb(self, state: str):
        """ Return the knowledge base loaded
        with state and state_map

        :param state: state entering node
        :return: knowledge base with state loaded
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).sentence())
        return kb

    def goal_test(self, state: str) -> bool:
        """ Test the state to see if goal is reached

        :param state: str representing state
        :return: bool
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                return False
        return True

    def h_1(self, node: Node):
        # note that this is not a true heuristic
        h_const = 1
        return h_const

    @lru_cache(maxsize=8192)
    def h_pg_levelsum(self, node: Node):
        """This heuristic uses a planning graph representation of the problem
        state space to estimate the sum of all actions that must be carried
        out from the current state in order to satisfy each individual goal
        condition.
        """
        # requires implemented PlanningGraph class
        pg = PlanningGraph(self, node.state)
        pg_levelsum = pg.h_levelsum()
        return pg_levelsum

    @lru_cache(maxsize=8192)
    def h_ignore_preconditions(self, node: Node):
        """This heuristic estimates the minimum number of actions that must be
        carried out from the current state in order to satisfy all of the goal
        conditions by ignoring the preconditions required for an action to be
        executed.
        """
        # check if clauses match goal state
        kb_pos = self.loaded_positive_kb(node.state)
        reached_gaol = True
        for clause in self.goal:
            if clause not in kb_pos.clauses:
                reached_gaol = False

        if reached_gaol:
            return 0

        # if not get actions_list and find an action that will get node.state
        # closer to goal
        kb = self.loaded_kb(node.state)
        goal_set = set(self.goal)
        count = 0
        while len(goal_set) > 0:
            for action in self.actions_list:
                args = action.args
                new_expr = Expr(action.name, *args)
                new_action = Action(new_expr, [[], []], [action.effect_add, action.effect_rem])
                action = new_action
                temp_kb = PropKB()
                temp_kb.clauses = kb.clauses.copy()
                action(temp_kb, action.args)

                remaining_goals = goal_set - set(temp_kb.clauses)
                if len(goal_set) > len(remaining_goals):
                    count += 1
                    goal_set = remaining_goals
                    kb = temp_kb
                    break
        return count


def air_cargo_p1() -> AirCargoProblem:
    cargos = ['C1', 'C2']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           ]
    neg = [expr('At(C2, SFO)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('At(C1, JFK)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('At(P1, JFK)'),
           expr('At(P2, SFO)'),
           ]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)


def air_cargo_p2() -> AirCargoProblem:
    cargos = ['C1', 'C2', 'C3']
    planes = ['P1', 'P2', 'P3']
    airports = ['JFK', 'SFO', 'ATL']
    pos = [
        expr('At(C1, SFO)'),
        expr('At(C2, JFK)'),
        expr('At(C3, ATL)'),
        expr('At(P1, SFO)'),
        expr('At(P2, JFK)'),
        expr('At(P3, ATL)'),
    ]
    neg = [
        expr('At(C1, JFK)'),
        expr('At(C1, ATL)'),
        expr('At(C2, SFO)'),
        expr('At(C2, ATL)'),
        expr('At(C3, SFO)'),
        expr('At(C3, JFK)'),
        expr('At(P1, JFK)'),
        expr('At(P1, ATL)'),
        expr('At(P2, ATL)'),
        expr('At(P2, SFO)'),
        expr('At(P3, SFO)'),
        expr('At(P3, JFK)'),
        expr('In(C1, P1)'),
        expr('In(C1, P2)'),
        expr('In(C1, P3)'),
        expr('In(C2, P1)'),
        expr('In(C2, P2)'),
        expr('In(C2, P3)'),
        expr('In(C3, P1)'),
        expr('In(C3, P2)'),
        expr('In(C3, P3)'),
    ]
    init = FluentState(pos, neg)
    goal = [
        expr('At(C1, JFK)'),
        expr('At(C2, SFO)'),
        expr('At(C3, SFO)')
    ]

    return AirCargoProblem(cargos, planes, airports, init, goal)

def air_cargo_p3() -> AirCargoProblem:
    cargos = ['C1', 'C2', 'C3', 'C4']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO', 'ATL', 'ORD']
    pos = [
        expr('At(C1, SFO)'),
        expr('At(C2, JFK)'),
        expr('At(C3, ATL)'),
        expr('At(C4, ORD)'),
        expr('At(P1, SFO)'),
        expr('At(P2, JFK)'),
    ]
    cargoports = {
        expr('At({}, {})'.format(c, a)) for c in cargos for a in airports
    }
    planeports = {
        expr('At({}, {})'.format(p, a)) for p in planes for a in airports
    }
    cargoplanes = {
        expr('In({}, {})'.format(c, p)) for p in planes for c in cargos
    }
    neg = list(cargoports.union(planeports).union(cargoplanes) - set(pos))

    init = FluentState(pos, neg)
    goal = [
        expr('At(C1, JFK)'),
        expr('At(C3, JFK)'),
        expr('At(C2, SFO)'),
        expr('At(C4, SFO)'),
    ]
    return AirCargoProblem(cargos, planes, airports, init, goal)
