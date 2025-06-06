import inspect
from typing import get_type_hints, Callable, Any as Any_, Tuple, Type

def _flat(*types):
    if not types:
        return (), False
    flat_list = []
    is_flexible = True
    def _flatten(item):
       if isinstance(item, type):
           flat_list.append(item)
       elif isinstance(item, (list, tuple)):
            for sub_item in item:
                _flatten(sub_item)
       else:
            raise TypeError(f"Unsupported type in _flat: {type(item)}")
    for typ in types:
       _flatten(typ)
    if not all(isinstance(t, type) for t in flat_list):
        raise TypeError("All arguments must be types.")
    return (tuple(flat_list), is_flexible)

def _runtime_domain(func):
    def wrapper(*args, **kwargs):
        types_at_runtime = tuple(type(arg) for arg in args)
        return tuple(*types_at_runtime)
    return wrapper

def _runtime_codomain(func):
    signature = inspect.signature(func)
    return_annotation = signature.return_annotation
    if return_annotation is not inspect.Signature.empty:
        return return_annotation
    return type(None)

def _is_domain_hinted(func):
    """Check if the function has type hints for all parameters if it has any parameters."""
    sig = inspect.signature(func)
    parameters = sig.parameters

    if not parameters:
        return True

    type_hints = get_type_hints(func)
    param_hints = {param_name: type_hints.get(param_name) for param_name, param in parameters.items()}
    non_hinted_params = [param_name for param_name, hint in param_hints.items() if hint is None]

    if non_hinted_params:
        raise TypeError(
            f"Function '{func.__name__}' must have type hints for all parameters if it has any."
            f"\n\t --> Missing hints: '{', '.join(non_hinted_params)}'."
        )
    return True

def _is_codomain_hinted(func):
    """Check if the function has a type hint for its return value and report if missing."""
    type_hints = get_type_hints(func)
    if 'return' not in type_hints or type_hints['return'] is None:
        raise TypeError(f"Function '{func.__name__}' must have a return type hint.")
    return True

def _get_original_func(func: Callable) -> Callable:
    """Recursively gets the original function if it's wrapped."""
    while hasattr(func, '__wrapped__'):
        func = func.__wrapped__
    if hasattr(func, 'func'):
        return _get_original_func(func.func)
    return func

def _hinted_domain(func: Callable) -> Tuple[Type, ...]:
    original_func = _get_original_func(func)
    type_hints = get_type_hints(original_func)
    if hasattr(original_func, '_composed_domain_hint'):
        return original_func._composed_domain_hint
    try:
        sig = inspect.signature(original_func)
        domain_types = []
        for param in sig.parameters.values():
            if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                     inspect.Parameter.POSITIONAL_ONLY,
                                     inspect.Parameter.KEYWORD_ONLY):
                hint = type_hints.get(param.name, inspect.Signature.empty)
                if hint is not inspect.Signature.empty:
                    domain_types.append(hint)
        return tuple(domain_types)
    except ValueError:
        pass
    return ()

def _hinted_codomain(func: Callable) -> Any_:
    original_func = _get_original_func(func)
    type_hints = get_type_hints(original_func)

    if hasattr(original_func, '_composed_codomain_hint'):
        return original_func._composed_codomain_hint

    try:
        sig = inspect.signature(original_func)
        return type_hints.get('return', inspect.Signature.empty)
    except ValueError:
        pass
    return inspect.Signature.empty

def _get_type_display_name(tp):
    if hasattr(tp, '__display__'):
        return tp.__display__
    name = getattr(tp, '__name__', repr(tp))
    if name in ['int', 'float', 'str', 'bool']:
        return name.capitalize()
    if name == 'NoneType':
        return "Nill"

def _check_domain(func, param_names, expected_domain, actual_domain, args, allow_subclass=True):
    mismatches = []
    for name, expected_type in zip(param_names, expected_domain):
        actual_value = args[param_names.index(name)]
        actual_type = type(actual_value)

        expected_display_name = _get_type_display_name(expected_type)
        actual_display_name = _get_type_display_name(actual_type)

        if isinstance(expected_type, type) and hasattr(expected_type, '__types__') and isinstance(expected_type.__types__, tuple):
            if not any(isinstance(actual_value, t) for t in expected_type.__types__):
                mismatches.append(f"\n\t --> '{name}':")
                mismatches.append(f"\n\t\t [value]: '{actual_value}'")
                mismatches.append(f"\n\t\t [expected_type]: '{expected_display_name}'")
                mismatches.append(f"\n\t\t [received_type]: '{actual_display_name}'")
            else:
                for t in expected_type.__types__:
                    if isinstance(actual_value, t) and hasattr(t, 'check') and not t.check(actual_value):
                        mismatches.append(f"\n\t --> '{name}': additional check filed.")
                        mismatches.append(f"\n\t\t [value]: '{actual_value}'")
                        mismatches.append(f"\n\t\t [received_type]: '{actual_display_name}'")
                        mismatches.append(f"\n\t\t [failed_type]: '{_get_type_display_name(t)}'")
        elif not isinstance(actual_value, expected_type):
            mismatches.append(f"\n\t --> '{name}':")
            mismatches.append(f"\n\t\t [value]: '{actual_value}'")
            mismatches.append(f"\n\t\t [expected_type]: '{expected_display_name}'")
            mismatches.append(f"\n\t\t [received_type]: '{actual_display_name}'")
        else:
            if hasattr(expected_type, 'check'):
                if not expected_type.check(actual_value):
                    mismatches.append(f"\n\t\t [value]: '{actual_value}'")
                    mismatches.append(f"\n\t\t [expected_type]: '{expected_display_name}'")
                    mismatches.append(f"\n\t\t [received_type]: '{actual_display_name}'")

    if mismatches:
        mismatch_str = "".join(mismatches) + "."
        raise TypeError(f"Domain mismatch in func '{func.__name__}': {mismatch_str}")


