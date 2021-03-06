import builtins
import functools
import inspect
import os
import typing

def parseType(name, typeTable):
	if hasattr(builtins, name):
		return getattr(builtins, name)
	if name in typeTable:
		return typeTable[name]
	if '.' in name:
		seek = typeTable
		for part in name.split('.'):
			try:
				if not part in seek:
					break
				seek = seek[part]
			except TypeError:
				if not hasattr(seek, part):
					break
				seek = getattr(seek, part)
		else:
			return seek
	raise ValueError("Unrecognized type: %s" % name)

def describeTypeOf(obj):
	if obj is None:
		return 'None'
	if isinstance(obj, tuple):
		return "tuple of %s" % '/'.join(sorted(set(describeTypeOf(e) for e in obj))) if obj else "tuple"
	if isinstance(obj, list):
		return "list of %s" % '/'.join(sorted(set(describeTypeOf(e) for e in obj))) if obj else "list"
	if isinstance(obj, dict):
		return "map from %s to %s" % ('/'.join(sorted(set(describeTypeOf(k) for k in obj))), '/'.join(sorted(set(describeTypeOf(v) for v in obj.values())))) if obj else "map"
	if isinstance(obj, set):
		return "set of %s" % '/'.join(sorted(set(describeTypeOf(e) for e in obj))) if obj else "set"
	return type(obj).__name__

def describeTypestring(typestring, typeTable):
	typestring = typestring.strip()
	if typestring == '':
		# This isn't illegal at the top level, but verify() wouldn't have called in that case
		# If it happens here it means it's a fragment of a larger expression and can't be empty
		raise ValueError("Empty substring in type string")

	if typestring == 'None':
		return "None"
	if typestring[-1] == '?':
		return "(optional) %s" % describeTypestring(typestring[:-1], typeTable)
	if typestring[-1] == '^':
		return "(implicit) %s" % describeTypestring(typestring[:-1], typeTable)
	ends, rest = typestring[0] + typestring[-1], typestring[1:-1]
	if ends == '()':
		subtypes = rest.split(',')
		if len(subtypes) == 1:
			return "tuple of %s" % describeTypestring(rest, typeTable)
		elif len(subtypes) == 2:
			return "%s or %s" % tuple(describeTypestring(e, typeTable) for e in subtypes)
		else:
			return "%sor %s" % (''.join("%s, " % describeTypestring(e, typeTable) for e in subtypes[:-1]), describeTypestring(subtypes[-1], typeTable))
	if ends == '[]':
		return "list of %s" % describeTypestring(rest, typeTable)
	if ends == '{}':
		if ':' in rest:
			return "map from %s to %s" % tuple(describeTypestring(e, typeTable) for e in rest.split(':', 1))
		else:
			return "set of %s" % describeTypestring(rest, typeTable)

	try:
		return parseType(typestring, typeTable).__name__
	except ValueError as e:
		raise ValueError("Invalid typestring `%s': %s" % (typestring, e))

def verify(typestring, typeTable):
	"""
	Check that 'typestring' is a valid typestring. Throws ValueError if not
	"""
	if typestring == inspect.Parameter.empty:
		return True

	if isinstance(typestring, str):
		pass
	elif isinstance(typestring, tuple) and len(typestring) == 2 and isinstance(typestring[0], str) and callable(typestring[1]):
		typestring = typestring[0]
	else:
		raise ValueError("Invalid typestring `%s': not a string or string/predicate")

	if typestring.strip() == '':
		return True
	describeTypestring(typestring, typeTable) # Will throw ValueError if bad
	return True

