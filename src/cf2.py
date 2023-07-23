#!/usr/bin/python3

"""Configurator.

This tool is for bringing a Linux system into a certain configuration.
The intended usecase is to enable reproducible experiments by bringing
the system into a standardized environent.
"""

from abc import ABC, abstractmethod
import io
import pathlib
import sys # for stdout
from typing import Any, IO, Optional, TextIO

# ===[ HELPER FUNCTIONS ]===

# Helper function to insert text at start of each line
def PrefixLines(s: str, prefix: str):
    new_lines = [f'{prefix}{l}' for l in s.splitlines(keepends=True)]
    return ''.join(new_lines)

# ===[ PLUGS ]===
class Plug(ABC):
    @abstractmethod
    def Read(self):
        pass

    @abstractmethod
    def Write(self, value):
        pass

class FileStrPlug(Plug):
    __filename: pathlib.Path

    def __init__(self, filename: pathlib.Path):
        self.__filename = filename
    
    def Read(self) -> str:
        with open(self.__filename, "r") as f:
            return f.read()
    
    def Write(self, value: str) -> None:
        with open(self.__filename, "w") as f:
            f.write(value)

class ThpOptionPlug(Plug):
    # Handle THP option files (option selected with [])
    __fsplug: FileStrPlug

    def __init__(self, filename: pathlib.Path):
        self.__fsplug = FileStrPlug(filename)

    def Read(self) -> str:
        s = self.__fsplug.Read()
        
        for word in s.split():
            if word[0] == '[' and word[-1] == ']':
                return word[1:-1]
        
        raise RuntimeError("error reading thp option")
    
    def Write(self, value: str):
        self.__fsplug.Write(value)

class FileIntPlug(Plug):
    # Implement as a wrapper around FileStrPlug
    __fsplug: FileStrPlug

    def __init__(self, filename: pathlib.Path):
        self.__fsplug = FileStrPlug(filename)
    
    def Read(self) -> int:
        return int(self.__fsplug.Read())
    
    def Write(self, value: int) -> None:
        self.__fsplug.Write(str(value))
    
class FileBoolPlug(Plug):
    # Implement as a wrapper around FileStrPlug
    __fsplug: FileStrPlug

    def __init__(self, filename: pathlib.Path):
        self.__fsplug = FileStrPlug(filename)
    
    def Read(self) -> bool:
        s = self.__fsplug.Read()
        if s.lower() == "true":
            return True
        elif s.lower() == "false":
            return False
        else:
            raise RuntimeError("invalid/ambiguous bool value read")
    
    def Write(self, value: bool) -> None:
        s = "true" if value else "false"
        self.__fsplug.Write(s)

# ===[ META TREE STRUCTURE CLASSES ]===

class MetaTreeNode(ABC):
    __name: str
    __helpstring: str
    __parent: 'Optional[MetaTreeFixedDict]'

    # The Plug logic is actually decoupled from TypeChecking; we include it
    # here for convenience but it should be thought of as being seperated from
    # the rest of the MetaTreeNode data
    __plug: Optional[Plug]

    def __init__(self, name: str, helpstring: str, **kwargs):
        self.__name = name
        self.__helpstring = helpstring
        self.__parent = None
        if 'parent' in kwargs:
            self.__parent = kwargs['parent']
            self.__parent.RegisterChild(self)
        self.__plug = None
        if 'plug' in kwargs:
            self.__plug = kwargs['plug']

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

    def Plug(self) -> Optional[Plug]:
        return self.__plug
    
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

# ===[ SYSTEM SETTING COMMUNICATION ]===
class MetaTreePlugReaderVisitor(MetaTreeVisitor):
    __rawdata: dict[str, Any]

    def __init__(self, rawdata: Any):
        super().__init__()
        self.__rawdata = rawdata

    def VisitFixedDict(self, node: MetaTreeFixedDict) -> None:
        assert(node.Plug() is None)
        x = self.__rawdata[node.Name()] = {}
        for ch in node.Children():
            node[ch].AcceptVisitor(MetaTreePlugReaderVisitor(x))

    def VisitScalar(self, node: MetaTreeScalar) -> None:
        p = node.Plug()
        assert(p is not None)
        self.__rawdata[node.Name()] = p.Read()

# ===[ MODEL AND METAMODEL DEFINITIONS ]===
# Represents data that has been successfully typechecked against a metamodel
class TypecheckedModel:
    __rawdata: Any
    __metamodel: 'MetaModel'

    def __init__(self, data: Any, metamodel: 'MetaModel'):
        self.__rawdata = data
        self.__metamodel = metamodel
    
    def MetaModel(self) -> 'MetaModel':
        return self.__metamodel

    def RawData(self) -> Any:
        return self.__rawdata

class CreateTypecheckedModelResult:
    success: bool
    errors: list[str]
    model: Optional[TypecheckedModel]

    def __init__(self, success: bool, errors: list[str], model: Optional[TypecheckedModel]):
        self.success = success
        self.errors = errors
        self.model = model

