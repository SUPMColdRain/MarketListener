"""Independent Provider probing, bounded retries, and safe report output."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from .base import (
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    ConfigurationRequirement,
    ErrorCategory,
    Provider,
    ProviderError,
    ProviderOperation,
    ProviderRequest,
    ProviderRunResult,
)


_SENSITIVE_KEY_PARTS = frozenset(
    {
        "token",
        "accesstoken",
        "refreshtoken",
        "apikey",
        "secret",
        "clientsecret",
        "password",
        "passphrase",
        "privatekey",
        "authorization",
        "credential",
        "credentials",
        "cookie",
        "account",
        "username",
        "key",
        "passwd",
        "pwd",
        "secretkey",
        "accesskey",
        "awssecretaccesskey",
        "awsaccesskeyid",
        "bearer",
        "auth",
        "authkey",
        "consumerkey",
        "sessionkey",
        "masterkey",
        "signingkey",
        "encryptionkey",
    }
)
_SENSITIVE_SUFFIXES = (
    "token",
    "apikey",
    "secret",
    "password",
    "privatekey",
    "credential",
    "username",
    "account",
    "passwd",
    "pwd",
    "secretkey",
    "accesskey",
    "authorization",
    "cookie",
    "auth",
    "authkey",
    "consumerkey",
    "sessionkey",
    "masterkey",
    "signingkey",
    "encryptionkey",
)
_SEPARATOR_PADDING = (
    r"[\s\x00-\x1f\x7f\x80-\x9f\u200b\u200c\u200d\u2060\ufeff\u180e"
    r"\u00ad\u034f\u061c\u200e\u200f\u202a-\u202e\u2061-\u2064]*"
)
_EQUALS_ASSIGNMENT = re.compile(
    r"\b(?P<key>[A-Za-z][A-Za-z0-9_-]*)(?P<pad_before>" + _SEPARATOR_PADDING + r")"
    r"(?P<separator>=|\uff1d|\ufe66|\u2a75)(?P<pad_after>" + _SEPARATOR_PADDING + r")"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s,;}&{\[]+)"
)
_COLON_ASSIGNMENT = re.compile(
    r"(?<![A-Za-z0-9_/-])(?P<key>[A-Za-z][A-Za-z0-9_-]*)(?P<pad_before>" + _SEPARATOR_PADDING + r")"
    r"(?P<separator>:(?!//)|\uff1a|\ufe55|\u2236|\ua789|\u02d0|\u1361)(?P<pad_after>" + _SEPARATOR_PADDING + r")"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s,;}&{\[]+)"
)
_XML_ELEMENT = re.compile(r"(?is)<(?P<key>[^\W\d][\w.:-]*)(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=key)\s*>")
_UNCLOSED_XML_ELEMENT = re.compile(r"(?is)<(?P<key>[^\W\d][\w.:-]*)(?P<attrs>[^>]*)>(?P<body>[^<]*)$")
_AUTH_SCHEME_TOKEN = re.compile(
    r"(?i)\b(Bearer|Basic|Digest)(?:\s|%20|%09|%0A|%0D|%5C|%u0020|\\u0020|\\u0009|\\u000a|\\u000d|\\x20|\\x09|\\x0a|\\x0d|\\U00000020|&#32;|&#x20;|&#9;|&#x9;|&#92;|&Tab;|&NewLine;|&bsol;|[\u00ad\u034f\u061c\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2060-\u2064\ufeff\u180e])+[^\s,;]+"
)
_URL_CREDENTIALS = re.compile(
    r"([a-z][a-z0-9+.-]*://)([^\s/@:]+)(?:[:：﹕∶꞉ː፡])([^\s/@]+)@", re.IGNORECASE
)
_HEADER = re.compile(r"(?im)^(?P<prefix>\s*(?P<key>[A-Za-z][A-Za-z0-9_-]*)\s*:\s*)(?P<value>.+)$")
_JSON_FIELD = re.compile(
    r'(?P<prefix>"(?P<key>[A-Za-z][A-Za-z0-9_-]*)"\s*:\s*)(?P<value>"(?:\\.|[^"\\])*"|null|true|false|[^,}\]\r\n{\[\"]+)(?!\s*:)',
)
_MARKDOWN_INLINE_FIELD = re.compile(r"`(?P<key>[A-Za-z][A-Za-z0-9_-]*)`\s*:\s*`(?P<value>[^`\r\n]*)`")
_JSON_DECODER = json.JSONDecoder()
_CONTROL_CHARS = "".join(chr(codepoint) for codepoint in list(range(0x00, 0x20)) + [0x7F] + list(range(0x80, 0xA0)))
_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\u2060\ufeff\u180e\u00ad\u034f\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2061\u2062\u2063\u2064"
_IGNORABLE_SEPARATOR_CHARS = _ZERO_WIDTH_CHARS + _CONTROL_CHARS
_MAX_REDACTION_DEPTH = 64
_MAX_JSON_CANDIDATES = 128
_MAX_JSON_CANDIDATE_CHARS = 8 * 1024
_MAX_PREFLIGHT_NORMALIZATION_ROUNDS = 4
_MAX_PREFLIGHT_VIEW_CHARS = 512 * 1024


def _is_ignorable_between(character: str) -> bool:
    """Whitespace plus control/zero-width characters used to split separators."""

    return character.isspace() or character in _IGNORABLE_SEPARATOR_CHARS


def _has_ignorable_format_char(text: str) -> bool:
    """Whether text contains literal Unicode format/control characters."""

    return any(character in _IGNORABLE_SEPARATOR_CHARS for character in text)


_HOMOGLYPH_MAP = str.maketrans(
    {
        0x0430: "a",
        0x0435: "e",
        0x043E: "o",
        0x0440: "p",
        0x0441: "c",
        0x0443: "y",
        0x0445: "x",
        0x0456: "i",
        0x0458: "j",
        0x0455: "s",
        0x0432: "b",
        0x043A: "k",
        0x043C: "m",
        0x043D: "h",
        0x0442: "t",
        0x03BF: "o",
        0x03B9: "i",
        0x03BD: "v",
        0x03C1: "p",
        0x03F2: "c",
        0x03B1: "a",
        0x03B5: "e",
        0x03C4: "t",
        0x0251: "a",
        0x03C3: "s",
        0x03C2: "s",
        0x0448: "w",
    }
)
_LEET_CHAR_MAP = {"0": "o", "1": "i", "2": "z", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"}
_CJK_CREDENTIAL_MAP = (
    ("密码", "password"),
    ("口令", "password"),
    ("密钥", "secret"),
    ("令牌", "token"),
    ("私钥", "privatekey"),
)


def redact_secrets(value: Any, *, secret_values: Iterable[str] = ()) -> Any:
    """Recursively redact credential-shaped values before any output boundary.

    Registered local values are replaced even when short; mappings and sequences
    preserve their shape so JSON reports remain machine-readable.
    """

    secrets = tuple(item for item in secret_values if item)
    return _redact_value(value, secrets)


def _redact_value(value: Any, secret_values: tuple[str, ...], depth: int = 0) -> Any:
    if depth >= _MAX_REDACTION_DEPTH:
        return "[redaction depth limit]"
    if isinstance(value, str):
        return _redact_text(value, secret_values)
    if isinstance(value, Mapping):
        return {
            str(key): (
                "***"
                if _is_sensitive_key(str(key)) or _contains_sensitive_key_candidate(str(key))
                else _redact_value(item, secret_values, depth + 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(_redact_value(item, secret_values, depth + 1) for item in value)
    if isinstance(value, list):
        return [_redact_value(item, secret_values, depth + 1) for item in value]
    if isinstance(value, set):
        return {_redact_value(item, secret_values, depth + 1) for item in value}
    if isinstance(value, BaseException):
        return _redact_text(str(value), secret_values)
    return value


def _normalise_key(key: str, *, loose: bool = False) -> str:
    """Normalize a key for sensitive-name comparison.

    The strict form keeps ASCII digits (so ``password1`` still strips to
    ``password``), while the loose form additionally applies common leet
    digit/symbol replacements (``passw0rd`` -> ``password``).  Both forms
    fold homoglyphs, NFKC/NFKD variants, combining marks and non-ASCII
    decimal digits so ``passw0rd``/``pässword``/``password١`` are all
    recognised.
    """

    normalized = unicodedata.normalize("NFKC", key).translate(_HOMOGLYPH_MAP)
    for chinese, latin in _CJK_CREDENTIAL_MAP:
        normalized = normalized.replace(chinese, latin)
    normalized = unicodedata.normalize("NFKD", normalized)
    characters: list[str] = []
    for character in normalized:
        if unicodedata.combining(character):
            continue
        if loose and character in _LEET_CHAR_MAP:
            characters.append(_LEET_CHAR_MAP[character])
        elif character.isdecimal():
            characters.append(str(unicodedata.digit(character)))
        else:
            characters.append(character)
    return "".join(character for character in characters if character.isalnum()).casefold()


def _is_near_sensitive_key(key: str, strict: str) -> bool:
    """Fail closed for non-CJK keys whose stripped form is close to a secret name.

    Keys containing non-ASCII alphabetic characters (diacritics, Cyrillic,
    Greek, mathematical alphanumerics) cannot be proven safe by exact
    matching alone; a bounded Levenshtein check against the sensitive name
    set catches obfuscations such as ``passwérd``/``paшword``/``pas𝐡ord``
    without touching pure-CJK keys such as ``账户``.
    """

    if len(strict) < 4:
        return False
    if not any(character.isalpha() and ord(character) > 0x7F for character in key):
        return False
    if not any(character.isalpha() and not (0x4E00 <= ord(character) <= 0x9FFF) for character in key):
        return False
    for part in _SENSITIVE_KEY_PARTS:
        if len(part) < 4:
            continue
        if abs(len(strict) - len(part)) > 2:
            continue
        previous = list(range(len(part) + 1))
        for row_index, left_character in enumerate(strict, 1):
            current = [row_index] + [0] * len(part)
            for column_index, right_character in enumerate(part, 1):
                current[column_index] = min(
                    previous[column_index] + 1,
                    current[column_index - 1] + 1,
                    previous[column_index - 1] + (left_character != right_character),
                )
            previous = current
        if previous[-1] <= 2:
            return True
    return False


def _is_sensitive_key(key: str) -> bool:
    strict = _normalise_key(key)
    loose = _normalise_key(key, loose=True)
    for normalized in (strict, loose):
        without_digits = normalized.rstrip("0123456789")
        if (
            normalized in _SENSITIVE_KEY_PARTS
            or without_digits in _SENSITIVE_KEY_PARTS
            or normalized.endswith(_SENSITIVE_SUFFIXES)
            or without_digits.endswith(_SENSITIVE_SUFFIXES)
        ):
            return True
    return _is_near_sensitive_key(key, strict)


def _redact_text(message: str, secret_values: tuple[str, ...]) -> str:
    complete_json = _redact_complete_json(message, secret_values)
    if complete_json is not None:
        return complete_json
    if _has_unsafe_preflight_sensitive_assignment(message, secret_values):
        return "[redacted sensitive text]"

    def redact_assignment(match: re.Match[str]) -> str:
        key = match.group("key")
        if _is_sensitive_key(key):
            return (
                f"{key}{match.group('pad_before')}{match.group('separator')}"
                f"{match.group('pad_after')}***"
            )
        return match.group(0)

    def redact_header(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}***" if _is_sensitive_key(match.group("key")) else match.group(0)

    def redact_xml_element(match: re.Match[str]) -> str:
        key = match.group("key")
        if _is_sensitive_key(key) and match.group("body").strip():
            return f"<{key}{match.group('attrs')}>***</{key}>"
        return match.group(0)

    def redact_unclosed_xml_element(match: re.Match[str]) -> str:
        key = match.group("key")
        if _is_sensitive_key(key) and match.group("body").strip():
            return f"<{key}{match.group('attrs')}>***"
        return match.group(0)

    redacted = _redact_embedded_json(message, secret_values)
    redacted = _JSON_FIELD.sub(redact_json_field, redacted)
    redacted = _MARKDOWN_INLINE_FIELD.sub(redact_markdown_field, redacted)
    if any(character in redacted for character in ("=", "\uff1d", "\ufe66", "\u2a75")):
        redacted = _EQUALS_ASSIGNMENT.sub(redact_assignment, redacted)
    if any(character in redacted for character in (":", "\uff1a", "\ufe55", "\u2236", "\ua789", "\u02d0", "\u1361")):
        redacted = _COLON_ASSIGNMENT.sub(redact_assignment, redacted)
    redacted = _XML_ELEMENT.sub(redact_xml_element, redacted)
    redacted = _UNCLOSED_XML_ELEMENT.sub(redact_unclosed_xml_element, redacted)
    redacted = _AUTH_SCHEME_TOKEN.sub(r"\1 ***", redacted)
    if _has_unsafe_url_userinfo(redacted):
        redacted = _URL_CREDENTIALS.sub(r"\1***:***@", redacted)
    redacted = _HEADER.sub(redact_header, redacted)
    for secret in sorted(set(secret_values), key=len, reverse=True):
        redacted = _replace_registered_secret(redacted, secret)
    return "[redacted sensitive text]" if _has_unsafe_residual_sensitive_assignment(redacted) else redacted


def _redact_complete_json(message: str, secret_values: tuple[str, ...]) -> str | None:
    """Redact a complete JSON object or array before applying text fallbacks.

    This deliberately has no embedded-fragment size cap: a complete, legal JSON
    payload is a structured value and must remain valid JSON after redaction.
    Broken or excessively deep payloads fall through to the bounded scanner and
    fail-closed residual detector below.
    """

    try:
        payload = json.loads(message)
    except (json.JSONDecodeError, RecursionError, ValueError):
        return None
    if not isinstance(payload, (dict, list)):
        return None
    return json.dumps(_redact_value(payload, secret_values), ensure_ascii=False, separators=(",", ":"))


def _has_unsafe_preflight_sensitive_assignment(message: str, secret_values: tuple[str, ...]) -> bool:
    """Check original text and a layer-independent escape-normalized view.

    Normalization is detection-only.  It collapses any run of backslashes that
    wraps a supported quote/backtick or printable ASCII JSON escape in one pass,
    so normal JSON serialization depth is not a security boundary.  A small
    fixed number of rounds handles escapes that *produce* a backslash (for
    example ``\\u005c``); remaining supported escapes are fail-closed only when
    they still contain a credential-shaped candidate.

    Percent-encoding and HTML entities are decoded into additional detection
    views so ``Bearer%20…``, ``accessToken%3D…``, ``accessToken&equals;…``
    and numeric entities cannot bypass the residual detector.
    """

    if _has_unsafe_residual_sensitive_assignment(message):
        return True
    if _has_unsafe_url_userinfo(message):
        return True
    if len(message) > _MAX_PREFLIGHT_VIEW_CHARS:
        return _contains_sensitive_key_candidate(message)

    views: list[str] = []
    view = message
    for _ in range(_MAX_PREFLIGHT_NORMALIZATION_ROUNDS):
        next_view = _decode_html_entities(_decode_percent_escapes(_collapse_preflight_escape_runs(view)))
        views.append(next_view)
        if next_view == view:
            break
        view = next_view

    for candidate_view in views:
        if candidate_view == message:
            continue
        if _has_unsafe_residual_sensitive_assignment(candidate_view):
            return True
        if any(_replace_registered_secret(candidate_view, secret) != candidate_view for secret in secret_values):
            return True
        if _has_unsafe_auth_scheme(candidate_view):
            return True
        if _has_unsafe_url_userinfo(candidate_view):
            return True
        if _has_unsafe_remaining_encoding(candidate_view):
            return True

    if _has_malformed_preflight_unicode_escape(message):
        malformed_view = _normalize_malformed_preflight_unicode_escapes(view)
        if _has_unsafe_residual_sensitive_assignment(malformed_view):
            return True
    return False


def _has_malformed_preflight_unicode_escape(text: str) -> bool:
    """Identify malformed ``\\u`` escapes without deciding their safety alone."""

    index = 0
    while index < len(text):
        if text[index : index + 2] != "\\u":
            index += 1
            continue
        digits = text[index + 2 : index + 6]
        if len(digits) != 4 or not all(digit in "0123456789abcdefABCDEF" for digit in digits):
            return True
        index += 6
    return False


def _normalize_malformed_preflight_unicode_escapes(text: str) -> str:
    """Detection-only view removing malformed ``\\u`` sequences.

    A malformed escape is a backslash followed by ``u`` whose next four
    characters are not all hexadecimal (or fewer than four remain).  Any
    leading run of backslashes belongs to the same malformed sequence, so it
    is removed as well; that is what JSON serialization layers leave in front
    of a malformed escape.  Removing the sequence lets the residual assignment
    detector see a sensitive key split by the malformed escape, without hiding
    ordinary prose such as ``C:\\users\\...`` or
    ``normal \\u12ZZ no credentials``.
    """

    fragments: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] == "\\":
            run_end = index + 1
            while run_end < length and text[run_end] == "\\":
                run_end += 1
            if run_end < length and text[run_end] == "u":
                digits = text[run_end + 1 : run_end + 5]
                if len(digits) != 4 or not all(digit in "0123456789abcdefABCDEF" for digit in digits):
                    index = min(run_end + 5, length)
                    continue
        fragments.append(text[index])
        index += 1
    return "".join(fragments)


def _decode_percent_escapes(text: str) -> str:
    """Decode ``%HH`` and ``%uHHHH`` percent escapes into a detection-only view."""

    fragments: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] == "%" and index + 1 < length and text[index + 1] in "uU" and index + 5 < length:
            digits = text[index + 2 : index + 6]
            if all(digit in "0123456789abcdefABCDEF" for digit in digits):
                fragments.append(chr(int(digits, 16)))
                index += 6
                continue
        if text[index] == "%" and index + 2 < length:
            digits = text[index + 1 : index + 3]
            if all(digit in "0123456789abcdefABCDEF" for digit in digits):
                fragments.append(chr(int(digits, 16)))
                index += 3
                continue
        fragments.append(text[index])
        index += 1
    return "".join(fragments)


_HTML_NUMERIC_ENTITY = re.compile(r"&#(?:x([0-9a-fA-F]{1,6})|([0-9]{1,7}));")
_HTML_NAMED_ENTITY = re.compile(
    r"&(equals|colon|Colon|ratio|Tab|NewLine|nbsp|sol|bsol|quest|num|apos|quot|grave|period|comma|semi|lsqb|rsqb|lcub|rcub|lpar|rpar);"
)
_HTML_ENTITY_VALUES = {
    "equals": "=",
    "colon": ":",
    "Colon": ":",
    "ratio": "\u2236",
    "Tab": "\t",
    "NewLine": "\n",
    "nbsp": " ",
    "sol": "/",
    "bsol": "\\",
    "quest": "?",
    "num": "#",
    "apos": "'",
    "quot": '"',
    "grave": "`",
    "period": ".",
    "comma": ",",
    "semi": ";",
    "lsqb": "[",
    "rsqb": "]",
    "lcub": "{",
    "rcub": "}",
    "lpar": "(",
    "rpar": ")",
}


def _decode_html_entities(text: str) -> str:
    """Decode common named and numeric HTML entities into a detection-only view."""

    def replace_numeric(match: re.Match[str]) -> str:
        hex_digits = match.group(1)
        decimal_digits = match.group(2)
        digits = hex_digits if hex_digits is not None else decimal_digits
        base = 16 if hex_digits is not None else 10
        codepoint = int(digits, base)
        if codepoint > 0x10FFFF:
            return match.group(0)
        return chr(codepoint)

    text = _HTML_NUMERIC_ENTITY.sub(replace_numeric, text)
    return _HTML_NAMED_ENTITY.sub(lambda match: _HTML_ENTITY_VALUES[match.group(1)], text)


_AUTH_SCHEME_VIEW = re.compile(
    r"(?i)\b(?:Bearer|Basic|Digest)(?:\s|[%&]|[\u200b\u200c\u200d\u2060\ufeff\u180e\u00ad\u034f\u061c\u200e\u200f\u202a-\u202e\u2061-\u2064\x00-\x1f\x7f\x80-\x9f])+[^\s,;]+"
)
_URL_USERINFO_VIEW = re.compile(r"[a-z][a-z0-9+.-]*://[^\s/@:]+[:：﹕∶꞉ː፡][^\s/@]+@", re.IGNORECASE)
_URL_USERINFO_REMAINING = re.compile(
    r"[a-z][a-z0-9+.-]*://[^\s/@]+(?:%[0-9a-fA-F]{2}|%[uU][0-9a-fA-F]{4}|&#(?:x[0-9a-fA-F]{1,6}|[0-9]{1,7});|&[A-Za-z]+;)[^\s/@]*",
    re.IGNORECASE,
)
_REMAINING_ENCODING = re.compile(
    r"%(?:[0-9a-fA-F]{2}|[uU][0-9a-fA-F]{4})|&#(?:x[0-9a-fA-F]{1,6}|[0-9]{1,7});|&[A-Za-z]+;|\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}|\\U[0-9a-fA-F]{4,8}"
)
_URL_USERINFO_MARKER = re.compile(r"[:：﹕∶꞉ː፡%&\\]")
_URL_USERINFO_COLONS = ":：﹕∶꞉ː፡"
_ENCODED_USERINFO_MARKER = re.compile(
    r"%(?:[0-9a-fA-F]{2}|[uU][0-9a-fA-F]{4})|&#(?:x[0-9a-fA-F]{1,6}|[0-9]{1,7});"
    r"|&[A-Za-z]+;|\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}|\\U[0-9a-fA-F]{4,8}"
)


def _has_unsafe_auth_scheme(text: str) -> bool:
    """Detect ``Bearer``/``Basic``/``Digest`` prefix plus token on a decoded view."""

    return _AUTH_SCHEME_VIEW.search(text) is not None


def _has_unsafe_url_userinfo(text: str) -> bool:
    """Detect URL userinfo ``scheme://user:pass@`` without regex backtracking."""

    search_from = 0
    while True:
        scheme = text.find("://", search_from)
        if scheme == -1:
            return False
        at = text.find("@", scheme + 3)
        if at != -1:
            segment = text[scheme + 3 : at]
            if (
                any(character in _URL_USERINFO_COLONS for character in segment)
                and " " not in segment
                and "\t" not in segment
                and "\n" not in segment
                and "\r" not in segment
                and "/" not in segment
            ):
                return True
        search_from = scheme + 3


