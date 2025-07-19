<p align="center">
  <img width="180px" src="assets/logo.png">
  
  <p align="center">
    A secure and flexible file storage service designed for modern applications. It supports both local and cloud-based storage (e.g., AWS S3), allowing you to manage uploads, downloads, and file visibility with ease.
  </p>
</p>

## Key Features

- 📂 Upload files via FastAPI endpoints
- ☁️ Supports local storage and S3-compatible providers
- 🔒 Control file access: public or private
- 🔐 Generate signed download URLs for private files
- 🚀 Pluggable `StorageBackend` interface for extensibility
- 🧪 Production-ready and test-friendly design

## Use Cases

- Uploading and accessing user files securely
- Serving private media through signed links
- Reusable storage backend for microservices

## Coming Soon

- UI for file browsing and access control
- Support for Google Cloud Storage and MinIO
- File expiration and audit logging

# Vaulta

Asset management API for Estate Buddy.

## File Upload Configuration

### File Size Limits

The API supports configurable file upload size limits. By default, the maximum file size is set to **100MB**.

#### Environment Variables

You can configure file upload limits using these environment variables:

- `MAX_FILE_SIZE_MB`: Maximum file size in megabytes (default: 100)
- `MAX_FILE_SIZE`: Maximum file size in bytes (overrides MAX_FILE_SIZE_MB if set)

#### Examples

```bash
# Set maximum file size to 500MB
export MAX_FILE_SIZE_MB=500

# Or set it directly in bytes
export MAX_FILE_SIZE=524288000  # 500MB in bytes
```

#### Cloudflare Considerations

If you're using Cloudflare in front of your API, you may also need to configure Cloudflare's file upload limits:

1. **Cloudflare Enterprise**: Contact support to increase file upload limits
2. **Cloudflare Pro/Free**: Limited to 100MB by default
3. **Alternative**: Use direct upload to your server bypassing Cloudflare for large files

#### Troubleshooting 413 Errors

If you're getting 413 "Payload Too Large" errors:

1. **Check your file size**: Ensure it's within the configured limits
2. **Verify Cloudflare settings**: If using Cloudflare, check their file size limits
3. **Check server configuration**: Ensure uvicorn and FastAPI are configured for large files
4. **Review environment variables**: Make sure `MAX_FILE_SIZE_MB` is set correctly

#### Detailed Configuration Guide

For comprehensive documentation on all configuration parameters, server settings, and troubleshooting, see:
**[File Upload Configuration Guide](docs/file_upload_configuration.md)**

## Development

### Prerequisites

- Python 3.12+
- Poetry
- PostgreSQL

### Setup

1. Install dependencies:
```bash
poetry install
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run migrations:
```bash
alembic upgrade head
```

4. Start the development server:
```bash
poetry run dev
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

## Testing

Run tests with:
```bash
poetry run pytest
```