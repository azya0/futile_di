from enum import IntEnum
from typing import Any, Generator

from .depends import Depends
from .depends_processors import process_arg_sequence
from .wrappers_data import WrapperData


def process_args_kwargs(
    args: tuple[Any], kwargs: dict[str, Any],
    processed_args: list[Any], processed_kwargs: dict[str, Any]
) -> Generator[Depends, Any]:
    
    args_generator = process_arg_sequence(
        sequence=args,
        get_arg=lambda value: value,
        callback=lambda _, result : processed_args.append(result)
    )
    for _, depends in args_generator:
        result_arg = yield depends
        processed_args.append(result_arg)
    kwargs_generator = process_arg_sequence(
        sequence=kwargs.items(),
        get_arg=lambda items: items[1],
        callback=lambda items, result : processed_kwargs.__setitem__(items[0], result)
    )
    for key, depends in kwargs_generator:
        result_kwarg = yield depends
        processed_kwargs[key] = result_kwarg


class NewFuncState(IntEnum):
        PROCESS_DATA = 0
        CLOSE_CONTEXT = 1


def main_new_function(params: tuple[tuple[Any], dict[str, Any]]) -> Generator[tuple[NewFuncState, list[Any]]]:
    function_data = WrapperData()

    depends_generator = process_args_kwargs(*params, *function_data.get_params())

    depends = next(depends_generator, None)

    if depends is not None:
        yield NewFuncState.PROCESS_DATA, [depends, depends_generator, function_data.get_context()]

    new_args, new_kwargs = function_data.get_params()

    yield NewFuncState.CLOSE_CONTEXT, [function_data, [new_args, new_kwargs]]
