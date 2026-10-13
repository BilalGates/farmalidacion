"""Genera un certificado temporal para probar HTTPS en una IP de VPN.

La clave de la autoridad de prueba sólo existe en memoria. Distribuir únicamente
ca.crt; server.key debe permanecer en el equipo que sirve Farmalidación.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def generate(ip_text: str, output_dir: Path, days: int = 30) -> None:
    ip = ipaddress.ip_address(ip_text)
    if not ip.is_private:
        raise ValueError("La dirección debe pertenecer a una red privada.")
    if days < 1 or days > 90:
        raise ValueError("La validez debe estar entre 1 y 90 días.")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: output_dir / name for name in ("ca.crt", "server.crt", "server.key")}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("Ya existen certificados en el destino; no se sobrescriben.")

    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Farmalidacion VPN piloto CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                                     key_encipherment=False, data_encipherment=False,
                                     key_agreement=False, key_cert_sign=True, crl_sign=True,
                                     encipher_only=False, decipher_only=False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip_text)])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name).issuer_name(ca_name).public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip)]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                     key_encipherment=True, data_encipherment=False,
                                     key_agreement=False, key_cert_sign=False, crl_sign=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    for name, content in (
        ("ca.crt", ca_cert.public_bytes(serialization.Encoding.PEM)),
        ("server.crt", server_cert.public_bytes(serialization.Encoding.PEM)),
        ("server.key", server_key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption())),
    ):
        path = paths[name]
        with path.open("xb") as destination:
            destination.write(content)
        if os.name != "nt":
            path.chmod(0o600 if name.endswith(".key") else 0o644)
    print(f"Certificado de prueba para {ip_text}, válido hasta {now + timedelta(days=days):%Y-%m-%d}.")
    print(f"Autoridad pública: {paths['ca.crt']}")
    print(f"Certificado de servidor: {paths['server.crt']}")
    print(f"Clave privada del servidor: {paths['server.key']} (no compartir)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ip", help="IPv4 privada de la interfaz VPN")
    parser.add_argument("--output-dir", type=Path, default=Path("data/local/vpn-tls"))
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    generate(args.ip, args.output_dir, args.days)
