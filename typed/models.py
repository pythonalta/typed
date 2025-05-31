from typing import Type
from typed.mods.types.base import Json, Any
from typed.mods.helper_models import _OptionalWrapper

def Optional(type: Type, default_value: Any):
    if not isinstance(type, type) and not hasattr(type, '__instancecheck__'):
        raise TypeError(f"OptionalArg type must be a type or have an __instancecheck__ method, got {type}.")
    if not isinstance(default_value, type):
        if hasattr(type, '__instancecheck__') and not type.__instancecheck__(default_value):
            raise TypeError(f"Default value {default_value} is not an instance of {getattr(type, '__name__', str(type))}.")
        elif isinstance(type, type) and not isinstance(default_value, type):
            raise TypeError(f"Default value {default_value} is not an instance of {getattr(type, '__name__', str(type))}.")
    return _OptionalWrapper(type, default_value)

def Model(**kwargs: Type) -> Type[Json]:
    """
    Build a 'model' which is a subclass of Json with support for optional arguments.
        > An object 'x' is an instance of Model(arg1: Type1, arg2: Type2 = default_value, ...) iff:
            1. isinstance(x, Json) is True
            2. x is a dictionary
            3. x.get(arg1) has type Type1
            4. If arg2 is present in x, x.get(arg2) has type Type2, otherwise the default value is used implicitly.

    Concatenation of Models is supported.
    """
    if not kwargs:
        return dict

    if not all(isinstance(key, str) for key in kwargs.keys()):
        raise TypeError("All arguments to Model must be strings representing attribute names.")

    processed_attributes_and_types = []
    required_attribute_keys = set()
    optional_attributes_and_defaults = {}

    for key, value in kwargs.items():
        if isinstance(value, _OptionalWrapper):
            processed_attributes_and_types.append((key, value.type))
            optional_attributes_and_defaults[key] = value.default_value
        elif isinstance(value, type) or hasattr(value, '__instancecheck__'):
            processed_attributes_and_types.append((key, value))
            required_attribute_keys.add(key)
        else:
            raise TypeError(f"All argument values to Model must be types or OptionalArg instances. Invalid type for '{key}': {type(value)}")

    attributes_and_types = tuple(processed_attributes_and_types)

    class __Model(type(Json)):
        def __new__(cls, name, bases, dct):
            new_class = super().__new__(cls, name, bases, dct)
            setattr(new_class, '_required_attributes_and_types', dct.get('_initial_attributes_and_types', ()))
            setattr(new_class, '_required_attribute_keys', dct.get('_initial_required_attribute_keys', set()))
            setattr(new_class, '_optional_attributes_and_defaults', dct.get('_initial_optional_attributes_and_defaults', {}))
            return new_class

        def __init__(cls, name, bases, dct):
            if '_initial_attributes_and_types' in dct:
                del dct['_initial_attributes_and_types']
            if '_initial_required_attribute_keys' in dct:
                del dct['_initial_required_attribute_keys']
            if '_initial_optional_attributes_and_defaults' in dct:
                del dct['_initial_optional_attributes_and_defaults']
            super().__init__(name, bases, dct)

        def __instancecheck__(cls, instance: Any) -> bool:
            if not isinstance(instance, dict):
                return False

            required_attributes_and_types = getattr(cls, '_required_attributes_and_types', ())
            required_attribute_keys = getattr(cls, '_required_attribute_keys', set())
            optional_attributes_and_defaults = getattr(cls, '_optional_attributes_and_defaults', {})

            if not required_attribute_keys.issubset(instance.keys()):
                return False

            for attr_name, expected_type in required_attributes_and_types:
                attr_value = instance.get(attr_name, optional_attributes_and_defaults.get(attr_name))

                if not isinstance(attr_value, expected_type):
                    if isinstance(expected_type, type) and hasattr(expected_type, '__instancecheck__'):
                        if not expected_type.__instancecheck__(attr_value):
                            return False
                    else:
                        return False
            return True

        def __subclasscheck__(cls, subclass: Type) -> bool:
            if not issubclass(subclass, Json):
                return False

            if not hasattr(subclass, '_required_attributes_and_types') or not hasattr(subclass, '_required_attribute_keys') or not hasattr(subclass, '_optional_attributes_and_defaults'):
                return False

            cls_attrs = dict(getattr(cls, '_required_attributes_and_types', ()))
            subclass_attrs = dict(getattr(subclass, '_required_attributes_and_types', ()))
            cls_required_keys = getattr(cls, '_required_attribute_keys', set())
            subclass_required_keys = getattr(subclass, '_required_attribute_keys', set())
            cls_optional_keys = set(getattr(cls, '_optional_attributes_and_defaults', {}).keys())
            subclass_optional_keys = set(getattr(subclass, '_optional_attributes_and_defaults', {}).keys())

            if not cls_required_keys.issubset(subclass_required_keys):
                return False

            if not (cls_required_keys | cls_optional_keys).issubset(subclass_required_keys | subclass_optional_keys):
                return False

            for attr_name, parent_type in cls_attrs.items():
                if attr_name not in subclass_attrs:
                    return False

                subclass_type = subclass_attrs[attr_name]

                if isinstance(parent_type, type) and isinstance(subclass_type, type):
                    if not issubclass(subclass_type, parent_type):
                        return False
                elif hasattr(parent_type, '__subclasscheck__') and isinstance(subclass_type, type):
                    if not parent_type.__subclasscheck__(subclass_type):
                        return False
                elif isinstance(parent_type, type) and hasattr(subclass_type, '__subclasscheck__'):
                    if not issubclass(subclass_type, parent_type):
                        return False
                elif hasattr(parent_type, '__subclasscheck__') and hasattr(subclass_type, '__subclasscheck__'):
                    if not parent_type.__subclasscheck__(subclass_type):
                        return False
                else:
                    return False

            return True

    args_str = ", ".join(f"{key}: {getattr(value, '__name__', str(value))}" if not isinstance(value, _OptionalWrapper) else f"{key}: {getattr(value.type, '__name__', str(value.type))} = {repr(value.default_value)}" for key, value in kwargs.items())
    class_name = f"Model({args_str})"
    return __Model(class_name, (dict,), {
        '_initial_attributes_and_types': attributes_and_types,
        '_initial_required_attribute_keys': required_attribute_keys,
        '_initial_optional_attributes_and_defaults': optional_attributes_and_defaults
    })