def _has_encoded_url_userinfo(text: str) -> bool:
    """Detect encoded userinfo separators between ``://`` and ``@`` linearly."""

    search_from = 0
    while True:
        scheme = text.find("://", search_from)
        if scheme == -1:
            return False
        token_end = len(text)
        for stop in (" ", "\t", "\n", "\r", "/", "@"):
            position = text.find(stop, scheme + 3)
            if position != -1:
                token_end = min(token_end, position)
        if _ENCODED_USERINFO_MARKER.search(text[scheme + 3 : token_end]) is not None:
            return True
        search_from = scheme + 3


def _has_unsafe_remaining_encoding(text: str) -> bool:
    """Fail closed when decode-budget exhaustion still leaves encodings."""

    if _REMAINING_ENCODING.search(text) is None:
        return False
    return (
        _contains_sensitive_key_candidate(text)
        or _has_unsafe_auth_scheme(text)
        or _has_unsafe_url_userinfo(text)
        or _has_encoded_url_userinfo(text)
    )


def _contains_sensitive_key_candidate(text: str) -> bool:
    """Find credential-shaped key candidates while ignoring supported wrappers.

    This deliberately supports only the boundary probe.  It makes a residual
    fifth-or-deeper escaping layer conservative without applying unbounded
    decoding, and lets malformed escapes fail closed only when adjacent to an
    explicit credential-shaped candidate.
    """

    token: list[str] = []

    def flush() -> bool:
        if not token:
            return False
        candidate = "".join(token)
        token.clear()
        return _is_sensitive_key(candidate)

    index = 0
    while index < len(text):
        current = text[index]
        if current == "\\":
            run_end = index + 1
            while run_end < len(text) and text[run_end] == "\\":
                run_end += 1
            if run_end < len(text) and text[run_end] in "\"'`":
                index = run_end + 1
                continue
            if run_end < len(text) and text[run_end] == "u":
                digits = text[run_end + 1 : run_end + 5]
                if len(digits) == 4 and all(digit in "0123456789abcdefABCDEF" for digit in digits):
                    character = chr(int(digits, 16))
                    if character.isalnum() or character in "_-":
                        token.append(character)
                    elif flush():
                        return True
                    index = run_end + 5
                    continue
                # Treat malformed ``\\+u`` as a zero-width wrapper for this
                # candidate-only check; normal text without a credential-shaped
                # key remains unchanged by the caller.
                index = min(run_end + 5, len(text))
                continue
        if current.isalnum() or current in "_-@":
            token.append(current)
        elif flush():
            return True
        index += 1
    return flush()


