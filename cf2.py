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

#class MetaTreeFixedDict(MetaTreeNode):
#    __dict: dict[str, MetaTreeNode]
#    pass

#class MetaModel:
#    root: MetaTreeNode
#    pass

n = MetaTreeNode("cheese", "this is cheesy")
s = MetaTreeScalar("egg", "how many eggs", int, parent=n)
print(f"{s.Name()}: {s.HelpString()}. Type={s.Ty().__name__}. (parent = {s.Parent()})")
print(f"{n.Name()}: {n.HelpString()} (parent = {n.Parent()}) (children = {n.Children()})")
