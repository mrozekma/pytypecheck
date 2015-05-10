This is a library for typechecking Python function calls at runtime. Goals include things like providing type safety and being easy to use, and don't include things like running quickly; if your code needs to be quick you should probably not be using runtime typechecking in the first place.

The expected types are specified via [function annotations](https://docs.python.org/3/tutorial/controlflow.html#function-annotations), so this requires Python 3. Functions are only checked if they are decorated with `@tc`, and only annotated parameters are checked. For example:

```python
from pytypecheck import tc

@tc
def fn(can_be_anything, must_be_an_int : 'int'):
    pass
```

## Type specifiers

The function annotations you use to restrict a parameter's type are called *type specifiers*. They are always strings, with the following syntax (see the [tests](/test.py) for examples):

![](/../doc-imgs/typestring.png?raw=true)

### Optional types

A typestring ending in a question mark, e.g. `int?`, is *optional* -- `None` is a valid argument for this parameter.

### Convertable types

A typestring ending in a caret, e.g. `Foo^`, is *implicitly convertable*. This implements the notion of *converting constructors* from C++. If the type specified in the typestring has a unary constructor annotated with a given type, and you pass the checked function that type, pytypecheck will automatically construct the type, passing it the argument passed to the function. For example:

```python
class Foo:
    def __init__(self, x : 'int'):
        self.x = x
        print("Constructed Foo(%d)" % self.x)
    def __repr__(self):
        return "<Foo: %d>" % self.x

@tc
def fn1(foo : 'Foo'):
    print("Passed Foo: %s" % foo)

fn1(4)
# TypeError: Invalid argument `foo' of type [int]; expected [Foo]

@tc
def fn2(foo : 'Foo^'):
    print("Passed Foo: %s" % foo)

fn2(4)
# Constructed Foo(4)
# Passed Foo: <Foo: 4>

foo = Foo(5)
# Constructed Foo(5)

fn2(foo)
# Passed Foo: <Foo: 5>

fn2(5)
# Constructed Foo(5)
# Passed Foo: <Foo: 5>
```

Conversion is only done if the specified class has a unary (single-parameter, other than `self`) constructor, and that parameter is annotated with a typestring that matches the user-provided argument.

### Union types

A comma-separated list of typesrings wrapped in parentheses, e.g. `(int, str, Foo)`, allows any of the specified types. For example:

```python
@tc
def fn(foo : '(int, str)'):
    pass

fn(4)

fn('foo')

fn([])
TypeError: Invalid argument `foo' of type [list]; expected [any of int, str]
```

Note that marking any of the types optional, or the union itself optional, will allow a `None` argument. That is, these are all functionally identical:

* `(int?, str, Foo)`
* `(int, str?, Foo)`
* `(int, str, Foo?)`
* `(int, str, Foo)?`

### List types

A typestring wrapped in brackets, e.g. `[int]`, is a list of that type. The argument must actually be a list (or a subclass), not just an iterable. The type of the list members is not optional, but you can use `object` to accept a list containing anything (including `None`). Note the difference between:

* `[int?]` -- The list can contain `None` elements. `[4, None]` is valid, but `['foo', None]` and `None` are not.
* `[int]?` -- The function argument can be `None`, but `[None]` is not valid
* `[int?]?` -- The list can contain `None` elements as well as be `None` itself

### Set types

A typestring wrapped in braces, e.g. `{int}`, is a set of that type. All the provisos about list types apply to set types as well.

### Dict types

Two colon-separated typestrings wrapped in braces, e.g. `{int: int}`, are a dict mapping the first type to the second. The key and the value types are distinct, so e.g. `{int?: int}` allows `None` keys but not values.

### Types

Anything not matching one of the above is assumed to be the name of an actual type, e.g. `int`. It can be anything in-scope at the point where the function is defined.

---

The examples above generally used `int` as a placeholder for a typestring, but any typestring is valid -- typestrings can nest as needed. For example, `[{int?: [{Foo^}]}?]` is a list that contains an optional map from optional ints to a list of sets of Foo instances that will be implicitly converted if necessary.
