"""Navigate the real place/section widgets in offline AppTests."""
from views.navigation import LEGACY, PLACES


def navigate(at, page):
    if page in LEGACY:
        place, section = LEGACY[page]
    else:
        place, section = page, PLACES[page][0]
    widget = next(w for w in at.radio if w.label == 'View')
    if widget.value != place:
        widget.set_value(place).run()
    controls = at.get('button_group')
    if controls and controls[0].value != section:
        controls[0].set_value(section).run()
    return at
