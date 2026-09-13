import unittest

from agents.bfs import BFSAgent
from agents.dfs import DFSAgent
from agents import AGENTS_MAP, get_agent_name
from core.agent import Agent
from core.map import Map


class AgentsTests(unittest.TestCase):
    def test_agent_snapshots_start_and_goal_and_falls_back_to_class_name(self):
        class UnnamedAgent(Agent):
            def find_path(self):
                return [self.start, self.goal]

        map_obj = Map([list('--'), list('--')], diagonal_moves=False)
        map_obj.set_start_goal((0, 0), (1, 1))
        agent = UnnamedAgent(map_obj)

        self.assertEqual(agent.start, (0, 0))
        self.assertEqual(agent.goal, (1, 1))
        self.assertEqual(agent.get_name(), 'UnnamedAgent')

    def test_builtin_agents_are_discovered_by_name(self):
        self.assertTrue({'BFS', 'DFS', 'Dijkstra'}.issubset(AGENTS_MAP))
        self.assertTrue(any(name.startswith('A*') for name in AGENTS_MAP))
        self.assertEqual(get_agent_name(BFSAgent), 'BFS')

    def test_agents_record_expanded_nodes_via_move_helper(self):
        for agent_type in AGENTS_MAP.values():
            map_obj = Map([list('--'), list('--')], diagonal_moves=False)
            map_obj.set_start_goal((0, 0), (1, 1))
            agent = agent_type(map_obj)
            self.assertIsNotNone(agent.run())
            self.assertTrue(agent.get_explored(), agent_type.__name__)

    def test_bfs_returns_a_valid_path(self):
        map_obj = Map([list('---'), list('-#-'), list('---')], diagonal_moves=False)
        map_obj.set_start_goal((0, 0), (2, 2))

        path = BFSAgent(map_obj).run()

        self.assertIsNotNone(path)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (2, 2))
        self.assertTrue(all(not map_obj.is_wall(x, y) for x, y in path))

    def test_dfs_returns_none_when_unreachable(self):
        map_obj = Map([list('---'), list('###'), list('---')], diagonal_moves=False)
        map_obj.set_start_goal((0, 0), (2, 2))

        self.assertIsNone(DFSAgent(map_obj).run())

    def test_agents_return_none_without_start_or_goal(self):
        map_obj = Map([list('--'), list('--')], diagonal_moves=False)

        self.assertIsNone(BFSAgent(map_obj).run())
        self.assertIsNone(DFSAgent(map_obj).run())

    def test_base_agent_is_abstract_by_behavior(self):
        with self.assertRaises(NotImplementedError):
            Agent(Map([list('-')])).run()

    def test_exploration_sink_receives_marked_locations(self):
        locations = []
        agent = Agent(Map([list('-')]))
        agent._exploration_sink = locations.append

        agent.mark_explored(0, 0)

        self.assertEqual(agent.get_explored(), [(0, 0)])
        self.assertEqual(locations, [(0, 0)])


if __name__ == '__main__':
    unittest.main()
