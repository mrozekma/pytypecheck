class OneOf:
	def __init__(self, members):
		self.members = members

	def __call__(self, candidate):
		if candidate in self.members:
			return True
		return "%s not in %s" % (candidate, self.members)

	def __repr__(self):
		return "one of %s" % ', '.join(map(repr, self.members))

def oneof(*members):
	return OneOf(members)

class InRange:
	def __init__(self, start, end):
		self.start = start
		self.end = end

	def __call__(self, candidate):
		if self.start <= candidate <= self.end:
			return True
		return "%s not between %s and %s" % (candidate, self.start, self.end)

	def __repr__(self):
		return "between %s and %s" % (self.start, self.end)

def inrange(start, end):
	return InRange(start, end)
