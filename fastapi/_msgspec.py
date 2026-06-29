from __future__ import annotations

import email.message
from copy import copy
from typing import TYPE_CHECKING, Any, Literal, cast, get_args, get_origin

from fastapi.datastructures import DefaultPlaceholder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_TEMPLATE
from pydantic.fields import FieldInfo
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:  # pragma: nocover
    from fastapi._compat import ModelField

try:
    import msgspec
except ImportError:  # pragma: nocover
    msgspec = None  # type: ignore[assignment]

__all__ = [
    "MsgspecJSONResponse",
    "create_struct_model_field",
    "decode_json_body",
    "encode_struct",
    "generate_msgspec_definitions",
    "get_struct_annotation",
    "is_struct_annotation",
    "is_struct_body_field",
    "is_struct_type",
    "maybe_raise_msgspec_request_validation_error",
    "msgspec",
    "normalize_schema",
    "replace_schema_refs",
    "serialize_struct_response",
    "should_dump_json",
]


def _lenient_issubclass(cls: Any, class_or_tuple: Any) -> bool:
    try:
        return isinstance(cls, type) and issubclass(cls, class_or_tuple)
    except TypeError:  # pragma: no cover
        return False


def is_struct_type(type_: Any) -> bool:
    return msgspec is not None and _lenient_issubclass(type_, msgspec.Struct)


def is_struct_annotation(annotation: Any) -> bool:
    if is_struct_type(annotation):
        return True
    origin = get_origin(annotation)
    if origin is not None:
        return any(is_struct_annotation(arg) for arg in get_args(annotation))
    return False


def get_struct_annotation(field: ModelField) -> Any:
    """Return the msgspec annotation for a field, if any, else None."""
    original = getattr(field, "original_annotation", None)
    if original is not None and is_struct_annotation(original):
        return original
    if is_struct_annotation(field.field_info.annotation):
        return field.field_info.annotation
    return None


def replace_schema_refs(schema: Any) -> Any:
    """Replace msgspec's #/$defs/... refs with FastAPI's #/components/schemas/... format."""
    if isinstance(schema, dict):
        new_schema: dict[str, Any] = {}
        for key, value in schema.items():
            if (
                key == "$ref"
                and isinstance(value, str)
                and value.startswith("#/$defs/")
            ):
                ref_name = value[len("#/$defs/") :]
                new_schema[key] = REF_TEMPLATE.format(model=ref_name)
            elif key == "mapping" and isinstance(value, dict):
                # OpenAPI discriminator mappings contain URI fragment refs.
                new_schema[key] = {
                    k: REF_TEMPLATE.format(model=v.split("/")[-1])
                    if isinstance(v, str) and v.startswith("#/$defs/")
                    else v
                    for k, v in value.items()
                }
            else:
                new_schema[key] = replace_schema_refs(value)
        return new_schema
    elif isinstance(schema, list):
        return [replace_schema_refs(item) for item in schema]
    return schema


