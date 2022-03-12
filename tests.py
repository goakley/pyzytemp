import unittest

import pyzytemp


class TestDecrypt(unittest.TestCase):
    def test_decrypt(self):
        key = [1, 2, 3, 4, 5, 6, 7, 8]
        data = [11, 22, 33, 44, 55, 66, 77, 88]
        expected = [0, 191, 75, 53, 123, 214, 213, 78]
        self.assertEqual(expected, pyzytemp.decrypt(key, data))


class TestParse(unittest.TestCase):
    def test_parse_co2(self):
        data = [80, 2, 146, 228, 13, 0, 0, 0]
        expected = (pyzytemp.Measurement.CO2.value, 0x0292)
        self.assertEqual(expected, pyzytemp.parse(data))

    def test_parse_t(self):
        data = [66, 18, 13, 97, 13, 0, 0, 0]
        expected = (pyzytemp.Measurement.T.value, 0x120D)
        self.assertEqual(expected, pyzytemp.parse(data))


class TestConvert(unittest.TestCase):
    def test_convert_unknown(self):
        self.assertEqual(None, pyzytemp.convert(1, 200))

    def test_convert_co2(self):
        measurement, value = pyzytemp.convert(
            pyzytemp.Measurement.CO2.value,
            292,
        )
        self.assertEqual(pyzytemp.Measurement.CO2, measurement)
        self.assertAlmostEqual(292, value)

    def test_convert_t(self):
        measurement, value = pyzytemp.convert(
            pyzytemp.Measurement.T.value,
            4621,
        )
        self.assertEqual(pyzytemp.Measurement.T, measurement)
        self.assertAlmostEqual(15.6625, value)

    def test_convert_rh(self):
        measurement, value = pyzytemp.convert(
            pyzytemp.Measurement.RH.value,
            42,
        )
        self.assertEqual(pyzytemp.Measurement.RH, measurement)
        self.assertAlmostEqual(0.42, value)


if __name__ == "__main__":
    unittest.main()
