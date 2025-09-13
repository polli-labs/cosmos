from cosmos.ffmpeg.presets import build_encoder_settings


def test_presets_nvenc_quality():
    args = build_encoder_settings("h264_nvenc", mode="quality", crf=18)
    joined = " ".join(args)
    assert "-c:v h264_nvenc" in joined
    assert "-preset p7" in joined
    assert "-qp 18" in joined


def test_presets_videotoolbox_balanced():
    args = build_encoder_settings("h264_videotoolbox", mode="balanced", crf=None)
    # CRF default for balanced is 23
    joined = " ".join(args)
    assert "-c:v h264_videotoolbox" in joined
    assert "-crf 23" in joined


def test_presets_x264_threads():
    args = build_encoder_settings("libx264", mode="performance", crf=28, threads=2)
    joined = " ".join(args)
    assert "-c:v libx264" in joined
    assert "-crf 28" in joined
    assert "-threads 2" in joined
    assert "x264-params threads=2" in joined


def test_presets_qsv_icq_like():
    args = build_encoder_settings("h264_qsv", mode="balanced", crf=23)
    joined = " ".join(args)
    assert "-c:v h264_qsv" in joined
    assert "-global_quality 23" in joined
    assert "-b:v 0" in joined


def test_presets_amf_cqp():
    args = build_encoder_settings("h264_amf", mode="quality", crf=18)
    joined = " ".join(args)
    assert "-c:v h264_amf" in joined
    assert "-rc cqp" in joined
    assert "-qp_i 18" in joined and "-qp_p 18" in joined
