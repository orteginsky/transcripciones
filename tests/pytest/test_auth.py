# tests/test_auth.py
import pytest
from unittest.mock import patch, MagicMock
from src.ingestion import auth

def test_get_google_creds_with_valid_token(tmp_path, monkeypatch):
    # Crear un archivo token.json ficticio
    fake_token_file = tmp_path / "token.json"
    fake_token_file.write_text("{}", encoding="utf-8")

    # Sobrescribir paths en settings
    monkeypatch.setattr(auth, "GOOGLE_OAUTH_TOKEN_FILE", fake_token_file)
    monkeypatch.setattr(auth, "GOOGLE_OAUTH_CREDENTIALS_FILE", tmp_path / "credentials.json")

    # Mock Credentials para que simule ser válido
    mock_creds = MagicMock()
    mock_creds.valid = True

    with patch("src.ingestion.auth.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("src.ingestion.auth.build") as mock_build:

        _,sheets, drive, creds = auth.get_google_creds()

        # Se debe haber creado los servicios
        assert sheets is not None
        assert drive is not None
        assert creds == mock_creds
        mock_build.assert_any_call("sheets", "v4", credentials=mock_creds)
        mock_build.assert_any_call("drive", "v3", credentials=mock_creds)


def test_get_google_creds_refresh_expired(monkeypatch):
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh-token"

    monkeypatch.setattr(auth, "GOOGLE_OAUTH_TOKEN_FILE", MagicMock())
    monkeypatch.setattr(auth, "GOOGLE_OAUTH_CREDENTIALS_FILE", MagicMock())

    with patch("src.ingestion.auth.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("src.ingestion.auth.build") as mock_build:

        _,sheets, drive, creds = auth.get_google_creds()

        # Se deben haber refrescado las credenciales
        mock_creds.refresh.assert_called_once()
        assert creds == mock_creds
        mock_build.assert_any_call("sheets", "v4", credentials=mock_creds)


# Fallara porque crea un json falso para las credenciales
def test_get_google_creds_new_flow(monkeypatch):
    monkeypatch.setattr(auth, "GOOGLE_OAUTH_TOKEN_FILE", MagicMock())
    monkeypatch.setattr(auth, "GOOGLE_OAUTH_CREDENTIALS_FILE", MagicMock())

    # Simulamos credenciales con .to_json()
    mock_creds = MagicMock(valid=True)
    mock_creds.to_json.return_value = '{"access_token": "fake"}'

    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds

    with patch("src.ingestion.auth.Credentials.from_authorized_user_file", side_effect=Exception("token inválido")), \
         patch("src.ingestion.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
         patch("src.ingestion.auth.build") as mock_build:

        _,sheets, drive, creds = auth.get_google_creds()

        assert creds.valid
        assert creds.to_json() == '{"access_token": "fake"}'
        mock_flow.run_local_server.assert_called_once()
        mock_build.assert_any_call("sheets", "v4", credentials=creds)
        mock_build.assert_any_call("drive", "v3", credentials=creds)
