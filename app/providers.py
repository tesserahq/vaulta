from enum import StrEnum


class StorageProvider(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class AnalysisProvider(StrEnum):
    LOCAL = "local"
    TEXTRACT = "textract"
    GOOGLE_DAI = "google_dai"
    CLAUDE = "claude"
    MODELA = "modela"
