"""Shell evidence from the same read-only inventory as Data."""
import contextlib

from fastapi import APIRouter, BackgroundTasks

from brownstone import navigation, pipeline, scan_inputs

from . import context
from .models import Sources

router = APIRouter()


def waiting(source):
    if source['provider'] != 'addon':
        return 0, None
    try:
        if source.get('drop_folder'):
            preview = scan_inputs.preview_inputs(source)
            ids = {sid for file in preview.files if file.preview for sid in file.preview.new_ids}
            errors = '; '.join(file.error for file in preview.files if file.error)
            return (None, errors) if errors else (len(ids), None)
        return len(pipeline.preview_scans(source).new_ids), None
    except (OSError, ValueError, RuntimeError) as error:
        return None, f'Unable to check new scans: {error}. Open Data to review.'


def warm(source):
    """Build the explorer while the shell renders, so the first search is quick."""
    with contextlib.suppress(Exception):  # A warm-up only: the search or record request reports a failure.
        context.explorer(source)


@router.get('/sources', response_model=Sources)
def sources(background: BackgroundTasks, source: str = '', inventory: bool = True):
    options = context.enabled()
    chosen = context.resolve(source, options) if source or len(options) == 1 else None
    if chosen and not inventory:  # The shell's first, fast request.
        background.add_task(warm, chosen)
    count, error = waiting(chosen) if chosen and inventory else (None, None)
    return Sources(sources=[context.option(s) for s in options], selected=context.option(chosen) if chosen else None,
                   evidence=context.evidence(chosen) if chosen else None, waiting=count, waiting_error=error,
                   questions=navigation.QUESTIONS)
