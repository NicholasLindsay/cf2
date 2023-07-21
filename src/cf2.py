#!/usr/bin/python3

"""Configurator.

This tool is for bringing a Linux system into a certain configuration.
The intended usecase is to enable reproducible experiments by bringing
the system into a standardized environent.
"""

from abc import ABC, abstractmethod
import io
import sys # for stdout
from typing import Any, IO, Optional, TextIO

# ===[ HELPER FUNCTIONS ]===

# Helper function to insert text at start of each line
def PrefixLines(s: str, prefix: str):
    new_lines = [f'{prefix}{l}' for l in s.splitlines(keepends=True)]
    return ''.join(new_lines)

# ===[ META TREE STRUCTURE CLASSES ]===

class MetaTreeNode(ABC):
    __name: str
    __helpstring: str
    __parent: 'Optional[MetaTreeFixedDict]'

    def __init__(self, name: str, helpstring: str, **kwargs):
        self.__name = name
        self.__helpstring = helpstring
        self.__parent = None
        if 'parent' in kwargs:
            self.__parent = kwargs['parent']
            self.__parent.RegisterChild(self)

    def Name(self) -> str:
        return self.__name
    
    def HelpString(self) -> str:
        return self.__helpstring

    def Parent(self) -> 'Optional[MetaTreeFixedDict]':
        return self.__parent
    
    def Path(self) -> list[str]:
        if self.__parent:
            return [*self.__parent.Path(), self.Name()]
        else:
            return [self.Name()]

    @abstractmethod
    def TypeString(self) -> str:
        pass

    @abstractmethod
    def AcceptVisitor(self, visitor: 'MetaTreeVisitor') -> None:
        pass
    
class MetaTreeFixedDict(MetaTreeNode):
    __children: dict[str, 'MetaTreeNode']

    def __init__(self, name: str, helpstring: str, **kwargs):
        super().__init__(name, helpstring, **kwargs)
        self.__children = {}

    def Children(self) -> 'dict[str, MetaTreeNode]':
        return self.__children
    
    def ChildrenNames(self) -> list[str]:
        return list(self.__children.keys())
    
    def TypeString(self) -> str:
        return "FixedDict"

    def __getitem__(self, key: str) -> 'MetaTreeNode':
        return self.__children[key]

    def RegisterChild(self, ch: 'MetaTreeNode'):
        assert(ch.Name() not in self.__children)
        self.__children[ch.Name()] = ch
    
    def AcceptVisitor(self, visitor: 'MetaTreeVisitor') -> None:
        return visitor.VisitFixedDict(self)

class MetaTreeScalar(MetaTreeNode):
    __ty: type

    def __init__(self, name: str, helpstring: str, ty: type, **kwargs):
        super().__init__(name, helpstring, **kwargs)
        self.__ty = ty

    def Ty(self) -> type:
        return self.__ty
    
    def HelpString(self) -> str:
        s = super().HelpString()
        return f'{s} [Type = {self.Ty().__name__}]'
    
    def TypeString(self) -> str:
        return self.Ty().__name__
    
    def AcceptVisitor(self, visitor: 'MetaTreeVisitor') -> None:
        return visitor.VisitScalar(self)
    
# ===[ META TREE VISITOR CLASSES ]===
class MetaTreeVisitor(ABC):
    @abstractmethod
    def VisitFixedDict(self, node: MetaTreeFixedDict) -> None:
        pass

    @abstractmethod
    def VisitScalar(self, node: MetaTreeScalar) -> None:
        pass

class MetaTreePrinter(MetaTreeVisitor):
    __output: TextIO
    __is_top: bool
    __is_last_sibling: bool

    def __init__(self, output: TextIO, is_top: bool, is_last_sibling: bool):
        super().__init__()
        self.__output = output
        self.__is_top = is_top
        self.__is_last_sibling = is_last_sibling
    
    def PrintCommon(self, node: MetaTreeNode) -> None:
        if self.__is_top:
            print(f'{node.Name()}: {node.HelpString()}', file=self.__output)
        else:
            if self.__is_last_sibling:
                print(f' └── {node.Name()}: {node.HelpString()}', file=self.__output)
            else:
                print(f' ├── {node.Name()}: {node.HelpString()}', file=self.__output)

    def VisitFixedDict(self, node: MetaTreeFixedDict) -> None:
        self.PrintCommon(node)

        prefix = ''
        if not self.__is_top:
            if self.__is_last_sibling:
                prefix = '    '
            else:
                prefix = ' │  '

        children_list = list(node.ChildrenNames())
        for c in children_list:
            str_io = io.StringIO()

            if c == children_list[-1]:
                new_visitor = MetaTreePrinter(str_io, False, True)
            else:
                new_visitor = MetaTreePrinter(str_io, False, False)
        
            node[c].AcceptVisitor(new_visitor)
            print(PrefixLines(str_io.getvalue(), prefix), file = self.__output, end="")

    def VisitScalar(self, node: MetaTreeScalar) -> None:
        self.PrintCommon(node)

