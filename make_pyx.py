#!/usr/bin/env python3

import datetime, re, sys

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


def read(header_file):
    in_struct = False
    namespace = []
    structs = []
    classname = ''

    for line in open(header_file):
        comment = line.find('//')
        if comment >= 0:
            line = line[:comment]
        line = line.strip()
        if not line:
            continue

        if in_struct:
            if '{' in line or line.startswith('};') or line.startswith('class'):
                break
            structs.append(clean_struct(line))
            continue
        m = re.compile(r'namespace \s+(\S+)', re.X).match(line)
        if m:
            namespace.append(m.group(1))
            continue

        m = re.compile(r'struct \s+(\S+)', re.X).match(line)
        if m:
            Classname = m.group(1)
            in_struct = True

    return namespace, structs, Classname


def make(header_file):
    namespaces, structs, Classname = read(header_file)
    namespace = ':'.join(namespaces)
    classname = Classname.lower()

    indent = '\n        '
    pyx_structs = indent + indent.join(
        (t + ' ' + ', '.join(v)) for t, v in structs)
    struct_definition = '    struct %s:%s' % (Classname, pyx_structs)
    props = []
    for t, v in structs:
        props += v
    str_format = ', '.join(n + '=%s' for n in props)
    variable_names = ', '.join('self.' + n for n in props)
    property_list = []
    for typename, variables in structs:
        for prop in variables:
            property_list.append(PROP_TEMPLATE.format(**locals()))
    property_list = '\n'.join(property_list)
    timestamp = datetime.datetime.utcnow().isoformat()
    return MAIN_TEMPLATE.format(**locals())


MAIN_TEMPLATE = """\
# Automatically generated on {timestamp}
# by https://github.com/rec/make_pyx/make_pyx.py

cdef extern from "<{header_file}>" namespace "{namespace}":
{struct_definition}

    void clear({Classname}&)


cdef class _{Classname}(_Wrapper):
    cdef {Classname} _{classname};

    def __cinit__(self):
        clear(self._{classname})

    def clear(self):
        clear(self._{classname})

    def __str__(self):
        return '({str_format})' % (
            {variable_names})

{property_list}"""

PROP_TEMPLATE = """\
    property {prop}:
        def __get__(self):
            return self._{classname}.{prop}
        def __set__(self, {typename} x):
            self._{classname}.{prop} = x
"""

if __name__ == '__main__':
    for f in sys.argv[1:]:
        assert f.endswith('.h'), 'Not a header file: ' + f
        data = make(f)
        outfile = f[:-2] + '.pyx'
        open(outfile, 'w').write(data)
