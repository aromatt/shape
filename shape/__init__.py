import types
import re

def apply_patterns(patterns, data):
    if patterns and isinstance(data, str):
        for pattern, replace_with in patterns.items():
            data = re.sub(pattern, replace_with, data)
    return data


def shape(data, key_patterns=None, describe_numbers=False, sort=False):
    """Return a best-effort summary of `data`, having nestedly replaced values
    with type names.
    - Assumes Nones are really unions (i.e. no schema has a field whose value is
      always None) so any type can override a NoneType.
    - Assumes lists are homogeneous, so the first-encountered non-NoneType type
      is used.
    - `key_patterns`: a dict of { regex => replacement } applied to all dict keys.
    - `describe_numbers`: return e.g. "int:nonzero" instead of "int"
    - `sort`: sort keys for determinism (e.g. for snapshot tests)
    """
    class Index:
        def __init__(self, i): self.i = i
        def __repr__(self): return f'Index<{self.i}>'
        def __hash__(self): return self.i
        def __eq__(self, other): return self.i == other.i
        def __lt__(self, other): return self.i < other.i

    def _get_paths(data, prefix=()):
        if isinstance(data, (types.GeneratorType, list, map, filter, tuple)):
            kv_iter = ((Index(i),v) for i, v in enumerate(data))
        elif isinstance(data, dict):
            kv_iter = data.items()
        else:
            typ = type(data)
            if describe_numbers and typ in (int, float):
                desc = 'zero' if data == 0 else 'nonzero'
                return [(f'{typ.__name__}:{desc}',)]
            else:
                return [(typ.__name__,)]
        paths = []
        for k,v in kv_iter:
            kv_paths = [(k, *p) for p in _get_paths(v, prefix)]
            paths += [(*prefix, *kvp) for kvp in kv_paths]
        return paths

    def _apply_patterns(paths):
        return [tuple(apply_patterns(key_patterns, x) for x in path)
                for path in paths]

    def _describe_numbers(paths):
        if not describe_numbers:
            return paths
        else:
            out = []
            for path in paths:
                if isinstance(path[-1], (int, float)):
                    desc = 'zero' if path[-1] == 0 else 'nonzero'
                    path[-1] = f'{type(path[-1])}:{desc}'
                out.append(path)
            return out

    def _collapse_paths(paths):
        paths = [tuple(map(lambda x: Index(0) if type(x) == Index else x, path))
                 for path in paths]
        # poor man's ordered set
        return list(dict.fromkeys(paths))

    def _merge_paths(paths):
        merged = {}
        for path in paths:
            cur = merged
            for i in range(len(path) - 1):
                key, *rest = path[i:]
                node = rest[0] if len(rest) == 1 else {}
                if key not in cur or cur[key] == 'NoneType':
                    cur[key] = node
                cur = cur[key]
        def _convert_lists(coll):
            if not isinstance(coll, dict) or len(coll) == 0:
                return coll
            if type(list(coll.keys())[0]) == Index:
                return [_convert_lists(v) for v in coll.values()]
            else:
                return {k: _convert_lists(v) for k,v in coll.items()}
        return _convert_lists(merged)

    paths = _get_paths(data)
    paths = _apply_patterns(paths)
    paths = _describe_numbers(paths)
    if sort:
        paths = sorted(paths)
    paths = _collapse_paths(paths)
    merged = _merge_paths(paths)
    return merged

if __name__ == '__main__':
    import json
    import sys
    print(json.dumps(shape(json.loads(sys.argv[1]))))
