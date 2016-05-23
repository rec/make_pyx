def make_enums(enum_classes, header_file, namespace, classname):
    enums, declarations = [], []
    for ec in enum_classes:
        enum_name, parts = (i.strip() for i in ec)
        parts = [p.strip() for p in parts.split(',')]
        if parts and parts[-1].startswith('last ='):
            parts.pop()
        enums.append((enum_name, parts))
        main = ENUM_CLASS_TEMPLATE.format(**locals())
        defs = ('    cdef %s %s' % (enum_name, p) for p in parts)
        declarations.append(main + '\n'.join(defs))

    decl = '\n\n'.join(declarations)
    if decl:
        decl += '\n'

    enum_names = []
    enum_types = {}
    for name, values in enums:
        enum_types[name] = set()
        values = ', '.join("'%s'" % v for v in values)
        enum_names.append('    %s_NAMES = %s' % (name.upper(), values))

    enum_names = '\n'.join(enum_names)
    if enum_names:
        enum_names = '\n%s\n' % enum_names

    return enums, decl, enum_names, enum_types


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
