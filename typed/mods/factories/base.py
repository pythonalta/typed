import re
from typing import Type, Tuple as Tuple_, Hashable
from typed.mods.helper import _flat

def Union(*types: Tuple_[Type]) -> Type:
    """
    Build the 'union' of types:
        > an object 'p' of 'Union(X, Y, ...)'
        > is an object of some of 'X, Y, ...'
    """
    _flattypes, _ = _flat(*types)

    if not _flattypes:
        class __EmptyUnion(type):
            def __instancecheck__(cls, instance):
                return False
            def __subclasscheck__(cls, subclass):
                from typed.mods.types.base import Any
                if subclass is cls or subclass is Any:
                    return True
                return False
        return __EmptyUnion("Union()", (), {})

    class __Union(type):
        def __instancecheck__(cls, instance):
            for t in cls.__types__:
                if isinstance(t, type):
                    if hasattr(t, '__instancecheck__'):
                        result = t.__instancecheck__(instance)
                        if result:
                            return True
                    else:
                        result = isinstance(instance, t)
                        if result:
                            return True
            return False

        def __subclasscheck__(cls, subclass):
            from typed.mods.types.base import Any

            if subclass is cls:
                return True
            if subclass is Any:
                return True
            if subclass in cls.__types__:
                return True

            for t in cls.__types__:
                if isinstance(t, type): # Check if it's a type
                    if hasattr(t, '__subclasscheck__'):
                        if t.__subclasscheck__(subclass): # Corrected call
                            return True
                    else:
                        if issubclass(subclass, t):
                            return True
            return False

    class_name = f"Union({', '.join(t.__name__ for t in _flattypes)})"
    return __Union(class_name, (), {'__types__': _flattypes}) 

def Prod(*types: Tuple_[Type, int]) -> Type:
    """
    Build the 'product' of types:
        > the objects of 'Product(X, Y, ...)'
        > are the tuples '(x, y, ...)' such that
            1. 'len(x, y, ...) == len(X, Y, ...)'
            2. 'x is in X', 'y is in Y', ...

    New case:
        > Prod(SomeType, some_int): if SomeType is a type and some_int is some int > 0,
        > then Prod(SomeType, some_int) = Prod(SomeType, SomeType, SomeType ,...),
        > with SomeType repeated some_int times
    """
    if len(types) == 2 and isinstance(types[0], type) and isinstance(types[1], int) and types[1] > 0:
        _flattypes = (types[0],) * types[1]
        is_flexible = False
    else:
        _flattypes, is_flexible = _flat(*types)

    class __Prod(type):
        def __instancecheck__(cls, instance):
            if not isinstance(instance, tuple):
                return False
            if len(instance) != len(cls.__types__):
                return False
            return all(isinstance(x, t) for x, t in zip(instance, cls.__types__))

        def check(self, instance):
            if not isinstance(instance, tuple):
                return False
            if len(instance) != len(self.__types__):
                return False
            return all(isinstance(x, t) for x, t in zip(instance, self.__types__))

        def __subclasscheck__(cls, subclass):
            from typed.mods.types.base import Any
            if subclass is cls or subclass is Any or issubclass(subclass, tuple):
                return True
            if hasattr(subclass, '__bases__') and tuple in subclass.__bases__ and hasattr(subclass, '__types__') and len(subclass.__types__) == len(cls.__types__):
                return all(issubclass(st, ct) for st, ct in zip(subclass.__types__, cls.__types__))
            return False

    class_name = f"Prod({', '.join(t.__name__ for t in _flattypes)})"
    return __Prod(class_name, (tuple,), {'__types__': _flattypes}) 

