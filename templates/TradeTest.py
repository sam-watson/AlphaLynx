import unittest
import psycopg2 as pg

class TestTrades(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db_url = """postgres://zbbkqlsfdaogoj:6c6b047fc1856aa4332a19dac73083af7a8d007c21f51ecaf324dcd085516e79@ec2-23-23-222-184.compute-1.amazonaws.com:5432/d9nsd1kp8hr78k"""

        conn = pg.connect(db_url)
        cls.cursor = conn.cursor()


    def test_buy_btc_on_kraken_yields_correct_amounts(self):
        SQL = "select sum(dollarvalue) from Holdings where exchangecode = 'BitLynx'"
        cls.cursor.execute(SQL)

        cls.bl_cash_start = cursor.fetchall()

    def test_split(self):
        s = 'hello world'
        self.assertEqual(s.split(), ['hello', 'world'])
        # check that s.split fails when the separator is not a string
        with self.assertRaises(TypeError):
            s.split(2)

if __name__ == '__main__':
    unittest.main()