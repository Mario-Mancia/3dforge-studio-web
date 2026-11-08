from django.core.exceptions import ValidationError


def mensaje_de(error):
    if isinstance(error, ValidationError):
        return " ".join(error.messages)
    return str(error)
