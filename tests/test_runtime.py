import ast
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from flask import Flask


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {}, clear=True):
            import wsgi
        cls.app = wsgi.app
        cls.app.config.update(TESTING=True, SECRET_KEY='test-only')

    def setUp(self):
        self.client = self.app.test_client()
        self.network = patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected external call'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def login(self):
        with self.client.session_transaction() as session:
            session['dc_authenticated'] = True
            session['dc_user'] = 'test'

    def test_all_python_syntax(self):
        for path in Path('.').glob('*.py'):
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding='utf-8-sig'))

    def test_health_and_login(self):
        self.assertEqual(self.client.get('/healthz').json, {'status': 'ok'})
        self.assertEqual(self.client.get('/login').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_all_analytics_apis_require_json_auth(self):
        for rule in self.app.url_map.iter_rules():
            if rule.rule in ('/', '/login', '/logout', '/healthz') or rule.rule.startswith('/static/'):
                continue
            with self.subTest(path=rule.rule):
                response = self.client.get(rule.rule)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json['code'], 'AUTH_REQUIRED')

    def test_pages_and_all_local_assets(self):
        self.login()
        for page in ('dashboard-v2.html', 'revisions.html', 'procurement.html', 'staff.html'):
            response = self.client.get('/static/' + page)
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            response.close()
            self.assertIn('analytics-ui-standard.css', html)
            for url in set(re.findall(r'(?:src|href)=[\"\x27](/static/[^\"\x27]+)', html)):
                with self.subTest(page=page, asset=url):
                    resource = self.client.get(url)
                    self.assertEqual(resource.status_code, 200)
                    resource.close()

    def test_initialization_is_idempotent(self):
        from runtime import install_runtime
        before = len(list(self.app.url_map.iter_rules()))
        install_runtime(self.app)
        self.assertEqual(len(list(self.app.url_map.iter_rules())), before)

    def test_safe_login_redirects(self):
        from dashboard_auth import _safe_next
        for value in ('//example.com', '/\\example.com', '/%5cexample.com', '/%2fexample.com', '/%0a/example.com'):
            with self.subTest(value=value):
                self.assertEqual(_safe_next(value), '/static/dashboard-v2.html')
        self.assertEqual(_safe_next('/static/staff.html?from=2026-01-01'), '/static/staff.html?from=2026-01-01')

    def test_invalid_periods(self):
        self.login()
        for path in ('/analytics', '/receipt-analytics', '/revision-data', '/management-metrics', '/cashier-analytics', '/economics-analytics', '/channel-analytics', '/sales-mix', '/staff-analytics'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path+'?from=invalid&to=invalid').status_code, 400)


    def test_arai_revision_classifier_prefers_counter_context(self):
        from revisions_data_v2 import _arai_revision_kind, _store_matches

        self.assertEqual(
            _arai_revision_kind([
                'Шаурму Говяжий Сырой',
                'Шаурму Куриный Сырой',
                'Влажные салфетки',
                'Pepsi 0,5л',
                'Айран',
            ]),
            'counter',
        )
        self.assertEqual(
            _arai_revision_kind([
                'Шаурму Говяжий Сырой',
                'Шаурму Куриный Сырой',
                'Картофель ФРИ очищенный',
            ]),
            'kitchen',
        )
        self.assertTrue(_store_matches('arai_kitchen', 'Арай (АРАЙ общий)'))
        self.assertTrue(_store_matches('arai_counter', 'Арай (АРАЙ общий)'))
        self.assertFalse(_store_matches('arai_kitchen', 'Арай (Хоз.товары АРАЙ)'))
        self.assertFalse(_store_matches('arai_counter', 'Арай (Хоз.товары АРАЙ)'))

    def test_arai_revision_scopes_and_last_date(self):
        from revisions_data_v5 import _build

        names = {
            'date': 'DateTime.DateTyped',
            'transaction': 'TransactionType',
            'document': 'Document',
            'product': 'Product.Name',
            'productId': None,
            'unit': 'Product.MeasureUnit',
            'stores': ['Store.Name'],
            'accounts': ['Account.Name'],
            'aggregates': ['Amount.StoreInOutTyped', 'Product.AvgSum'],
        }

        def row(date, document, store, product, delta=-1, cost=100):
            return {
                'DateTime.DateTyped': date,
                'TransactionType': 'Инвентаризация',
                'Document': document,
                'Product.Name': product,
                'Product.MeasureUnit': 'шт',
                'Store.Name': store,
                'Account.Name': 'Недостача инвентаризации',
                'Amount.StoreInOutTyped': delta,
                'Product.AvgSum': cost,
            }

        rows = [
            # This later household document used to make the site report 22 Sep
            # as Arai's latest revision. Household inventory is a separate scope.
            row('2026-09-22', 'Arai0115', 'Арай (Хоз.товары АРАЙ)', 'Перчатки'),
            # Arai counter/drinks revision. Raw meat can be present here too, so
            # strong point markers must win at document level.
            row('2026-09-18', 'Arai0114', 'Арай (АРАЙ общий)', 'Pepsi 0,5л'),
            row('2026-09-18', 'Arai0114', 'Арай (АРАЙ общий)', 'Айран'),
            row('2026-09-18', 'Arai0114', 'Арай (АРАЙ общий)', 'Шаурму Говяжий Сырой'),
            # Separate kitchen revision on the same physical warehouse/date.
            row('2026-09-18', 'Arai0112', 'Арай (АРАЙ общий)', 'Шаурму Говяжий Сырой'),
            row('2026-09-18', 'Arai0112', 'Арай (АРАЙ общий)', 'Шаурму Куриный Сырой'),
            row('2026-09-18', 'Arai0112', 'Арай (АРАЙ общий)', 'Картофель ФРИ очищенный'),
        ]

        counter = _build('arai_counter', '2026-09', rows, names, {})
        kitchen = _build('arai_kitchen', '2026-09', rows, names, {})
        legacy = _build('arai', '2026-09', rows, names, {})

        self.assertEqual(counter['summary']['lastRevision'], '2026-09-18')
        self.assertEqual(counter['summary']['documentsCount'], 1)
        self.assertEqual(counter['history'][0]['documents'], ['Arai0114'])
        self.assertEqual(counter['summary']['documentState'], 'posted')

        self.assertEqual(kitchen['summary']['lastRevision'], '2026-09-18')
        self.assertEqual(kitchen['summary']['documentsCount'], 1)
        self.assertEqual(kitchen['history'][0]['documents'], ['Arai0112'])

        self.assertEqual(legacy['summary']['lastRevision'], '2026-09-18')
        self.assertNotIn('Arai0115', legacy['diagnostics']['matchedDocuments'])


    def test_telegram_nontext_commands(self):
        from telegram_bot import _command
        for value in (None, '', '   ', '\n'):
            self.assertEqual(_command(value), '')
        self.assertEqual(_command('/GO@MyBot today'), '/go')

    def test_telegram_payloads_without_sending(self):
        import telegram_bot as bot
        app = Flask('telegram-test')
        with patch.object(bot, '_settings', return_value=('test', '123', 'https://example.com', 'secret')), patch.object(bot.threading.Thread, 'start'):
            bot.install_telegram_bot(app)
        client = app.test_client()
        headers = {'X-Telegram-Bot-Api-Secret-Token': 'secret'}
        for payload in ([1], {'update_id': []}, {'message': 'bad'}, {'message': {'chat': 'bad'}}):
            self.assertEqual(client.post('/telegram/webhook/secret', json=payload, headers=headers).status_code, 400)
        response = client.post('/telegram/webhook/secret', json={'message': {'chat': {'id': 123}, 'photo': []}}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['ignored'], 'command')


if __name__ == '__main__':
    unittest.main()