def UProd(*types: Tuple_[Type]) -> Type:
    """
    Build the 'unordered product' of types:
        > the objects of 'UProd(X, Y, ...)'
        > are the tuples '(x, y, ...)' such that:
            1. 'len(x, y, ...) == len(X, Y, ...)'
            2. 'x, y, ... are in Union(X, Y, ...)'
    """
    _flattypes, is_flexible = _flat(*types)

    class __Uprod(type):
        def __instancecheck__(cls, instance):
            if not isinstance(instance, tuple):
                return False

            if len(instance) != len(cls.__types__):
                return False

            type_counts = {typ: cls.__types__.count(typ) for typ in cls.__types__}
            for elem in instance:
                for typ in type_counts:
                    if isinstance(elem, typ) and type_counts[typ] > 0:
                        type_counts[typ] -= 1
                        break
                else:
                    return False
            return all(count == 0 for count in type_counts.values())

        def check(self, instance):
            if not isinstance(instance, set):
                return False
            return all(any(isinstance(elem, typ) for typ in self.__types__) for elem in instance)

        def __subclasscheck__(cls, subclass):
            from typed.mods.types.base import Any
            if subclass is cls or subclass is Any or issubclass(subclass, tuple):
                return True
            if hasattr(subclass, '__bases__') and tuple in subclass.__bases__ and hasattr(subclass, '__types__') and len(subclass.__types__) == len(cls.__types__):
                return all(any(issubclass(st, ct) for ct in cls.__types__) for st in subclass.__types__)
            return False
    class_name = f"UProd({', '.join(t.__name__ for t in _flattypes)})"
    return __Uprod(class_name, (tuple,), {'__types__': _flattypes})

def Tuple(*args: Tuple_[Type]) -> Type:
    """
    Build the 'tuple' of types with flexible length:
        > the objects of 'Tuple(X, Y, ...)'
        > are the tuples '(x, y, ...)' such that:
            1. 'x, y, ... are in Union(X, Y, ...)'
           and
            2. The tuple can have any length >= 0.
    """
    _flattypes, is_flexible = _flat(*args)

    if not is_flexible and args:
        raise ValueError("Tuple() based on this definition is always flexible; check _flat implementation.")

    if not _flattypes:
        # Make it a subclass of tuple
        class _EmptyFlexibleTupleMeta(type(tuple)): # Inherit from type(tuple)
            def __instancecheck__(cls, instance):
                return isinstance(instance, tuple)
            def __subclasscheck__(cls, subclass):
                from typed.mods.types.base import Any
                if subclass is cls or subclass is Any or issubclass(subclass, tuple):
                    return True
                return False
        return _EmptyFlexibleTupleMeta("Tuple()", (tuple,), {}) # Pass tuple as base

    class _ElementUnionMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, tuple(cls.__types__))

    ElementUnion = _ElementUnionMeta("ElementUnion", (), {'__types__': _flattypes})

    class __Tuple(type(tuple)):
        def __instancecheck__(cls, instance):
            if not isinstance(instance, tuple):
                return False
            return all(isinstance(x, ElementUnion) for x in instance)

        def __subclasscheck__(cls, subclass):
            from typed.mods.types.base import Any
            if subclass is cls or subclass is Any or issubclass(subclass, tuple):
                return True
            if hasattr(subclass, '__bases__') and tuple in subclass.__bases__ and hasattr(subclass, '__types__'):
                subclass_element_types = subclass.__types__
                return all(any(issubclass(st, ct) for ct in cls.__types__) for st in subclass_element_types)
            return False

    class_name = f"Tuple({', '.join(t.__name__ for t in _flattypes)})"
    if _flattypes:
        class_name = f"Tuple({', '.join(t.__name__ for t in _flattypes)}, ...)"
    else:
        class_name = "Tuple()"
    return __Tuple(class_name, (tuple,), {'__types__': _flattypes}) # Pass tuple as base

def List(*args: Tuple_[Type]) -> Type:
    """
    Build the 'list' of types:
        > the objects of 'List(X, Y, ...)'
        > are the lists '[x, y, ...]' such that:
            1. 'x, y, ... are in Union(X, Y, ...)'
           and
            2. The list can have any length >= 0.
    """
    _flattypes, is_flexible = _flat(*args)

    if not is_flexible and args:
        raise ValueError("List() based on this definition is always flexible; check _flat implementation.")

    class _ElementUnionMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, tuple(cls.__types__))

    ElementUnion = _ElementUnionMeta("ListElementUnion", (), {'__types__': _flattypes})

    class __List(type(list)):
        def __instancecheck__(cls, instance):
            if not isinstance(instance, list):
                return False
            return all(isinstance(x, ElementUnion) for x in instance)
        def __subclasscheck__(cls, subclass):
            from typed.mods.types.base import Any
            if subclass is cls or subclass is Any or issubclass(subclass, list):
                return True
            if hasattr(subclass, '__bases__') and list in subclass.__bases__ and hasattr(subclass, '__types__'):
                subclass_element_types = subclass.__types__
                return all(any(issubclass(st, ct) for ct in cls.__types__) for st in subclass_element_types)
            return False

    class_name = f"List({', '.join(t.__name__ for t in _flattypes)})"
    if _flattypes:
        class_name = f"List({', '.join(t.__name__ for t in _flattypes)}, ...)"
    else:
        class_name = "List()"
    return __List(class_name, (list,), {'__types__': _flattypes}) # Pass list as base

