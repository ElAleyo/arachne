#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generally useful utilities."""

import re
import inspect
from collections import defaultdict

class Registry(defaultdict):
    """An OpenStruct-like registry."""
    def __getattr__(self, name):
        if name in self: return self[name]
        return None

def argspec(function, ignore_self=True):
    """Returns a properly formatted argspec for a function.  If ignore_self is
    True, then a 'self' arg is thrown away.  The return value is meant to look
    like the function definition."""
    spec = inspect.getargspec(function)
    if 'self' in spec[0]:
        spec = (spec[0][1:], spec[1], spec[2], spec[3])
    return '%s%s' % (function.__name__, inspect.formatargspec(*spec))

ntb_re = re.compile(r'\r\n|\r|\n')
def newline_to_br(text):
    return ntb_re.sub('<br>', text)

def keygetter(key, default=None):
    def getkey(obj):
        return obj.get(key, default)
    return getkey

from heapq import heappush, heappop, heapify, heapreplace

class Heap(object):
    """Heap class using heapq library."""
    def __init__(self, items=None):
        self.items = heapify(items or [])

    def pop(self):
        return heappop(self.items)

    def push(self, item):
        return heappush(self.items, item)

    def replace(self, item):
        return heapreplace(self.items, item)

    def __getitem__(self, item):
        return self.items[item]

