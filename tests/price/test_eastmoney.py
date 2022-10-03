import datetime
import textwrap
import unittest
from decimal import Decimal
from unittest import mock

import requests
from dateutil.tz import tz
from requests import Session

from beancount_extras_cn.price import eastmoney


class MockResponse:
    """A mock requests.Models.Response object for testing."""

    def __init__(self, contents, status_code=requests.codes.ok):
        self.status_code = status_code
        self.contents = textwrap.dedent(f"thecallback({contents})").strip()

    @property
    def text(self):
        return self.contents


class EastmoneyPriceFetcher(unittest.TestCase):

    def _test_get_latest_price(self):
        response = MockResponse("""
            {
              "Data": {
                "LSJZList": [
                  {
                    "FSRQ": "2022-09-30",
                    "DWJZ": "1.0410",
                    "LJJZ": "3.6020",
                    "SDATE": null,
                    "ACTUALSYI": "",
                    "NAVTYPE": "1",
                    "JZZZL": "-2.16",
                    "SGZT": "开放申购",
                    "SHZT": "开放赎回",
                    "FHFCZ": "",
                    "FHFCBZ": "",
                    "DTYPE": null,
                    "FHSP": ""
                  }
                ],
                "FundType": "002",
                "SYType": null,
                "isNewType": false,
                "Feature": "215"
              },
              "ErrCode": 0,
              "ErrMsg": null,
              "TotalCount": 5046,
              "Expansion": null,
              "PageSize": 1,
              "PageIndex": 1
            }
        """)
        with mock.patch.object(Session, 'get', return_value=response):
            srcprice = eastmoney.Source().get_latest_price('000001')
            self.assertTrue(isinstance(srcprice.price, Decimal))
            self.assertEqual(Decimal('1.0410'), srcprice.price)
            timezone = datetime.timezone(datetime.timedelta(hours=8), "Asia/Shanghai")
            self.assertEqual(datetime.datetime(2022, 9, 30, 0, 0, 0, tzinfo=timezone), srcprice.time)
            self.assertEqual('CNY', srcprice.quote_currency)

    def test_get_latest_price(self):
        self._test_get_latest_price()

    def _test_get_historical_price(self):
        response = MockResponse("""
            {
              "Data": {
                "LSJZList": [
                  {
                    "FSRQ": "2022-09-01",
                    "DWJZ": "1.0410",
                    "LJJZ": "3.6020",
                    "SDATE": null,
                    "ACTUALSYI": "",
                    "NAVTYPE": "1",
                    "JZZZL": "-2.16",
                    "SGZT": "开放申购",
                    "SHZT": "开放赎回",
                    "FHFCZ": "",
                    "FHFCBZ": "",
                    "DTYPE": null,
                    "FHSP": ""
                  }
                ],
                "FundType": "002",
                "SYType": null,
                "isNewType": false,
                "Feature": "215"
              },
              "ErrCode": 0,
              "ErrMsg": null,
              "TotalCount": 5046,
              "Expansion": null,
              "PageSize": 1,
              "PageIndex": 1
            }
        """)
        with mock.patch.object(Session, 'get', return_value=response):
            srcprice = eastmoney.Source().get_historical_price('000001', datetime.datetime(2022, 9, 1, 0, 0, 0,
                                                                                           tzinfo=tz.tzutc()))
            self.assertTrue(isinstance(srcprice.price, Decimal))
            self.assertEqual(Decimal('1.0410'), srcprice.price)
            timezone = datetime.timezone(datetime.timedelta(hours=8), "Asia/Shanghai")
            self.assertEqual(datetime.datetime(2022, 9, 1, 0, 0, 0, tzinfo=timezone), srcprice.time)
            self.assertEqual('CNY', srcprice.quote_currency)

    def test_get_historical_price(self):
        self._test_get_historical_price()

    def test_parse_response_error_status_code(self):
        response = MockResponse('{}', status_code=404)
        with self.assertRaises(eastmoney.EastMoneyError):
            eastmoney.parse_response(response)

    def test_parse_response_empty_result(self):
        response = MockResponse("""
            {
              "Data": {
                "LSJZList": [],
                "FundType": "",
                "SYType": null,
                "isNewType": false,
                "Feature": null
              },
              "ErrCode": 0,
              "ErrMsg": null,
              "TotalCount": 0,
              "Expansion": null,
              "PageSize": 1,
              "PageIndex": 1
            }
        """)
        with self.assertRaises(eastmoney.EastMoneyError):
            eastmoney.parse_response(response)


if __name__ == '__main__':
    unittest.main()
