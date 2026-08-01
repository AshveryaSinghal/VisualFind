import cloudinary
import cloudinary.uploader

from app.config import settings

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)

def upload_image(image_bytes: bytes, filename: str) -> str:
    """
    Upload an image to Cloudinary.

    Args:
        image_bytes: Raw bytes of the uploaded image.
        filename: Original filename.

    Returns:
        Public HTTPS URL of the uploaded image.
    """

    result = cloudinary.uploader.upload(
        image_bytes,
        public_id=None,
        folder="visualfind",
        resource_type="image",
        overwrite=False,
        filename_override=filename,
    )

    return result["secure_url"]
