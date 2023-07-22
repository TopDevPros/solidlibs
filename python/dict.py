'''
    Dict utilities.

    Copyright 2013-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.

    To do

    Fix infinite recursion:
        File "site-packages/syr/dict.py", line 533 in resolve_instance
        File "site-packages/syr/dict.py", line 621 in resolve_obj
        File "site-packages/syr/dict.py", line 533 in resolve_instance
        File "site-packages/syr/dict.py", line 621 in resolve_obj
        File "site-packages/syr/dict.py", line 533 in resolve_instance
        File "site-packages/syr/dict.py", line 621 in resolve_obj
        ...

        Line 533 was 'd[name] = resolve_obj(attr(*[instance]))' and
        621 was 'value = resolve_instance(obj)'.

        In dictify.resolve_obj(), after check_circular_reference() we need
        to check if obj is None. Otherwise why call it?
        Maybe check_circular_reference() should return the earlier computed value.

        After
            elif isinstance(obj, dict):

                value = resolve_dict(obj, json_compatible=json_compatible)
                if debug: log('resolve_obj(%s) value is dict: %r' % (obj, value))

            if value is None:
        we can probably skip "if value is None:" and change the nested 'if's with 'elif's.

        If types.ModuleType is an instance, we need to check
        'isinstance(obj, types.ModuleType)' before 'is_class_instance(obj)'.
'''

import datetime
import json
import types
from collections.abc import Mapping

from solidlibs.python.internals import is_class_instance
from solidlibs.python.log import Log
from solidlibs.python.utils import last_exception, object_name

log = Log()

_unimplemented_types = set()
datetime_types = (datetime.timedelta, datetime.date, datetime.datetime, datetime.time, datetime.timezone)

class Simple(dict):
    ''' You can reference a field in a Simple object by either obj.name or
        obj['name']. It's ideal for going to and from json, or when you need to iterate through fields.

        Simple is both a class and a dict. It's also a very simple way to
        create a class instance.

        You can inherit from Simple and get its benefits plus the
        documentation of a python class.

        If a key includes any character that can't be used in a python
        identifier, access the value using dict syntax. Or change the key.

        If the data structure is not really very simple, use a class.

        An alternative is the "dataclass" decorator. But dataclass
        has unusual syntax and semantics. Simple is plain python.

        >>> simpl = Simple()

        >>> simpl.a = 1
        >>> simpl['b'] = 'hi'

        >>> simpl['a']
        1
        >>> simpl.b
        'hi'

        Or init with a dict, such as returned by json.dumps().

        >>> simpl = Simple({'x': 3, 'y': 'blue'})

        >>> simpl.x
        3
        >>> simpl['x']
        3
        >>> simpl.y
        'blue'
        >>> simpl['y']
        'blue'

        This class is very similar to javascript objects and django template dicts.

        No __init__ to define. Just pythonic duck typing with flexible
        access.

        It's especially useful when you often have to convert between
        class instances and dicts, such as with JSON.

        If you know some or all of the keys and values in advance, use
        Simple anywhere you would use {} or dict(). Code is must cleaner.
        Simple is also a great solution when you don't know all of the
        members of a class in advance. In that case init fields with just
        obj.name.

        You can initialize Simple with anything you can pass to dict().

        Keys and values which are of type dict are converted to Simple
        instances.

        To convert a class instance to a dict, see solidlibs.python.dict.dictify().
        Python's builtin dict() does not convert inner instances of Simple,
        at least in python2.

        >>> d = {'a': 1, 'b': 'hi'}

        >>> simpl = Simple(d)
        >>> simpl.c = {'a': 1, 'b': 'hi'}

        >>> sorted(simpl.keys())
        ['a', 'b', 'c']

        >>> simpl.a
        1
        >>> simpl.b
        'hi'

        >>> sorted(simpl.c.keys())
        ['a', 'b']
        >>> simpl.c['a']
        1
        >>> simpl.c['b']
        'hi'
        >>> isinstance(simpl.c, Simple)
        True

        >>> simpl.d
        Traceback (most recent call last):
            ...
        AttributeError: d
        >>> 'd' in simpl
        False

        >>> simpl.d = 'hey'
        >>> 'd' in simpl
        True
        >>> simpl['d']
        'hey'

        >>> redict = dict(simpl)
        >>> type(redict) is dict
        True
        >>> sorted(redict.keys())
        ['a', 'b', 'c', 'd']

        >>> redict['a']
        1
        >>> redict['b']
        'hi'

        >>> isinstance(redict['c'], dict)
        True
        >>> sorted(redict['c'].keys())
        ['a', 'b']
        >>> redict['c']['a']
        1
        >>> redict['c']['b']
        'hi'

        >>> isinstance(redict['c'], Simple)
        True
        >>> redict['c'].a
        1
        >>> redict['c'].b
        'hi'

        >>> redict['d']
        'hey'

        >>> redict['e']
        Traceback (most recent call last):
            ...
        KeyError: 'e'

    '''

    def __getattr__(self, name):
        if name in self:
            value = self[name]
        else:
            raise AttributeError(name)
        return value

    def __setattr__(self, name, value):
        if isinstance(name, dict):
            name = Simple(name)
        if isinstance(value, dict):
            value = Simple(value)
        self[name] = value

    def __delattr__(self, name):
        if name in self.keys():
            del self[name]
        else:
            raise AttributeError(name)

    def __repr__(self):
        try:
            result = repr(dict(self))
        except (Exception, AttributeError, IOError, OSError):
            result = '>>>Simple repr error>>>'
        return result

    def __str__(self):
        try:
            result = str(dict(self))
        except (Exception, AttributeError, IOError, OSError):
            result = 'Simple str error'
        return result

    def __dir__(self):
        return self.keys()

    def __hash__(self):
        return id(self)

