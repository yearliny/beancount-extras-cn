"""从天天基金网获取净值价格"""

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

import requests
from beancount.prices import source
from dateutil import tz, utils

TZ_CN = tz.gettz("Asia/Shanghai")


class EastMoneyError(ValueError):
    """An error from the EastMoney API."""


def parse_response(response) -> Dict:
    """Process as response from EastMoney.
    Raises:
      EastMoneyError: If there is an error in the response.
    """
    if response.status_code != requests.codes.ok:
        raise EastMoneyError(f"Error status {response.status_code}")

    result_str: str = response.text.removeprefix("thecallback(").removesuffix(")")
    result: Dict = json.loads(result_str)
    records = result["Data"]["LSJZList"]
    if len(records) == 0:
        raise EastMoneyError("No data returned from EastMoney, ensure that the symbol is correct")
    return records[0]


class Source(source.Source):
    """
    天天基金 基金/股票/指数 净值数据源
    bean-price -e CNY:beancount_extras_cn.price.eastmoney/F000001
    """

    fund_code_regex = re.compile(r"\d{6}")

    def __init__(self):
        self.http = requests.Session()
        self.http.headers.update({
            "Referer": "https://fundf10.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/106.0.0.0 Safari/537.36 "
        })

    def get_latest_price(self, ticker: str) -> Optional[source.SourcePrice]:
        """See contract in beanprice.source.Source."""
        return self._get_price_series(ticker)

    def get_historical_price(self, ticker: str, time) -> Optional[source.SourcePrice]:
        """See contract in beanprice.source.Source."""
        return self._get_price_series(ticker, time)

    def _get_price_series(self, ticker: str, time=None) -> Optional[source.SourcePrice]:
        """
        获取价格序列
        :param ticker: 股票/基金代码，需要包含六位基金代码
        :param time: 需要查询的日期
        :return: 查询的结果
        """
        fund_code: str = self.fund_code_regex.search(ticker).group()
        payload = {
            "callback": "thecallback",
            "fundCode": fund_code,
            "pageIndex": 1,
            "pageSize": 1,
        }
        if time is not None:
            datetime_str = time.strftime("%Y-%m-%d")
            payload.update({
                "startDate": datetime_str,
                "endDate": datetime_str,
            })
        url = "https://api.fund.eastmoney.com/f10/lsjz"
        response: requests.Response = self.http.get(url, params=payload)
        result = parse_response(response)

        trade_date = result["FSRQ"]
        price = Decimal(result["DWJZ"])
        trade_date = datetime.strptime(trade_date, "%Y-%m-%d")
        trade_date = utils.default_tzinfo(trade_date, TZ_CN)
        return source.SourcePrice(price, trade_date, "CNY")
