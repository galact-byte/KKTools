"""真实后端与浏览器的卡库回归：需安装 Playwright 及 Chromium。"""
from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import msgpack
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import card_scan, settings
import launch_web
from web_bridge import KKToolsBridge


class LibraryRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='library-', dir=ARGS.output)
        cls.work = Path(cls.temp.name)
        cls.cards = cls.work / 'cards'
        cls.cards.mkdir()
        cls.exports = cls.work / 'exports'
        cls.exports.mkdir()
        cls.appdata = cls.work / 'appdata'
        cls.appdata.mkdir()
        spec = importlib.util.spec_from_file_location(
            'card_fixtures', ROOT / 'tests/test_large_library_and_author.py',
        )
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        for i in range(180):
            author = 'Alice' if i < 100 or 120 <= i < 170 else 'Bob' if i < 120 else 'Carol'
            authors = msgpack.packb([author], use_bin_type=True)
            (cls.cards / f'{i:03d}.png').write_bytes(helper._make_card_bytes(
                lastname='测试', firstname=f'{i:03d}',
                kkex={'marco.authordata': [1, {'Authors': authors}]},
            ))
        cls.small = cls.work / 'small'
        cls.small.mkdir()
        authors = msgpack.packb(['Delta'], use_bin_type=True)
        (cls.small / 'only.png').write_bytes(helper._make_card_bytes(
            kkex={'marco.authordata': [1, {'Authors': authors}]},
        ))
        cls.patches = [
            patch.object(settings, 'app_dir', lambda: cls.appdata),
            patch.object(settings, '_CONFIG_PATH', cls.appdata / 'config.json'),
            patch.object(launch_web, 'resolve_dist_dir', lambda: ARGS.dist),
        ]
        for p in cls.patches:
            p.start()
        settings.save({**settings.DEFAULTS, 'last_browse_dir': str(cls.cards),
                       'output_dir': str(cls.exports)})
        cls.bridge = KKToolsBridge()
        card_scan.scan_dir_fast(cls.cards, recursive=True)
        cls.bridge.pick_directory = lambda *args: {'ok': True, 'data': str(cls.exports)}
        cls.server, port = launch_web.start_local_server(cls.bridge)
        cls.url = f'http://127.0.0.1:{port}/'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        for p in reversed(cls.patches):
            p.stop()
        cls.temp.cleanup()

    def setUp(self):
        settings.save({**settings.DEFAULTS, 'last_browse_dir': str(self.cards),
                       'output_dir': str(self.exports)})
        self.page = self.browser.new_page(viewport={'width': 1340, 'height': 860})
        self.page.set_default_timeout(7000)
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.goto(self.url)
        expect(self.page.get_by_text('共匹配 180', exact=False)).to_be_visible()
        expect(self.page.get_by_role('button', name='扫描目录', exact=True)).to_be_enabled()
        self.author = self.page.get_by_role('combobox', name='按作者筛选')

    def tearDown(self):
        self.page.screenshot(path=str(ARGS.output / f'{self._testMethodName}.png'))
        self.page.close()
        self.assertEqual(self.errors, [])

    def wait_filter(self, count):
        expect(self.page.get_by_text(f'共匹配 {count} 张卡片', exact=False)).to_be_visible()
        expect(self.page.get_by_role('button', name='导出 CSV')).to_be_enabled()

    def test_author_options_survive_filtering_and_search(self):
        self.author.select_option('Bob')
        self.wait_filter(20)
        values = self.author.locator('option').evaluate_all('(els) => els.map(e => e.value)')
        self.assertIn('Alice', values)
        self.assertIn('Bob', values)
        self.author.select_option('Alice')
        self.wait_filter(150)
        self.page.get_by_placeholder('名称 / 作者 / 标签').fill('不存在的名字')
        expect(self.page.get_by_text('没有符合当前筛选条件的卡片', exact=True)).to_be_visible()
        self.assertEqual(self.page.locator('[role=button][tabindex="0"]').count(), 0)
        self.assertIn('Bob', self.author.locator('option').evaluate_all('(els) => els.map(e => e.value)'))
        self.assertEqual(self.author.input_value(), 'Alice')

    def test_export_includes_loaded_author_pages_without_duplicates(self):
        self.page.get_by_role('button', name='按作者', exact=True).click()
        self.page.get_by_role('button', name='查该作者全部').first.click()
        expect(self.page.get_by_role('button', name='从索引加载该作者下一页 (40 / 150)', exact=True)).to_be_visible()
        # 作者首批只有40张时，主列表中已经加载的100张Alice仍应计入导出。
        expect(self.page.get_by_role('button', name='导出 CSV')).to_have_attribute(
            'title', '导出当前已加载的 120 张卡片列表为 CSV',
        )
        for count in (40, 80, 120):
            self.page.get_by_role('button', name=f'从索引加载该作者下一页 ({count} / 150)', exact=True).click()
        expect(self.page.get_by_role('button', name='展开该作者更多卡片 (40 / 150)', exact=True)).to_be_visible()
        for count in (40, 80, 120):
            self.page.get_by_role('button', name=f'展开该作者更多卡片 ({count} / 150)', exact=True).click()
        self.assertEqual(self.page.locator('[role=button][tabindex="0"]').count(), 170)
        with self.page.expect_request('**/api/start_export_data') as sent:
            self.page.get_by_role('button', name='导出 CSV').click()
        paths = sent.value.post_data_json['args'][0]['paths']
        self.assertEqual(len(paths), 170)
        self.assertEqual(len(set(paths)), 170)
        self.assertTrue(any(p.endswith('169.png') for p in paths))
        expect(self.page.get_by_role('status').get_by_text('资料已导出', exact=False)).to_be_visible()
        csv_file = max(self.exports.glob('*.csv'), key=lambda p: p.stat().st_mtime_ns)
        with csv_file.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(len(list(csv.reader(stream))) - 1, 170)
        self.page.screenshot(path=str(ARGS.output / 'author-export-170.png'))
        self.page.get_by_role('button', name='平铺', exact=True).click()
        expect(self.page.get_by_role('button', name='导出 CSV')).to_have_attribute('title', '导出当前已加载的 120 张卡片列表为 CSV')
        self.page.set_viewport_size({'width': 1060, 'height': 680})
        self.page.screenshot(path=str(ARGS.output / 'minimum-light.png'))
        self.page.get_by_role('navigation').get_by_role('button', name='外观与设置', exact=True).click()
        self.page.get_by_role('button', name='月夜·星图', exact=False).first.click()
        self.page.get_by_role('navigation').get_by_role('button', name='卡片画廊', exact=True).click()
        self.page.screenshot(path=str(ARGS.output / 'minimum-dark.png'))

    def test_author_options_reset_when_directory_changes(self):
        self.page.get_by_placeholder('选择恋活 UserData/chara 或任意角色卡目录...').fill(str(self.small))
        self.page.get_by_role('button', name='扫描目录', exact=True).click()
        self.wait_filter(1)
        values = self.author.locator('option').evaluate_all('(els) => els.map(e => e.value)')
        self.assertIn('Delta', values)
        self.assertNotIn('Alice', values)
        self.assertNotIn('Bob', values)

    def check_scan_keeps_latest_filter(self, *, cancel=False, recursive=False):
        gate = threading.Event()
        entered = threading.Event()
        original_scan = card_scan.scan_dir_fast

        def controlled_scan(*args, **kwargs):
            entered.set()
            if not gate.wait(15):
                raise TimeoutError('等待测试释放扫描超时')
            return original_scan(*args, **kwargs)

        queries = []
        def capture(req):
            if req.method == 'POST' and req.url.endswith('/query_card_page'):
                queries.append(req.post_data_json)
        self.page.on('request', capture)
        if recursive:
            self.page.get_by_text('含子目录', exact=True).click()
            self.wait_filter(180)
        with patch.object(card_scan, 'scan_dir_fast', controlled_scan):
            try:
                self.page.get_by_role('button', name='扫描目录', exact=True).click()
                self.assertTrue(entered.wait(5))
                self.author.select_option('Bob')
                self.wait_filter(20)
                if cancel:
                    self.page.get_by_role('button', name='取消', exact=True).click()
                gate.set()
                expect(self.page.get_by_role('button', name='扫描目录', exact=True)).to_be_enabled(timeout=15000)
                # 等待完成分支自身的分页响应，避免只检查任务结束前的旧画面。
                self.page.wait_for_function("!document.body.innerText.includes('正在从索引加载卡片分页')")
                self.page.wait_for_timeout(400)
                self.assertEqual(self.author.input_value(), 'Bob')
                self.assertEqual(self.page.locator('[role=button][tabindex="0"]').count(), 20)
                expect(self.page.get_by_text('共匹配 20', exact=False)).to_be_visible()
                last_main = next(q for q in reversed(queries) if q['args'][1].get('limit') == 120)
                self.assertEqual(last_main['args'][1]['author'], 'Bob')
                self.assertEqual(last_main['args'][1]['recursive'], recursive)
            finally:
                gate.set()

    def test_scan_completion_keeps_latest_filter(self):
        self.check_scan_keeps_latest_filter()

    def test_scan_cancellation_keeps_latest_filter(self):
        self.check_scan_keeps_latest_filter(cancel=True)

    def test_scan_completion_keeps_filter_in_recursive_scope(self):
        self.check_scan_keeps_latest_filter(recursive=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True, help='待验证的 Vite 构建目录')
    parser.add_argument('--output', type=Path, required=True, help='截图、日志与临时环境目录')
    ARGS = parser.parse_args()
    ARGS.dist = ARGS.dist.resolve()
    ARGS.output = ARGS.output.resolve()
    ARGS.output.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[sys.argv[0]], verbosity=2)
