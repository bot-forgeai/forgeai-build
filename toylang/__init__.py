"""toylang: a tiny interpreted scripting language.

Numbers, strings, booleans, nil, variables, arithmetic/comparison/
logical operators, if/else, while, functions with closures, and a
handful of builtins (print, len). Implemented as a straightforward
lexer -> recursive-descent parser -> tree-walking interpreter, in the
classic "build your own language" shape.
"""
