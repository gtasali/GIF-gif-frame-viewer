"""GIF 逐帧查看器 · 桌面版启动器（pywebview + WebView2）

- 直接双击 gif 打开时，Windows 会把文件路径作为第一个参数传进来，这里读出字节推给页面。
- 窗口对象必须放在模块级变量里：pywebview 启动时会递归遍历 js_api 对象的属性来生成
  可调用函数列表，若把 Window 存成 Api 的属性，会一路递归进 .NET 原生窗口对象并栈溢出。
"""
import base64
import json
import os
import sys
import threading
import time

import webview

APP_TITLE = 'GIF 逐帧查看器'
HTML_FILE = 'GIF逐帧查看器.html'

_WINDOW = None
_INITIAL_FILE = None


def resource_path(name):
    """兼容 PyInstaller 单文件模式（资源解包到 _MEIPASS）"""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def parse_file_arg(argv):
    """从命令行里挑出被打开的文件路径（双击关联文件时由 Windows 传入）"""
    for arg in argv[1:]:
        if not arg or arg.startswith('-'):
            continue
        candidate = arg.strip('"')
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


class Api:
    """暴露给页面的原生能力：打开 GIF、保存 PNG 帧（不要在这里保存任何原生对象）"""

    def pick_gif(self):
        try:
            paths = _WINDOW.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=('GIF 图片 (*.gif)', '所有文件 (*.*)'),
            )
        except Exception as exc:
            return {'error': repr(exc)}
        if not paths:
            return None
        path = paths[0]
        try:
            with open(path, 'rb') as fp:
                data = fp.read()
        except Exception as exc:
            return {'error': repr(exc)}
        return {
            'name': os.path.basename(path),
            'b64': base64.b64encode(data).decode('ascii'),
        }

    def save_frame(self, data_url, filename):
        try:
            result = _WINDOW.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=filename or 'frame.png',
                file_types=('PNG 图片 (*.png)',),
            )
        except Exception:
            return {'ok': False, 'error': 'dialog'}
        if not result:
            return {'ok': False, 'cancelled': True}
        target = result if isinstance(result, str) else result[0]
        try:
            _, _, payload = data_url.partition(',')
            with open(target, 'wb') as fp:
                fp.write(base64.b64decode(payload))
            return {'ok': True, 'path': target}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}


def push_file_to_page(window, path):
    """把文件字节交给页面里的 window.GifViewer.open(name, base64)"""
    try:
        with open(path, 'rb') as fp:
            data = fp.read()
        name = os.path.basename(path)
        js = 'window.GifViewer && window.GifViewer.open(%s, %s)' % (
            json.dumps(name), json.dumps(base64.b64encode(data).decode('ascii')),
        )
        result = window.evaluate_js(js)
        try:
            window.title = '%s — %s' % (name, APP_TITLE)
        except Exception:
            pass
        return result
    except Exception as exc:
        return 'ERR ' + repr(exc)


def _diag_enabled():
    return os.environ.get('GIFVIEW_DIAG') == '1'


def _attach_diag(window):
    """仅在 GIFVIEW_DIAG=1 时生效：把启动后的页面状态写入临时日志，用于验证打包产物。"""
    if not _diag_enabled():
        return

    log_path = os.path.join(os.environ.get('TEMP', '.'), 'gifview_diag.log')

    def write(text):
        try:
            with open(log_path, 'a', encoding='utf-8') as fp:
                fp.write(text + '\n')
        except Exception:
            pass

    def run():
        try:
            boot = window.evaluate_js(
                "JSON.stringify({"
                "bridge: !!(window.pywebview && window.pywebview.api),"
                "hook: !!(window.GifViewer && window.GifViewer.open),"
                "title: document.title,"
                "canvas: [document.getElementById('view').width, document.getElementById('view').height],"
                "emptyVisible: !document.getElementById('empty').hidden"
                "})"
            )
            write('BOOT ' + str(boot))

            if _INITIAL_FILE:
                write('ARGV_FILE ' + _INITIAL_FILE)
                write('PUSH_RESULT ' + str(push_file_to_page(window, _INITIAL_FILE)))
                time.sleep(1.0)
                state = window.evaluate_js(
                    "JSON.stringify({"
                    "cur: document.getElementById('curFrame').textContent,"
                    "total: document.getElementById('totalFrames').textContent,"
                    "thumbs: document.querySelectorAll('.thumb').length,"
                    "file: document.getElementById('fmName').textContent,"
                    "canvas: [document.getElementById('view').width, document.getElementById('view').height],"
                    "emptyVisible: !document.getElementById('empty').hidden"
                    "})"
                )
                write('AFTER_FILE ' + str(state))
            else:
                window.evaluate_js("document.getElementById('btnDemo').click();")
                time.sleep(1.2)
                state = window.evaluate_js(
                    "JSON.stringify({"
                    "cur: document.getElementById('curFrame').textContent,"
                    "total: document.getElementById('totalFrames').textContent,"
                    "thumbs: document.querySelectorAll('.thumb').length,"
                    "canvas: [document.getElementById('view').width, document.getElementById('view').height],"
                    "alpha: document.getElementById('view').getContext('2d').getImageData(240,120,1,1).data[3]"
                    "})"
                )
                write('AFTER_DEMO ' + str(state))
        except Exception as exc:
            write('DIAG_ERROR ' + repr(exc))

    def on_loaded():
        threading.Thread(target=run, daemon=True).start()

    window.events.loaded += on_loaded


def create_app_window(width=1360, height=900):
    global _WINDOW
    with open(resource_path(HTML_FILE), 'r', encoding='utf-8') as fp:
        page = fp.read()

    _WINDOW = webview.create_window(
        APP_TITLE,
        html=page,
        js_api=Api(),
        width=width,
        height=height,
        min_size=(960, 640),
        background_color='#0c0d0f',
        text_select=True,
    )
    _attach_diag(_WINDOW)
    return _WINDOW


def main():
    global _INITIAL_FILE
    _INITIAL_FILE = parse_file_arg(sys.argv)

    window = create_app_window()

    if _INITIAL_FILE and not _diag_enabled():
        def on_loaded():
            threading.Thread(
                target=lambda: push_file_to_page(window, _INITIAL_FILE),
                daemon=True,
            ).start()

        window.events.loaded += on_loaded

    webview.start(debug=False)


if __name__ == '__main__':
    main()
