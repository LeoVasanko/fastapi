from __future__ import annotations

import types
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar, Union

from pydantic import BaseModel
from pydantic.main import IncEx as IncEx

if TYPE_CHECKING:  # pragma: nocover
    import msgspec

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])
UnionType = getattr(types, "UnionType", Union)
ModelNameMap = dict[type[BaseModel] | type[Enum] | type["msgspec.Struct"], str]
DependencyCacheKey = tuple[Callable[..., Any] | None, tuple[str, ...], str]
