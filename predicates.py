class Predicate:
	def __init__(self, fn, desc, onFail = None):
		self.fn = fn
		self.desc = desc
		self.onFail = onFail

	def __call__(self, *args, **kw):
		rtn = self.fn(*args, **kw)
		if rtn is False and self.onFail:
			rtn = self.onFail(*args, **kw)
		return rtn

	def __repr__(self):
		return self.desc

def oneof(*members):
	return Predicate(
		lambda candidate: candidate in members,
		"one of %s" % ', '.join(map(repr, members)),
		lambda candidate: "%s not in %s" % (candidate, members)
	)

def inrange(start, end):
	return Predicate(
		lambda candidate: start <= candidate <= end,
		"between %s and %s" % (start, end),
		lambda candidate: "%s not between %s and %s" % (candidate, start, end)
	)
