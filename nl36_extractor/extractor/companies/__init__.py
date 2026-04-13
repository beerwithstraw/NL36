from .bajaj_general import parse_bajaj_general
from .ecgc import parse_ecgc

PARSER_REGISTRY = {
    "parse_bajaj_general": parse_bajaj_general,
    "parse_ecgc":          parse_ecgc,
}
