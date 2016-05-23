#!/usr/bin/env python3

import datetime, os, re, sys
from read_header_file import read_header_file, Context
from make_enums import make_enums


def make(header_file):
    header = read_header_file(header_file)
    classname = header.classname
    namespace = ':'.join(header.namespaces)
    member_name = '_instance'

    enums, enum_class, enum_names, enum_types = make_enums(
        header.enum_classes, header_file, namespace, header.classname)

    indent = '\n        '
    fmt = lambda s: s.typename + ' ' + ', '.join(s.variables)
    pyx_structs = indent.join(fmt(s) for s in header.structs)
    if pyx_structs:
        pyx_structs = indent + pyx_structs

    struct_definition = '    struct %s:%s' % (classname, pyx_structs)
    props = []

    variables_to_enum_type = {}

    for s in header.structs:
        if s.typename in enum_types:
            for i in s.variables:
                variables_to_enum_type[i] = s.typename
        props += s.variables

    str_format = [n + ("='%s'" if n in variables_to_enum_type else '=%s')
                  for n in props]
    str_format = ', '.join(str_format)
    variable_names = ', '.join('self.' + n for n in props)
    property_list = []
    for s in header.structs:
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
# Automatically generated by https://github.com/rec/make_pyx/make_pyx.py
# from {header_file}.
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
