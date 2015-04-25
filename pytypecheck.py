import builtins
import inspect
import os

def tc(f):
	# Make sure the annotations are valid
	getCheckers(f)

	def wrap(*args, **kw):
		doCheck(f, args, kw)
		return f(*args, **kw)
	return wrap

def typedescr(s):
	if hasattr(s, 'typedescr'):
		return s.typedescr
	elif isinstance(s, type):
		return s.__name__
	else:
		return str(s)

def getChecker(typestring):
	if typestring == inspect.Parameter.empty:
		return lambda _: True

	typestring = typestring.strip()
	if typestring == '':
		return getChecker(inspect.Parameter.empty)

	# Optional type, e.g. 'int?'
	if typestring[-1] == '?':
		subchecker = getChecker(typestring[:-1])
		rtn = lambda inst: inst is None or subchecker(inst)
		rtn.typedescr = "optional %s" % typedescr(rtn)
		return rtn

	# Union type, e.g. '(int, str)'
	if typestring[0] == '(' and typestring[-1] == ')':
		substrs = typestring[1:-1].split(',')
		subchecks = map(getChecker, typestring[1:-1].split(','))
		rtn = lambda inst: any(getChecker(substr)(inst) for substr in substrs)
		rtn.typedescr = "any of %s" % ', '.join(typedescr(substr) for substr in substrs)
		return rtn

	# List type, e.g. '[int]'
	if typestring[0] == '[' and typestring[-1] == ']':
		subchecker = getChecker(typestring[1:-1])
		rtn = lambda inst: isinstance(inst, list) and all(subchecker(e) for e in inst)
		rtn.typedescr = "list of %s" % typedescr(subchecker)
		return rtn

	# Either set or dict
	if typestring[0] == '{' and typestring[-1] == '}':
		# Dict type, e.g. '{int: int}'
		if ':' in typestring:
			keychecker, valchecker = map(getChecker, typestring[1:-1].split(':', 1))
			rtn = lambda inst: isinstance(inst, dict) and all(keychecker(k) and valchecker(v) for k, v in inst.items())
			rtn.typedescr = "map from %s to %s" % (typedescr(keychecker), typedescr(valchecker))
			return rtn

		# Set type, e.g. '{int}'
		else:
			subchecker = getChecker(typestring[1:-1])
			rtn = lambda inst: isinstance(inst, set) and all(subchecker(e) for e in inst)
			rtn.typedescr = "set of %s" % typedescr(subchecker)
			return rtn

	# Bare type, e.g. 'int'
	ty = None
	if hasattr(builtins, typestring):
		ty = getattr(builtins, typestring)
	else:
		# Need to look up the type in the caller's scope
		# Scan for the first frame not part of this file (not sure if there's a saner way to do this)
		here = os.path.abspath(__file__)
		for frame, filename, _, _, _, _ in inspect.stack():
			if os.path.abspath(filename) != here:
				if typestring in frame.f_globals:
					ty = frame.f_globals[typestring]
				break
	if ty is None:
		raise RuntimeError("Malformed typestring: %s" % typestring)
	rtn = lambda inst: type(inst) == ty
	rtn.typedescr = typestring
	return rtn

def getCheckers(f):
	signature = inspect.signature(f)
	return {name: getChecker(param.annotation) for name, param in signature.parameters.items()}

def doCheck(f, args, kw):
	checkers = getCheckers(f)
	print(checkers)

	signature = inspect.signature(f)
	binding = signature.bind(*args, **kw)
	for name, param in signature.parameters.items():
		if name in binding.arguments: # If not, using the default value. We could typecheck the default as well, but choosing not to
			if not checkers[name](binding.arguments[name]):
				raise TypeError("Invalid argument `%s' of type %s; expected %s" % (name, typedescr(type(binding.arguments[name])), typedescr(checkers[name])))
