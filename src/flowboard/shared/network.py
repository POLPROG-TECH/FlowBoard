"""Shared networking utilities — CA bundle resolution, session SSL, proxy config.

This module centralises corporate-network concerns (proxy CAs, Zscaler,
custom cert bundles) so that the Jira HTTP client — and any future outgoing
HTTPS calls — works reliably behind corporate proxies and VPNs.

Corporate environments commonly intercept HTTPS traffic via proxy CAs
(Zscaler, Netskope, etc.).  The ``requests`` library uses ``certifi`` by
default, which may not include the corporate CA.  This module provides a
``get_ca_bundle_path()`` function that resolves the correct CA bundle using
the same strategy as ReleaseBoard's ``make_ssl_context()``.

Resolution order for CA certificates:

1. ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` env var  (explicit override)
2. ``certifi`` package  (ships Mozilla CA bundle — ``requests`` default)
3. macOS system keychain export  (includes corporate CAs like Zscaler)
4. ``True`` (let ``requests`` use its built-in default)

Usage::

    from flowboard.shared.network import configure_session_ssl

    session = requests.Session()
    configure_session_ssl(session)
    # session.verify is now set to the resolved CA bundle path

Configuration
-------------
Set one of the following environment variables before starting FlowBoard
to use a custom CA bundle:

- ``SSL_CERT_FILE=/path/to/ca-bundle.pem``
- ``REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem``

On macOS, if neither env var is set and the system keychain contains
corporate CAs, the module generates a temporary PEM file automatically.
"""

from __future__ import annotations

import logging
import os
import ssl
import sys
import tempfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CA bundle resolution (for the `requests` library)
# ---------------------------------------------------------------------------

_cached_ca_path: str | bool | None = None


def get_ca_bundle_path() -> str | bool:
    """Resolve the CA bundle path for use with ``requests.Session.verify``.

    Returns a file path (``str``) when a custom/corporate CA bundle is found,
    or ``True`` to tell ``requests`` to use its built-in default (certifi).

    The result is cached process-wide after the first call.
    """
    global _cached_ca_path
    if _cached_ca_path is not None:
        return _cached_ca_path

    result = _resolve_ca_bundle()
    _cached_ca_path = result
    return result


def _resolve_ca_bundle() -> str | bool:
    """Internal resolver — not cached."""
    # 1. Honour explicit env var
    for env in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        ca = os.environ.get(env)
        if ca and os.path.isfile(ca):
            logger.debug("SSL: using CA bundle from %s=%s", env, ca)
            return ca

    # 2. certifi is requests' default — check if it's available
    try:
        import certifi

        logger.debug("SSL: certifi available (%s)", certifi.where())
        return True  # Let requests use its own certifi
    except ImportError:
        pass

    # 3. Try macOS system certificates (includes corporate CAs)
    pem_path = _export_macos_certs()
    if pem_path:
        return pem_path

    # 4. Default — let requests figure it out
    logger.debug("SSL: using requests built-in defaults")
    return True


def _export_macos_certs() -> str | None:
    """Export macOS system keychain certs to a temp PEM file.

    Returns the file path or None on failure.  Only runs on macOS.
    The temp file is registered for cleanup via ``atexit``.
    """
    if sys.platform != "darwin":
        return None
    try:
        import atexit
        import subprocess

        result = subprocess.run(
            [
                "security",
                "find-certificate",
                "-a",
                "-p",
                "/Library/Keychains/System.keychain",
                "/System/Library/Keychains/SystemRootCertificates.keychain",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "BEGIN CERTIFICATE" in result.stdout:
            # Write to a persistent temp file (survives the process lifetime)
            tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
                mode="w",
                suffix=".pem",
                prefix="flowboard-ca-",
                delete=False,
            )
            tmp.write(result.stdout)
            tmp.close()

            def _cleanup_cert(path: str) -> None:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except OSError as exc:
                    logger.warning("Failed to clean up temp cert file %s: %s", path, exc)

            atexit.register(_cleanup_cert, tmp.name)
            logger.debug("SSL: exported macOS system certs to %s", tmp.name)
            return tmp.name
    except subprocess.TimeoutExpired:
        logger.warning("macOS CA bundle export timed out after 5s — using default CA bundle")
        return None
    except OSError as exc:
        logger.debug("macOS CA bundle export failed: %s", exc)
        return None
    except Exception as exc:
        logger.debug("macOS CA bundle export failed: %s", exc)
    return None


def configure_session_ssl(session: object, *, verify: bool | str = True) -> None:
    """Configure a ``requests.Session`` with the resolved CA bundle.

    Parameters
    ----------
    session:
        A ``requests.Session`` instance.
    verify:
        If ``False``, disables SSL verification entirely (insecure).
        If a ``str``, uses it as the CA bundle path directly.
        If ``True`` (default), resolves the CA bundle automatically.
    """
    if isinstance(verify, str):
        session.verify = verify  # type: ignore[attr-defined]
    elif not verify:
        session.verify = False  # type: ignore[attr-defined]
    else:
        bundle = get_ca_bundle_path()
        session.verify = bundle  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# SSL context (stdlib — for any future non-requests HTTP usage)
# ---------------------------------------------------------------------------

_cached_ssl_ctx: ssl.SSLContext | None = None


def make_ssl_context(*, force_new: bool = False) -> ssl.SSLContext:
    """Build an SSL context that works in corporate proxy environments.

    Resolution order matches ``get_ca_bundle_path()``:

    1. ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` env var
    2. ``certifi`` package
    3. macOS system keychain
    4. Python default

    The result is cached process-wide unless *force_new* is True.
    """
    global _cached_ssl_ctx
    if _cached_ssl_ctx is not None and not force_new:
        return _cached_ssl_ctx

    ctx = _build_ssl_context()
    _cached_ssl_ctx = ctx
    return ctx


def _build_ssl_context() -> ssl.SSLContext:
    """Internal builder — not cached."""
    for env in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        ca = os.environ.get(env)
        if ca and os.path.isfile(ca):
            return ssl.create_default_context(cafile=ca)

    try:
        import certifi  # type: ignore[import-untyped]

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    if sys.platform == "darwin":
        try:
            import subprocess

            pem = subprocess.run(
                [
                    "security",
                    "find-certificate",
                    "-a",
                    "-p",
                    "/Library/Keychains/System.keychain",
                    "/System/Library/Keychains/SystemRootCertificates.keychain",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if pem.returncode == 0 and "BEGIN CERTIFICATE" in pem.stdout:
                ctx = ssl.create_default_context()
                ctx.load_verify_locations(cadata=pem.stdout)
                return ctx
        except (OSError, subprocess.SubprocessError):
            pass

    return ssl.create_default_context()
