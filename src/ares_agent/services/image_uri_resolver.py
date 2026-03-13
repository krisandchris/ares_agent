"""Resolve model-consumable image URIs, including MinIO-backed s3:// objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Protocol
from urllib.parse import urlparse


class ImageUriResolver(Protocol):
    def resolve(self, image_uri: str) -> str: ...


class MinioClientProtocol(Protocol):
    def presigned_get_object(self, bucket_name: str, object_name: str, expires: timedelta) -> str: ...


MinioClientFactory = Callable[..., MinioClientProtocol]


@dataclass
class MinioS3UriResolver:
    enabled: bool
    endpoint: str
    access_key: str
    secret_key: str
    presign_expiry_seconds: int
    secure: bool = False
    region: str | None = None
    client_factory: MinioClientFactory | None = None

    def resolve(self, image_uri: str) -> str:
        if not image_uri.startswith("s3://"):
            return image_uri
        if not self.enabled:
            raise ValueError("MinIO resolver is disabled")
        bucket_name, object_name = _parse_s3_uri(image_uri)
        client = self._build_client()
        return client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_name,
            expires=timedelta(seconds=self.presign_expiry_seconds),
        )

    def _build_client(self) -> MinioClientProtocol:
        factory = self.client_factory or _default_minio_client_factory
        return factory(
            endpoint=_normalize_endpoint(self.endpoint),
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            region=self.region,
        )


def resolve_image_uri(image_uri: str, *, resolver: ImageUriResolver | None = None) -> str:
    if resolver is None:
        return image_uri
    return resolver.resolve(image_uri)


def _parse_s3_uri(image_uri: str) -> tuple[str, str]:
    parsed = urlparse(image_uri)
    bucket_name = parsed.netloc
    object_name = parsed.path.lstrip("/")
    if not bucket_name or not object_name:
        raise ValueError(f"Invalid s3 URI: {image_uri}")
    return bucket_name, object_name


def _normalize_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme:
        return parsed.netloc or parsed.path
    return endpoint


def _default_minio_client_factory(**kwargs: Any) -> MinioClientProtocol:
    from minio import Minio

    return Minio(**kwargs)
