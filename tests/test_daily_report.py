"""Offline regression checks for point lookup and daily-report availability."""
import ast
import html
import os
from pathlib import Path
from datetime import datetime, timedelta
import unittest


def functions(path, names=None, scope=None):
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and (names is None or node.name in names)]
    scope = scope or {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), scope)
    return scope


class DailyReportTests(unittest.TestCase):
    def test_cloud_and_server_point_aliases(self):
        names = {"point_search_terms", "find_department", "find_iiko_server_department"}
        for code, name in [("RESPUBLIKA", "Республика"), ("Republic", "Doner Club"), ("other", "Doner Club Республика")]:
            departments = [{"code": "Arai", "name": "Арай"}, {"code": code, "name": name}]
            scope = functions("app.py", names, {"get_departments": lambda: departments})
            for query in ["Republic", "RESPUBLIKA", "Республика", " republic "]:
                self.assertEqual(scope["find_department"](query)[0], departments[1])
                self.assertEqual(scope["find_iiko_server_department"](query, departments), departments[1])
            self.assertEqual(scope["find_department"]("Arai")[0], departments[0])
            self.assertIsNone(scope["find_department"]("")[0])
            self.assertIsNone(scope["find_iiko_server_department"]("unknown", departments))

    def report(self):
        return functions("telegram_daily_report.py", scope={
            "html": html, "datetime": datetime, "timedelta": timedelta, "os": os,
            "POINT_LABELS": {"arai": "Арай", "republic": "Республика", "respublika": "Республика"},
            "DEFAULT_POINTS": ("Arai", "Republic"),
        })

    def test_error_is_not_reported_as_no_sales(self):
        row = dict(point="RESPUBLIKA", cur=None, receipt=None, mix=None,
                   prev=None, week=None, errors=["upstream unavailable"])
        report = self.report()
        text = report["point_message"](row)
        self.assertIn("Республика", text)
        self.assertIn("Не удалось получить", text)
        self.assertNotIn("точка не работала", text)
        self.assertIn("Итог неполный", report["network_message"]([row], "2026-09-30"))

    def test_confirmed_sales_are_included(self):
        row = dict(point="Republic", cur={"summary": {"revenue": 25000, "itemsQuantity": 10}},
                   receipt={"summary": {"revenue": 25000, "checks": 5}},
                   mix=None, prev=None, week=None, errors=[])
        report = self.report()
        self.assertIn("25 000", report["point_message"](row))
        text = report["network_message"]([row], "2026-09-30")
        self.assertIn("25 000", text)
        self.assertNotIn("Итог неполный", text)


if __name__ == "__main__":
    unittest.main()
