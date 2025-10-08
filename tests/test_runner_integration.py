import pytest
from src.orchestration.runner import run_pipeline2

# ⚠️ Este test es de INTEGRACIÓN REAL (requiere internet, credenciales, y APIs habilitadas)
@pytest.mark.integration
def test_run_pipeline_real():
    SHEET_ID = "1Dyq4QJgwKcW3LEAetga43CkAdvzBZDtW7vLddPugVfo"
    RANGE = "Hoja1!A2:F10"

    transcript = run_pipeline2(SHEET_ID, RANGE)

    assert transcript is not None
    assert isinstance(transcript, str)
    assert "TRANSCRIPCIÓN:" in transcript
