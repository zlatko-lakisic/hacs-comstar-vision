"""One-time mTLS enrollment against AO engine."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import aiohttp

from .mtls import (
    ReachMtlsMaterial,
    assert_reach_mtls_uses_tls,
    persist_reach_mtls_material,
)


class ReachMtlsEnroller:
    """Generate key+CSR, redeem AO enroll token, persist PEMs."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        self._session = session

    async def enroll(
        self,
        *,
        base_url: str,
        enroll_token: str,
        material_dir: str | None = None,
        common_name: str | None = None,
        ca_pem: str | None = None,
        trust_enrollment_ca: bool = False,
    ) -> ReachMtlsMaterial:
        assert_reach_mtls_uses_tls(base_url)
        token = enroll_token.strip()
        if not token:
            raise ValueError("enrollToken is required")
        cn = (common_name or "").strip() or f"reach-{int(time.time() * 1000)}"
        base = base_url.rstrip("/")

        owned = self._session is None
        connector = aiohttp.TCPConnector(ssl=False) if trust_enrollment_ca and not ca_pem else None
        session = self._session or aiohttp.ClientSession(connector=connector)
        try:
            pinned_ca = (ca_pem or "").strip()
            if not pinned_ca:
                if not trust_enrollment_ca:
                    raise RuntimeError(
                        "Pass ca_pem or trust_enrollment_ca=True to trust the AO CA on first enroll"
                    )
                pinned_ca = await self._fetch_ca_pem(session, base)

            with tempfile.TemporaryDirectory(prefix="ao-reach-mtls-") as tmp:
                key_path = Path(tmp) / "key.pem"
                csr_path = Path(tmp) / "csr.pem"
                await self._generate_key_and_csr(cn, key_path, csr_path)
                csr_pem = csr_path.read_text(encoding="utf-8")
                key_pem = key_path.read_text(encoding="utf-8")
                enrolled = await self._post_enroll(
                    session, base, token, csr_pem, cn
                )
                out_dir = (material_dir or "").strip() or str(Path.cwd() / ".ao-mtls")
                return persist_reach_mtls_material(
                    dir=out_dir,
                    client_cert_pem=enrolled["certificatePem"],
                    client_key_pem=key_pem,
                    ca_pem=enrolled.get("caPem") or pinned_ca,
                    subject=enrolled.get("subject") or cn,
                    expires_at=enrolled.get("expiresAt"),
                )
        finally:
            if owned:
                await session.close()

    async def _fetch_ca_pem(self, session: aiohttp.ClientSession, base_url: str) -> str:
        async with session.get(f"{base_url}/api/v1/mtls/ca") as res:
            body = await res.text()
            if res.status != 200:
                raise RuntimeError(f"GET /api/v1/mtls/ca failed: HTTP {res.status} {body}")
            data = json.loads(body)
            pem = (data.get("caPem") or "").strip()
            if not pem:
                raise RuntimeError("GET /api/v1/mtls/ca: missing caPem")
            return pem

    async def _post_enroll(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: str,
        csr_pem: str,
        client_name: str,
    ) -> dict:
        payload = {"csrPem": csr_pem, "token": token, "clientName": client_name}
        async with session.post(
            f"{base_url}/api/v1/mtls/enroll",
            json=payload,
            headers={"Accept": "application/json"},
        ) as res:
            body = await res.text()
            if res.status != 200:
                raise RuntimeError(f"enroll failed: HTTP {res.status} {body}")
            data = json.loads(body)
            if "certificatePem" not in data:
                raise RuntimeError("enroll response missing certificatePem")
            return data

    async def _generate_key_and_csr(
        self, cn: str, key_path: Path, csr_path: Path
    ) -> None:
        """Prefer openssl when present; fall back to cryptography (HA Core image)."""
        import asyncio

        openssl = shutil.which("openssl")
        if openssl:

            def _run_openssl() -> None:
                subprocess.run(
                    [
                        openssl,
                        "req",
                        "-new",
                        "-newkey",
                        "rsa:2048",
                        "-nodes",
                        "-keyout",
                        str(key_path),
                        "-out",
                        str(csr_path),
                        "-subj",
                        f"/CN={cn}",
                    ],
                    check=True,
                    capture_output=True,
                )

            await asyncio.to_thread(_run_openssl)
            return

        def _run_cryptography() -> None:
            try:
                from cryptography import x509
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import rsa
                from cryptography.x509.oid import NameOID
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "openssl not on PATH and cryptography is unavailable "
                    "(required for mTLS enroll on Home Assistant Core)"
                ) from exc

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            csr = (
                x509.CertificateSigningRequestBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
                .sign(key, hashes.SHA256())
            )
            key_path.write_bytes(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            csr_path.write_bytes(csr.public_bytes(serialization.Encoding.PEM))

        await asyncio.to_thread(_run_cryptography)
