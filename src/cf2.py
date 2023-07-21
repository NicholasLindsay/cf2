#!/usr/bin/python3

"""Configurator.

This tool is for bringing a Linux system into a certain configuration.
The intended usecase is to enable reproducible experiments by bringing
the system into a standardized environent.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

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

    def Parent(self) -> 'Optional[MetaTreeNode]':
        return self.__parent
    
    @abstractmethod
    def TypeString(self) -> str:
        pass

    # TODO: Use the Visitor pattern instead
    def MetadataTreeAsStr(self, is_top=True, is_last_sibling=True):
        s = ''
        if is_top:
            s = f'{self.Name()}: {self.HelpString()}\n'
        else:
            if is_last_sibling:
                s = f' └── {self.Name()}: {self.HelpString()}\n'
            else:
                s = f' ├── {self.Name()}: {self.HelpString()}\n'
            
        return s

    # TODO: Use the Visitor pattern instead
    @abstractmethod
    def _TypeCheckRecursive(self, path: list[str], data: Any) -> list[str]:
        pass
    
class MetaTreeFixedDict(MetaTreeNode):
    __children: dict[str, 'MetaTreeNode']

    def __init__(self, name: str, helpstring: str, **kwargs):
        super().__init__(name, helpstring, **kwargs)
        self.__children = {}

    def Children(self) -> 'dict[str, MetaTreeNode]':
        return self.__children
    
    def TypeString(self) -> str:
        return "FixedDict"

    def __getitem__(self, key: str) -> 'MetaTreeNode':
        return self.__children[key]

    def RegisterChild(self, ch: 'MetaTreeNode'):
        assert(ch.Name() not in self.__children)
        self.__children[ch.Name()] = ch

    def MetadataTreeAsStr(self, is_top=True, is_last_sibling=True):
        s = super().MetadataTreeAsStr(is_top, is_last_sibling)

        prefix = ''
        if not is_top:
            if is_last_sibling:
                prefix = '    '
            else:
                prefix = ' │  '

        children_list = list(self.Children().values())
        for c in children_list:
            if c == children_list[-1]:
                s += PrefixLines(c.MetadataTreeAsStr(False, True), prefix)
            else:
                s += PrefixLines(c.MetadataTreeAsStr(False, False), prefix)
            
        return s

    def _TypeCheckRecursive(self, path: list[str], data: Any) -> list[str]:
        errlist: list[str] = []
        pathstr = '.'.join(path)

        if type(data) is not dict:
            errlist.append(f"{pathstr}: type mismatch (expected: dict got: {type(data).__name__})")
        else:
            for k in data:
                if k not in self.Children():
                    errlist.append(f"{pathstr}: \"{k}\" is not a valid key")
                else:
                    errlist += self[k]._TypeCheckRecursive((path + [k]), data[k])

            for k in self.Children():
                if k not in data:
                    typetext = self[k].TypeString()
                    errlist.append(f"{pathstr}: missing \"{k}\" field [Type = {typetext}]")

        return errlist

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

    def _TypeCheckRecursive(self, path: list[str], data: Any) -> list[str]:
        errlist: list[str] = []
        pathstr = '.'.join(path)

        if type(data) != self.Ty():
            errlist.append(f"{pathstr}: type mismatch (expected: {self.TypeString()} got: {type(data).__name__})")

        return errlist

# Helper function to insert text at start of each line
def PrefixLines(s: str, prefix: str):
    new_lines = [f'{prefix}{l}' for l in s.splitlines(keepends=True)]
    return ''.join(new_lines)

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

    def TreeAsString(self) -> str:
        return self.__root.MetadataTreeAsStr()
    
    def TypeCheck(self, data) -> list[str]:
        return self.Root()._TypeCheckRecursive([], data)

STANDARD_METAMODEL = MetaModel(top)
