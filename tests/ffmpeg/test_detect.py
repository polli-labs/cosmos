import shutil
from unittest.mock import patch

import pytest

if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not available on PATH", allow_module_level=True)

from cosmos.ffmpeg.detect import choose_encoder


def test_choose_encoder_prefers_nvenc_linux():
    text = "Encoders:\n V..... libx264 x264\n V..... h264_nvenc NVIDIA NVENC H.264 encoder\n V..... h264_vaapi H.264 VAAPI encoder\n"
    with patch("subprocess.run") as mock_run, patch("platform.system", return_value="Linux"):
        mock_run.return_value.stdout = text
        mock_run.return_value.stderr = ""
        enc = choose_encoder()
        assert enc == "h264_nvenc"


def test_choose_encoder_vaapi_if_only_vaapi_on_linux():
    text = "Encoders:\n V..... libx264 x264\n V..... h264_vaapi H.264 VAAPI encoder\n"
    with patch("subprocess.run") as mock_run, patch("platform.system", return_value="Linux"):
        mock_run.return_value.stdout = text
        mock_run.return_value.stderr = ""
        enc = choose_encoder()
        assert enc == "h264_vaapi"
