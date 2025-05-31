from typed.main import *
from typed.models import Instance, Model, ExactModel

json1 = {
    "arg1": "aaa",
    "arg2": 10
}


Model1 = Model(
    arg1=Str,
    arg2=Int#,
    #arg3=Str
)

#direct_instance = Model1(json1)

instance = Instance(entity=json1, model=Model1)

print(issubclass(Model1, Json))
print(isinstance(instance, Json))
print(isinstance(json1, Json))
print(instance.get('arg1'))