def _collapse_preflight_escape_runs(text: str) -> str:
    """Linearly normalize supported escaping without changing emitted text."""

    fragments: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        current = text[index]
        if current != "\\":
            fragments.append(current)
            index += 1
            continue
        run_end = index + 1
        while run_end < length and text[run_end] == "\\":
            run_end += 1
        if run_end >= length:
            fragments.append(text[index:run_end])
            break
        escaped = text[run_end]
        if escaped in "\"'`":
            fragments.append(escaped)
            index = run_end + 1
            continue
        if escaped == "u" and run_end + 4 < length:
            digits = text[run_end + 1 : run_end + 5]
            if all(digit in "0123456789abcdefABCDEF" for digit in digits):
                fragments.append(chr(int(digits, 16)))
                index = run_end + 5
                continue
        if escaped == "x" and run_end + 2 < length:
            digits = text[run_end + 1 : run_end + 3]
            if all(digit in "0123456789abcdefABCDEF" for digit in digits):
                fragments.append(chr(int(digits, 16)))
                index = run_end + 3
                continue
        if escaped == "U" and run_end + 8 < length:
            digits = text[run_end + 1 : run_end + 9]
            if all(digit in "0123456789abcdefABCDEF" for digit in digits):
                codepoint = int(digits, 16)
                if codepoint <= 0x10FFFF:
                    fragments.append(chr(codepoint))
                    index = run_end + 9
                    continue
        if escaped == "U" and run_end + 4 < length:
            digits = text[run_end + 1 : run_end + 5]
            if all(digit in "0123456789abcdefABCDEF" for digit in digits):
                fragments.append(chr(int(digits, 16)))
                index = run_end + 5
                continue
        fragments.append(text[index:run_end])
        index = run_end
    return "".join(fragments)


