import builtins
import inspect
import os

def parseType(name):
	if hasattr(builtins, name):
		return getattr(builtins, name)

	# Need to look up the type in the caller's scope
	# Scan for the first frame not part of this file (not sure if there's a saner way to do this)
	here = os.path.abspath(__file__)
	for frame, filename, _, _, _, _ in inspect.stack():
		if os.path.abspath(filename) != here:
			if name in frame.f_globals:
				return frame.f_globals[name]
			break
	raise ValueError("Unrecognized type: %s" % name)

def describeTypeOf(obj):
	if obj is None:
		return 'None'
	if isinstance(obj, list):
		return "list of %s" % '/'.join(sorted(set(describeTypeOf(e) for e in obj))) if obj else "list"
	if isinstance(obj, dict):
		return "map from %s to %s" % ('/'.join(sorted(set(describeTypeOf(k) for k in obj))), '/'.join(sorted(set(describeTypeOf(v) for v in obj.values())))) if obj else "map"
	if isinstance(obj, set):
		return "set of %s" % '/'.join(sorted(set(describeTypeOf(e) for e in obj))) if obj else "set"
	return type(obj).__name__

def describeTypestring(typestring):
	typestring = typestring.strip()
	if typestring == '':
		# This isn't illegal at the top level, but verify() wouldn't have called in that case
		# If it happens here it means it's a fragment of a larger expression and can't be empty
		raise ValueError("Empty substring in type string")

	if typestring[-1] == '?':
		return "(optional) %s" % describeTypestring(typestring[:-1])
	if typestring[-1] == '^':
		return "(implicit) %s" % describeTypestring(typestring[:-1])
	ends, rest = typestring[0] + typestring[-1], typestring[1:-1]
	if ends == '()':
		return "any of %s" % ', '.join(map(describeTypestring, rest.split(',')))
	if ends == '[]':
		return "list of %s" % describeTypestring(rest)
	if ends == '{}':
		if ':' in rest:
			return "map from %s to %s" % tuple(map(describeTypestring, rest.split(':', 1)))
		else:
			return "set of %s" % describeTypestring(rest)

	try:
		return parseType(typestring).__name__
	except ValueError as e:
		raise ValueError("Invalid typestring `%s': %s" % (typestring, e))

def verify(typestring):
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
	describeTypestring(typestring) # Will throw ValueError if bad
	return True

def typecheck(typestring, value, setter = None):
	"""
	Check that 'value' satisfies 'typestring'.
	If 'setter' is non-None, it may be called to replace the function parameter with a converted instance
	"""

	if typestring == inspect.Parameter.empty:
		return True
	typestring = typestring.strip()
	if typestring == '':
		return True

	# Optional type, e.g. 'int?'
	if typestring[-1] == '?':
		return (value is None) or typecheck(typestring[:-1], value, setter)

	# Convertable type, e.g. 'int^'
	if typestring[-1] == '^':
		substr = typestring[:-1]
		try:
			ty = parseType(substr)
		except ValueError as e:
			raise ValueError("Can't implicitly convert to unrecognized type: %s" % substr)

		# Already the proper type; no conversion necessary
		if isinstance(value, ty):
			return True

		# Attempt the conversion
		try:
			spec = inspect.getfullargspec(getattr(ty, '__init__'))
			if len(spec.args) != 2: # self + the one parameter
				raise TypeError("constructor is not unary")
			argName = spec.args[1]
			if argName not in spec.annotations:
				raise TypeError("constructor parameter has no type annotation")
			if not typecheck(spec.annotations[argName], value):
				raise TypeError("got type [%s]; constructor takes [%s]" % (describeTypeOf(value), describeTypestring(spec.annotations[argName])))
			setter(ty(value))
			return True
		except Exception as e:
			raise TypeError("Unable to implicitly convert to %s: %s" % (ty.__name__, e))

	ends, rest = typestring[0] + typestring[-1], typestring[1:-1]

	# Union type, e.g. '(int, str)'
	if ends == '()':
		return any(typecheck(substr, value, setter) for substr in rest.split(','))

	# List type, e.g. '[int]'
	if ends == '[]':
		if not isinstance(value, list):
			return False
		return all(typecheck(rest, e, lambda new: value.__setitem__(i, new)) for i, e in enumerate(value))

	if ends == '{}':
		# Dict type, e.g. '{int: int}'
		if ':' in rest:
			if not isinstance(value, dict):
				return False
			keystr, valstr = map(lambda s: s.strip(), rest.split(':', 1))
			def renameKey(old, new):
				value[new] = value[old]
				del value[old]
			return all(typecheck(keystr, k, lambda new: renameKey(k, new)) and typecheck(valstr, v, lambda new: value.__setitem__(k, new)) for k, v in value.items())

		# Set type, e.g. '{int}'
		else:
			if not isinstance(value, set):
				return False
			def replaceEntry(old, new):
				value.remove(old)
				value.add(new)
			return all(typecheck(rest, e, lambda new: replaceEntry(e, new)) for e in value)

	# Bare type, e.g. 'int'
	return isinstance(value, parseType(typestring))

def tc(f):
	signature = inspect.signature(f)

	# Make sure the annotations are valid
	for param in signature.parameters.values():
		verify(param.annotation)

	def wrap(*args, **kw):
		binding = signature.bind(*args, **kw)
		for name, param in signature.parameters.items():
			typestring = param.annotation

			# Already did the checking in verify(); at this point typestring is either just the string or a tuple with the string and predicate
			predicate = None
			if isinstance(typestring, tuple):
				typestring, predicate = typestring

			if name in binding.arguments: # If not, using the default value. We could typecheck the default as well, but choosing not to
				value = binding.arguments[name]
				if not typecheck(typestring, value, lambda new: binding.arguments.__setitem__(name, new)):
					raise TypeError("Invalid argument `%s' of type [%s]; expected [%s]" % (name, describeTypeOf(binding.arguments[name]), describeTypestring(typestring)))
				if predicate is not None and not predicate(value):
					raise TypeError("Invalid argument `%s': predicate unsatisfied" % name)
		f(*binding.args, **binding.kwargs)
	return wrap
