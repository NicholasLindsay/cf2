#!/usr/bin/python3

"""cf2.

This tool is for bringing a Linux system into a certain configuration.
The intended usecase is to enable reproducible experiments by bringing
the system into a standardized environent.
"""

from abc import ABC, abstractmethod
import io
import pathlib
import platform # for platform.uname()
import sys # for stdout
from typing import Any, IO, Optional, TextIO

# ===[ HELPER FUNCTIONS ]===

# Helper function to insert text at start of each line
def PrefixLines(s: str, prefix: str):
    new_lines = [f'{prefix}{l}' for l in s.splitlines(keepends=True)]
    return ''.join(new_lines)

# === [ Helper functions for kernel version processing ]===

# Using the terminology from https://askubuntu.com/a/843198:
class KernelVersionNumber:
    w: int
    x: int
    y: int
    z: int
    suffix: str

    def __init__(self, version_string: str):
        # Version string of style: w.x.y-z-suffix
        top_split = version_string.split('-')
        bottom_split = top_split[0].split('.')
        self.w = int(bottom_split[0])
        self.x = int(bottom_split[1])
        self.y = int(bottom_split[2])
        self.z = int(top_split[1])
        if len(top_split) == 3:
            self.suffix = top_split[2]
        else:
            self.suffix = ''
    
    def __eq__(self, other: 'KernelVersionNumber') -> bool:
        return ((self.w == other.w) and (self.x == other.x)
                                    and (self.y == other.y)
                                    and (self.z == other.z)
                                    and (self.suffix == other.suffix))

    def __str__(self) -> str:
        base =  f'{self.w}.{self.x}.{self.y}-{self.z}'
        if self.suffix != '':
            base += f'-{self.suffix}'
        return base

    def __repr__(self) -> str:
        class_name = type(self).__name__
        return f'{class_name}("{str(self)}")'

def GetKernelVersion() -> KernelVersionNumber:
    version_str = platform.uname().release
    version = KernelVersionNumber(version_str)
    return version

# ===[ PLUGS ]===
class Plug(ABC):
    @abstractmethod
    def Read(self):
        pass

    @abstractmethod
    def Write(self, value):
        pass

class KernelVersionPlug(Plug):
    def Read(self) -> KernelVersionNumber:
        return GetKernelVersion()

    def Write(self, value: KernelVersionNumber):
        raise RuntimeError('cannot write kernel version number')

class FileStrPlug(Plug):
    __filename: pathlib.Path

    def __init__(self, filename: pathlib.Path):
        self.__filename = filename
    
    def Read(self) -> str:
        with open(self.__filename, "r") as f:
            return f.read().rstrip()
    
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
    __applyable: bool
    __parent: 'Optional[MetaTreeFixedDict]'

    # The Plug logic is actually decoupled from TypeChecking; we include it
    # here for convenience but it should be thought of as being seperated from
    # the rest of the MetaTreeNode data
    __plug: Optional[Plug]

    def __init__(self, name: str, helpstring: str, applyable: bool, **kwargs):
        self.__name = name
        self.__helpstring = helpstring
        self.__applyable = applyable
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
        suffix = '[Ap]' if self.Applyable() else '[RO]' 
        return (f'{self.__helpstring} {suffix}')

    def Applyable(self) -> bool:
        return self.__applyable

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

    def __init__(self, name: str, helpstring: str, applyable: bool, **kwargs):
        super().__init__(name, helpstring, applyable, **kwargs)
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

    def __init__(self, name: str, helpstring: str, applyable: bool, ty: type, **kwargs):
        super().__init__(name, helpstring, applyable, **kwargs)
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


# ===[ KERNEL VERSION CUSTOM LOGIC ]===
# Custom code to handle kernel version numbers in meta tree
class KvnPlug(Plug):
    def Read(self) -> dict[str, any]:
        kvn = GetKernelVersion()
        ret = {
                'w' : kvn.w,
                'x' : kvn.x,
                'y' : kvn.y,
                'z' : kvn.z,
                'suffix' : kvn.suffix
              }
        return ret
    
    def Write(self, value: int) -> None:
        raise RuntimeError('cannot write kernel version number')

class MetaTreeKvn(MetaTreeFixedDict):
    # Special class for handling kernel version numbers
    def __init__(self, name: str, helpstring: str, **kwargs):
        super().__init__(name, helpstring, False, plug = KvnPlug(), **kwargs)
        MetaTreeScalar('w', 'w component of version name', False, int, parent=self)
        MetaTreeScalar('x', 'x component of version name', False, int, parent=self)
        MetaTreeScalar('y', 'y component of version name', False, int, parent=self)
        MetaTreeScalar('z', 'z component of version name', False, int, parent=self)
        MetaTreeScalar('suffix', 'suffix component of version name',\
                       False, str, parent=self)

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
        # Some FixedDict nodes might have a custom plug
        if node.Plug() is not None:
            p = node.Plug()
            self.__rawdata[node.Name()] = p.Read()
        # ... otherwise run the child plugs elementwise
        else:
            x = self.__rawdata[node.Name()] = {}
            for ch in node.Children():
                node[ch].AcceptVisitor(MetaTreePlugReaderVisitor(x))

    def VisitScalar(self, node: MetaTreeScalar) -> None:
        p = node.Plug()
        assert(p is not None)
        self.__rawdata[node.Name()] = p.Read()

