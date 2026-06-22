from app.providers import ANALYSIS_PROVIDER_LABELS, AnalysisProvider


class TestAnalysisConfigRouter:
    def test_list_analysis_providers(self, client):
        response = client.get("/analysis-configs/providers")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == len(AnalysisProvider)
        assert data["items"] == [
            {"id": provider.value, "label": ANALYSIS_PROVIDER_LABELS[provider]}
            for provider in AnalysisProvider
        ]
