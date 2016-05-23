#!/usr/bin/env python3

from . read_header_file import Context

def make_enums(enum_classes, header_file, namespace, classname):
    enums, declarations = [], []
    for ec in enum_classes:
        enum_name, parts = (i.strip() for i in ec)
        parts = [(p[:-1] if p.endswith(',') else p) for p in parts.split()]
        try:
            parts.remove('size')
        except ValueError:
            pass
        enums.append((enum_name, parts))
        main = ENUM_CLASS_TEMPLATE.format(**locals())
        defs = ('    cdef %s %s' % (enum_name, p) for p in parts)
        declarations.append(main + '\n'.join(defs))

    decl = '\n\n'.join(declarations)
    if decl:
        decl += '\n'
    return Context(enums=enums, declarations=decl)
