from new_util import helper


def orchestrate(xs: list[int]) -> list[int]:
    return [helper(x) for x in xs]
