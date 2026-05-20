from .constants import CATEGORY
from .helpers import build_inverse_switch_input_types, build_switch_input_types


class AnySwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return build_switch_input_types()

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("output",)
    FUNCTION = "switch"
    CATEGORY = CATEGORY

    def switch(self, select=1, input_1=None, input_2=None):
        if select == 1:
            return (input_1,)
        return (input_2,)


class AnySwitchInverse:
    @classmethod
    def INPUT_TYPES(cls):
        return build_inverse_switch_input_types()

    RETURN_TYPES = ("*", "*")
    RETURN_NAMES = ("output_1", "output_2")
    FUNCTION = "switch"
    CATEGORY = CATEGORY

    def switch(self, select=1, input_any=None):
        if select == 1:
            return (input_any, None)
        return (None, input_any)
