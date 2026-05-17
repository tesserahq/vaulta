import io

from PIL import Image

try:
    from pdf2image import convert_from_bytes

    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    _PDF2IMAGE_AVAILABLE = False

_SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
}


class AnalysisPreprocessor:
    """Normalizes any supported input (PNG/JPG/GIF/PDF) into JPEG bytes for provider submission."""

    def __init__(self, max_image_px: int = 2048) -> None:
        self.max_image_px = max_image_px

    def to_jpeg_bytes(self, file_bytes: bytes, content_type: str) -> bytes:
        """Convert file bytes to a JPEG byte payload ready for a provider.

        Handles PDF first-page extraction and resizes to max_image_px on the longest side.

        Raises:
            ValueError: If the content type is not supported and PIL cannot open the file.
        """
        ct = content_type.lower().split(";")[0].strip()

        if "pdf" in ct:
            return self._pdf_to_jpeg(file_bytes)
        elif ct == "image/gif":
            return self._image_to_jpeg(file_bytes, first_frame=True)
        elif ct in ("image/jpeg", "image/jpg", "image/png"):
            return self._image_to_jpeg(file_bytes)
        else:
            # Unknown content type — try PIL; raise if it fails
            try:
                return self._image_to_jpeg(file_bytes)
            except Exception:
                raise ValueError(
                    f"Unsupported content type for document analysis: {content_type!r}. "
                    f"Supported types: {', '.join(sorted(_SUPPORTED_CONTENT_TYPES))}"
                )

    def _pdf_to_jpeg(self, file_bytes: bytes) -> bytes:
        if not _PDF2IMAGE_AVAILABLE:
            raise ValueError(
                "pdf2image is required for PDF analysis: pip install pdf2image"
            )
        images = convert_from_bytes(file_bytes, dpi=300, first_page=1, last_page=1)
        if not images:
            raise ValueError("Could not extract a page from the PDF")
        return self._pil_to_jpeg(images[0])

    def _image_to_jpeg(self, file_bytes: bytes, first_frame: bool = False) -> bytes:
        img = Image.open(io.BytesIO(file_bytes))
        if first_frame and hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)
        return self._pil_to_jpeg(img)

    def _pil_to_jpeg(self, img: Image.Image) -> bytes:
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        longest = max(w, h)
        if longest > self.max_image_px:
            scale = self.max_image_px / longest
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()
