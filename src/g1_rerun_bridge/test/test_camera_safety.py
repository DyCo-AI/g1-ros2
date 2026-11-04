from g1_rerun_bridge.bridge import (
    DEFAULT_ENABLE_FRONT_VIDEO_TOPIC,
    DEFAULT_ENABLE_STOCK_H264_CAMERA,
    stock_h264_pipeline,
)


def test_default_camera_uses_only_stock_multicast() -> None:
    assert DEFAULT_ENABLE_STOCK_H264_CAMERA is True
    assert DEFAULT_ENABLE_FRONT_VIDEO_TOPIC is False


def test_stock_camera_pipeline_is_receiver_only() -> None:
    pipeline = stock_h264_pipeline("230.1.1.1", 1720, "enp0s31f6")

    assert pipeline.startswith(
        "udpsrc address=230.1.1.1 port=1720 multicast-iface=enp0s31f6 "
    )
    assert "appsink name=sink" in pipeline

    forbidden = (
        "v4l2src",
        "realsense",
        "/dev/video",
        "ssh",
        "systemctl",
        "videohub",
        "master_service",
    )
    assert not any(token in pipeline.lower() for token in forbidden)