def _has_unsafe_residual_sensitive_assignment(text: str) -> bool:
    """Detect unproven sensitive assignments without relying on regex matches.

    The function is used both as a preflight on original free text and as a
    final defense after substitutions.  If a credential-shaped key is followed
    by any value form other than a complete ``***`` sentinel, the surrounding
    text is not safe to publish.  Returning one fixed placeholder is intentional
    fail-closed behavior: no parser budget or earlier match position can bypass
    either pass.
    """

    index = 0
    length = len(text)
    while index < length:
        key, after_key = _read_assignment_key(text, index)
        if key is None:
            index += 1
            continue
        value_start = _read_assignment_value_start(text, after_key)
        if value_start is None:
            index = max(index + 1, after_key)
            continue
        if _is_sensitive_key(key) and not _is_known_redacted_value(text, value_start):
            return True
        index = max(index + 1, after_key)
    return False


def _read_assignment_key(text: str, index: int) -> tuple[str | None, int]:
    """Read a quoted, backticked, or bare key from one text position."""

    length = len(text)
    current = text[index]
    if current in "\"'`":
        end = text.find(current, index + 1)
        if end == -1:
            return None, index + 1
        candidate = text[index + 1 : end].strip(" \t\r\n\f\v" + _ZERO_WIDTH_CHARS)
        if candidate and candidate[0].isalpha() and all(
            char.isalnum() or char in "_-." or char == "@" or _is_ignorable_between(char) for char in candidate
        ):
            return candidate, end + 1
        return None, end + 1
    if not current.isalpha():
        return None, index + 1
    end = index + 1
    while end < length and (
        text[end].isalnum() or text[end] in "_-." or text[end] == "@" or _is_ignorable_between(text[end])
    ):
        end += 1
    return text[index:end], end


