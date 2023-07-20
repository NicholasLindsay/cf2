#!/usr/bin/python3

"""Configurator.

This tool is for bringing a Linux system into a certain configuration.
The intended usecase is to enable reproducible experiments by bringing
the system into a standardized environent.
"""

class MetaTreeNode:
    __name: str
    __helpstring: str
    __parent: 'Optional[MetaTreeNode]'
    __children: dict[str, 'MetaTreeNode']

    def __init__(self, name: str, helpstring: str, **kwargs):
        self.__name = name
        self.__helpstring = helpstring
        self.__parent = None
        if 'parent' in kwargs:
            self.__parent = kwargs['parent']
            self.__parent.__RegisterChild(self)
        self.__children = {}

    def Name(self) -> str:
        return self.__name
    
    def HelpString(self) -> str:
        return self.__helpstring

    def Parent(self) -> 'MetaTreeNode':
        return self.__parent
    
    def Children(self) -> 'dict[str, MetaTreeNode]':
        return self.__children
    
    def __RegisterChild(self, ch: 'MetaTreeNode'):
        self.__children[ch.Name()] = ch

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

# Helper function to insert text at start of each line
def PrefixLines(s: str, prefix: str):
    new_lines = [f'{prefix}{l}' for l in s.splitlines(keepends=True)]
    return ''.join(new_lines)

def MetadataTreeAsStr(root: MetaTreeNode, is_top=True, is_last_sibling=True):
    s = ''
    if is_top:
        s = f'{root.Name()}: {root.HelpString()}\n'
    else:
        if is_last_sibling:
            s = f' └── {root.Name()}: {root.HelpString()}\n'
        else:
            s = f' ├── {root.Name()}: {root.HelpString()}\n'

    prefix = ''
    if not is_top:
        if is_last_sibling:
            prefix = '    '
        else:
            prefix = ' |  '

    children_list = list(root.Children().values())

    for c in children_list:
        if c == children_list[-1]:
            s += PrefixLines(MetadataTreeAsStr(c, False, True), prefix)
        else:
            s += PrefixLines(MetadataTreeAsStr(c, False, False), prefix)
        
    return s

# ===[ META MODEL DEFINITION ]===
top = MetaTreeNode("top", "top node")
ksm = MetaTreeNode("ksm", "kernel samepage merging", parent=top)
MetaTreeScalar("max_page_sharing", "", int, parent=ksm)
MetaTreeScalar("merge_accross_nodes", "", int, parent=ksm)
MetaTreeScalar("pages_to_scan", "", int, parent=ksm)
MetaTreeScalar("run", "", int, parent=ksm)
MetaTreeScalar("sleep_millisecs", "", int, parent=ksm)
MetaTreeScalar("stable_node_chains_prune_millisecs", "", int, parent=ksm)
MetaTreeScalar("use_zero_pages", "", int, parent=ksm)
lru_gen = MetaTreeNode("lru_gen", "", parent=top)
MetaTreeScalar("enabled", "", str, parent=lru_gen)
MetaTreeScalar("min_ttl_ms", "", int, parent=lru_gen)
numa = MetaTreeNode("numa", "non-uniform memory access", parent = top)
MetaTreeScalar("demotion_enabled", "", bool, parent=numa)
swap = MetaTreeNode("swap", "", parent=top)
MetaTreeScalar("vma_ra_enabled", "", bool, parent=swap)
thp = MetaTreeNode("transparent_hugepage", "transparent hugepages", parent=top)
MetaTreeScalar("defrag", "", str, parent=thp)
MetaTreeScalar("enabled", "", str, parent=thp)
MetaTreeScalar("hpage_pmd_size", "", int, parent=thp)
khpd = MetaTreeNode("khugepaged", "huge pages daemon", parent=thp)
MetaTreeScalar("alloc_sleep_millisecs", "", int, parent=khpd)
MetaTreeScalar("max_ptes_none", "", int, parent=khpd)
MetaTreeScalar("max_ptes_shared", "", int, parent=khpd)
MetaTreeScalar("max_ptes_swap", "", int, parent=khpd)
MetaTreeScalar("pages_to_scan", "", int, parent=khpd)
MetaTreeScalar("scan_sleep_millisecs", "", int, parent=khpd)
MetaTreeScalar("shmem_enabled", "", str, parent=thp)
MetaTreeScalar("use_zero_page", "", int, parent=thp)

print(MetadataTreeAsStr(top))
