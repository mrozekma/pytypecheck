#!/usr/bin/env python3
from pytypecheck import tc, tc_opts
from unittest import TestCase, main, skip

class NoConstructor:
	pass

class NullaryConstructor:
	def __init__(self):
		pass

class UnannotatedConstructor:
	def __init__(self, x):
		self.x = x

class IntConstructor:
	@tc
	def __init__(self, x : 'int'):
		self.x = x

class UserConstructor:
	def __init__(self, x : 'NoConstructor'):
		self.x = x

class BinaryConstructor:
	def __init__(self, x : 'int', y : 'int'):
		self.x = x
		self.y = y

class Test(TestCase):
	def __init__(self, *args, **kw):
		super().__init__(*args, **kw)
		self.throws = self.assertRaisesRegex

	def try_arg(self, typestring, arg, err = None):
		@tc
		def fn(a : typestring): pass
		if err is None:
			fn(arg)
		else:
			with self.throws(TypeError, '' if err is True else err) as cm:
				fn(arg)

	def bad_typestring(self, typestring):
		with self.throws(ValueError, 'Invalid typestring') as cm:
			@tc
			def fn(a : typestring): pass

	def test_no_types(self):
		@tc
		def fn(): pass
		fn()

	def test_bad_typestring(self):
		self.bad_typestring('asdf')

	def test_none(self):
		self.try_arg('None', None)
		self.try_arg('None', True, 'Invalid argument')

	def test_int(self):
		self.try_arg('int', 4)
		self.try_arg('int', 'foo', 'Invalid argument')
		self.try_arg('int', None, 'Invalid argument')

	def test_opt(self):
		self.try_arg('int?', 4)
		self.try_arg('int?', 'foo', 'Invalid argument')
		self.try_arg('int?', None)

	def test_union(self):
		self.try_arg('(bool, str)', True)
		self.try_arg('(bool, str)', 'foo')
		self.try_arg('(bool, str, int, NoConstructor, NullaryConstructor)', NoConstructor())
		self.try_arg('(bool, str)', 4, 'Invalid argument')
		self.bad_typestring('(int, x)')
		# Bit of a weird case in the grammar, now that I think about it, but oh well:
		self.try_arg('(bool?, str)', None)
		self.try_arg('(bool, str)?', None)

	def test_list(self):
		self.try_arg('[int]', [])
		self.try_arg('[int]', [4])
		self.try_arg('[int]', [None], 'Invalid argument')
		self.try_arg('[int]', [4, None], 'Invalid argument')
		self.try_arg('[int]', None, 'Invalid argument')
		self.try_arg('[int?]', [4])
		self.try_arg('[int?]', [None])
		self.try_arg('[int?]', [4, None])
		self.try_arg('[int?]', [None])
		self.try_arg('[int]?', [4])
		self.try_arg('[int]?', [4, None], 'Invalid argument')
		self.try_arg('[int]?', None)
		self.try_arg('[int?]?', [4, None])
		self.try_arg('[int?]?', None)
		self.bad_typestring('[x]')
		self.bad_typestring('[int, int]')

	def test_dict(self):
		self.try_arg('{int: int}', {})
		self.try_arg('{int: int}', {4: 4})
		self.try_arg('{int: int}', {4: 4, 'foo': 5}, 'Invalid argument')
		self.try_arg('{int: int}', {4: 4, 5: 'foo'}, 'Invalid argument')
		self.try_arg('{(int, str): (int, str)}', {4: 4, 'foo': 'foo'})
		self.try_arg('{(int, str): (int, str)}', {4: 4, 'foo': 'foo', 'bar': None}, 'Invalid argument')
		self.try_arg('{int: int}', {None: 4}, 'Invalid argument')
		self.try_arg('{int: int}', {4: None}, 'Invalid argument')
		self.try_arg('{int?: int}', {None: 4})
		self.try_arg('{int: int?}', {4: None})
		self.try_arg('{int?: int?}', {})
		self.try_arg('{int?: int?}', {4: 4, None: None})
		self.try_arg('{int?: int?}', None, 'Invalid argument')
		self.try_arg('{int: int}?', None)
		self.try_arg('{int: int}?', {4: 4})
		self.try_arg('{int: int}?', {None: 4}, 'Invalid argument')
		self.try_arg('{int: int}?', {4: None}, 'Invalid argument')
		self.try_arg('{int?: int?}?', {None: None})
		self.try_arg('{int?: int?}?', None)
		self.bad_typestring('{x: int}')
		self.bad_typestring('{int: x}')

	def test_set(self):
		self.try_arg('{int}', set())
		self.try_arg('{int}', {4})
		self.try_arg('{int}', {None}, 'Invalid argument')
		self.try_arg('{int}', {4, None}, 'Invalid argument')
		self.try_arg('{int}', None, 'Invalid argument')
		self.try_arg('{int?}', {4})
		self.try_arg('{int?}', {None})
		self.try_arg('{int?}', {4, None})
		self.try_arg('{int?}', {None})
		self.try_arg('{int}?', {4})
		self.try_arg('{int}?', {4, None}, 'Invalid argument')
		self.try_arg('{int}?', None)
		self.try_arg('{int?}?', {4, None})
		self.try_arg('{int?}?', None)
		self.bad_typestring('{x}')
		self.bad_typestring('{int, int}')

	def test_conv(self):
		self.try_arg('int^', 4)
		self.try_arg('UnannotatedConstructor^', 4, 'Unable to implicitly convert.*constructor parameter has no type annotation')
		self.try_arg('IntConstructor^', 4)
		self.try_arg('IntConstructor^', 'foo', 'Unable to implicitly convert')
		self.try_arg('UserConstructor^', 4, 'Unable to implicitly convert')
		self.try_arg('UserConstructor^', NoConstructor())
		self.try_arg('BinaryConstructor^', 4, 'Unable to implicitly convert.*constructor is not unary')

	def test_partial(self):
		@tc
		def fn(x, y : 'int', z): pass
		fn('x', 4, 'z')
		with self.throws(TypeError, 'Invalid argument'):
			fn('x', 'y', 'z')

	@skip('Broken') # Can't have a set that contains a dict because a ':' anywhere in the typestring makes the parser think it's a dict
	def test_complicated(self):
		self.try_arg('[{{int?: [IntConstructor^]}}?]', None) # None isn't actually a valid value, but the typestring doesn't parse anyway

	def test_slightly_less_complicated(self):
		ts = '[{int?: [{IntConstructor^}]}?]'

		self.try_arg(ts, [None])
		self.try_arg(ts, [{}])
		self.try_arg(ts, [{None: []}])
		self.try_arg(ts, [{4: []}])
		self.try_arg(ts, [{4: [{4}]}])
		self.try_arg(ts, [{4: [{IntConstructor(4)}]}])

		self.try_arg(ts, None, 'Invalid argument')
		self.try_arg(ts, [{'foo': []}], 'Invalid argument')

	def test_predicate(self):
		ts = '[int]', lambda l: all(4 <= x <= 6 for x in l)

		self.try_arg(ts, [])
		self.try_arg(ts, [4, 5, 6])
		self.try_arg(ts, [4, 5, 6, 7], 'Invalid argument.*predicate unsatisfied')

	def test_return(self):
		@tc
		def fn(x : 'int'):
			return x
		self.assertEqual(4, fn(4))

	def test_bad_return_typestring(self):
		with self.throws(ValueError, 'Invalid typestring') as cm:
			@tc
			def fn() -> 'asdf':
				pass

	def test_wrong_return_typestring(self):
		with self.throws(TypeError, 'Invalid return value') as cm:
			@tc
			def fn() -> 'int':
				return None
			fn()

	def test_valid_return_typestrings(self):
		@tc
		def fn() -> 'int?':
			return None
		fn()

		@tc
		def fn() -> 'int':
			return 4
		fn()

		@tc
		def fn() -> 'None':
			pass

	def test_no_verify(self):
		@tc_opts(verify = False)
		def fn(x : 'asdf'):
			pass

	def test_overloading(self):
		@tc
		def fn(x : 'int'):
			return 1

		@tc_opts(overload = fn)
		def fn(x : 'str'):
			return 2

		@tc_opts(overload = fn)
		def fn(x, y):
			return 3

		self.assertEqual(fn(4), 1)
		self.assertEqual(fn('test'), 2)
		self.assertEqual(fn(None, None), 3)
		with self.throws(TypeError, None):
			fn(None)

	@skip('Unimplemented')
	def test_ambiguous_overloading(self):
		@tc
		def fn(x : 'int?'):
			pass

		@tc_opts(overload = fn)
		def fn(x : 'str?'):
			pass

		with self.throws(TypeError, None):
			fn(None)

if __name__ == '__main__':
	main()