class MetaTreeTypeChecker(MetaTreeVisitor):
    __data: Any
    __errlist: list[str]

    def __init__(self, data: Any, errlist: list[str]):
        super().__init__()

        self.__data = data
        self.__errlist = errlist

    def VisitFixedDict(self, node: MetaTreeFixedDict) -> None:
        pathstr = '.'.join(node.Path())

        if type(self.__data) is not dict:
            self.__errlist.append(f"{pathstr}: type mismatch (expected: dict got: {type(self.__data).__name__})")
        else:
            for k in self.__data:
                if k not in node.ChildrenNames():
                    self.__errlist.append(f"{pathstr}: \"{k}\" is not a valid key")
                else:
                    node[k].AcceptVisitor(MetaTreeTypeChecker(self.__data[k], self.__errlist))

            for k in node.ChildrenNames():
                if k not in self.__data:
                    typetext = node[k].TypeString()
                    self.__errlist.append(f"{pathstr}: missing \"{k}\" field [Type = {typetext}]")
    
    def VisitScalar(self, node: MetaTreeScalar) -> None:
        pathstr = '.'.join(node.Path())

        if type(self.__data) != node.Ty():
            self.__errlist.append(f"{pathstr}: type mismatch (expected: {node.TypeString()} got: {type(self.__data).__name__})")

# ===[ META MODEL DEFINITION ]===
top = MetaTreeFixedDict("top", "top node")
ksm = MetaTreeFixedDict("ksm", "kernel samepage merging", parent=top)
MetaTreeScalar("max_page_sharing", "", int, parent=ksm)
MetaTreeScalar("merge_accross_nodes", "", int, parent=ksm)
MetaTreeScalar("pages_to_scan", "", int, parent=ksm)
MetaTreeScalar("run", "", int, parent=ksm)
MetaTreeScalar("sleep_millisecs", "", int, parent=ksm)
MetaTreeScalar("stable_node_chains_prune_millisecs", "", int, parent=ksm)
MetaTreeScalar("use_zero_pages", "", int, parent=ksm)
lru_gen = MetaTreeFixedDict("lru_gen", "", parent=top)
MetaTreeScalar("enabled", "", str, parent=lru_gen)
MetaTreeScalar("min_ttl_ms", "", int, parent=lru_gen)
numa = MetaTreeFixedDict("numa", "non-uniform memory access", parent = top)
MetaTreeScalar("demotion_enabled", "", bool, parent=numa)
swap = MetaTreeFixedDict("swap", "", parent=top)
MetaTreeScalar("vma_ra_enabled", "", bool, parent=swap)
thp = MetaTreeFixedDict("transparent_hugepage", "transparent hugepages", parent=top)
MetaTreeScalar("defrag", "", str, parent=thp)
MetaTreeScalar("enabled", "", str, parent=thp)
MetaTreeScalar("hpage_pmd_size", "", int, parent=thp)
khpd = MetaTreeFixedDict("khugepaged", "huge pages daemon", parent=thp)
MetaTreeScalar("alloc_sleep_millisecs", "", int, parent=khpd)
MetaTreeScalar("max_ptes_none", "", int, parent=khpd)
MetaTreeScalar("max_ptes_shared", "", int, parent=khpd)
MetaTreeScalar("max_ptes_swap", "", int, parent=khpd)
MetaTreeScalar("pages_to_scan", "", int, parent=khpd)
MetaTreeScalar("scan_sleep_millisecs", "", int, parent=khpd)
MetaTreeScalar("shmem_enabled", "", str, parent=thp)
MetaTreeScalar("use_zero_page", "", int, parent=thp)

# Encapsulate a MetaModel tree in a "MetaModel"
class MetaModel:
    __root: MetaTreeNode

    def __init__(self, root):
        self.__root = root
    
    def Root(self) -> MetaTreeNode:
        return self.__root
    
    def PrintTree(self, output = sys.stdout):
        visitor = MetaTreePrinter(output, True, True)
        self.Root().AcceptVisitor(visitor)

    def TypeCheck(self, data) -> list[str]:
        errlist = []
        visitor = MetaTreeTypeChecker(data, errlist)
        self.Root().AcceptVisitor(visitor)
        return errlist

STANDARD_METAMODEL = MetaModel(top)
STANDARD_METAMODEL.PrintTree()