def Set(*args: Type) -> Type:
    """
    Build the 'set' of types:
        > the objects of 'Set(X, Y, ...)'
        > are the sets '{x, y, ...}' such that:
            1. 'x, y, ... are in Union(X, Y, ...)'
           and
            2. The set can have any size >= 0.
            3. Elements must be hashable.
    """
    _flattypes, is_flexible = _flat(*args)

    if not is_flexible and args:
        raise ValueError("Set() based on this definition is always flexible; check _flat implementation.")

    class _ElementUnionMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, tuple(cls.__types__)) and isinstance(instance, Hashable)

    ElementUnion = _ElementUnionMeta("SetElementUnion", (), {'__types__': _flattypes})
 
    class __Set(type(set)):
        def __instancecheck__(cls, instance):
            if not isinstance(instance, set):
                return False
            return all(isinstance(x, ElementUnion) for x in instance)

        def __subclasscheck__(cls, subclass: Type) -> bool:
            from typed.mods.types.base import Any

            if subclass is cls or subclass is Any or issubclass(subclass, set):
                return True

            if hasattr(subclass, '__bases__') and set in subclass.__bases__ and hasattr(subclass, '__types__'):
                subclass_element_types = subclass.__types__
                return all(any(issubclass(st, ct) for ct in cls.__types__) for st in subclass_element_types)

            return False

    class_name = f"Set({', '.join(t.__name__ for t in _flattypes)})"
    if _flattypes:
        class_name = f"Set({', '.join(t.__name__ for t in _flattypes)}, ...)"
    else:
        class_name = "Set()"

    return __Set(class_name, (set,), {'__types__': _flattypes}) # Pass set as base

def Dict(*args: Type) -> Type:
    """
    Build the 'dict' of types:
        > the objects of 'Dict(X, Y, ...)'
        > are the dictionaries '{k: v, ...}' such that:
            1. 'v, ... are in Union(X, Y, ...)' (keys are not restricted)
           and
            2. The dict can have any size >= 0.
            3. Keys must be hashable (standard dict behavior).
    """
    if not args:
        class _AnyAnyDictMeta(type(dict)):
            def __instancecheck__(cls, instance):
                return isinstance(instance, dict)
            def __subclasscheck__(cls, subclass):
                from typed.mods.types.base import Any
                if subclass is cls or subclass is Any or issubclass(subclass, dict):
                    return True
                return False
        return _AnyAnyDictMeta("Dict()", (dict,), {})

    _flattypes, is_flexible = _flat(*args)

    if not is_flexible and args:
        pass

    class _ValueUnionMeta(type):
        def __instancecheck__(cls, instance):
            for t in cls.__types__:
                if isinstance(t, type) and hasattr(t, '__instancecheck__'):
                    result = t.__instancecheck__(t, instance)
                    if result:
                        return True
                else:
                    result = isinstance(instance, t)
                    if result:
                        return True
            return False

    ValueUnion = _ValueUnionMeta("DictValueUnion", (), {'__types__': _flattypes})

    class __Dict(type(dict)):
        def __instancecheck__(cls, instance):
            if not isinstance(instance, dict):
                return False
            all_values_ok = True
            for i, v in enumerate(instance.values()):
                if not isinstance(v, ValueUnion):
                    all_values_ok = False
                    break
            return all_values_ok

        def __subclasscheck__(cls, subclass):
            from typed.mods.types.base import Any
            if subclass is cls or subclass is Any or issubclass(subclass, dict):
                return True
            if hasattr(subclass, '__bases__') and dict in subclass.__bases__ and hasattr(subclass, '__types__'):
                subclass_value_union_types = subclass.__types__
                return all(any(issubclass(svt, vt) for vt in cls.__types__) for svt in subclass_value_union_types)
            return False

    class_name = f"Dict(..., {', '.join(t.__name__ for t in _flattypes)})"
    return __Dict(class_name, (dict,), {'__types__': _flattypes})