def _read_assignment_value_start(text: str, after_key: int) -> int | None:
    """Return the value position after a longest-match ``:=``, ``:``, or ``=``.

    Whitespace includes CRLF/LF and zero-width format characters, and the
    separators include full-width ``：``/``＝``, so neither a split
    key/separator nor a split colon/equal pair can be converted into a
    misleading safe scalar by an earlier field substitution.
    """

    cursor = after_key
    length = len(text)
    while cursor < length and _is_ignorable_between(text[cursor]):
        cursor += 1
    if cursor >= length:
        return None
    if text[cursor] in (":", "\uff1a", "\ufe55", "\u2236", "\ua789", "\u02d0", "\u1361"):
        cursor += 1
        while cursor < length and _is_ignorable_between(text[cursor]):
            cursor += 1
        if cursor < length and text[cursor] in ("=", "\uff1d", "\ufe66", "\u2a75"):
            cursor += 1
            while cursor < length and _is_ignorable_between(text[cursor]):
                cursor += 1
        return cursor
    if text[cursor] in ("=", "\uff1d", "\ufe66", "\u2a75"):
        cursor += 1
        while cursor < length and _is_ignorable_between(text[cursor]):
            cursor += 1
        return cursor
    return None


def _is_known_redacted_value(text: str, index: int) -> bool:
    """Accept only the exact safe sentinel, optionally wrapped in one quote."""

    length = len(text)
    if text.startswith("***", index):
        return _is_value_boundary(text, index + 3)
    if index >= length or text[index] not in "\"'`":
        return False
    quote = text[index]
    if not text.startswith("***", index + 1):
        return False
    end = index + 4
    return end < length and text[end] == quote and _is_value_boundary(text, end + 1)