def ExactModel(**kwargs: Type) -> Type[Json]:
    """
    Build an 'exact model' with support for optional arguments.
        > 'x' is an object of 'ExactModel(arg1=Type1, arg2=Type2 = default_value, ...)' iff:
            1. isinstance(x, Json) is True
            2. The set of keys in x is exactly the set of required argument keys.
            3. x.get(arg1) is of type Type1 (for required args)
            4. x.get(arg2) is of type Type2 (for optional args present in x)

    Concatenation of ExactModels is supported.
    """
    if not kwargs:
        return dict

    if not all(isinstance(key, str) for key in kwargs.keys()):
        raise TypeError("All arguments to ExactModel must be strings representing attribute names.")

    processed_attributes_and_types = []
    required_attribute_keys = set()
    optional_attributes_and_defaults = {}

    for key, value in kwargs.items():
        if isinstance(value, _OptionalWrapper):
            processed_attributes_and_types.append((key, value.type))
            optional_attributes_and_defaults[key] = value.default_value
        elif isinstance(value, type) or hasattr(value, '__instancecheck__'):
            processed_attributes_and_types.append((key, value))
            required_attribute_keys.add(key)
        else:
            raise TypeError(f"All argument values to ExactModel must be types or OptionalArg instances. Invalid type for '{key}': {type(value)}")

    attributes_and_types = tuple(processed_attributes_and_types)

    class __ExactModel(type(Json)):
        def __new__(cls, name, bases, dct):
            new_class = super().__new__(cls, name, bases, dct)
            setattr(new_class, '_required_attributes_and_types', dct.get('_initial_attributes_and_types', ()))
            setattr(new_class, '_required_attribute_keys', dct.get('_initial_required_attribute_keys', set()))
            setattr(new_class, '_optional_attributes_and_defaults', dct.get('_initial_optional_attributes_and_defaults', {}))
            setattr(new_class, '_all_possible_keys', dct.get('_initial_all_possible_keys', set()))
            return new_class

        def __init__(cls, name, bases, dct):
            if '_initial_attributes_and_types' in dct:
                del dct['_initial_attributes_and_types']
            if '_initial_required_attribute_keys' in dct:
                del dct['_initial_required_attribute_keys']
            if '_initial_optional_attributes_and_defaults' in dct:
                del dct['_initial_optional_attributes_and_defaults']
            if '_initial_all_possible_keys' in dct:
                del dct['_initial_all_possible_keys']
            super().__init__(name, bases, dct)

        def __instancecheck__(cls, instance: Any) -> bool:
            if not isinstance(instance, dict):
                return False

            required_attributes_and_types = dict(getattr(cls, '_required_attributes_and_types', ()))
            required_attribute_keys = getattr(cls, '_required_attribute_keys', set())
            optional_attributes_and_defaults = getattr(cls, '_optional_attributes_and_defaults', {})
            instance_keys = set(instance.keys())
            all_possible_keys = required_attribute_keys | set(optional_attributes_and_defaults.keys())
            if not instance_keys.issubset(all_possible_keys):
                return False
            if not required_attribute_keys.issubset(instance_keys):
                return False

            for attr_name, attr_value in instance.items():
                if attr_name in required_attributes_and_types:
                    expected_type = required_attributes_and_types[attr_name]
                    if not isinstance(attr_value, expected_type):
                        if isinstance(expected_type, type) and hasattr(expected_type, '__instancecheck__'):
                            if not expected_type.__instancecheck__(attr_value):
                                return False
                        else:
                            return False
                elif attr_name in optional_attributes_and_defaults:
                    expected_type = optional_attributes_and_defaults[attr_name].type
                    if not isinstance(attr_value, expected_type):
                        if isinstance(expected_type, type) and hasattr(expected_type, '__instancecheck__'):
                            if not expected_type.__instancecheck__(attr_value):
                                return False
                        else:
                            return False
                else:
                    return False
            return True

        def __subclasscheck__(cls, subclass: Type) -> bool:
            if not issubclass(subclass, Json):
                return False

            if not hasattr(subclass, '_required_attributes_and_types') or not hasattr(subclass, '_required_attribute_keys') or not hasattr(subclass, '_optional_attributes_and_defaults'):
                 return False

            cls_attrs = dict(getattr(cls, '_required_attributes_and_types', ()))
            subclass_attrs = dict(getattr(subclass, '_required_attributes_and_types', ()))
            cls_required_keys = getattr(cls, '_required_attribute_keys', set())
            subclass_required_keys = getattr(subclass, '_required_attribute_keys', set())
            cls_optional_attrs_defaults = getattr(cls, '_optional_attributes_and_defaults', {})
            subclass_optional_attrs_defaults = getattr(subclass, '_optional_attributes_and_defaults', {})
            cls_optional_keys = set(cls_optional_attrs_defaults.keys())
            subclass_optional_keys = set(subclass_optional_attrs_defaults.keys())

            if (cls_required_keys | cls_optional_keys) != (subclass_required_keys | subclass_optional_keys):
                return False

            if not cls_required_keys.issubset(subclass_required_keys):
                return False

            for attr_name in cls_optional_keys:
                if attr_name not in subclass_optional_keys:
                    return False

                parent_type = cls_optional_attrs_defaults[attr_name].type
                subclass_info = subclass_optional_attrs_defaults[attr_name]
                subclass_type = subclass_info.type
                subclass_default_value = subclass_info.default_value

                if isinstance(parent_type, type) and isinstance(subclass_type, type):
                    if not issubclass(subclass_type, parent_type):
                        return False
                elif hasattr(parent_type, '__subclasscheck__') and isinstance(subclass_type, type):
                    if not parent_type.__subclasscheck__(subclass_type):
                        return False
                elif isinstance(parent_type, type) and hasattr(subclass_type, '__subclasscheck__'):
                    if not issubclass(subclass_type, parent_type):
                        return False
                elif hasattr(parent_type, '__subclasscheck__') and hasattr(subclass_type, '__subclasscheck__'):
                      if not parent_type.__subclasscheck__(subclass_type):
                        return False
                else:
                    return False

                if not isinstance(subclass_default_value, parent_type):
                    if hasattr(parent_type, '__instancecheck__') and not parent_type.__instancecheck__(subclass_default_value):
                        return False
                    elif isinstance(parent_type, type):
                        return False

            for attr_name in cls_required_keys:
                parent_type = [t for k,t in cls_attrs.items() if k == attr_name][0]
                if attr_name not in subclass_attrs:
                    return False

                subclass_type = subclass_attrs[attr_name]

                if isinstance(parent_type, type) and isinstance(subclass_type, type):
                    if not issubclass(subclass_type, parent_type):
                        return False
                elif hasattr(parent_type, '__subclasscheck__') and isinstance(subclass_type, type):
                    if not parent_type.__subclasscheck__(subclass_type):
                        return False
                elif isinstance(parent_type, type) and hasattr(subclass_type, '__subclasscheck__'):
                    if not issubclass(subclass_type, parent_type):
                        return False
                elif hasattr(parent_type, '__subclasscheck__') and hasattr(subclass_type, '__subclasscheck__'):
                    if not parent_type.__subclasscheck__(subclass_type):
                        return False
                else:
                    return False
            return True

    args_str = ", ".join(f"{key}: {getattr(value, '__name__', str(value))}" if not isinstance(value, _OptionalWrapper) else f"{key}: {getattr(value.type, '__name__', str(value.type))} = {repr(value.default_value)}" for key, value in kwargs.items())
    class_name = f"ExactModel({args_str})"

    return __ExactModel(class_name, (dict,), {
        '_initial_attributes_and_types': attributes_and_types,
        '_initial_required_attribute_keys': required_attribute_keys,
        '_initial_optional_attributes_and_defaults': optional_attributes_and_defaults,
        '_initial_all_possible_keys': required_attribute_keys | set(optional_attributes_and_defaults.keys())
    })

AnyModel = Model()

def Instance(entity: dict, model: Type) -> Any:
    # Get the metaclass of the provided model
    model_metaclass = type(model)

    # Check if the model's metaclass is __Model or __ExactModel
    if not isinstance(model, type) or (model_metaclass.__name__ != "__Model" and model_metaclass.__name__ != "__ExactModel"):
         raise TypeError(f"'{getattr(model, '__name__', str(model))}' not of Model or ExactModel types. Received type: {type(model).__name__}.")

    if not isinstance(entity, dict):
        # Changed the error message to reflect the actual type received
        raise TypeError(f"'{getattr(entity, '__name__', str(entity))}': not of Json type. Received type: {type(entity).__name__}.")


    if isinstance(entity, model):
        return entity
    else:
        # Changed the error message to be more informative
        raise TypeError(f"'{getattr(entity, '__name__', str(entity))}': not an instance of {model.__name__}.")
