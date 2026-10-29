"""Password policy for new credentials; never applied to existing sign-in."""
import re
import string

PASSWORD_REQUIREMENTS = 'Use at least 8 characters, including an uppercase letter, a lowercase letter, and a special character.'


def validate_new_password(value: str) -> str:
    if len(value) < 8 or not re.search(r'[A-Z]', value) or not re.search(r'[a-z]', value) or not any(char in string.punctuation for char in value):
        raise ValueError(PASSWORD_REQUIREMENTS)
    if len(value.encode('utf-8')) > 72:
        raise ValueError('Password must not exceed 72 UTF-8 bytes')
    return value
