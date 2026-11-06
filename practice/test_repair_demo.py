import unittest

from repair_demo import add


class AddTests(unittest.TestCase):

    def test_adds_two_numbers(self):
        self.assertEqual(add(1, 2), 3)


if __name__ == "__main__":
    unittest.main()