class CaseInsensitiveDict(Mapping):
    ''' Case insensitive dict.

        Dict lookups ignore key case. The key matches in lower, upper, or mixed case.

        Mostly from http://stackoverflow.com/questions/3296499/case-insensitive-dictionary-search-with-python
    '''

    def __init__(self, d=None):
        if d is None:
            d = {}
        self._d = d
        # _s is a dict mapping lowercase _d keys to actual _d keys
        self._s = dict((k.lower(), k) for k in d)

    def __contains__(self, k):
        return k.lower() in self._s

    def __len__(self):
        return len(self._s)

    def __iter__(self):
        return iter(self._s)

    def __getitem__(self, k):
        return self._d[self._s[k.lower()]]

    def __setitem__(self, k, v):
        self._d[k] = v
        self._s[k.lower()] = k

    def __delitem__(self, k):
        del self._d[self._s[k.lower()]]
        del self._s[k.lower()]

    def __str__(self):
        strings = []
        for key in self._d:
            strings.append(f'{key}: {self._d[key]}')
        return ', '.join(strings)

    def pop(self, k):
        k0 = self._s.pop(k.lower())
        return self._d.pop(k0)

    def actual_key_case(self, k):
        return self._s.get(k.lower())

def dictify(obj, deep=False, json_compatible=False, debug=False):
    ''' Resolves an object to a dictionary.

        If deep is True, recurses as needed. Default is False.

        Allowable object types are:
            NoneType,
            BooleanType,
            IntType, LongType, FloatType, ComplexType,
            StringTypes,
            TupleType, ListType, DictType,
            #MethodType, FunctionType,
            #GeneratorType,
            datetime.timedelta, datetime.date, datetime.datetime, datetime.time,
            class instances

        As of Python 2.6 2013-05-02 types.Instancetype is not reliable. We use
        solidlibs.python.internals.is_class_instance().

        A class instance is converted to a dict, with only data members and
        functions without parameters. Functions that require parameters (beyond self)
        are ignored. For an object that accepts dot
        notation so you may not have to change your code, see
        solidlibs.python.dict.Simple(). Builtin instance member names beginning
        with '__' are ignored.

        dictify tries to use the current return value from methods.
        The method is called with no args (except self, i.e. the instance).
        We try a static method with no arguments. If these fail,
        the method is ignored.

        dictify converts a generator to a list. Warning: This may result in
        large, or even infinite, lists.

        json_compatible makes dictionary keys compatible with json, i.e. one of
        (str, unicode, int, long, float, bool, None).

        To do:
            dictify() could also find why json.dumps() doesn't always work.
            Add a param 'test_json=True'. When set call json.dumps() on
            every object.Log or raise exception on errors. Probabaly
            the deepest/last error is most important.

        >>> from solidlibs.python.format import pretty

        >>> class Test(object):
        ...     a = 1
        ...     b = 'hi'
        ...     def __init__(self):
        ...         self.c = 2
        ...         self.d = 'hey'
        ...         self.e = datetime.timedelta(weeks=1, days=2, hours=3,
        ...                                     minutes=4, seconds=5)
        ...         self.f = datetime.date(2000, 1, 2)
        ...         self.g = datetime.datetime(2000, 1, 2, 3, 4, 5, 6)
        ...         self.h = datetime.time(1, 2, 3, 4)

        >>> test = Test()
        >>> print(pretty(dictify(test)))
        {
            'a': 1,
            'b': 'hi',
            'c': 2,
            'd': 'hey',
            'e': {
                'days': 9,
                'microseconds': 0,
                'seconds': 11045,
            },
            'f': {
                'day': 2,
                'month': 1,
                'year': 2000,
            },
            'g': {
                'day': 2,
                'hour': 3,
                'microsecond': 6,
                'minute': 4,
                'month': 1,
                'second': 5,
                'tzinfo': None,
                'year': 2000,
            },
            'h': {
                'hour': 1,
                'microsecond': 4,
                'minute': 2,
                'second': 3,
                'tzinfo': None,
            },
        }

        >>> import datetime
        >>> dt = datetime.date(2001, 12, 1)
        >>> dictified = dictify(dt)
        >>> sorted(dictified.keys())
        ['day', 'month', 'year']
        >>> dictified['year']
        2001
        >>> dictified['month']
        12
        >>> dictified['day']
        1

        >>> dt = {1: datetime.date(2002, 12, 1)}
        >>> print(pretty(dictify(dt)))
        {
            1: {
                'day': 1,
                'month': 12,
                'year': 2002,
            },
        }

        >>> class OldStyleClass:
        ...     class_data = 27
        ...
        ...     def __init__(self):
        ...         self.instance_data = 'idata'

        ...     def instance_function(self):
        ...         return 3
        >>> old_c = OldStyleClass()
        >>> print(pretty(dictify(old_c)))
        {
            'class_data': 27,
            'instance_data': 'idata',
        }

        >>> class NewStyleClass(object):
        ...     class_data = 27
        ...
        ...     def __init__(self):
        ...         self.instance_data = 'idata'

        ...     def instance_function(self):
        ...         return 3
        >>> new_c = NewStyleClass()
        >>> print(pretty(dictify(new_c)))
        {
            'class_data': 27,
            'instance_data': 'idata',
        }

        >>> from datetime import timezone
        >>> dictify(timezone.utc)

        >>> try:
        ...     from zoneinfo import ZoneInfo
        ...     dictify(ZoneInfo('UTC').utcoffset(None))
        ... except ImportError:
        ...     try:
        ...         import pytz
        ...         dictify(pytz.timezone('UTC').utcoffset(None))
        ...     except ImportError:
        ...         pass
        {'days': 0, 'seconds': 0, 'microseconds': 0}
        >>> dictify({'_dst': {'days': 0, 'microseconds': 0, 'seconds': 0}, '_tzname': 'UTC', '_utcoffset': {'days': 0, 'microseconds': 0, 'seconds': 0}, 'zone': 'UTC'})
        {'_dst': {'days': 0, 'microseconds': 0, 'seconds': 0}, '_tzname': 'UTC', '_utcoffset': {'days': 0, 'microseconds': 0, 'seconds': 0}, 'zone': 'UTC'}

        # if the following line does not have the new line escaped, then python rejects the formating of the dict
        >>> timing_access_line = {'line': '207.241.233.238 - - [16/Oct/2019:19:11:06 +0000] "HEAD /page_timing/?nt_red_cnt=1&nt_nav_type=0&nt_nav_st=1571253056365&nt_red_st=1571253056365&nt_red_end=1571253057865&nt_fet_st=1571253057865&nt_dns_st=1571253057865&nt_dns_end=1571253057865&nt_con_st=1571253057865&nt_con_end=1571253057865&nt_req_st=1571253057866&nt_res_st=1571253060162&nt_res_end=1571253060349&nt_domloading=1571253060345&nt_domint=1571253060738&nt_domcontloaded_st=1571253060738&nt_domcontloaded_end=1571253060747&nt_domcomp=1571253065139&nt_load_st=1571253065140&nt_load_end=1571253065146&nt_unload_st=0&nt_unload_end=0&u=http%3A%2F%2Fweb.archive.org%2Fweb%2F20160128095330%2Fhttp%3A%2F%2Fwww.example.com%2F&v=0.9&vis.st=visible HTTP/1.1" 301 0 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0.2 Safari/605.1.15"\\n', 'ip_address': b'207.241.233.238', 'domain': '', 'method': b'HEAD', 'timestamp': datetime.datetime(2019, 10, 16, 19, 11, 6, tzinfo=datetime.timezone.utc), 'referer': '', 'url': b'/page_timing/', 'query_string': b'nt_red_cnt=1&nt_nav_type=0&nt_nav_st=1571253056365&nt_red_st=1571253056365&nt_red_end=1571253057865&nt_fet_st=1571253057865&nt_dns_st=1571253057865&nt_dns_end=1571253057865&nt_con_st=1571253057865&nt_con_end=1571253057865&nt_req_st=1571253057866&nt_res_st=1571253060162&nt_res_end=1571253060349&nt_domloading=1571253060345&nt_domint=1571253060738&nt_domcontloaded_st=1571253060738&nt_domcontloaded_end=1571253060747&nt_domcomp=1571253065139&nt_load_st=1571253065140&nt_load_end=1571253065146&nt_unload_st=0&nt_unload_end=0&u=http%3A%2F%2Fweb.archive.org%2Fweb%2F20160128095330%2Fhttp%3A%2F%2Fwww.example.com%2F&v=0.9&vis.st=visible', 'http_status_code': 301, 'protocol': b'HTTP/1.1', 'bytes': 0, 'user': '', 'agent': b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0.2 Safari/605.1.15', 'browser_name': 'Mozilla', 'browser_version': '5.0', 'other': '(Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0.2 Safari/605.1.15', 'trace_url_found': False}
        >>> d = dictify(timing_access_line)
        >>> isinstance(d, Simple)
        True
    '''

    allowed_types = (
            type(None),
            bool,
            int, int, float, complex,
            # ?? StringTypes is itself a tuple; can we nest it like this?
            str,
            tuple, list, dict,
            object,
            # types.MethodType, types.FunctionType,
            # types.ModuleType,
            # types.GeneratorType,
            ) + datetime_types

    def type_allowed(obj):
        return isinstance(obj, allowed_types)
        #return (isinstance(obj, allowed_types) or
        #    is_class_instance(obj))

    def check_circular_reference(obj):
        ''' Check for circular references to instances. '''

        # do not check classes that we resolve specially
        #if is_class_instance(obj) and not isinstance(obj, datetime_types):
        if not isinstance(obj, datetime_types):

            obj_id = id(obj)
            if obj_id in obj_ids:
                obj = f'__syr.dict.dictify: circular_reference to {repr(obj)}, type {type(obj)}__'
                if debug: log.warning(obj)

            else:
                obj_ids.add(obj_id)

        return obj

    def resolve_string(obj):
        ''' Return object if unicode, else return str.

            Starting with python 2.6 all strings are unicode.
            But for readability we use a plain string where possible. '''

        try:
            value = str(obj)
        except (Exception, AttributeError, IOError, OSError):
            value = f'{obj}'

        return value

    def resolve_datetime(obj):
        if isinstance(obj, datetime.timedelta):
            value = Simple({
                'days': obj.days,
                'seconds': obj.seconds,
                'microseconds': obj.microseconds,
                })
        elif isinstance(obj, datetime.datetime):
            value = Simple({
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond,
                'tzinfo': obj.tzinfo,
                })
        elif isinstance(obj, datetime.date):
            value = Simple({
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                })
        elif isinstance(obj, datetime.time):
            value = Simple({
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond,
                'tzinfo': obj.tzinfo,
                })
        else:
            value = None

        if debug: log(f'datetime obj: {obj!r}, type: {type(obj)}, value: {value!r}')
        return value

    def resolve_dict(obj, json_compatible=False):
        ''' Resolve a simple dict object. This is a deep resolve to a Simple. '''

        d = Simple({})
        for key in obj:

            # a dictionary needs a hashable key
            try:
                new_key = resolve_obj(key)
                hash(new_key)
            except (Exception, AttributeError, IOError, OSError):
                new_key = f'{type(key)}-{id(key)}'

            if json_compatible:
                # convert key to a json compatible type
                if not isinstance(new_key, (str, int, float, bool, None)):
                    new_key = repr(new_key)

            new_value = resolve_obj(obj[key])

            try:
                d[new_key] = new_value
            except TypeError: # e.g. unhashable type
                if debug:
                    log.warning('resolving Simple, got TypeError')
                    log(f'    key is {key}, type {type(key)}')
                    log(f'    new_key is {new_key}, type {type(new_key)}')
                    log(f'    obj[key] is {obj[key]}, type {type(obj[key])}')
                    log(f'    new_value is {new_value}, type {type(new_value)}')
                    log(last_exception())
                d[key] = new_value

        return d

    def resolve_instance(obj):
        ''' Resolve an instance of a class. '''

        d = Simple({})

        # call the obj an instance for clarity here
        instance = obj
        # get names of instance attributes
        for name in dir(instance):
            # ignore builtins, etc.
            if not name.startswith('__'):

                # usually commented out - set debug to test special case
                #if name == 'previous_conversion': #DEBUG
                #    _old_debug = debug #DEBUG
                #    debug = True #DEBUG

                if debug: log('in resolve_obj() getting "%s" attribute "%s"' %
                    (repr(instance), name))

                try:
                    attr = getattr(instance, name)
                    if debug: log(
                        'in resolve_obj() instance: "%s", attribute: "%s", type: %s' %
                        (repr(instance), name, type(attr)))

                    # convert name to an allowed type
                    # infinite recursion
                    # name = resolve_obj(name)

                    if type_allowed(attr):

                        # if this attr is a method object
                        if isinstance(attr, types.MethodType):
                            if debug: log(f'{attr!r} is a MethodType, so skipping')

                        # if this attr is a static method object
                        elif isinstance(attr, types.FunctionType) and deep:
                            if debug: log(f'{attr!r} is a FunctionType, so skipping')

                        else:
                            if debug: log('member {}.{} is an allowed type ({}) so resolving object'.
                                              format(name, repr(attr), type(attr)))
                            d[name] = resolve_obj(attr)

                    else:
                        if debug: log.warning(f'in resolve_obj() type not allowed ({attr!r}), so skipping')

                except (Exception, AttributeError, IOError, OSError):
                    # these seem to be caused by using @property, making it hard to
                    # get a function attr without calling the function
                    if debug:
                        log('in resolve_obj() ignoring following exception')
                        log(last_exception())

                # usually commented out - set debug to test special case
                #if name == 'previous_conversion': #DEBUG
                #    debug = _old_debug #DEBUG

        return d

    def resolve_module(module):
        ''' Resolve a module to a dict object. '''

        d = Simple({})
        for k, v in list(module.__dict__.items()):
            if not k.startswith('__'):
                d[k] = v

        return d

    def resolve_obj(obj):
        ''' Resolve any type to a dict object. '''

        #assert not debug #DEBUG
        # usually commented out - set debug locally to test special case
        # if isinstance(obj, datetime_types): #DEBUG
        #     debug = True #DEBUG

        value = None

        if debug: log(f'resolve_obj({obj}) type {type(obj)}')
        obj = check_circular_reference(obj)

        if isinstance(obj, str):
            value = resolve_string(obj)

        elif isinstance(obj, (tuple, types.GeneratorType)):

            # immutable iterators
            value = tuple(resolve_obj(item) for item in obj)
            if debug: log(f'resolve_obj({obj}) value is tuple: {value!r}')

        elif isinstance(obj, list):

            # mutable iterator
            value = list(resolve_obj(item) for item in obj)
            if debug: log(f'resolve_obj({obj}) value is list: {value!r}')

        elif isinstance(obj, dict):

            value = resolve_dict(obj, json_compatible=json_compatible)
            if debug: log(f'resolve_obj({obj}) value is dict: {value!r}')

        elif isinstance(obj, datetime_types):

            value = resolve_datetime(obj)

        elif isinstance(obj, datetime.tzinfo):

            # obviously wrong for some systems, but not ours
            value = None

        elif is_class_instance(obj):

            value = resolve_instance(obj)
            if debug: log(f'resolve_obj({obj}) value is instance: {value!r}')

        elif isinstance(obj, types.ModuleType):

            value = resolve_module(obj)
            if debug: log(f'resolve_obj({obj}) value is module: {value!r}')

        elif type_allowed(obj):

            value = obj
            if debug: log(f'resolve_obj({obj}) value is allowed type: {type(obj)}')

        else:

            # any other type as just the type, not restorable
            value = str(type(obj))
            if value not in _unimplemented_types:
                # mention each type just once
                _unimplemented_types.add(value)
                if debug: log.warning(f'resolve_obj({obj}) value is unimplemented type: {value}')

        if debug: log(f'resolve_obj({obj}) final type: {type(value)}, value: {value!r}')
        assert not isinstance(value, datetime_types) #DEBUG

        # remove the object from circular reference check
        if id(obj) in obj_ids:
            obj_ids.remove(id(obj))

        return value

    debug = debug

    if debug: log(f'dictify({obj})')
    obj_ids = set()

    value = resolve_obj(obj)

    # if debug: log('dictify(%s) is %r' % (object_name(obj, include_repr=True), value))
    return value

def force_json(obj, debug=False):
    ''' Return json for the object, dropping fields as needed. '''

    try:
        json_out = json.dumps(obj)
    except TypeError as t_error:
        t_error_str = str(t_error)
        log(t_error_str)
        if 'is not JSON serializable' in t_error_str:

            log(f'json.dumps({type(obj)}) failed; try dictify()')
            d = dictify(obj, debug=debug)
            json_out = json.dumps(d)

        else:
            # we don't know what happened, so raise the exception
            raise

    return json_out


if __name__ == "__main__":
    import doctest
    doctest.testmod()
