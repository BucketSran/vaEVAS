"""Supported numeric $display format contract, shared with the Rust formatter."""
import re

_CONVERSION = re.compile(r'%(?:%|d|g|\.(?:[1-9]|[12][0-9]|3[0-2])g)')


def validate_format(format_string: str, argument_count: int) -> None:
    """Accept literals, %% and %d/%g/%.Ng with 1..32 significant digits."""
    count, offset = 0, 0
    while offset < len(format_string):
        if format_string[offset] != '%':
            offset += 1
            continue
        conversion = _CONVERSION.match(format_string, offset)
        if conversion is None:
            raise ValueError('$display supports only %d, %g, %.Ng (1..32) and %%')
        count += conversion.group() != '%%'
        offset = conversion.end()
    if count != argument_count:
        raise ValueError('$display format conversion count does not match numeric arguments')
