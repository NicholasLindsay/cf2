#!/usr/bin/python3

"""Configurator.

This tool is for bringing a Linux system into a certain configuration.
The intended usecase is to enable reproducible experiments by bringing
the system into a standardized environent.
"""

# This is what the DataModel should look like in code
#   DM = DataModel()
#   thp = DM["thp"] = DataModel(help="transparent hugepage subsystem", path="/sys/kernel/mm/transparent_hugepage/")
#   thp["enabled"] = DataModel(help="enables THP", path_suffix="enabled")
# Don't like it...
# 
#   TOP = DataModel()
#   thp = DataModel("thp", parent=TOP, help="...", path="../../../..")
#     OR
#   TOP.AddChild("thp", help="...", path="../../../..")
#     -> Creates a DataModel under the hood
 

class DataModel:
    __name: str
    __parent: 'Optional[DataModel]'
    __help: str
    __is_leaf: bool
    __children: dict[str, 'DataModel']

    def __init__(self, name: str, **kwargs):
        self.__name = name

        if "parent" in kwargs:
            self.__parent = kwargs["parent"]
        else:
            self.__parent = None

        if "help" in kwargs:
            self.__help = kwargs['help']
        else:
            self.__help = ''
        
        self.__is_leaf = False

        self.__children = {}
    
    def Name(self) -> str:
        return self.__name

    def AddChild(self, child: 'DataModel'):
        if self.__is_leaf:
            raise RuntimeError(f'Cannot add child to "{self.name}" - is leaf')

        if child.__name in self.__children:
            raise RuntimeError(f'{child.__name} already a child in f{self.__name}')

        self.__children[child.__name] = child
        child.__parent = self

    # print function for debugging only
    def print(self) -> None:
        if self.__is_leaf:
            pass
        else:
            print(f"{self.__name}:")


# === TESTING: ===
TOP = DataModel("top")
TOP.AddChild(DataModel("cabbage"))

TOP.print()
