from django import template

register = template.Library()

STATUS_LABELS = {
    "saved": "Saved",
    "downloaded": "Downloaded",
    "printed": "Printed",
    "painted": "Painted",
    "gifted": "Gifted",
}

SITE_LABELS = {
    "printables": "Printables",
    "printables.com": "Printables",
    "makerworld": "MakerWorld",
    "makerworld.com": "MakerWorld",
    "thangs": "Thangs",
    "thangs.com": "Thangs",
    "thingiverse": "Thingiverse",
    "thingiverse.com": "Thingiverse",
    "myminifactory": "MyMiniFactory",
    "myminifactory.com": "MyMiniFactory",
    "cults3d": "Cults3D",
    "cults3d.com": "Cults3D",
    "upload": "Upload",
}


@register.filter
def status_label(value):
    return STATUS_LABELS.get(value, value.replace("_", " ").title())


@register.filter
def site_label(value):
    if not value:
        return "Unknown"
    return SITE_LABELS.get(value.lower(), value.replace(".com", "").title())


@register.filter
def get_item(mapping, key):
    if not mapping:
        return ""
    return mapping.get(key, "")


@register.filter
def initials(value):
    if not value:
        return "?"
    parts = value.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return value[:2].upper()
