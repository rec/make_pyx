#!/usr/bin/env python3

import datetime, os, re, sys

class Context(object):
    def __init__(self, **kwds):
        for (k, v) in kwds.items():
            setattr(self, k, v)

def read_header_file(header_file):
    context = Context(
        namespaces=[],
        structs=[],
        classname='',
        enum_classes=[],
        enums=[],
        declarations=[],
        )

    def clean_struct(s):
        typename, *parts = s.split()

        was_equal = False
        variables = []
        for p in parts:
            if p[-1] in ';,':
                p = p[:-1]
            was_equal or p == '=' or variables.append(p)
            was_equal = p == '='

        assert typename and parts and variables
        return Context(typename=typename, variables=variables)

    def struct_is_finished(line):
        return ('{' in line or
                '(' in line or
                line.startswith('};') or
                line.startswith('class') or
                line.startswith('template'))

    def strip_comments_and_empties(f):
        for line in f:
            comment = line.find('//')
            if comment >= 0:
                line = line[:comment]
            line = line.strip()
            if line:
                 yield line

    regex = Context(
        namespace=re.compile(r'namespace (\w+)'),
        cstruct=re.compile(r'struct (\w+)'),
        enum_class=re.compile(r'enum class (\w+) \{([^}]+)}'),
        )

    in_struct = False
    for line in strip_comments_and_empties(open(header_file)):
        if in_struct:
            m = regex.enum_class.match(line)
            if m:
                context.enum_classes.append(m.group(1, 2))
            elif struct_is_finished(line):
                break
            else:
                context.structs.append(clean_struct(line))
        else:
            m = regex.namespace.match(line)
            if m:
                context.namespaces.append(m.group(1))
            else:
                m = regex.cstruct.match(line)
                if m:
                    context.classname = m.group(1)
                    in_struct = True

    return context


def make_enums(enum_classes, header_file, namespace, classname):
    enums, declarations = [], []
    for ec in enum_classes:
        enum_name, parts = (i.strip() for i in ec)
        parts = [(p[:-1] if p.endswith(',') else p) for p in parts.split()]
        enums.append((enum_name, parts))
        main = ENUM_CLASS_TEMPLATE.format(**locals())
        defs = ('    cdef %s %s' % (enum_name, p) for p in parts)
        declarations.append(main + '\n'.join(defs))

    decl = '\n\n'.join(declarations)
    if decl:
        decl += '\n'
    return Context(enums=enums, declarations=decl)


def make(header_file):
    c = read_header_file(header_file)
    namespaces, structs, classname, enum_classes = (
        c.namespaces, c.structs, c.classname, c.enum_classes)
    namespace = ':'.join(namespaces)

    c2 = make_enums(enum_classes, header_file, namespace, classname)
    enums, enum_class = c2.enums, c2.declarations

    member_name = '_instance' # '_' + classname.lower()

    enum_names = []
    enum_types = {}
    for name, values in enums:
        enum_types[name] = set()
        values = ', '.join("'%s'" % v for v in values)
        enum_names.append('    %s_NAMES = %s' % (name.upper(), values))

    enum_names = '\n'.join(enum_names)
    if enum_names:
        enum_names = '\n%s\n' % enum_names
    indent = '\n        '
    fmt = lambda s: s.typename + ' ' + ', '.join(s.variables)
    pyx_structs = indent.join(fmt(s) for s in structs)
    if pyx_structs:
        pyx_structs = indent + pyx_structs

    struct_definition = '    struct %s:%s' % (classname, pyx_structs)
    props = []

    variables_to_enum_type = {}

    for s in structs:
        if s.typename in enum_types:
            for i in s.variables:
                variables_to_enum_type[i] = s.typename
        props += s.variables

    str_format = [n + ("='%s'" if n in variables_to_enum_type else '=%s')
                  for n in props]
    str_format = ', '.join(str_format)
    variable_names = ', '.join('self.' + n for n in props)
    property_list = []
    for s in structs:
        for prop in s.variables:
            if prop in variables_to_enum_type:
                Type = variables_to_enum_type[prop]
                TYPE = Type.upper()
                template = ENUM_PROP_TEMPLATE
            else:
                template = PROP_TEMPLATE
            typename, variables = s.typename, s.variables
            property_list.append(template.format(**locals()))
    property_list = '\n'.join(property_list)
    timestamp = datetime.datetime.utcnow().isoformat()
    mt = MAIN_TEMPLATE.format(**locals())
    if property_list:
        mt += CLASS_TEMPLATE.format(**locals())
    return mt


MAIN_TEMPLATE = """\
# Automatically generated on {timestamp}
# by https://github.com/rec/make_pyx/make_pyx.py
{enum_class}"""

CLASS_TEMPLATE = """\

cdef extern from "<{header_file}>" namespace "{namespace}":
{struct_definition}

cdef class _{classname}(_Wrapper):
    cdef {classname} {member_name};
{enum_names}
    def __cinit__(self):
        clearStruct(self.{member_name})

    def clear(self):
        clearStruct(self.{member_name})

    def __str__(self):
        return "({str_format})" % (
            {variable_names})

{property_list}"""

PROP_TEMPLATE = """\
    property {prop}:
        def __get__(self):
            return self.{member_name}.{prop}
        def __set__(self, {typename} x):
            self.{member_name}.{prop} = x
"""

ENUM_CLASS_HEADER_TEMPLATE = """\
cdef extern from "<{header_file}>" namespace "{namespace}::{classname}":
"""

ENUM_CLASS_ENUM_TEMPLATE = """\
    cdef cppclass {enum_name}:
        pass
"""

ENUM_CLASS_NAME_TEMPLATE = """\
cdef extern from "<{header_file}>" namespace "{namespace}::{classname}::{enum_name}":
"""

ENUM_CLASS_TEMPLATE = """\
cdef extern from "<{header_file}>" namespace "{namespace}::{classname}":
    cdef cppclass {enum_name}:
        pass

cdef extern from "<{header_file}>" namespace "{namespace}::{classname}::{enum_name}":
"""

ENUM_CLASS_TEMPLATE = (
    ENUM_CLASS_HEADER_TEMPLATE +
    ENUM_CLASS_ENUM_TEMPLATE +
    '\n' +
    ENUM_CLASS_NAME_TEMPLATE)

ENUM_PROP_TEMPLATE = """\
    property {prop}:
        def __get__(self):
            return self.{TYPE}_NAMES[<int> self.{member_name}.{prop}]
        def __set__(self, string x):
            cdef uint8_t i
            i = self.{TYPE}_NAMES.index(x)
            self.{member_name}.{prop} = <{Type}>(i)
"""

if __name__ == '__main__':
    for f in sys.argv[1:]:
        assert f.endswith('.h'), 'Not a header file: ' + f
        data = make(f)
        base, fname = os.path.split(os.path.splitext(f)[0])
        outfile = os.path.join(base, '_' + fname + '.pyx')
        open(outfile, 'w').write(data)