def _check_codomain(func, expected_codomain, actual_codomain, result, allow_subclass=True):
    from typed.mods.types.base import Any as TypedAny_
    if expected_codomain is TypedAny_ or expected_codomain is inspect.Signature.empty:
        return

    expected_display_name = _get_type_display_name(expected_codomain)
    actual_display_name = _get_type_display_name(actual_codomain)

    if isinstance(expected_codomain, type) and hasattr(expected_codomain, '__types__') and isinstance(expected_codomain.__types__, tuple):
        union_types = expected_codomain.__types__
        if any(isinstance(result, union_type) for union_type in union_types):
            for t in union_types:
                if isinstance(result, t):
                    if hasattr(t, 'check') and not t.check(result):
                        raise TypeError(
                            f"Codomain mismatch in func '{func.__name__}':"
                            f"\n\t --> failed additional type check."
                            f"\n\t\t [result_value]: '{result}'"
                            f"\n\t\t [expected_type]: '{expected_display_name}'"
                            f"\n\t\t [received_type]: '{actual_display_name}'"
                            f"\n\t\t [failed_typed]:  '{_get_type_display_name(t)}'"
                        )
            return

        expected_union_names = [_get_type_display_name(t) for t in union_types]
        raise TypeError(
            f"Codomain mismatch in func '{func.__name__}':"
            f"\n\t [result_value]: '{result}'."
            f"\n\t [expected_type]: 'Union({', '.join(expected_union_names)})'."
            f"\n\t [received_type]: '{actual_display_name}'"
        )

    elif isinstance(expected_codomain, type):
        if isinstance(result, expected_codomain):
            if allow_subclass or (not allow_subclass and actual_codomain is expected_codomain):
                if hasattr(expected_codomain, 'check') and not expected_codomain.check(result):
                    raise TypeError(
                        f"Codomain mismatch in func '{func.__name__}':"
                        f"\n\t --> failed additional type check."
                        f"\n\t\t [result_value]: '{result}'."
                        f"\n\t\t [expected_type]: '{expected_display_name}'"
                        f"\n\t\t [received_type]: '{actual_display_name}'"
                        f"\n\t\t [failed_typed]:  '{_get_type_display_name(t)}'"
                    )
                return

        raise TypeError(
            f"Codomain mismatch in func '{func.__name__}':"
            f"\n\t [result_value]: '{result}'"
            f"\n\t [expected_type]: '{expected_display_name}'"
            f"\n\t [received_type]: '{actual_display_name}'"
        )
    else:
        if not isinstance(result, expected_codomain):
            raise TypeError(
                f"Codomain mismatch in func '{func.__name__}':"
                f"\n\t [result_value]: '{result}'"
                f"\n\t [expected_type]: '{expected_display_name}'"
                f"\n\t [received_type]: '{actual_display_name}'"
            )

class __Any(type):
    def __instancecheck__(cls, instance):
        return True
    def __subclasscheck__(cls, subclass):
        return True

def _builtin_nulls():
    from typed.mods.factories.base import List, Tuple, Set, Dict
    return {
        Dict: {},
        dict: {},
        Tuple: (),
        tuple: (),
        List: [],
        list: [],
        Set: set(),
        set: set(),
        frozenset: frozenset(),
        str: "",
        int: 0,
        float: 0.0,
        bool: False,
        type(None): None,
    }

def _get_null_object(typ):
    if hasattr(typ, '__bases__'):
        bases = typ.__bases__
        if list in bases:
            if hasattr(typ, '__types__') and typ.__types__:
                elem_null = _get_null_object(typ.__types__[0])
                return [elem_null]
            else:
                return []
        if tuple in bases:
            if hasattr(typ, '__types__') and typ.__types__:
                if hasattr(typ, '__name__') and typ.__name__.startswith("Prod"):
                    return tuple(_get_null_object(t) for t in typ.__types__)
                return tuple()
            else:
                return ()
        if set in bases:
            if hasattr(typ, '__types__') and typ.__types__:
                elem_null = _get_null_object(typ.__types__[0])
                return {elem_null}
            else:
                return set()
        if dict in bases:
            if hasattr(typ, '__types__') and typ.__types__:
                vtyp = typ.__types__[0]
                vnull = _get_null_object(vtyp)
                if vtyp in (str,):
                    return {"": vnull}
                elif vtyp in (int,):
                    return {0: vnull}
                elif vtyp in (float,):
                    return {0.0: vnull}
                else:
                    return {None: vnull}
            else:
                return {}

    if typ in _builtin_nulls():
        return _builtin_nulls()[typ]
    return None

def _is_null_of_type(x, typ):
    null = _get_null_object(typ)
    if typ in _builtin_nulls().keys():
        return x == _builtin_nulls()[typ]
    if hasattr(typ, '__bases__'):
        base = typ.__bases__[0]
        return x == null and isinstance(x, base)
    return x == null