def normalize_schema(
    schema: dict[str, Any],
    definitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Extract $defs from a msgspec schema, collect them, and rewrite refs."""
    schema = copy(schema)
    defs = schema.pop("$defs", {})
    for name, def_schema in defs.items():
        if name not in definitions:
            definitions[name] = normalize_schema(def_schema, definitions)
    return cast(dict[str, Any], replace_schema_refs(schema))


def encode_struct(content: Any, type_: Any) -> bytes:
    """Convert ``content`` to ``type_`` and serialize directly with msgspec."""
    assert msgspec is not None
    converted = msgspec.convert(content, type_)
    return msgspec.json.encode(converted)


class MsgspecJSONResponse(JSONResponse):
    """
    JSON response using the high-performance msgspec library to serialize data to JSON.

    This response class handles:
    - msgspec.Struct instances: directly serialized with msgspec.json.encode
    - Plain dicts, lists, and other types: serialized with msgspec.json.encode

    Read more about it in the
    [FastAPI docs for Custom Response - HTML, Stream, File, others](https://fastapi.tiangolo.com/advanced/custom-response/).
    """

    def render(self, content: Any) -> bytes:
        assert msgspec is not None, (
            "msgspec must be installed to use MsgspecJSONResponse"
        )
        return msgspec.json.encode(content)


def serialize_struct_response(
    *,
    field: Any,
    response_content: Any,
) -> tuple[bool, bytes]:
    """Serialize a response whose field is (or contains) a msgspec.Struct.

    Returns (True, JSON bytes) when the field is a msgspec field, otherwise
    (False, b"").
    """
    msgspec_type = getattr(field, "original_annotation", None)
    if msgspec is not None and is_struct_annotation(msgspec_type):
        # Validate/normalize the returned value through msgspec (matches Pydantic
        # response_model behavior), then serialize directly to JSON bytes.
        return True, encode_struct(response_content, msgspec_type)
    return False, b""


def is_struct_body_field(field: Any) -> bool:
    """Return True if the body field is (or contains) a msgspec.Struct."""
    if msgspec is None:
        return False
    msgspec_annotation = getattr(field, "original_annotation", None)
    return is_struct_annotation(msgspec_annotation)


def maybe_raise_msgspec_request_validation_error(
    exc: Exception,
    *,
    body: bytes | None,
    endpoint_ctx: Any,
) -> None:
    """Convert a msgspec DecodeError/ValidationError into a RequestValidationError.

    Does nothing if the exception is not a msgspec decode error.
    """
    if msgspec is None or not isinstance(exc, msgspec.DecodeError):
        return
    if isinstance(exc, msgspec.ValidationError):
        raise RequestValidationError(
            [
                {
                    "type": "msgspec_validation",
                    "loc": ("body",),
                    "msg": str(exc),
                    "input": {},
                }
            ],
            body=body,
            endpoint_ctx=endpoint_ctx,
        ) from exc
    raise RequestValidationError(
        [
            {
                "type": "json_invalid",
                "loc": ("body",),
                "msg": "JSON decode error",
                "input": {},
                "ctx": {"error": str(exc)},
            }
        ],
        body=body,
        endpoint_ctx=endpoint_ctx,
    ) from exc


def create_struct_model_field(
    *,
    name: str,
    field_info: FieldInfo,
    mode: Literal["validation", "serialization"],
    original_annotation: Any,
) -> ModelField | None:
    """Create a ModelField for a msgspec.Struct annotation, or None if it isn't one."""
    if not is_struct_annotation(original_annotation):
        return None
    # Pydantic cannot introspect msgspec.Struct (or containers of it), so use
    # annotation=Any for FastAPI's runtime handling and keep the original
    # annotation for msgspec-aware decoding/encoding and OpenAPI generation.
    from fastapi._compat import copy_field_info, v2

    field_info = copy_field_info(field_info=field_info, annotation=Any)
    field = v2.ModelField(mode=mode, name=name, field_info=field_info)
    field.original_annotation = original_annotation  # type: ignore
    return field


async def decode_json_body(
    request: Request,
    body_bytes: bytes,
    body_field: Any,
    strict_content_type: bool,
) -> Any:
    """Decode a JSON request body, using msgspec when the body field is a Struct."""
    from fastapi._compat import Undefined

    msgspec_type = getattr(body_field, "original_annotation", None)
    use_msgspec = (
        msgspec is not None
        and msgspec_type is not None
        and is_struct_annotation(msgspec_type)
    )
    content_type_value = request.headers.get("content-type")
    if not content_type_value:
        if strict_content_type:
            return Undefined
        if use_msgspec:
            return msgspec.json.decode(body_bytes, type=msgspec_type)
        return await request.json()

    message = email.message.Message()
    message["content-type"] = content_type_value
    if message.get_content_maintype() == "application":
        subtype = message.get_content_subtype()
        if subtype == "json" or subtype.endswith("+json"):
            if use_msgspec:
                return msgspec.json.decode(body_bytes, type=msgspec_type)
            return await request.json()
    return Undefined


def should_dump_json(
    *,
    response_field: Any,
    response_class: Any,
) -> bool:
    """Whether serialize_response should return raw JSON bytes."""
    if response_field is None:
        return False
    if isinstance(response_class, DefaultPlaceholder):
        return True
    return msgspec is not None and is_struct_annotation(
        getattr(response_field, "original_annotation", None)
    )


def generate_msgspec_definitions(
    fields: Any,
    field_mapping: dict[tuple[Any, Literal["validation", "serialization"]], Any],
) -> dict[str, dict[str, Any]]:
    """Generate schemas for msgspec annotations and merge them into the Pydantic output."""
    assert msgspec is not None
    msgspec_definitions: dict[str, dict[str, Any]] = {}
    for field in fields:
        msgspec_annotation = get_struct_annotation(field)
        if msgspec_annotation is None:
            continue
        schema = msgspec.json.schema(msgspec_annotation)
        normalized_schema = normalize_schema(schema, msgspec_definitions)
        for mode in ("validation", "serialization"):
            field_mapping[(field, mode)] = normalized_schema
    return msgspec_definitions