def typecheck(typestring, value, typeTable, setter = None):
	"""
	Check that 'value' satisfies 'typestring'.
	If 'setter' is non-None, it may be called to replace the function parameter with a converted instance
	"""

	if typestring == inspect.Parameter.empty:
		return True
	typestring = typestring.strip()
	if typestring == '':
		return True

	# None type
	if typestring == 'None':
		return value is None

	# Optional type, e.g. 'int?'
	if typestring[-1] == '?':
		return (value is None) or typecheck(typestring[:-1], value, typeTable, setter)

	# Convertable type, e.g. 'int^'
	if typestring[-1] == '^':
		substr = typestring[:-1]
		try:
			ty = parseType(substr, typeTable)
		except ValueError as e:
			raise ValueError("Can't implicitly convert to unrecognized type: %s" % substr)

		# Already the proper type; no conversion necessary
		if isinstance(value, ty):
			return True

		# Attempt the conversion
		try:
			ctor = getattr(ty, '__init__')
			# If the constructor is wrapped in a typechecker, get the real constructor
			while hasattr(ctor, 'tcWrappedFn'):
				ctor = ctor.tcWrappedFn
			spec = inspect.getfullargspec(ctor)
			if len(spec.args) != 2: # self + the one parameter
				raise TypeError("constructor is not unary")
			argName = spec.args[1]
			if argName not in spec.annotations:
				raise TypeError("constructor parameter has no type annotation")
			if not typecheck(spec.annotations[argName], value, typeTable):
				raise TypeError("got type [%s]; constructor takes [%s]" % (describeTypeOf(value), describeTypestring(spec.annotations[argName], typeTable)))
			setter(ty(value))
			return True
		except Exception as e:
			raise TypeError("Unable to implicitly convert to %s: %s" % (ty.__name__, e))

	ends, rest = typestring[0] + typestring[-1], typestring[1:-1]

	if ends == '()':
		# Union type, e.g. '(int, str)'
		if ',' in rest:
			return any(typecheck(substr, value, typeTable, setter) for substr in rest.split(','))

		# Tuple type, e.g. '(int)'
		else:
			if not isinstance(value, tuple):
				return False
			return all(typecheck(rest, e, typeTable) for e in value)

	# List type, e.g. '[int]'
	if ends == '[]':
		if not isinstance(value, list):
			return False
		return all(typecheck(rest, e, typeTable, lambda new: value.__setitem__(i, new)) for i, e in enumerate(value))

	if ends == '{}':
		# Dict type, e.g. '{int: int}'
		if ':' in rest:
			if not isinstance(value, dict):
				return False
			keystr, valstr = map(lambda s: s.strip(), rest.split(':', 1))
			def renameKey(old, new):
				value[new] = value[old]
				del value[old]
			return all(typecheck(keystr, k, typeTable, lambda new: renameKey(k, new)) and typecheck(valstr, v, typeTable, lambda new: value.__setitem__(k, new)) for k, v in value.items())

		# Set type, e.g. '{int}'
		else:
			if not isinstance(value, set):
				return False
			def replaceEntry(old, new):
				value.remove(old)
				value.add(new)
			return all(typecheck(rest, e, typeTable, lambda new: replaceEntry(e, new)) for e in value)

	# Bare type, e.g. 'int'
	return isinstance(value, parseType(typestring, typeTable))

@typing.no_type_check_decorator
def tc(f, preVerifyAnnotations = True, nextOverload = None):
	signature = inspect.signature(f)

	# Need to look up types in the scope that 'f' was declared in
	# Scan for the first frame that's within the function's
	fFile = inspect.getsourcefile(f)
	lines, fStartLine = inspect.getsourcelines(f)
	fEndLine = fStartLine + len(lines) - 1
	for frame, filename, lineno, _, _, _ in inspect.stack():
		if filename == fFile and fStartLine <= lineno <= fEndLine:
			typeTable = frame.f_globals
			break
	else:
		raise RuntimeError("Unable to find scope containing the declaration of %s" % f)

	# Make sure the annotations are valid
	if preVerifyAnnotations:
		for param in signature.parameters.values():
			verify(param.annotation, typeTable)
		verify(signature.return_annotation, typeTable)

	@functools.wraps(f)
	def wrap(*args, **kw):
		try:
			binding = signature.bind_partial(*args, **kw)
			for name, param in signature.parameters.items():
				typestring = param.annotation

				# Already did the checking in verify(); at this point typestring is either just the string or a tuple with the string and predicate
				predicate = None
				if isinstance(typestring, tuple):
					typestring, predicate = typestring

				if name in binding.arguments: # If not, using the default value. We could typecheck the default as well, but choosing not to
					value = binding.arguments[name]
					if not typecheck(typestring, value, typeTable, lambda new: binding.arguments.__setitem__(name, new)):
						raise TypeError("Invalid argument `%s' of type [%s]; expected [%s]" % (name, describeTypeOf(binding.arguments[name]), describeTypestring(typestring, typeTable)))
					if predicate is not None:
						result = predicate(value)
						if result is not True:
							result = ("predicate unsatisfied: %s" % result) if result else 'predicate unsatisfied'
							raise TypeError("Invalid argument `%s': %s" % (name, result))

			rtn = {'rtn': f(*binding.args, **binding.kwargs)}

			typestring, predicate = signature.return_annotation, None
			if isinstance(typestring, tuple):
				typestring, predicate = typestring
			if not typecheck(typestring, rtn['rtn'], typeTable, lambda new: rtn.__setitem__('rtn', new)):
				raise TypeError("Invalid return value of type [%s]; expected [%s]" % (describeTypeOf(rtn['rtn']), describeTypestring(typestring, typeTable)))
			if predicate is not None and not predicate(rtn['rtn']):
				raise TypeError("Invalid return value: predicate unsatisfied")
		except TypeError:
			# If there are overloads, move on to those
			if nextOverload is not None:
				try:
					return nextOverload(*args, **kw)
				except TypeError:
					# The overload didn't match; keep the exception chain going
					raise
				except Exception as e:
					# If an overload matched (i.e. didn't raise a TypeError) but then the method threw some other exception, it shouldn't chain into previous TypeErrors raised by overload resolution failures
					raise e from None
			#TODO Right now all the overload type errors come out in a chain because of PEP3134; it'd be nice to generate a single exception that lists all the signatures, but an elegant way to do that escapes me at the moment
			raise

		return rtn['rtn']
	wrap.tcWrappedFn = f
	return wrap

# 'tc' is designed to be used as '@tc', not '@tc()', so it can't take arguments. This version takes arguments and forwards them to tc
def tc_opts(*, verify = True, overload = None):
	def wrap(f):
		return tc(f, verify, overload)
	return wrap
