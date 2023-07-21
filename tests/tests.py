#!/usr/bin/python3

import io
import unittest

from src.cf2 import *

# ===[ Simple MetaModel used by tests ]===
TOP = MetaTreeFixedDict("top", "i am top")
BAR = MetaTreeScalar("bar", "i am bar", int, parent=TOP)
BAZ = MetaTreeFixedDict("baz", "i am baz", parent=TOP)
MetaTreeScalar("name", "person's name", str, parent=BAZ)
MetaTreeScalar("age", "person's age", int, parent=BAZ)
TEAMS = MetaTreeFixedDict("teams", "sports teams", parent=TOP)
MetaTreeScalar("soccer", "soccer", str, parent=TEAMS)
MetaTreeScalar("nfl", "american football", str, parent=TEAMS)
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
top: i am top
 ├── bar: i am bar [Type = int]
 ├── baz: i am baz
 │   ├── name: person's name [Type = str]
 │   └── age: person's age [Type = int]
 └── teams: sports teams
     ├── soccer: soccer [Type = str]
     └── nfl: american football [Type = str]
"""
        self.assertEqual(s, expected)

# ===[ Boilerplate ]===
if __name__ == '__main__':
    unittest.main()