# Encapsulate a MetaModel tree within a "MetaModel"
class MetaModel:
    __root: MetaTreeNode

    def __init__(self, root):
        self.__root = root
    
    def Root(self) -> MetaTreeNode:
        return self.__root
    
    def PrintTree(self, output = sys.stdout):
        visitor = MetaTreePrinter(output, True, True)
        self.Root().AcceptVisitor(visitor)

    def TypeCheck(self, rawdata) -> list[str]:
        errlist = []
        visitor = MetaTreeTypeChecker(rawdata, errlist)
        self.Root().AcceptVisitor(visitor)
        return errlist
    
    def CreateTypecheckedModel(self, rawdata: Any) -> CreateTypecheckedModelResult:
        errs = self.TypeCheck(rawdata)
        if errs:
            return CreateTypecheckedModelResult(False, errs, None)
        else:
            return CreateTypecheckedModelResult(True, [], TypecheckedModel(rawdata, self))

# ===[ META MODEL DEFINITION ]===
MM_FS_PATH = pathlib.Path("/sys/kernel/mm")

_TOP = MetaTreeFixedDict("top", "top node")
_KSM = MetaTreeFixedDict("ksm", "kernel samepage merging", parent=_TOP)
_LRU_GEN = MetaTreeFixedDict("lru_gen", "", parent=_TOP)
_NUMA = MetaTreeFixedDict("numa", "non-uniform memory access", parent = _TOP)
_SWAP = MetaTreeFixedDict("swap", "", parent=_TOP)
_THP = MetaTreeFixedDict("transparent_hugepage", "transparent hugepages", parent=_TOP)
_KHPD = MetaTreeFixedDict("khugepaged", "huge pages daemon", parent=_THP)

MM_KSM_PATH = MM_FS_PATH / "ksm"
MetaTreeScalar("max_page_sharing", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "max_page_sharing"))
MetaTreeScalar("merge_across_nodes", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "merge_across_nodes"))
MetaTreeScalar("pages_to_scan", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "pages_to_scan"))
MetaTreeScalar("run", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "run"))
MetaTreeScalar("sleep_millisecs", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "sleep_millisecs"))
MetaTreeScalar("stable_node_chains_prune_millisecs", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "stable_node_chains_prune_millisecs"))
MetaTreeScalar("use_zero_pages", "", int, parent=_KSM,
               plug=FileIntPlug(MM_KSM_PATH / "use_zero_pages"))

# TODO: Plugs for the following

#MetaTreeScalar("enabled", "", str, parent=_LRU_GEN)
#MetaTreeScalar("min_ttl_ms", "", int, parent=_LRU_GEN)

#MetaTreeScalar("demotion_enabled", "", bool, parent=_NUMA)

#MetaTreeScalar("vma_ra_enabled", "", bool, parent=_SWAP)

#MetaTreeScalar("defrag", "", str, parent=_THP)
#MetaTreeScalar("enabled", "", str, parent=_THP)
#MetaTreeScalar("hpage_pmd_size", "", int, parent=_THP)

#MetaTreeScalar("alloc_sleep_millisecs", "", int, parent=_KHPD)
#MetaTreeScalar("max_ptes_none", "", int, parent=_KHPD)
#MetaTreeScalar("max_ptes_shared", "", int, parent=_KHPD)
#MetaTreeScalar("max_ptes_swap", "", int, parent=_KHPD)
#MetaTreeScalar("pages_to_scan", "", int, parent=_KHPD)
#MetaTreeScalar("scan_sleep_millisecs", "", int, parent=_KHPD)
#MetaTreeScalar("shmem_enabled", "", str, parent=_THP)
#MetaTreeScalar("use_zero_page", "", int, parent=_THP)

STANDARD_METAMODEL = MetaModel(_TOP)
# STANDARD_METAMODEL.PrintTree()

def ReadSystemConfig(metamodel: MetaModel) -> TypecheckedModel:
    rawdata = {}
    reader = MetaTreePlugReaderVisitor(rawdata)
    metamodel.Root().AcceptVisitor(reader)
    result = metamodel.CreateTypecheckedModel(rawdata["top"])
    if result.success:
        assert(result.model is not None)
        return result.model
    else:
        raise RuntimeError(f'errors when typechecking read system rawdata:\n {",".join(result.errors)}')

model = ReadSystemConfig(STANDARD_METAMODEL)
print(f"Created model succesfully!: {model.RawData()}")

# ===[ USER PROCESSING ]===
if __name__ == "__main__":
    import argparse
    import yaml

    parser = argparse.ArgumentParser("cf2", description=__doc__)
    parser.add_argument("filename", type=pathlib.Path,
                        help="path to configuration file")
    args = parser.parse_args()

    with open(args.filename, "r") as file:
        rawdata = yaml.safe_load(file)
        typecheck_results = STANDARD_METAMODEL.CreateTypecheckedModel(rawdata)
        if typecheck_results.success:
            print("File typechecking passed!")
            print("Raw Data:")
            print(rawdata)
            exit(0)
        else:
            print("File typechecking failed!")
            print("ERRORS:")
            print("\n".join(typecheck_results.errors))
            exit(1)