def _is_value_boundary(text: str, index: int) -> bool:
    return index >= len(text) or text[index].isspace() or text[index] in ",;}&])>`'\""


def redact_json_field(match: re.Match[str]) -> str:
    """Keep a quoted JSON property name while replacing its value validly."""

    key = match.group("key")
    return f'{match.group("prefix")}"***"' if _is_sensitive_key(key) else match.group(0)


def redact_markdown_field(match: re.Match[str]) -> str:
    key = match.group("key")
    return f"`{key}`: `***`" if _is_sensitive_key(key) else match.group(0)


def _redact_embedded_json(message: str, secret_values: tuple[str, ...]) -> str:
    """Structurally redact every complete object/array embedded in text.

    ``raw_decode`` returns the exact end position of a JSON value.  Advancing
    from that end prevents the scanner from repeatedly processing a fragment;
    when a malformed outer object is encountered, moving one character allows
    a later valid nested object/array to be considered safely.
    """

    fragments: list[str] = []
    copied_until = 0
    index = 0
    candidates = 0
    while index < len(message) and candidates < _MAX_JSON_CANDIDATES:
        if message[index] not in "{[":
            index += 1
            continue
        candidates += 1
        try:
            payload, relative_end = _JSON_DECODER.raw_decode(message[index : index + _MAX_JSON_CANDIDATE_CHARS])
            end = index + relative_end
        except (json.JSONDecodeError, RecursionError, ValueError):
            index += 1
            continue
        if not isinstance(payload, (dict, list)) or end <= index:
            index += 1
            continue
        fragments.extend((message[copied_until:index], json.dumps(_redact_value(payload, secret_values), ensure_ascii=False, separators=(",", ":"))))
        copied_until = end
        index = end
    if copied_until == 0:
        return message
    fragments.append(message[copied_until:])
    return "".join(fragments)


