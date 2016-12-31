This is a library for typechecking Python function calls at runtime. Goals include things like providing type safety and being easy to use, and don't include things like running quickly; if your code needs to be quick you should probably not be using runtime typechecking in the first place.

The expected types are specified via [function annotations](https://docs.python.org/3/tutorial/controlflow.html#function-annotations), so this requires Python 3. Functions are only checked if they are decorated with `@tc`, and only annotated parameters and return values are checked. For example:

```python
from pytypecheck import tc

@tc
def fn(can_be_anything, must_be_an_int : 'int') -> 'bool':
    return must_be_an_int > 0
```

## Type specifiers

The function annotations you use to restrict a parameter's type are called *type specifiers*. They are always strings, with the following syntax (see the [tests](/test.py) for examples):

![](/../doc-imgs/typestring.png?raw=true)

### Regular types

Anything not matching one of the following cases is assumed to be the name of an actual type, e.g. `int`. It can be anything in-scope at the point where the function is defined.

A special case is provided for `None`, which only matches `None`. This is most useful when annotating the return type of a function that returns nothing:

```python
@tc
def fn() -> 'None':
    pass
```

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

A comma-separated list of typestrings wrapped in parentheses, e.g. `(int, str, Foo)`, allows any of the specified types. For example:

```python
@tc
def fn(foo : '(int, str)'):
    pass

fn(4)

fn('foo')

fn([])
# TypeError: Invalid argument `foo' of type [list]; expected [any of int, str]
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

---

The examples above generally used `int` as a placeholder for a typestring, but any typestring is valid -- typestrings can nest as needed. For example, `[{int?: [{Foo^}]}?]` is a list that contains an optional map from optional ints to a list of sets of Foo instances that will be implicitly converted if necessary.

## Predicates

Along with the typestring, you can optionally provide a *predicate*. This is a function that takes the function argument and returns a boolean indicating its validity. Note that the predicate is only called if the typestring is satisfied. For example:

```python
@tc
def fn(a : ('int', lambda x: x == 4)): pass

fn(4)

fn('foo')
# TypeError: Invalid argument `a' of type [str]; expected [int]

fn(5)
# TypeError: Invalid argument `a': predicate unsatisfied
```

## tc options

An alternative form of `@tc` is provided when additional control is required. `@tc_opts(...)` takes several keyword-only arguments:

### Unverified typestrings

Normally typestrings are sanity checked at function definition time to make sure they are syntactically valid. Providing the option `verify = False` will disable this checking; an invalid typestring will not be detected until the function is called. This is most useful when a typestring refers to a type that isn't yet defined, but will be by the time the function is called. One common case is a method that takes an instance of the parent class as an argument (the `self` parameter or another), since the class isn't yet in scope when the method is defined:

```python
class Foo:
    @tc
    def mth(self : 'Foo'):
        pass
# ValueError: Invalid typestring `Foo': Unrecognized type: Foo

class Foo:
    @tc_opts(verify = False)
    def mth(self : 'Foo'):
        pass
```

### Overloading

Functions can be overloaded based on their arity and declared parameter types. pytypecheck will call the first overload it finds whose interface matches the provided arguments. Overloading is facilitated by passing a function as the `overload` option; this function will be attempted next if the annotated function fails to match (and if that function was defined with an `overload` option, the process continues). Most commonly the functions will have the same name, so each new function overwrites the previous one while maintaining a chain via `overload` options:

```python
@tc
def fn(x : 'int'):
    return "int: %d" % x

@tc_opts(overload = fn)
def fn(x : 'str'):
    return "str: %s" % x

@tc_opts(overload = fn)
def fn(x : 'bool', y : 'bool'):
    return "bools: %s, %s" % (x, y)

fn(4)
# int: 4

fn('test')
# str: test

fn(True, False)
# bools: True, False

fn([4])
# TypeError: Invalid argument `x' of type [list of int]; expected [bool]
#
# During handling of the above exception, another exception occurred:
#
# TypeError: Invalid argument `x' of type [list of int]; expected [str]
#
# During handling of the above exception, another exception occurred:
#
# TypeError: Invalid argument `x' of type [list of int]; expected [int]
```

Note that it is not hard to construct ambiguous overloads, particularly if the parameters have no typestring. Due to the way the resolution chain is constructed, functions are checked in reverse-definition order, so the latest function matching the arguments will be invoked. In the following example, passing any `int` will invoke the third function, while any other argument will invoke the second function; the first function will never be called:

```python
@tc
def fn(x):
    return "first"

@tc_opts(overload = fn)
def fn(x):
    return "second"

@tc_opts(overload = fn)
def fn(x : 'int'):
    return "third"

fn(None)
# second

fn(4)
# third
```

This behavior should be considered **undefined**; at some point in the future it is likely this will be checked for and considered an error condition.
