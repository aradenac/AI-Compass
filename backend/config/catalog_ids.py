"""RFC 9562 UUIDv7 identities and permanent, friendly public IDs.

The word lists are deliberately curated, ASCII-only and versioned by source.
Existing IDs never depend on future dictionary versions.
"""
import secrets
import time
import uuid

ADJECTIVES = """amber brisk calm clear clever cool crisp daring eager fair fast gentle golden happy honest humble ivory kind lively lucky mellow merry mild modern noble open peaceful quiet rapid ready royal simple smart smooth soft solid steady sunny swift tidy vivid warm wise young""".split()
COLOURS = """amber azure beige black blue bronze brown coral cream cyan emerald gold gray green indigo ivory jade lilac lime mint navy olive orange pearl pink purple red rose ruby rust sage silver sky slate teal violet white yellow""".split()
NOUNS = """acorn arrow ash bay bear beacon birch bird blossom boat brook cedar cloud coast comet creek dawn deer dolphin dove eagle elm falcon fern field finch flame forest fox garden gate glade grove harbor hill island lake lantern leaf lighthouse maple meadow moon mountain oak ocean otter owl panda path pine planet pond quartz rabbit rain raven reef ridge river robin rock salmon shore sparrow star stone stream summit swan tiger trail tree valley wave whale willow wind wolf wood wren""".split()


def uuid7():
    """UUIDv7: 48-bit Unix milliseconds, version 7, RFC variant, 74 random bits."""
    milliseconds = time.time_ns() // 1_000_000
    if not 0 <= milliseconds < (1 << 48):
        raise ValueError("System time is outside UUIDv7 range")
    bits = (
        (milliseconds << 80)
        | (7 << 76)
        | (secrets.randbits(12) << 64)
        | (2 << 62)
        | secrets.randbits(62)
    )
    return uuid.UUID(int=bits)


PREFIXES = frozenset({"mdl", "prv", "hrn", "frm", "tsk", "mnt", "tcs", "gui", "cmp", "ptp", "ses", "run", "sol", "src", "wat", "fct", "evl", "rec", "thr", "msg", "wlp"})


def new_public_id(prefix="mdl"):
    if prefix not in PREFIXES:
        raise ValueError("Unregistered catalog public ID prefix")
    return "-".join((
        prefix,
        secrets.choice(ADJECTIVES),
        secrets.choice(COLOURS),
        secrets.choice(NOUNS),
    ))