def _replace_registered_secret(text: str, secret: str) -> str:
    """Replace complete registered values without touching JSON property names.

    A short value is still protected when it appears as a complete token in an
    exception or path.  Substring matching is deliberately avoided so a value
    such as ``id`` cannot corrupt unrelated words, and a quoted JSON key is
    detected by its following colon and left intact.
    """

    fragments: list[str] = []
    cursor = 0
    for match in re.finditer(re.escape(secret), text):
        start, end = match.span()
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        is_complete_token = (not before or not before.isalnum()) and (not after or not after.isalnum())
        is_json_key = (
            start > 0
            and end < len(text)
            and text[start - 1] == '"'
            and text[end] == '"'
            and text[end + 1 :].lstrip().startswith(":")
        )
        if not is_complete_token or is_json_key:
            continue
        fragments.extend((text[cursor:start], "***"))
        cursor = end
    if cursor == 0:
        return text
    fragments.append(text[cursor:])
    return "".join(fragments)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must not be negative")

    def delay_after(self, attempt: int) -> float:
        return self.base_delay_seconds * (2 ** (attempt - 1))


@dataclass(frozen=True)
class ProbeReport:
    generated_at: str
    results: Sequence[ProviderRunResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "generated_at": self.generated_at,
            "providers": [result.to_dict() for result in self.results],
        }


@dataclass(frozen=True)
class _InvocationOutcome:
    result: ProviderRunResult
    timed_out: bool = False


