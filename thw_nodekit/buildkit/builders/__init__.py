"""Builder modules for build processes."""

from typing import Type
import logging

from thw_nodekit.config import Config
from .base import BaseBuilder
from .agave import AgaveBuilder
from .jito import JitoBuilder
from .firedancer import FiredancerBuilder

logger = logging.getLogger(__name__)

BUILDER_MAP = {
    "agave": AgaveBuilder,
    "jito": JitoBuilder,
    "firedancer": FiredancerBuilder,
}

def get_builder(
    config: Config,
    client: str,
    repo_type: str,
    tag: str,
    update_symlink: bool,
    build_threads: int,
    native_build: bool
) -> BaseBuilder:
    """Factory function to get the correct builder instance.

    Args:
        config: Configuration object.
        client: Client name (e.g., 'agave', 'jito', 'firedancer').
        repo_type: Repository type ('official' or 'mod').
        tag: Release tag string.
        update_symlink: Boolean indicating if symlink should be updated.
        build_threads: Number of parallel build jobs.
        native_build: Boolean indicating if the build is native.

    Returns:
        An instance of the appropriate BaseBuilder subclass.

    Raises:
        ValueError: If the client name is not recognized.
    """
    builder_class: Optional[Type[BaseBuilder]] = BUILDER_MAP.get(client.lower())

    if builder_class:
        logger.info(f"Using builder: {builder_class.__name__}")
        return builder_class(
            config=config,
            client=client,
            repo_type=repo_type,
            tag=tag,
            update_symlink=update_symlink,
            build_threads=build_threads,
            native_build=native_build
        )
    else:
        logger.error(f"Unknown client specified: {client}")
        raise ValueError(f"No builder available for client: {client}")

__all__ = ["get_builder", "BaseBuilder", "AgaveBuilder", "JitoBuilder", "FiredancerBuilder"]