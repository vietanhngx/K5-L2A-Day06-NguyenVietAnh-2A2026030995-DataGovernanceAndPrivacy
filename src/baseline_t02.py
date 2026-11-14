"""T02 required baseline: global Laplacian sharpness, dev-frozen threshold."""
from .pipeline import run_method


def run(ctx):
    run_method(ctx, "laplacian")