class ProbeRunner:
    """Probe every provider independently, with bounded run-level retries.

    Adapter-level capability probes stay independent.  A runner retry only
    applies when an entire provider invocation cannot produce its capability
    list (for example, a timeout or rate limit), never erasing a partial list.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 45.0,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = sleep,
        now: Callable[[], datetime] | None = None,
        secret_values: Iterable[str] = (),
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._secret_values = tuple(secret_values)

    def run(self, providers: Iterable[Provider]) -> ProbeReport:
        results = [self._run_one(provider) for provider in providers]
        return ProbeReport(generated_at=self._timestamp(), results=results)

    def write_reports(self, report: ProbeReport, report_dir: Path) -> tuple[Path, Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        machine_path = report_dir / "provider-capabilities.json"
        human_path = report_dir / "provider-capabilities.md"
        safe_report = redact_secrets(report.to_dict(), secret_values=self._secret_values)
        machine_path.write_text(json.dumps(safe_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        human_path.write_text(self._human_report(safe_report), encoding="utf-8")
        return machine_path, human_path

    def _run_one(self, provider: Provider) -> ProviderRunResult:
        started_at = self._timestamp()
        missing = tuple(provider.missing_configuration_requirements())
        if missing:
            return ProviderRunResult(
                run_id=f"probe-{provider.name}-{uuid4().hex[:12]}",
                source=provider.source,
                started_at=started_at,
                completed_at=self._timestamp(),
                capabilities=tuple(self._configuration_blocked_capability(item) for item in missing),
            )

        for attempt in range(1, self._retry_policy.max_attempts + 1):
            outcome = self._invoke_once(provider, started_at)
            result = outcome.result
            error = result.capabilities[0].error if len(result.capabilities) == 1 else None
            if outcome.timed_out or error is None or error.category not in {ErrorCategory.NETWORK, ErrorCategory.QUOTA}:
                return result
            if attempt == self._retry_policy.max_attempts:
                return result
            self._sleeper(self._retry_policy.delay_after(attempt))
        raise AssertionError("retry loop must return")

    def _invoke_once(self, provider: Provider, started_at: str) -> _InvocationOutcome:
        run_id = f"probe-{provider.name}-{uuid4().hex[:12]}"
        completed = Event()
        capabilities: Sequence[Capability] = ()
        raised: Exception | None = None

        def invoke() -> None:
            nonlocal capabilities, raised
            try:
                capabilities = tuple(provider.probe_capabilities())
            except Exception as error:  # External SDKs may use arbitrary exception classes.
                raised = error
            finally:
                completed.set()

        Thread(target=invoke, name=f"provider-probe-{provider.name}", daemon=True).start()
        if not completed.wait(self._timeout_seconds):
            return _InvocationOutcome(
                self._error_result(
                    provider,
                    run_id,
                    started_at,
                    ProviderError(ErrorCategory.NETWORK, f"provider probe exceeded {self._timeout_seconds:g} seconds"),
                ),
                timed_out=True,
            )
        if raised is not None:
            category = raised.category if isinstance(raised, ProviderError) else ErrorCategory.UNKNOWN
            return _InvocationOutcome(self._error_result(provider, run_id, started_at, ProviderError(category, str(raised))))
        return _InvocationOutcome(
            ProviderRunResult(
                run_id=run_id,
                source=provider.source,
                started_at=started_at,
                completed_at=self._timestamp(),
                capabilities=tuple(self._sanitize_capability(item) for item in capabilities),
            )
        )

    def _error_result(self, provider: Provider, run_id: str, started_at: str, error: ProviderError) -> ProviderRunResult:
        return ProviderRunResult(
            run_id=run_id,
            source=provider.source,
            started_at=started_at,
            completed_at=self._timestamp(),
            capabilities=(self._run_error_capability(error),),
        )

    def _sanitize_capability(self, capability: Capability) -> Capability:
        error = capability.error
        evidence = capability.evidence
        return replace(
            capability,
            detail=redact_secrets(capability.detail, secret_values=self._secret_values),
            limitations=tuple(redact_secrets(item, secret_values=self._secret_values) for item in capability.limitations),
            evidence=(
                replace(evidence, summary=redact_secrets(evidence.summary, secret_values=self._secret_values))
                if evidence is not None
                else None
            ),
            error=(
                ProviderError(error.category, redact_secrets(error.message, secret_values=self._secret_values))
                if error is not None
                else None
            ),
        )

    def _configuration_blocked_capability(self, requirement: ConfigurationRequirement) -> Capability:
        error = ProviderError(ErrorCategory.CONFIGURATION, "required local configuration is absent")
        return Capability(
            requirement.capability_id,
            CapabilityStatus.BLOCKED,
            detail=requirement.description,
            registration=CapabilityRegistration(
                requirement.capability_id,
                requirement.description,
                ProviderRequest(ProviderOperation.OTHER),
            ),
            limitations=("configure this value locally outside the repository",),
            error=error,
        )

    def _run_error_capability(self, error: ProviderError) -> Capability:
        return Capability(
            "provider-run-error",
            CapabilityStatus.FAILED,
            detail="provider probe did not return individual capability results",
            registration=CapabilityRegistration(
                "provider-run-error",
                "Provider run-level error represented as an independent capability",
                ProviderRequest(ProviderOperation.HEALTH_CHECK),
            ),
            error=ProviderError(error.category, redact_secrets(error.message, secret_values=self._secret_values)),
        )

    def _timestamp(self) -> str:
        return self._now().astimezone(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _human_report(report: Mapping[str, object]) -> str:
        lines = ["# Provider capability report", "", f"Generated at: {report['generated_at']}", ""]
        providers = report["providers"]
        if not providers:
            lines.extend(["No providers were registered.", ""])
        for result in providers:
            assert isinstance(result, Mapping)
            source = result["source"]
            assert isinstance(source, Mapping)
            lines.extend([f"## {source['display_name']}", ""])
            capabilities = result["capabilities"]
            assert isinstance(capabilities, list)
            for capability in capabilities:
                assert isinstance(capability, Mapping)
                registration = capability["registration"]
                assert isinstance(registration, Mapping)
                lines.append(f"- {registration['id']}: {capability['status']}")
                error = capability.get("error")
                if isinstance(error, Mapping):
                    lines.append(f"  - error: {error['category']} - {error['message']}")
            lines.append("")
        return "\n".join(lines)
