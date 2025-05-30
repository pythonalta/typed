from typed.mods.factories.base import Union, Dict, Set, List, Regex

Int   = int
Str   = str
Bool  = bool
Float = float
Type  = type
Nill  = type(None)

class Any(type):
    def __instancecheck__(cls, instance):
        return True
    def __subclasscheck__(self, subclass):
        return True

Json = Union(Dict(Str, Any), Set(Any), List(Any))
Path = Regex(r"^/?(?:[^/:\r\n*?\"<>|\\]+/)*[^/:\r\n*?\"<>|\\]+/?$")
