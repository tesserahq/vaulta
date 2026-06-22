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


ANALYSIS_PROVIDER_LABELS: dict[AnalysisProvider, str] = {
    AnalysisProvider.LOCAL: "Local",
    AnalysisProvider.TEXTRACT: "AWS Textract",
    AnalysisProvider.GOOGLE_DAI: "Google Document AI",
    AnalysisProvider.CLAUDE: "Claude",
    AnalysisProvider.MODELA: "Modela",
}
