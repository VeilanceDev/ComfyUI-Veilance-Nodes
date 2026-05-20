from __future__ import annotations

import unittest

from tests.helpers import import_repo_module


seed_strategy = import_repo_module("node_packages.seed_strategy.seed_strategy")


class SeedStrategyTests(unittest.TestCase):
    def test_increment_wraps_seed_space(self):
        node = seed_strategy.SeedStrategy()

        seed, info = node.generate_seed(
            mode="increment",
            base_seed=seed_strategy.SeedStrategy._MAX_SEED,
            step=2,
            run_index=1,
            prompt="",
            seed_list="",
            random_min=0,
            random_max=10,
        )

        self.assertEqual(seed, 1)
        self.assertIn("increment:1", info)

    def test_hash_prompt_is_deterministic(self):
        node = seed_strategy.SeedStrategy()

        first = node.generate_seed(
            "hash_prompt",
            0,
            1,
            0,
            "same prompt",
            "",
            0,
            10,
        )
        second = node.generate_seed(
            "hash_prompt",
            999,
            50,
            5,
            "same prompt",
            "",
            0,
            10,
        )

        self.assertEqual(first, second)

    def test_cycle_list_ignores_invalid_entries(self):
        node = seed_strategy.SeedStrategy()

        seed, info = node.generate_seed(
            "cycle_list",
            42,
            1,
            2,
            "",
            "5, invalid, 7",
            0,
            10,
        )

        self.assertEqual(seed, 5)
        self.assertIn("idx=0/2", info)


if __name__ == "__main__":
    unittest.main()
