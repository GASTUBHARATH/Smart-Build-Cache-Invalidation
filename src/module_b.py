"""Sample module that depends on module A."""

from module_a import module_a_value


def module_b_value() -> str:
    return module_a_value() + " -> B"