class MetaTreePlugWriterVisitor(MetaTreeVisitor):
    __diffonly: bool
    __rawdata: Any
    __errlist: list[str]

    def __init__(self, diffonly: bool, rawdata: Any, errlist: list[str]):
        self.__diffonly = diffonly
        self.__rawdata = rawdata
        self.__errlist = errlist

    def __TryWriteIfNeeded(self, node: MetaTreeNode, p: Plug) -> Optional[str]:
        # Returns none if success, or an error string if an error
        if self.__diffonly or not node.Applyable():
            # If diffonly, only perform a write if value different from current
            val = p.Read()
            if val == self.__rawdata:
                return None
            elif not node.Applyable():
                return f'{".".join(node.Path())}: difference in non-applyable value (desired = {self.__rawdata} actual = {val})'

        try:
            p.Write(self.__rawdata)
            return None
        except Exception as e:
            return f'When applying {".".join(node.Path())}: {e}'

    def VisitFixedDict(self, node: MetaTreeFixedDict) -> None:
        # Some FixedDicts may have custom Plugs
        if node.Plug() is not None:
            err: Optional[str] = self.__TryWriteIfNeeded(node, node.Plug())
            if err is not None:
                self.__errlist.append(err)
        # ... otherwise use child plugs elementwise
        else:
            if not node.Applyable():
                raise NotImplemented()
            
            for ch in node.Children():
                node[ch].AcceptVisitor(MetaTreePlugWriterVisitor(self.__diffonly, self.__rawdata[ch], self.__errlist))

    def VisitScalar(self, node: MetaTreeScalar) -> None:
        p = node.Plug()
        assert(p is not None)
        self.__TryWriteIfNeeded(node, p)
 
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

# ===[ MODEL COMPARISON ]===

class MetaTreeDiffVisitor(MetaTreeVisitor):
    __left: Any
    __right: Any
    __leftname: str
    __rightname: str
    __difflist: list[str]

    def __init__(self, left: Any, right: Any, leftname: str, rightname: str, difflist: list[str]) -> None:
        super().__init__()
        self.__left = left
        self.__right = right
        self.__leftname = leftname
        self.__rightname = rightname
        self.__difflist = difflist
    
    def VisitFixedDict(self, node: MetaTreeFixedDict) -> None:
        # Assume: self.__left and self.__right have same keys
        for k in node.Children():
            node[k].AcceptVisitor(MetaTreeDiffVisitor(self.__left[k], self.__right[k], self.__leftname, 
                                                      self.__rightname, self.__difflist))

    def VisitScalar(self, node: MetaTreeScalar) -> None:
        # Assume: self.__left and self.__right have same type
        if self.__left != self.__right:
            s = f"{node.Name()}: {self.__leftname} = {self.__left} | {self.__rightname} = {self.__right}"
            self.__difflist.append(s)

def DiffTypecheckedModels(left: TypecheckedModel, 
                          right: TypecheckedModel, 
                          leftname: str, 
                          rightname: str) -> list[str]:
    # TODO: Handle case where left and right metamodels aree different
    metamodel = left.MetaModel()
    difflist = []
    visitor = MetaTreeDiffVisitor(left.RawData(), right.RawData(), leftname, rightname, difflist)
    metamodel.Root().AcceptVisitor(visitor)
    return difflist

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

