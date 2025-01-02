"""Tools to parse common SHV parameters."""

from __future__ import annotations

import collections.abc
import typing

from .rpcerrors import RpcInvalidParamError
from .value import SHVType, is_shvlist

SHVT = typing.TypeVar("SHVT", bound=SHVType)
"""Generic type specifying the parametrization bount to :data:`shv.SHVType`."""


def shvt(value: SHVType, tp: type[SHVT]) -> SHVT:
    """Check type of value.

    This is just simple type check of parameter for simple types.

    :param value: The value received as parameter for SHV RPC.
    :param tp: Python type the value should be of.
    :return: The value.
    :raises RpcInvalidParamError: If doesn't match what was provided in value.
    """
    if not isinstance(value, tp):
        raise RpcInvalidParamError(f"Invalid type: {type(value)}")
    return value


class NoDefaultType:
    """Type for :data:`NO_DEFAULT` singleton."""

    def __new__(cls) -> NoDefaultType:
        """Implement as singleton."""
        if not hasattr(cls, "instance"):
            cls.instance = super(NoDefaultType, cls).__new__(cls)  # noqa UP008
        return cls.instance


NO_DEFAULT = NoDefaultType()
"""Singleton used to identify that there is no default."""


class SHVGetKey(typing.NamedTuple):
    """Key used in :func:`shvget` to allow both IMap as well as Map."""

    skey: str | None = None
    ikey: int | None = None


def shvget(
    value: SHVType,
    key: str | int | SHVGetKey | collections.abc.Sequence[str | int | SHVGetKey],
    default: SHVType | NoDefaultType = NO_DEFAULT,
) -> SHVType:
    """Get value from (i)map or (i)map of (i)maps or default.

    It is very common to query SHVType for keys and support both IMap as well as
    Map at the same time. This can be any number of nested Maps or IMaps. This
    simplifies access for such types.

    :param value: Some Map or IMap to be accessed
    :param key: Key or list of keys that should be recursively applied to the
      value.
    :param default: Default value used if value is not present.
      :class:`shv.RpcInvalidParamError` is raised instead if :data:`NO_DEFAULT`
      is specified.
    :return: extracted value or default.
    :raise RpcInvalidParamError: if the value is not present and no default was
      provided.
    """
    for k in [key] if isinstance(key, str | int | SHVGetKey) else key:
        if not isinstance(value, collections.abc.Mapping):
            break
        vmap = typing.cast(collections.abc.Mapping[str | int, SHVType], value)
        if isinstance(k, SHVGetKey) and k.ikey is not None and k.ikey in vmap:
            value = vmap[k.ikey]
        elif isinstance(k, SHVGetKey) and k.skey is not None and k.skey in vmap:
            value = vmap[k.skey]
        elif isinstance(k, str | int) and k in vmap:
            value = vmap[k]
        else:
            if isinstance(default, NoDefaultType):
                raise RpcInvalidParamError(f"Missing key: {k}")
            value = default
            break
    if value is None and not isinstance(default, NoDefaultType):
        return default  # None is alias for not present for us
    return value


def shvgett(
    value: SHVType,
    key: str | int | SHVGetKey | collections.abc.Sequence[str | int | SHVGetKey],
    tp: type[SHVT],
    default: SHVT | NoDefaultType = NO_DEFAULT,
) -> SHVT:
    """Variant of :func:`shvget` that also checks for type.

    It is very common to query SHVType for keys and expecting a specific type or
    using default value if it is present or is of invalid type. It is a fails
    safe approach.

    :param value: Some Map or IMap to be accessed
    :param key: Key or list of keys that should be recursively applied to the
      value.
    :param tp: Type of the expected value.
    :param default: Default value used if value is not present.
      :class:`shv.RpcInvalidParamError` is raised instead if :data:`NO_DEFAULT`
      is specified.
    :return: extracted value or default.
    :raise RpcInvalidParamError: if the value is not present and no default
      provided.
    """
    return shvt(shvget(value, key, default), tp)


def shvarg(
    value: SHVType,
    index: int,
    default: SHVType | NoDefaultType = NO_DEFAULT,
) -> SHVType:
    """Get value from list or default.

    Some methods expect sequence of values (tuples) as their parameters. This
    helps with parsing such value.

    There is special exception that if the argument is not list then it is
    considered to be the first argument in the list.

    :param value: Some List to be sanitized.
    :param index: The index in list we want to access.
    :param default: Default value used if value is not present.
      :class:`shv.RpcInvalidParamError` is raised instead if :data:`NO_DEFAULT`
      is specified.
    :return: extracted value or default.
    :raise RpcInvalidParamError: if the value is not present and no default
      provided.
    """
    if is_shvlist(value):
        if len(value) > index and (res := value[index]) is not None:
            return res
    elif index == 0 and value is not None:
        return value  # Covers that first argument is sent outside list
    if isinstance(default, NoDefaultType):
        raise RpcInvalidParamError(f"Field {index} not provided")
    return default


def shvargt(
    value: SHVType,
    index: int,
    tp: type[SHVT],
    default: SHVT | NoDefaultType = NO_DEFAULT,
) -> SHVT:
    """Variant of :func:`shvarg` that also checks for type.

    :param value: Some List to be sanitized.
    :param index: The index in list we want to access.
    :param tp: Type of the expected value.
    :param default: Default value used if value is not present.
      :class:`shv.RpcInvalidParamError` is raised instead if :data:`NO_DEFAULT`
      is specified.
    :return: extracted value or default.
    :raise RpcInvalidParamError: if the value is not present and no default
      provided.
    """
    return shvt(shvarg(value, index, default), tp)
