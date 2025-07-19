# File Upload Configuration Guide

This document explains how to configure file upload limits and the parameters used to handle large file uploads in the Vaulta API.

## Overview

The Vaulta API supports configurable file upload limits with multiple layers of validation to ensure reliable file handling. The configuration spans several components:

1. **Application-level limits** (FastAPI/Pydantic)
2. **Server-level limits** (Uvicorn)
3. **Infrastructure limits** (Cloudflare, load balancers, etc.)

## Configuration Parameters

### Application Settings (`app/config.py`)

#### `MAX_FILE_SIZE_MB`
- **Purpose**: Maximum file size in megabytes
- **Default**: 100 MB
- **Usage**: `export MAX_FILE_SIZE_MB=500`
- **Description**: Sets the maximum allowed file size for uploads. This is the primary limit that users will encounter.

#### `MAX_FILE_SIZE`
- **Purpose**: Maximum file size in bytes
- **Default**: 100 * 1024 * 1024 (100MB)
- **Usage**: `export MAX_FILE_SIZE=524288000`
- **Description**: Overrides `MAX_FILE_SIZE_MB` if set. Useful for precise control.

### Uvicorn Server Configuration

The following parameters are configured in both `run.py` (development) and `start.sh` (production):

#### `--limit-concurrency 1000`
- **Purpose**: Maximum number of concurrent connections
- **Default**: 1000
- **Description**: Limits how many simultaneous requests the server can handle. For file uploads, this prevents the server from being overwhelmed by too many concurrent uploads.

#### `--limit-max-requests 10000`
- **Purpose**: Maximum number of requests before worker restart
- **Default**: 10000
- **Description**: Restarts workers after processing this many requests to prevent memory leaks. Important for long-running file upload operations.

#### `--limit-request-line 8190`
- **Purpose**: Maximum size of HTTP request line (URL + headers)
- **Default**: 8190 bytes
- **Description**: Limits the size of the request URL and headers. For file uploads, this affects the maximum size of form data and metadata.

#### `--limit-request-fields 100`
- **Purpose**: Maximum number of HTTP headers
- **Default**: 100
- **Description**: Limits the number of HTTP headers in a request. Important for multipart form uploads which may have many headers.

#### `--limit-request-field-size 8190`
- **Purpose**: Maximum size of each HTTP header
- **Default**: 8190 bytes
- **Description**: Limits the size of individual HTTP headers. Affects the maximum size of form field names and values.

## File Size Validation Layers

### 1. Dependency Layer (`app/routers/utils/dependencies.py`)

```python
def validate_file_size(file: UploadFile) -> UploadFile:
    """Validate that the uploaded file size is within limits."""
    settings = get_settings()
    
    if hasattr(file, 'size') and file.size:
        if file.size > settings.max_file_size:
            max_size_mb = settings.max_file_size // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size allowed is {max_size_mb}MB. File size: {file.size // (1024 * 1024)}MB"
            )
    
    return file
```

**Purpose**: Early validation before processing begins
**When**: During FastAPI dependency injection
**Error**: 413 Payload Too Large with detailed message

### 2. Service Layer (`app/services/asset_upload.py`)

```python
# Validate file size
settings = get_settings()
if asset_size > settings.max_file_size:
    max_size_mb = settings.max_file_size // (1024 * 1024)
    file_size_mb = asset_size // (1024 * 1024)
    raise HTTPException(
        status_code=413,
        detail=f"File too large. Maximum size allowed is {max_size_mb}MB. File size: {file_size_mb}MB"
    )
```

**Purpose**: Secondary validation during actual file processing
**When**: After file metadata extraction
**Error**: 413 Payload Too Large with actual file size

## Environment Configuration Examples

### Development Environment
```bash
# .env file
MAX_FILE_SIZE_MB=500
PORT=8000
```

### Production Environment
```bash
# Environment variables
export MAX_FILE_SIZE_MB=1000  # 1GB limit
export PORT=8000
```

### Docker Environment
```dockerfile
# Dockerfile or docker-compose.yml
ENV MAX_FILE_SIZE_MB=500
ENV PORT=8000
```

## Cloudflare Considerations

### Cloudflare Limits
- **Free Plan**: 100MB maximum file size
- **Pro Plan**: 100MB maximum file size
- **Enterprise Plan**: Configurable limits (contact support)

### Solutions for Large Files

#### Option 1: Bypass Cloudflare for Large Files
```nginx
# nginx configuration
location /assets {
    if ($content_length > 104857600) {  # 100MB
        proxy_pass http://backend:8000;
        break;
    }
    # Normal Cloudflare routing
}
```

#### Option 2: Use Cloudflare Workers (Enterprise)
```javascript
// Cloudflare Worker
addEventListener('fetch', event => {
  if (event.request.headers.get('content-length') > 100 * 1024 * 1024) {
    // Handle large files differently
  }
});
```

#### Option 3: Direct Upload Endpoint
Create a separate endpoint that bypasses Cloudflare:
```python
@router.post("/upload-direct")
async def upload_large_file_direct(
    file: UploadFile = Depends(get_validated_file),
    # ... other parameters
):
    """Direct upload endpoint that bypasses Cloudflare."""
    pass
```

## Troubleshooting

### Common Issues

#### 1. 413 Payload Too Large from Cloudflare
**Symptoms**: Error before reaching your application
**Solution**: 
- Check Cloudflare plan limits
- Use direct upload for large files
- Contact Cloudflare support (Enterprise)

#### 2. 413 Payload Too Large from FastAPI
**Symptoms**: Error with detailed size information
**Solution**:
- Increase `MAX_FILE_SIZE_MB` environment variable
- Check file size against configured limits

#### 3. Connection Timeout
**Symptoms**: Upload fails after some time
**Solution**:
- Increase timeout settings in load balancer
- Check network stability
- Consider chunked uploads for very large files

#### 4. Memory Issues
**Symptoms**: Server becomes unresponsive
**Solution**:
- Reduce `limit-concurrency`
- Implement streaming uploads
- Monitor server memory usage

### Monitoring and Logging

#### Enable Debug Logging
```python
# app/config.py
log_level: str = Field(default="DEBUG", json_schema_extra={"env": "LOG_LEVEL"})
```

#### Monitor Upload Metrics
```python
# Add to upload endpoint
logger.info(f"File upload started: {file.filename}, size: {file.size}")
logger.info(f"File upload completed: {asset_id}")
```

## Best Practices

1. **Set Realistic Limits**: Balance user needs with server resources
2. **Monitor Usage**: Track file sizes and upload patterns
3. **Implement Progress**: Show upload progress for large files
4. **Handle Failures**: Provide clear error messages and retry options
5. **Security**: Validate file types and scan for malware
6. **Backup**: Ensure uploaded files are properly backed up

## Performance Tuning

### For High-Volume Uploads
```bash
# Increase concurrency for many small files
--limit-concurrency 2000

# Increase request limits for large files
--limit-request-field-size 16384
```

### For Large Files
```bash
# Increase timeout for slow uploads
--timeout-keep-alive 300

# Increase worker processes
--workers 4
```

## Testing

### Test File Size Limits
```bash
# Create test files of various sizes
dd if=/dev/zero of=test_50mb.bin bs=1M count=50
dd if=/dev/zero of=test_100mb.bin bs=1M count=100
dd if=/dev/zero of=test_500mb.bin bs=1M count=500

# Test uploads
curl -X POST "http://localhost:8000/assets" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_50mb.bin"
```

### Monitor Server Resources
```bash
# Monitor memory usage
htop

# Monitor disk usage
df -h

# Monitor network
iftop
``` 