# Given a kernel version number, generate the MetaModel
def GenerateMetamodel(kvn: KernelVersionNumber) -> MetaModel:
    # Prepare the tree
    node_top = MetaTreeFixedDict("top", "top node", True)
   
    # Track the OS version
    MetaTreeKvn("kvn", "kernel version number", parent=node_top)

    # Prepare the memory management related configuration options
    MM_FS_PATH = pathlib.Path("/sys/kernel/mm")

    node_ksm = MetaTreeFixedDict("ksm", "kernel samepage merging", True, parent=node_top)
    node_numa = MetaTreeFixedDict("numa", "non-uniform memory access", True, parent = node_top)
    node_swap = MetaTreeFixedDict("swap", "", True, parent=node_top)
    node_thp = MetaTreeFixedDict("transparent_hugepage", "transparent hugepages", True, parent=node_top)
    node_khpd = MetaTreeFixedDict("khugepaged", "huge pages daemon", True, parent=node_thp)

    MM_KSM_PATH = MM_FS_PATH / "ksm"
    MetaTreeScalar("max_page_sharing", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "max_page_sharing"))
    MetaTreeScalar("merge_across_nodes", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "merge_across_nodes"))
    MetaTreeScalar("pages_to_scan", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "pages_to_scan"))
    MetaTreeScalar("run", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "run"))
    MetaTreeScalar("sleep_millisecs", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "sleep_millisecs"))
    MetaTreeScalar("stable_node_chains_prune_millisecs", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "stable_node_chains_prune_millisecs"))
    MetaTreeScalar("use_zero_pages", "", True, int, parent=node_ksm,
                   plug=FileIntPlug(MM_KSM_PATH / "use_zero_pages"))

    # Assume MGLRU was released in Linux 6.1:
    # (see https://www.phoronix.com/news/Linux-6.1-rc1-Released)
    if (kvn.w == 6 and (kvn.x >= 1)):
        node_lru_gen = MetaTreeFixedDict("lru_gen", "", True, parent=node_top)
        MM_LRU_GEN_PATH = MM_FS_PATH / "lru_gen"
        MetaTreeScalar("enabled", "", True, str, parent=node_lru_gen,
                       plug=FileStrPlug(MM_LRU_GEN_PATH / "enabled"))
        MetaTreeScalar("min_ttl_ms", "", True, int, parent=node_lru_gen,
                       plug=FileIntPlug(MM_LRU_GEN_PATH / "min_ttl_ms"))

    MM_NUMA_PATH = MM_FS_PATH / "numa"
    MetaTreeScalar("demotion_enabled", "", True, bool, parent=node_numa,
                   plug=FileBoolPlug(MM_NUMA_PATH / "demotion_enabled"))

    MM_SWAP_PATH = MM_FS_PATH / "swap"
    MetaTreeScalar("vma_ra_enabled", "", True, bool, parent=node_swap,
                   plug=FileBoolPlug(MM_SWAP_PATH / "vma_ra_enabled"))

    MM_THP_PATH = MM_FS_PATH / "transparent_hugepage"
    MetaTreeScalar("defrag", "", True, str, parent=node_thp,
                   plug=ThpOptionPlug(MM_THP_PATH / "defrag"))
    MetaTreeScalar("enabled", "", True, str, parent=node_thp,
                   plug=ThpOptionPlug(MM_THP_PATH / "enabled"))
    MetaTreeScalar("hpage_pmd_size", "", False, int, parent=node_thp,
                   plug=FileIntPlug(MM_THP_PATH / "hpage_pmd_size"))
    MetaTreeScalar("shmem_enabled", "", True, str, parent=node_thp,
                   plug=ThpOptionPlug(MM_THP_PATH / "shmem_enabled"))
    MetaTreeScalar("use_zero_page", "", True, int, parent=node_thp,
                   plug=FileIntPlug(MM_THP_PATH / "use_zero_page"))

    MM_THP_KHPD_PATH = MM_THP_PATH / "khugepaged"
    MetaTreeScalar("alloc_sleep_millisecs", "", True, int, parent=node_khpd,
                   plug=FileIntPlug(MM_THP_KHPD_PATH / "alloc_sleep_millisecs"))
    MetaTreeScalar("max_ptes_none", "", True, int, parent=node_khpd,
                   plug=FileIntPlug(MM_THP_KHPD_PATH / "max_ptes_none"))
    MetaTreeScalar("max_ptes_shared", "", True, int, parent=node_khpd,
                   plug=FileIntPlug(MM_THP_KHPD_PATH / "max_ptes_shared"))
    MetaTreeScalar("max_ptes_swap", "", True, int, parent=node_khpd,
                   plug=FileIntPlug(MM_THP_KHPD_PATH / "max_ptes_swap"))
    MetaTreeScalar("pages_to_scan", "", True, int, parent=node_khpd,
                   plug=FileIntPlug(MM_THP_KHPD_PATH / "pages_to_scan"))
    MetaTreeScalar("scan_sleep_millisecs", "", True, int, parent=node_khpd,
                   plug=FileIntPlug(MM_THP_KHPD_PATH / "scan_sleep_millisecs"))

    return MetaModel(node_top)

# Get the metamodel for the current system
def SystemMetamodel() -> MetaModel:
    version_str = platform.uname().release
    kvn = KernelVersionNumber(version_str)
    return GenerateMetamodel(kvn)

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

def ApplySystemConfig(model: TypecheckedModel, diffonly: bool) -> list[str]:
    # Returns list of errors (empty if none)
    metamodel = model.MetaModel()
    rawdata = model.RawData()
    errlist = []
    writer = MetaTreePlugWriterVisitor(diffonly, rawdata, errlist)
    metamodel.Root().AcceptVisitor(writer)
    return errlist

