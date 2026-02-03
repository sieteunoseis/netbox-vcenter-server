"""Template tags for NetBox vCenter plugin."""

from django import template

register = template.Library()


@register.filter
def get_key(dictionary, key):
    """Get a value from a dictionary by key.

    Usage: {{ mydict|get_key:keyvar }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
