"""VMT (Valve Material Type) reader/writer -- pure Python, no dependencies.

VMT files are a simple, KeyValues-style hierarchical text format:

    "LightmappedGeneric"
    {
        "$basetexture" "brick/brick01"
        "$bumpmap"     "brick/brick01_normal"
        "$surfaceprop" "brick"
    }

Parsing is "loose" (matching VTFLib's default PARSE_MODE_LOOSE): multiple
top-level groups are merged into the first one, comments (``//``) are
stripped, and bare (unquoted) numeric values are auto-typed as int/float.
"""
import re

_TOKEN_RE = re.compile(r'//[^\n]*|"([^"\n]*)"|(\{)|(\})|(\S+)')


class VMTNode:
    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name


class VMTValueNode(VMTNode):
    __slots__ = ('value',)

    def __init__(self, name, value):
        super().__init__(name)
        self.value = value

    def __repr__(self):
        return f'{type(self).__name__}({self.name!r}, {self.value!r})'


class VMTStringNode(VMTValueNode):
    pass


class VMTIntegerNode(VMTValueNode):
    pass


class VMTFloatNode(VMTValueNode):
    pass


class VMTGroupNode(VMTNode):
    __slots__ = ('nodes',)

    def __init__(self, name):
        super().__init__(name)
        self.nodes = []

    # -- building --------------------------------------------------------
    def add_node(self, node):
        self.nodes.append(node)
        return node

    def add_group(self, name):
        return self.add_node(VMTGroupNode(name))

    def add_string(self, name, value):
        return self.add_node(VMTStringNode(name, str(value)))

    def add_integer(self, name, value):
        return self.add_node(VMTIntegerNode(name, int(value)))

    def add_float(self, name, value):
        return self.add_node(VMTFloatNode(name, float(value)))

    def remove(self, node):
        self.nodes.remove(node)

    # -- lookup ------------------------------------------------------------
    def get(self, name, default=None):
        low = name.lower()
        for n in self.nodes:
            if n.name.lower() == low:
                return n
        return default

    def __getitem__(self, name):
        node = self.get(name)
        if node is None:
            raise KeyError(name)
        return node.value if isinstance(node, VMTValueNode) else node

    def __setitem__(self, name, value):
        node = self.get(name)
        if isinstance(node, VMTValueNode):
            node.value = value
        elif isinstance(value, bool):
            self.add_integer(name, int(value))
        elif isinstance(value, int):
            self.add_integer(name, value)
        elif isinstance(value, float):
            self.add_float(name, value)
        else:
            self.add_string(name, value)

    def __contains__(self, name):
        return self.get(name) is not None

    def __iter__(self):
        return iter(self.nodes)

    def to_dict(self):
        out = {}
        for n in self.nodes:
            out[n.name] = n.to_dict() if isinstance(n, VMTGroupNode) else n.value
        return out

    def __repr__(self):
        return f'VMTGroupNode({self.name!r}, {len(self.nodes)} nodes)'


def _tokenize(text):
    tokens = []
    for m in _TOKEN_RE.finditer(text):
        if m.group(0).startswith('//'):
            continue
        if m.group(1) is not None:
            tokens.append(('Q', m.group(1)))
        elif m.group(2):
            tokens.append(('{', '{'))
        elif m.group(3):
            tokens.append(('}', '}'))
        elif m.group(4):
            tokens.append(('U', m.group(4)))
    return tokens


def _coerce(raw):
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


class _Parser:
    """Recursive-descent parser matching VTFLib's loose VMT grammar."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self):
        root = None
        while self._peek() is not None:
            kind, name = self._next()
            if kind not in ('Q', 'U'):
                raise ValueError(f"expected shader name, got {name!r}")
            group = VMTGroupNode(name)
            self._parse_group(group)
            if root is None:
                root = group
            else:
                root.nodes.extend(group.nodes)  # loose mode: merge extra roots
        if root is None:
            raise ValueError("empty VMT file")
        return root

    def _parse_group(self, group):
        kind, _ = self._next()
        if kind != '{':
            raise ValueError("expected open brace")
        while True:
            tok = self._peek()
            if tok is None:
                return
            if tok[0] == '}':
                self._next()
                return
            kind, name = self._next()
            if kind not in ('Q', 'U'):
                raise ValueError(f"expected group/attribute name, got {name!r}")
            nxt = self._peek()
            if nxt is not None and nxt[0] == '{':
                sub = VMTGroupNode(name)
                self._parse_group(sub)
                group.add_node(sub)
            elif nxt is not None and nxt[0] in ('Q', 'U'):
                vkind, value = self._next()
                if vkind == 'Q':
                    group.add_node(VMTStringNode(name, value))
                else:
                    parts = [value]
                    while self._peek() is not None and self._peek()[0] == 'U':
                        parts.append(self._next()[1])
                    raw = ' '.join(parts)
                    coerced = _coerce(raw)
                    if isinstance(coerced, int):
                        group.add_node(VMTIntegerNode(name, coerced))
                    elif isinstance(coerced, float):
                        group.add_node(VMTFloatNode(name, coerced))
                    else:
                        group.add_node(VMTStringNode(name, raw))
            else:
                raise ValueError("expected open brace or attribute value")


class VMTFile:
    """A VMT material file: a single root :class:`VMTGroupNode`."""

    def __init__(self, root=None):
        self.root = root

    # -- parsing -------------------------------------------------------------
    @classmethod
    def loads(cls, text):
        return cls(_Parser(_tokenize(text)).parse())

    @classmethod
    def load(cls, source):
        if isinstance(source, (bytes, bytearray)):
            text = source.decode('utf-8', errors='replace')
        elif hasattr(source, 'read'):
            data = source.read()
            text = data.decode('utf-8', errors='replace') if isinstance(data, (bytes, bytearray)) else data
        else:
            with open(source, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        return cls.loads(text)

    # -- writing -------------------------------------------------------------
    def dumps(self):
        lines = []
        self._dump_group(self.root, 0, lines)
        return '\n'.join(lines) + '\n'

    @staticmethod
    def _dump_group(group, level, lines):
        indent = '\t' * level
        lines.append(f'{indent}"{group.name}"')
        lines.append(f'{indent}{{')
        for node in group.nodes:
            if isinstance(node, VMTGroupNode):
                VMTFile._dump_group(node, level + 1, lines)
            else:
                lines.append(f'{indent}\t"{node.name}" "{node.value}"')
        lines.append(f'{indent}}}')

    def save(self, dest=None):
        text = self.dumps()
        if dest is not None:
            if hasattr(dest, 'write'):
                dest.write(text)
            else:
                with open(dest, 'w', encoding='utf-8', newline='\r\n') as f:
                    f.write(text)
        return text

    @classmethod
    def create(cls, shader_name):
        return cls(VMTGroupNode(shader_name))

    def __repr__(self):
        return f'VMTFile({self.root!r})'