def LoadAndCheckConfigFile(filename: pathlib.Path) -> TypecheckedModel:
    with open(filename, 'r') as file:
        rawdata = yaml.safe_load(file)
    
    typecheck_results = SystemMetamodel().CreateTypecheckedModel(rawdata)

    if not typecheck_results.success:
        print("File typechecking failed!")
        print("ERRORS:")
        print("\n".join(typecheck_results.errors))
        exit(1)

    assert(typecheck_results.model is not None)
    return typecheck_results.model

# ===[ USER PROCESSING ]===
import argparse
import yaml

class Subcommand(ABC):
    __name: str
    __help: str
    __desc: str # description for help message

    def __init__(self, name: str, help: str, desc: str = ""):
        super().__init__()
        self.__name = name
        self.__help = help
        self.__desc = desc

    def Name(self) -> str:
        return self.__name

    def Help(self) -> str:
        return self.__help

    def Desc(self) -> str:
        return self.__desc

    @abstractmethod
    def SetupParser(self, parser: argparse.ArgumentParser):
        pass

    @abstractmethod
    def Go(self, args):
        pass

class InfoSubcommand(Subcommand):
    def __init__(self):
        super().__init__("info", "display info about metamodel",
                         "This command prints the metamodel tree."
                         " Each field is marked as either [Ap] or [RO]."
                         " [Ap] indicates that a field is applyable - that is,"
                         " the tool can take action to set the system"
                         " configuration to the desired value."
                         " [RO] on the other hand indicates that the field is"
                         " read only - there is no action that this tool can"
                         " take to set its value. [RO] values"
                         " are only checked by the \"apply\" command, even if"
                         " --always is set.")

    def SetupParser(self, parser: argparse.ArgumentParser):
        pass

    def Go(self, args):
        SystemMetamodel().PrintTree()

class TypecheckSubcommand(Subcommand):
    def __init__(self):
        super().__init__("typecheck", "read data from file and check types")
    
    def SetupParser(self, parser: argparse.ArgumentParser):
        parser.add_argument("filename", type=pathlib.Path, help="config file to typecheck")
    
    def Go(self, args):
        LoadAndCheckConfigFile(args.filename) # will exit(1) if error
        exit(0)

class ObtainSubcommand(Subcommand):
    def __init__(self):
        super().__init__("obtain", "obtain current system configuration and store in file")
    
    def SetupParser(self, parser: argparse.ArgumentParser):
        parser.add_argument("filename", type=pathlib.Path, help="save config to this file")
    
    def Go(self, args):
        sysconfig = ReadSystemConfig(SystemMetamodel())
        with open(args.filename, "w") as file:
            yaml.safe_dump(sysconfig.RawData(), file)

class ApplySubcommand(Subcommand):
    def __init__(self):
        super().__init__("apply", "apply a configuration file to the system")
    
    def SetupParser(self, parser: argparse.ArgumentParser):
        parser.add_argument("filename", type=pathlib.Path, help="load config from this file")
        parser.add_argument("--always", 
                            help="always apply a setting even if system is already configured in desired state"
                                 " (NOTE: this does NOT apply to read-only [RO] options, which are only verified)",
                            action="store_true")
        
    def Go(self, args):
        diffonly = (not args.always)
        model = LoadAndCheckConfigFile(args.filename) # will exit(1) if error
        errlist = ApplySystemConfig(model, diffonly)
        if not errlist:
            print("Successfully applied config!")
            exit(0)
        else:
            print("Could not apply all settings!")
            print("Errors:")
            print('\n'.join(errlist))
            exit(1)

class VerifySubcommand(Subcommand):
    def __init__(self):
        super().__init__("verify", "verify that the system configuration matches config file")
    
    def SetupParser(self, parser: argparse.ArgumentParser):
        parser.add_argument("filename", type=pathlib.Path, help="config to verify against")

    def Go(self, args):
        model = LoadAndCheckConfigFile(args.filename)
        sysconfig = ReadSystemConfig(SystemMetamodel())
        difflist = DiffTypecheckedModels(model, sysconfig, "file", "system")
        if not difflist:
            print("Verify OK.")
            exit(0)
        else:
            print("Verify FAILED!")
            print("Differences:")
            print('\n'.join(difflist))
            exit(1)

def main():
    parser = argparse.ArgumentParser("cf2", description=__doc__)

    subcmds: list[Subcommand] = [InfoSubcommand(), TypecheckSubcommand(), ObtainSubcommand(), ApplySubcommand(), VerifySubcommand()]

    subparsers = parser.add_subparsers(title = "Mode")

    for subcmd in subcmds:
        p = subparsers.add_parser(subcmd.Name(), help=subcmd.Help(), description=subcmd.Desc())
        subcmd.SetupParser(p)
        p.set_defaults(func=subcmd.Go)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
