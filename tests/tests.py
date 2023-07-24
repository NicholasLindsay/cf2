#!/usr/bin/python3

import io
import unittest

from src.cf2 import *

# ===[ Simple MetaModel used by tests ]===
TOP = MetaTreeFixedDict("top", "i am top", True)
BAR = MetaTreeScalar("bar", "i am bar", True, int, parent=TOP)
BAZ = MetaTreeFixedDict("baz", "i am baz", True, parent=TOP)
MetaTreeScalar("name", "person's name", True, str, parent=BAZ)
MetaTreeScalar("age", "person's age", False, int, parent=BAZ)
TEAMS = MetaTreeFixedDict("teams", "sports teams", True, parent=TOP)
MetaTreeScalar("soccer", "soccer", True, str, parent=TEAMS)
MetaTreeScalar("nfl", "american football", True, str, parent=TEAMS)
TEST_METAMODEL = MetaModel(TOP)

# ===[ Data used by tests ]===
GOOD_RAW_DATA = {
                "bar": 5,
                "baz": {
                    "name": "john",
                    "age": 37,
                },
                "teams" : {
                    "soccer": "man utd",
                    "nfl": "tigers",
                }
            }

BAD_RAW_DATA = {
                "bar" : False,
                "baz" : {
                    "age" : "100",
                    "hobby" : [ "fishing" , "eating" ]
                },
                "teams": 619,
                "etc" : {
                    "phone" : 123456709,
                }
            }

# ===[ Tests ]===
class TestTypeCheck(unittest.TestCase):
    def test_good_data(self):
        errlist = TEST_METAMODEL.TypeCheck(GOOD_RAW_DATA)
        self.assertEqual(errlist, [], "detected error in good case")

    def test_bad_data(self):
        errlist = TEST_METAMODEL.TypeCheck(BAD_RAW_DATA)
        self.assertEqual("\n".join(errlist),"""\
top.bar: type mismatch (expected: int got: bool)
top.baz.age: type mismatch (expected: int got: str)
top.baz: "hobby" is not a valid key
top.baz: missing "name" field [Type = str]
top.teams: type mismatch (expected: dict got: int)
top: "etc" is not a valid key""")

class TestCreateTypecheckedModel(unittest.TestCase):
    def test_good_data(self):
        result = TEST_METAMODEL.CreateTypecheckedModel(GOOD_RAW_DATA)
        self.assertEqual(result.success, True)
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.model)
    
    def test_bad_data(self):
        result = TEST_METAMODEL.CreateTypecheckedModel(BAD_RAW_DATA)
        self.assertEqual(result.success, False)
        self.assertNotEqual(result.errors, [])
        self.assertIsNone(result.model)

class TestPrintTree(unittest.TestCase):
    def test_print_tree(self):
        strio = io.StringIO()
        TEST_METAMODEL.PrintTree(strio)
        s = strio.getvalue()
        expected = """\
top: i am top [Ap]
 ├── bar: i am bar [Ap] [Type = int]
 ├── baz: i am baz [Ap]
 │   ├── name: person's name [Ap] [Type = str]
 │   └── age: person's age [RO] [Type = int]
 └── teams: sports teams [Ap]
     ├── soccer: soccer [Ap] [Type = str]
     └── nfl: american football [Ap] [Type = str]
"""
        self.assertEqual(s, expected)

# ===[ Boilerplate ]===
if __name__ == '__main__':
    unittest.main()
