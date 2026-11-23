"""本地预览接口只接受同源 JSON 请求。"""
import json
import urllib.error
import urllib.request

from launch_web import start_local_server
from web_bridge import KKToolsBridge


def test_local_api_rejects_cross_origin_before_any_change():
    bridge = KKToolsBridge()
    server, port = start_local_server(bridge)
    try:
        request = urllib.request.Request(
            f'http://127.0.0.1:{port}/api/set_dirty_state',
            data=json.dumps({'args': [True]}).encode(),
            headers={'Content-Type': 'application/json', 'Origin': 'https://example.com'},
        )
        try:
            urllib.request.urlopen(request, timeout=5)
            status = 200
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status == 403
        assert not bridge.has_unsaved_edits()
    finally:
        server.shutdown()
        server.server_close()
