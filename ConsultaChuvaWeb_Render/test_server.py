import unittest
from datetime import date
from server import parse_date, parse_xml

class BasicTests(unittest.TestCase):
    def test_parse_iso_date(self):
        self.assertEqual(parse_date("2026-10-13"), date(2026, 10, 13))

    def test_parse_br_date(self):
        self.assertEqual(parse_date("13/10/2026"), date(2026, 10, 13))

    def test_invalid_date(self):
        self.assertIsNone(parse_date("31/02/2026"))

    def test_parse_xml_record(self):
        xml = b"""<?xml version="1.0"?>
        <DataTable xmlns="http://MRCS/">
          <Table>
            <CodEstacao>65060001</CodEstacao>
            <DataHora>2020-01-02T13:00:00</DataHora>
            <Chuva>2.5</Chuva>
          </Table>
        </DataTable>"""
        rows = parse_xml(xml, "65060001")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["station"], "65060001")
        self.assertEqual(rows[0]["date"], "2020-01-02")
        self.assertEqual(rows[0]["time"], "13:00")
        self.assertAlmostEqual(rows[0]["rain"], 2.5)

if __name__ == "__main__":
    unittest.main()
