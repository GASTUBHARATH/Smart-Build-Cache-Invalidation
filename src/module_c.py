"""Sample module that depends on module B."""

from module_b import module_b_value


def module_c_value() -> str:
    return module_b_value() + " -> C"