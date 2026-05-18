import uvicorn
from app.config import get_settings


def dev():
    settings = get_settings()

    # Configure uvicorn with file upload limits
    # Note: Some limits are configured via command line args in start.sh
    # For development, we use the run() function which has different parameters
    uvicorn.run(
        "app.main:app",
        reload=True,
        port=settings.port,
        # Development server configuration
        log_level="info",
        access_log=True,
    )
