"""Password policy for new credentials; never applied to existing sign-in."""

PASSWORD_REQUIREMENTS = 'Use at least 8 characters.'


def validate_new_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError(PASSWORD_REQUIREMENTS)
    if len(value.encode('utf-8')) > 72:
        raise ValueError('Password must not exceed 72 UTF-8 bytes')
    return value
