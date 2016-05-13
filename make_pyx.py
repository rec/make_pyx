#!/usr/bin/env python3

import datetime, os, re, sys


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

            if (
                '{' in line or
                '(' in line or
                line.startswith('};') or
                line.startswith('class') or
                line.startswith('template')
                ):
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

    decl = '\n\n'.join(declarations)
    if decl:
        decl += '\n'
    return enums, decl


def make(header_file):
    namespaces, structs, classname, enum_classes = read(header_file)
    namespace = ':'.join(namespaces)

    enums, enum_class = make_enums(
        enum_classes, header_file, namespace, classname)
    member_name = '_instance' # '_' + classname.lower()

    enum_names = []
    enum_types = {}
    for name, values in enums:
        enum_types[name] = set()
        values = ', '.join("'%s'" % v for v in values)
        enum_names.append('    %s_NAMES = %s' % (name.upper(), values))

    def prejoin(prefix, s):
        return prefix + prefix.join(s) if s else ''

    enum_names = '\n'.join(enum_names)
    if enum_names:
        enum_names = '\n%s\n' % enum_names
    indent = '\n        '
    pyx_structs = indent.join((t + ' ' + ', '.join(v)) for t, v in structs)
    if pyx_structs:
        pyx_structs = indent + pyx_structs

    struct_definition = '    struct %s:%s' % (classname, pyx_structs)
    props = []

    variables_to_enum_type = {}

    for t, v in structs:
        if t in enum_types:
            for i in v:
                variables_to_enum_type[i] = t
        props += v
    str_format = [n + ("='%s'" if n in variables_to_enum_type else '=%s')
                  for n in props]
    str_format = ', '.join(str_format)
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
