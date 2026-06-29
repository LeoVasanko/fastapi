# Using msgspec { #using-msgspec }

**FastAPI** is built on top of **Pydantic**, and the tutorial shows how to use Pydantic models to declare requests and responses.

But FastAPI also supports <a href="https://jcristharif.com/msgspec/" class="external-link" target="_blank">`msgspec`</a> `Struct` types the same way.

## Install `msgspec` { #install-msgspec }

Make sure you [create a virtual environment](../virtual-environments.md){.internal-link target="_blank"}, activate it, and then install FastAPI with the `msgspec` extra:

//// tab | `pip`

<div class="termy">

```console
$ pip install "fastapi[standard,msgspec]"
---> 100%
```

</div>

////

//// tab | `uv`

If you have [`uv`](https://github.com/astral-sh/uv):

<div class="termy">

```console
$ uv add "fastapi[standard,msgspec]"
---> 100%
```

</div>

////

## Return a `msgspec` struct { #return-a-msgspec-struct }

Import `msgspec` and declare your data model as a `msgspec.Struct`.

Then return it from a path operation:

{* ../../docs_src/msgspec/tutorial001_py310.py hl[1,4,7:12,18:19] *}

FastAPI detects that the returned value is a `msgspec.Struct` and serializes it directly with `msgspec.json.encode`, bypassing the normal JSON encoder.

## Parse a `msgspec` request body { #parse-a-msgspec-request-body }

Use a `msgspec.Struct` as a request body parameter the same way you would use a Pydantic model:

{* ../../docs_src/msgspec/tutorial002_py310.py hl[1:2,5,8:13,17:19] *}

FastAPI decodes the request body directly into the struct with `msgspec.json.decode`, bypassing Pydantic validation. Here the endpoint returns the parsed struct's `repr` as plain text, completely outside the msgspec response path.

## Use `MsgspecJSONResponse` { #use-msgspecjsonresponse }

If you want to use `msgspec` directly for response serialization, return a `MsgspecJSONResponse`:

{* ../../docs_src/msgspec/tutorial003_py310.py hl[2,5,16:20] *}

/// info

`MsgspecJSONResponse` is only available in FastAPI, not in Starlette.

///

## Nested `msgspec` structs { #nested-msgspec-structs }

You can combine `msgspec.Struct` types with standard type annotations to build nested data structures.

{* ../../docs_src/msgspec/tutorial004_py310.py hl[1,4,7:23,25:26] *}

In this example, `Library` contains a list of `Book` structs, and each `Book` contains an `Author` struct. FastAPI generates the OpenAPI schema for all of them automatically.

## Field aliases { #field-aliases }

`msgspec` supports field aliases via `msgspec.field(name="...")`. FastAPI uses the alias for request parsing, response serialization, and OpenAPI documentation.

{* ../../docs_src/msgspec/tutorial005_py310.py hl[5:7,13:15] *}

In this example, clients send and receive `itemName`, while the Python attribute is `item_name`.

## Coexist with Pydantic { #coexist-with-pydantic }

`msgspec` support does not replace Pydantic. You can mix `msgspec.Struct` models and Pydantic `BaseModel` models in the same application.

For example, one *path operation* can use a Pydantic model while another uses a `msgspec` struct.

## Learn more { #learn-more }

To learn more about `msgspec`, check the <a href="https://jcristharif.com/msgspec/" class="external-link" target="_blank">msgspec documentation</a>.
