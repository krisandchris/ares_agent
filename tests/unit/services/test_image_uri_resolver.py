from pathlib import Path

import pytest

from ares_agent.services.image_uri_resolver import MinioS3UriResolver, resolve_image_uri


def test_resolve_image_uri_passthroughs_http_url() -> None:
    resolver = MinioS3UriResolver(
        enabled=True,
        endpoint="minio.example.com:9000",
        access_key="access",
        secret_key="secret",
        presign_expiry_seconds=600,
        client_factory=lambda **_: None,
    )

    resolved = resolve_image_uri("https://minio.example.com/bucket/object.jpg", resolver=resolver)

    assert resolved == "https://minio.example.com/bucket/object.jpg"


def test_resolve_image_uri_converts_s3_uri_via_minio_presign() -> None:
    class FakeClient:
        def presigned_get_object(self, bucket_name: str, object_name: str, expires):
            assert bucket_name == "test-bucket"
            assert object_name == "folder/image.jpg"
            assert int(expires.total_seconds()) == 600
            return "https://minio.example.com/presigned/test-bucket/folder/image.jpg?X-Amz-Signature=demo"

    resolver = MinioS3UriResolver(
        enabled=True,
        endpoint="minio.example.com:9000",
        access_key="access",
        secret_key="secret",
        presign_expiry_seconds=600,
        client_factory=lambda **_: FakeClient(),
    )

    resolved = resolve_image_uri("s3://test-bucket/folder/image.jpg", resolver=resolver)

    assert resolved.startswith("https://minio.example.com/presigned/test-bucket/folder/image.jpg")


def test_resolve_image_uri_rejects_s3_uri_when_minio_disabled() -> None:
    resolver = MinioS3UriResolver(
        enabled=False,
        endpoint="minio.example.com:9000",
        access_key="access",
        secret_key="secret",
        presign_expiry_seconds=600,
        client_factory=lambda **_: None,
    )

    with pytest.raises(ValueError, match="MinIO resolver is disabled"):
        resolve_image_uri("s3://test-bucket/folder/image.jpg", resolver=resolver)
