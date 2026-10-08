"""Lossless model JSON normalization; never choose between conflicting values."""
import json
import math


class _ObjectPairs(list):
    pass


class _Number(str):
    """Keep number spellings until duplicates have been compared without rounding."""


def _identical(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_identical(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_identical(a, b) for a, b in zip(left, right))
    return left == right


def parse_model_output(raw):
    """Return the unchanged JSON value plus an auditable list of removed duplicates.

    Only equal decoded strings/booleans/nulls, equal number spellings, and equal
    nested structures can coalesce. No missing fields, prose, or values are fixed.
    The provider envelope and all other strict_json callers remain strict.
    """
    repairs = []

    def constant(_):
        raise ValueError('NonFiniteJSON')

    def pointer(path, key):
        return path + '/' + str(key).replace('~', '~0').replace('/', '~1')

    def normalize(value, path=''):
        if isinstance(value, _ObjectPairs):
            result = {}
            for key, item in value:
                child = pointer(path, key)
                item = normalize(item, child)
                if key in result:
                    if not _identical(result[key], item):
                        raise ValueError('ConflictingJSONKey:' + child)
                    repairs.append({'operation': 'coalesce_identical_duplicate', 'path': child})
                else:
                    result[key] = item
            return result
        if isinstance(value, list):
            return [normalize(item, pointer(path, i)) for i, item in enumerate(value)]
        return value

    def numbers(value):
        if isinstance(value, _Number):
            if any(char in value for char in '.eE'):
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError('NonFiniteJSON')
                return number
            return int(value)
        if isinstance(value, dict):
            return {key: numbers(item) for key, item in value.items()}
        if isinstance(value, list):
            return [numbers(item) for item in value]
        return value

    parsed = json.loads(raw, object_pairs_hook=_ObjectPairs, parse_int=_Number,
                        parse_float=_Number, parse_constant=constant)
    result = numbers(normalize(parsed))
    if not isinstance(result, dict):
        raise ValueError('ExpectedJSONObject')
    return result, {'parser': 'model-json-v1', 'repairs': repairs}


def normalize_empty_extras(value, schema):
    """Remove only null/empty-string fields explicitly forbidden by the schema.

    A nonempty unexpected assertion must still fail validation, not disappear
    before semantic review. Known fields, booleans, zero and containers stay intact.
    """
    repairs=[]
    def walk(item, rule, path=''):
        if not isinstance(rule,dict):return item
        if isinstance(item,dict):
            props=rule.get('properties',{});result={}
            for key,child in item.items():
                pointer=path+'/'+key.replace('~','~0').replace('/','~1')
                if key not in props and rule.get('additionalProperties') is False and (child is None or type(child) is str and child==''):
                    repairs.append({'operation':'remove_empty_unrecognized_field','path':pointer,'original_value':child})
                    continue
                result[key]=walk(child,props.get(key,{}),pointer)
            return result
        if isinstance(item,list):
            prefix=rule.get('prefixItems',[])
            return [walk(child,prefix[i] if i<len(prefix) else rule.get('items',{}),path+'/'+str(i)) for i,child in enumerate(item)]
        return item
    return walk(value,schema),repairs
