#!/usr/bin/env python3

import datetime, os, re, sys


def prejoin(prefix, s):
    return prefix + prefix.join(s) if s else ''

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
    return typename, variables

NAMESPACE_RE = re.compile(r'namespace (\w+)')
STRUCT_RE = re.compile(r'struct (\w+)')
ENUM_CLASS_RE = re.compile(r'enum class (\w+) \{([^}]+)}')

def read(header_file):
    in_struct = False
    namespace = []
    structs = []
    classname = ''
    enum_class = []

    for line in open(header_file):
        comment = line.find('//')
        if comment >= 0:
            line = line[:comment]
        line = line.strip()
        if not line:
            continue

        if in_struct:
            m = ENUM_CLASS_RE.match(line)
            if m:
                enum_class.append(m.group(1, 2))
                continue

            if '{' in line or line.startswith('};') or line.startswith('class'):
                break

            structs.append(clean_struct(line))
            continue

        m = NAMESPACE_RE.match(line)
        if m:
            namespace.append(m.group(1))
            continue

        m = STRUCT_RE.match(line)
        if m:
            classname = m.group(1)
            in_struct = True

    return namespace, structs, classname, enum_class


def make_enums(enum_classes, header_file, namespace, classname):
    enums, declarations = [], []
    for ec in enum_classes:
        enum_name, parts = (i.strip() for i in ec)
        parts = [(p[:-1] if p.endswith(',') else p) for p in parts.split()]
        enums.append((enum_name, parts))
        main = ENUM_CLASS_TEMPLATE.format(**locals())
        defs = ('    cdef %s %s' % (enum_name, p) for p in parts)
        declarations.append(main + '\n'.join(defs))

    decl = prejoin('\n', declarations)
    if decl:
        decl += '\n'
    return enums,  decl


def make(header_file):
    namespaces, structs, classname, enum_classes = read(header_file)
    namespace = ':'.join(namespaces)

    enums, enum_class = make_enums(
        enum_classes, header_file, namespace, classname)
    enum_names = []
    enum_types = {}
    for name, values in enums:
        enum_types[name] = set()
        values = ', '.join("'%s'" % v for v in values)
        enum_names.append('    %s_NAMES = %s' % (name.upper(), values))

    enum_names = prejoin('\n', enum_names)
    if enum_names:
        enum_names += '\n'
    pyx_structs = prejoin('\n        ',
                          ((t + ' ' + ', '.join(v)) for t, v in structs))
    struct_definition = '    struct %s:%s' % (classname, pyx_structs)
    props = []

    variables_to_enum_type = {}

    for t, v in structs:
        if t in enum_types:
            for i in v:
                variables_to_enum_type[i] = t
        props += v
    str_format = ', '.join(n + '=%s' for n in props)
    variable_names = ', '.join('self.' + n for n in props)
    property_list = []
    for typename, variables in structs:
        for prop in variables:
            if prop in variables_to_enum_type:
                Type = variables_to_enum_type[prop]
                TYPE = Type.upper()
                template = ENUM_PROP_TEMPLATE
            else:
                template = PROP_TEMPLATE
            property_list.append(template.format(**locals()))
    property_list = '\n'.join(property_list)
    timestamp = datetime.datetime.utcnow().isoformat()
    return MAIN_TEMPLATE.format(**locals())


MAIN_TEMPLATE = """\
# Automatically generated on {timestamp}
# by https://github.com/rec/make_pyx/make_pyx.py
{enum_class}
cdef extern from "<{header_file}>" namespace "{namespace}":
{struct_definition}


cdef class _{classname}(_Wrapper):
    cdef {classname} thisptr;
{enum_names}
    def __cinit__(self):
        clearStruct(self.thisptr)

    def clear(self):
        clearStruct(self.thisptr)

    def __str__(self):
        return '({str_format})' % (
            {variable_names})

{property_list}"""

PROP_TEMPLATE = """\
    property {prop}:
        def __get__(self):
            return self.thisptr.{prop}
        def __set__(self, {typename} x):
            self.thisptr.{prop} = x
"""

ENUM_CLASS_TEMPLATE = """\
cdef extern from "<{header_file}>" namespace "{namespace}::{classname}":
    cdef cppclass {enum_name}:
        pass

cdef extern from "<{header_file}>" namespace "{namespace}::{classname}::{enum_name}":
"""

ENUM_PROP_TEMPLATE = """\
    property {prop}:
        def __get__(self):
            return self.{TYPE}_NAMES[<int> self.thisptr.{prop}]
        def __set__(self, string x):
            cdef uint8_t i
            i = self.{TYPE}_NAMES.index(x)
            self.thisptr.{prop} = <{Type}>(i)
"""

if __name__ == '__main__':
    for f in sys.argv[1:]:
        assert f.endswith('.h'), 'Not a header file: ' + f
        data = make(f)
        base, fname = os.path.split(os.path.splitext(f)[0])
        outfile = os.path.join(base, '_' + fname + '.pyx')
        open(outfile, 'w').write(data)
